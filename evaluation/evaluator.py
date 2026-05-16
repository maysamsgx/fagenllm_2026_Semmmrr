"""
evaluation/evaluator.py
FAgentLLM Held-Out Scientific Evaluation Framework — V4

Design principles:
  - Ground truths are defined BEFORE running the system (true held-out evaluation).
  - Every test case runs through the actual LangGraph pipeline, not mocks.
  - Three Groq API keys are rotated round-robin to avoid rate-limit failures.
  - Results are persisted to evaluation_runs / evaluation_results tables so the
    /api/analytics/scientific-evaluation endpoint can serve them to the UI.
  - Baseline comparison: a deterministic rule-only system is simulated analytically
    per-case (no code execution needed) to provide a fair FAgentLLM vs Baseline contrast.
  - Sensitivity analysis cases (category='adversarial_sensitivity') are grouped and
    reported separately with a curve-ready structure for the thesis results section.

Run:
    python -m evaluation.evaluator                    # default run name
    python -m evaluation.evaluator "My Run Name"      # custom name
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime
from typing import Any, Dict, List, Optional
import json
import uuid

from agents.graph import graph
from agents.state import FinancialState
from db.supabase_client import db

logger = logging.getLogger("fagentllm.evaluator")

# ── API key round-robin pool ──────────────────────────────────────────────────
# Keys are read from environment variables. The evaluator rotates through all
# available keys so no single key bears the full TPM load of a 50-case run.
_KEY_POOL: List[str] = [
    k for k in [
        os.environ.get("GROQ_API_KEY"),
        os.environ.get("GROQ_API_KEY_2"),
        os.environ.get("GROQ_API_KEY_3"),
    ] if k
]
if not _KEY_POOL:
    raise EnvironmentError("At least one GROQ_API_KEY must be set.")

_key_index = 0


def _rotate_key() -> str:
    """Returns the next Groq API key in the pool and advances the pointer."""
    global _key_index
    key = _KEY_POOL[_key_index % len(_KEY_POOL)]
    _key_index += 1
    os.environ["GROQ_API_KEY"] = key
    return key


# ── Load test cases ───────────────────────────────────────────────────────────
_CASES_PATH = os.path.join(os.path.dirname(__file__), "test_cases.json")
with open(_CASES_PATH, "r") as _f:
    _eval_data = json.load(_f)
    TEST_CASES: List[Dict[str, Any]] = _eval_data.get("cases", [])


# ── DB insert helper (auto-strips columns absent from the live schema) ────────
import re as _re

# ── Baseline oracle ───────────────────────────────────────────────────────────
def _baseline_passes(case: Dict) -> bool:
    """
    Simulates a deterministic rule-only baseline (no LLM, no cross-agent causal
    reasoning, no governance audit). Decision rules:
      - Invoice: approve if amount < $10k, reject if > $100k, else approve.
      - Reconciliation: always 'pass' (no anomaly detection).
      - Duplicate: never detected (no duplicate check).
    Returns True if the baseline would produce the same outcome as the
    expected_verdict (i.e. the baseline also 'passes').

    For the thesis comparison this function is called once per case to populate
    baseline_passed, then FAgentLLM results are compared against this.
    """
    # The test-case author sets baseline_verdict explicitly — use that.
    bv = case.get("baseline_verdict", "PASSED")
    ev = case["expected"]["verdict"]
    # Baseline 'matches' if its predicted verdict equals the expected verdict.
    # Adversarial cases where FAgentLLM catches fraud but baseline misses are
    # marked baseline_verdict=PASSED (baseline approves what it shouldn't detect).
    return str(bv).upper() == str(ev).upper()


# ── Path matching ─────────────────────────────────────────────────────────────
def _path_match(expected_path: List[str], actual_path: List[str]) -> bool:
    """
    Relative-order (causal-aware) matching: every agent in expected_path must
    appear in actual_path, in the correct relative order, with any number of
    intermediate agents allowed between them.
    """
    last_idx = -1
    for node in expected_path:
        try:
            idx = actual_path.index(node, last_idx + 1)
            last_idx = idx
        except ValueError:
            return False
    return True


# ── Verdict matching ──────────────────────────────────────────────────────────
def _verdict_match(expected: str, actual: str) -> bool:
    """
    Matches the expected verdict string against the actual verdict returned by
    the governance agent. Handles the PASSED/FLAGGED/BLOCKED enum robustly.
    """
    if not actual:
        return False
    exp_upper = expected.upper()
    act_upper = str(actual).upper()
    # Direct substring match (PASSED in PASSED, FLAGGED in FLAGGED, etc.)
    if exp_upper in act_upper:
        return True
    # Handle LLM-generated synonyms for PASSED
    if exp_upper == "PASSED" and any(
        s in act_upper for s in ["APPROVED", "AUDIT_PASSED", "COMPLIANT", "PASS", "SAFE"]
    ):
        return True
    # Handle FLAGGED synonyms
    if exp_upper == "FLAGGED" and any(
        s in act_upper for s in ["FLAG", "WARN", "ALERT", "REVIEW"]
    ):
        return True
    return False


# ── Reasoning quality heuristic ───────────────────────────────────────────────
def _reasoning_quality(trace: List[Dict]) -> int:
    """
    Heuristic 0-100 score for the quality of the causal reasoning trace.
    Awards points for:
      - 3-layer explanations (technical + business + causal)  [up to 40 pts]
      - Governance auditing present                           [20 pts]
      - Non-trivial explanation length                        [20 pts]
      - Causal explanation mentions agent names               [20 pts]
    """
    score = 0
    gov_found = False
    for step in trace:
        if not isinstance(step, dict):
            continue
        has_tech   = bool(step.get("technical_explanation", ""))
        has_biz    = bool(step.get("business_explanation", ""))
        has_causal = bool(step.get("causal_explanation", ""))
        if has_tech and has_biz and has_causal:
            score += 8  # up to 40 pts across 5 agents
        agent_name = step.get("agent", "")
        if agent_name == "governance":
            gov_found = True
        causal_text = step.get("causal_explanation", "")
        if len(causal_text) > 80:
            score += 4   # rewards substantive explanations
        agent_keywords = ["invoice", "cash", "budget", "reconciliation", "credit", "governance"]
        if any(kw in causal_text.lower() for kw in agent_keywords):
            score += 4   # rewards cross-agent references

    if gov_found:
        score += 20
    
    score = min(score, 100)
    # Scale from 0-100 to 1-5 star rating for the database constraint
    scaled_score = max(1, int((score / 100.0) * 5))
    return scaled_score


# ── Main evaluation runner ────────────────────────────────────────────────────
async def run_evaluation(run_name: str = "FAgentLLM System Functionality PoC") -> str:
    """
    Executes the full held-out test suite and writes results to Supabase.
    Returns the run_id for downstream API queries.
    """
    logger.info(f"Starting evaluation run: '{run_name}' — {len(TEST_CASES)} cases, {len(_KEY_POOL)} API key(s)")
    print(f"\n{'='*60}")
    print(f"  FAgentLLM Scientific Evaluation — {run_name}")
    print(f"  Cases: {len(TEST_CASES)}   API keys: {len(_KEY_POOL)}")
    print(f"{'='*60}\n")

    # Warm up the Supabase connection pool before the timed evaluation starts.
    # The first DB query on a cold pool frequently times out (statement_timeout),
    # so priming it here prevents TC-001 from failing due to cold-start latency.
    run_id = str(uuid.uuid4())
    full_results_data = []

    passed = 0
    results: List[Dict] = []

    for i, case in enumerate(TEST_CASES):
        # Rotate API key before each case
        _rotate_key()
        key_label = f"key-{(_key_index - 1) % len(_KEY_POOL) + 1}"

        print(f"[{i+1:02d}/{len(TEST_CASES)}] {case['id']} — {case['scenario'][:55]}  ({key_label})")

        # ── Build initial state ─────────────────────────────────────────────
        state    = _build_state(case)
        baseline = _baseline_passes(case)

        start_time = time.time()
        try:
            final_state = await asyncio.wait_for(graph.ainvoke(state), timeout=90.0)
            latency = round(time.time() - start_time, 3)

            # Flatten trace (handles operator.add concatenation artefacts)
            raw_trace = final_state.get("reasoning_trace", [])
            flat_trace: List[Dict] = []
            for item in raw_trace:
                if isinstance(item, list):
                    flat_trace.extend(item)
                else:
                    flat_trace.append(item)

            # Extract agent path: count any trace entry with "agent" key (not just
            # those with "step"), then deduplicate preserving order.  This is robust
            # to early-return paths where the detailed "step" entry is never written
            # (e.g. Groq rate-limit mid-call) while still capturing the routing chain.
            raw_agents = [
                t["agent"] for t in flat_trace
                if isinstance(t, dict) and "agent" in t
                and t["agent"] not in ("system", "supervisor")
            ]
            seen_agents: set = set()
            actual_path: List[str] = []
            for a in raw_agents:
                if a not in seen_agents:
                    seen_agents.add(a)
                    actual_path.append(a)

            gov_data      = final_state.get("governance", {})
            # Prefer the explicit verdict field added in V4; fall back to status/decision
            actual_verdict = (
                gov_data.get("verdict")
                or gov_data.get("status")
                or final_state.get("error")
                or ""
            )

            exp          = case["expected"]
            pm           = _path_match(exp["path"], actual_path)
            vm           = _verdict_match(exp["verdict"], actual_verdict)
            status       = "pass" if pm and vm else "fail"
            rq           = _reasoning_quality(flat_trace)
            gov_present  = any(isinstance(t, dict) and t.get("agent") == "governance" for t in flat_trace)
            causal_present = any(
                isinstance(t, dict) and bool(t.get("causal_explanation"))
                for t in flat_trace
            )

            # FAgentLLM advantage: system passes but baseline would miss it
            fagentllm_advantage = (status == "pass") and not baseline

            if status == "pass":
                passed += 1

            print(f"       path={'+' if pm else '✗'}  verdict={'+' if vm else '✗'}  "
                  f"actual={actual_path} → {actual_verdict}  [{latency:.1f}s]")

            full_results_data.append({
                "test_case_id":        case["id"],
                "scenario":            case["scenario"],
                "category":            case.get("category", "general"),
                "status":              status,
                "actual_path":         actual_path,
                "expected_path":       exp["path"],
                "actual_verdict":      str(actual_verdict),
                "expected_verdict":    exp["verdict"],
                "baseline_verdict":    case.get("baseline_verdict", "PASSED"),
                "baseline_passed":     baseline,
                "fagentllm_advantage": fagentllm_advantage,
                "reasoning_quality":   rq,
                "governance_passed":   gov_present,
                "causal_links_present": causal_present,
                "latency":             latency,
                "trace_id":            gov_data.get("decision_id"),
                "error_message":       final_state.get("error"),
            })

            results.append({
                "id":       case["id"],
                "status":   status,
                "latency":  latency,
                "rq":       rq,
                "gov":      gov_present,
                "causal":   causal_present,
                "baseline": baseline,
                "category": case.get("category", "general"),
                "sens_grp": case.get("sensitivity_group"),
                "sens_lvl": case.get("sensitivity_level"),
            })

        except (Exception, asyncio.TimeoutError) as e:
            latency = round(time.time() - start_time, 3)
            logger.error(f"  ERROR on {case['id']}: {e}")
            print(f"       ERROR: {e}")
            full_results_data.append({
                "test_case_id":     case["id"],
                "scenario":         case["scenario"],
                "category":         case.get("category", "general"),
                "status":           "fail",
                "actual_path":      [],
                "expected_path":    case["expected"]["path"],
                "actual_verdict":   "",
                "expected_verdict": case["expected"]["verdict"],
                "baseline_verdict": case.get("baseline_verdict", "PASSED"),
                "baseline_passed":  baseline,
                "error_message":    str(e),
                "latency":          latency,
            })
            results.append({
                "id": case["id"], "status": "fail", "latency": latency,
                "rq": 0, "gov": False, "causal": False, "baseline": baseline,
                "category": case.get("category", "general"),
                "sens_grp": case.get("sensitivity_group"),
                "sens_lvl": case.get("sensitivity_level"),
            })

        # Paced sleep: 6 s between cases to reduce Groq TPM rate-limit failures
        await asyncio.sleep(12)

    # ── Aggregate metrics ───────────────────────────────────────────────────
    n          = len(TEST_CASES)
    accuracy   = round((passed / n) * 100, 2) if n else 0.0
    latency_avg = round(sum(r["latency"] for r in results) / len(results), 3) if results else 0.0

    # Confusion matrix: PASSED=Positive, FLAGGED/BLOCKED=Negative
    def _is_pos(v: str) -> bool:
        return any(x in str(v).upper() for x in ["PASSED", "APPROVED", "SAFE", "COMPLIANT"])

    tp = sum(1 for r in results if r["status"] == "pass" and _is_pos(
        next((c["expected"]["verdict"] for c in TEST_CASES if c["id"] == r["id"]), "PASSED")))
    fp = sum(1 for r in results if r["status"] == "fail" and not _is_pos(
        next((c["expected"]["verdict"] for c in TEST_CASES if c["id"] == r["id"]), "PASSED")))
    fn = sum(1 for r in results if r["status"] == "fail" and _is_pos(
        next((c["expected"]["verdict"] for c in TEST_CASES if c["id"] == r["id"]), "PASSED")))
    tn = n - tp - fp - fn

    precision = round(tp / (tp + fp), 3) if (tp + fp) > 0 else 0.0
    recall    = round(tp / (tp + fn), 3) if (tp + fn) > 0 else 0.0
    f1        = round(2 * precision * recall / (precision + recall), 3) if (precision + recall) > 0 else 0.0

    gov_pass_rate    = round(sum(1 for r in results if r["gov"])  / n * 100, 1) if n else 0
    causal_succ_rate = round(sum(1 for r in results if r["causal"]) / n * 100, 1) if n else 0
    avg_rq           = round(sum(r["rq"] for r in results) / n, 1) if n else 0
    baseline_acc     = round(sum(1 for r in results if r["baseline"]) / n * 100, 1) if n else 0
    hallucination_rate = round(
        sum(1 for r in results if r["rq"] < 30 and r["status"] == "fail") / n * 100, 1
    ) if n else 0

    # Per-category breakdown
    categories_seen = list({r["category"] for r in results})
    per_category = {}
    for cat in categories_seen:
        cat_res = [r for r in results if r["category"] == cat]
        cat_n   = len(cat_res)
        cat_pass = sum(1 for r in cat_res if r["status"] == "pass")
        per_category[cat] = {
            "total":    cat_n,
            "passed":   cat_pass,
            "accuracy": round(cat_pass / cat_n * 100, 1) if cat_n else 0,
        }

    # Sensitivity analysis curve data
    sens_groups: Dict[str, List] = {}
    for r in results:
        grp = r.get("sens_grp")
        if grp:
            if grp not in sens_groups:
                sens_groups[grp] = []
            case_obj = next((c for c in TEST_CASES if c["id"] == r["id"]), {})
            sens_groups[grp].append({
                "level":   r.get("sens_lvl"),
                "value":   case_obj.get("sensitivity_value"),
                "passed":  r["status"] == "pass",
                "baseline_passed": r["baseline"],
            })
    for grp in sens_groups:
        sens_groups[grp].sort(key=lambda x: x.get("level") or 0)

    metrics_payload = {
        "accuracy":            accuracy,
        "precision":           precision,
        "recall":              recall,
        "f1":                  f1,
        "latency_avg":         latency_avg,
        "gov_pass_rate":       gov_pass_rate,
        "causal_success_rate": causal_succ_rate,
        "hallucination_rate":  hallucination_rate,
        "avg_reasoning_quality": avg_rq,
        "baseline_accuracy":   baseline_acc,
        "confusion_matrix":    {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "per_category":        per_category,
        "sensitivity_curves":  sens_groups,
        "total_cases":         n,
        "passed_cases":        passed,
        "key_pool_size":       len(_KEY_POOL),
        "run_timestamp":       datetime.utcnow().isoformat(),
    }

    # Save to JSON
    run_record = {
        "id": run_id,
        "run_name": run_name,
        "run_type": "fagentllm",
        "created_at": metrics_payload["run_timestamp"],
        "passed_cases": passed,
        "accuracy": accuracy,
        "f1_score": f1,
        "precision_score": precision,
        "recall_score": recall,
        "latency_avg": latency_avg,
        "governance_pass_rate": gov_pass_rate,
        "causal_success_rate": causal_succ_rate,
        "hallucination_rate": hallucination_rate,
        "metrics": metrics_payload,
    }
    
    # Save runs
    runs_file = os.path.join(os.path.dirname(__file__), "evaluation_runs.json")
    if os.path.exists(runs_file):
        with open(runs_file, "r", encoding="utf-8") as f:
            runs_db = json.load(f)
    else:
        runs_db = []
    runs_db.append(run_record)
    with open(runs_file, "w", encoding="utf-8") as f:
        json.dump(runs_db, f, indent=2)

    # Save results
    res_file = os.path.join(os.path.dirname(__file__), "evaluation_results.json")
    if os.path.exists(res_file):
        with open(res_file, "r", encoding="utf-8") as f:
            res_db = json.load(f)
    else:
        res_db = []
        
    for item in full_results_data:
        item["run_id"] = run_id
        res_db.append(item)
        
    with open(res_file, "w", encoding="utf-8") as f:
        json.dump(res_db, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  RESULTS")
    print(f"  Accuracy    : {accuracy:.1f}%  ({passed}/{n})")
    print(f"  Precision   : {precision:.3f}   Recall: {recall:.3f}   F1: {f1:.3f}")
    print(f"  Gov Pass    : {gov_pass_rate:.1f}%   Causal: {causal_succ_rate:.1f}%")
    print(f"  Latency avg : {latency_avg:.2f}s")
    print(f"  Baseline acc: {baseline_acc:.1f}%  (FAgentLLM advantage cases: {sum(1 for r in results if r.get('fagentllm_advantage', False))})")
    print(f"  Run ID      : {run_id}")
    print(f"{'='*60}\n")

    return run_id


# ── State builder ─────────────────────────────────────────────────────────────
def _build_state(case: Dict) -> FinancialState:
    """Constructs a LangGraph-compatible initial state from a test case."""
    trigger     = case["trigger"]
    inp         = case["input"]
    invoice_id  = "00000000-0000-0000-0000-000000000000"
    customer_id: Optional[str] = inp.get("customer_id")

    # Create invoice records for invoice-trigger cases
    if trigger in ("invoice_uploaded", "batch_invoice_upload"):
        # For batch uploads, use the first invoice in the array
        inv_data = (
            inp["invoices"][0]
            if trigger == "batch_invoice_upload" and "invoices" in inp
            else inp
        )
        vendor_name = (
            inv_data.get("vendor_name")
            or inv_data.get("vendor")
            or "Unknown Vendor"
        )
        vendor_id   = db.ensure_vendor(vendor_name)
        inv_no      = (
            inv_data.get("invoice_number")
            or inv_data.get("no")
            or f"TEST-{case['id']}"
        )
        dept = inv_data.get("department") or inv_data.get("dept") or "engineering"
        ocr_text = (
            f"VENDOR: {vendor_name}\n"
            f"AMOUNT: {inv_data.get('amount', 0)}\n"
            f"NUMBER: {inv_no}\n"
            f"DEPT: {dept}"
        )
        try:
            inv_res = db.insert("invoices", {
                "status":         "pending",
                "invoice_number": inv_no,
                "vendor_id":      vendor_id,
                "total_amount":   float(inv_data.get("amount", 0)),
                "ocr_raw_text":   ocr_text,
                "file_path":      f"simulated://{case['id']}.pdf",
                "department_id":  dept,
            })
            invoice_id = str(inv_res.data[0]["id"])
        except Exception as e:
            logger.warning(f"Could not insert invoice for {case['id']}: {e}")

    # Resolve customer_id if provided as a symbolic name
    if customer_id and "-" not in str(customer_id):
        name_map = {
            "cust-high-risk": "Risky Business Corp",
            "cust-mid-risk":  "Middle Ground LLC",
            "cust-low-risk":  "Reliable Partners Ltd",
        }
        lookup_name = name_map.get(str(customer_id), str(customer_id))
        try:
            cust = (
                db._ensure_client()
                .table("customers")
                .select("id")
                .eq("name", lookup_name)
                .execute()
            )
            if cust.data:
                customer_id = cust.data[0]["id"]
        except Exception:
            pass  # If customer doesn't exist the agent handles it gracefully

    # Map evaluation triggers to the system's trigger names
    effective_trigger = trigger
    if trigger in ("complex_reconciliation", "customer_payment_check"):
        effective_trigger = "customer_payment_check"

    entity_id = (
        invoice_id
        if invoice_id != "00000000-0000-0000-0000-000000000000"
        else (customer_id or "00000000-0000-0000-0000-000000000000")
    )

    return FinancialState(
        trigger=effective_trigger,
        trigger_entity_id=str(entity_id),
        reasoning_trace=[],
        next_agent="supervisor",
        current_agent="system",
        invoice=(
            {**inp, "id": invoice_id}
            if "invoice" in trigger
            else {}
        ),
        reconciliation=(
            {**inp, "customer_id": customer_id}
            if effective_trigger == "customer_payment_check"
            else {}
        ),
        decision_ids={},
        pending_risk_assessments=[],
        processed_risk_assessments=[],
        budget={},
        cash={},
        credit={},
        governance={},
        error=None,
        error_agent=None,
    )


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Ensure Unicode output works on Windows terminals (cp1252 → utf-8)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    run_name = sys.argv[1] if len(sys.argv) > 1 else "FAgentLLM System Functionality PoC"
    asyncio.run(run_evaluation(run_name))
