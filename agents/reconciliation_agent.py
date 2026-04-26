"""
agents/reconciliation_agent.py
Reconciliation Agent — Scenario 2 primary handler.

Algorithm (thesis Section 2.7.1):
  1. Load all unmatched transactions (internal + bank)
  2. Build TF-IDF vectors on composite field: description + amount + date
  3. Compute cosine similarity matrix between internal vs bank records
  4. Threshold match: similarity >= 0.85 → matched pair
  5. Unmatched remainder → anomaly list
  6. Qwen3 generates natural-language explanation for anomalies (XAI)
  7. If systematic anomalies detected for a customer → trigger credit_node (Scenario 2)

Cross-agent coordination (Scenario 2):
  reconciliation_node → detects recurring delay pattern
    → sets state.next_agent = "credit"
    → credit_node reassesses risk score for that customer
"""

from __future__ import annotations
import uuid
import math
from collections import defaultdict
from datetime import date
from langgraph.graph import END

from agents.state import FinancialState, add_reasoning
from db.supabase_client import db
from utils.llm import qwen_json
from utils.prompts import reconciliation_anomaly_prompt

MATCH_THRESHOLD = 0.85   # cosine similarity threshold — thesis Section 2.7.1


def reconciliation_node(state: FinancialState) -> FinancialState:
    trigger = state.get("trigger", "daily_reconciliation")
    if trigger in ("daily_reconciliation", "manual_reconciliation"):
        return _run_reconciliation(state)
    return {**state, "next_agent": END, "current_agent": "reconciliation",
            "error": f"reconciliation_node: unknown trigger '{trigger}'"}


def _run_reconciliation(state: FinancialState) -> FinancialState:
    run_id = str(uuid.uuid4())
    period = state.get("reconciliation", {}).get("period") or _current_period()

    # ── Load unmatched transactions ──────────────────────────────────────────
    all_tx = db.get_unmatched_transactions(limit=500)
    internal = [t for t in all_tx if t["source"] == "internal"]
    bank     = [t for t in all_tx if t["source"] == "bank"]

    if not internal or not bank:
        note = f"Reconciliation {period}: insufficient data (internal={len(internal)}, bank={len(bank)})"
        state = add_reasoning(state, "reconciliation", "skipped", note)
        return {**state, "current_agent": "reconciliation", "next_agent": END,
                "reconciliation": {**state.get("reconciliation", {}),
                                   "run_id": run_id, "period": period,
                                   "match_rate": 0.0, "unmatched_count": 0}}

    # ── TF-IDF cosine similarity matching ────────────────────────────────────
    matched_pairs, unmatched_internal, unmatched_bank = _match_transactions(internal, bank)

    total         = len(internal) + len(bank)
    matched_count = len(matched_pairs) * 2
    unmatched     = unmatched_internal + unmatched_bank
    match_rate    = (matched_count / total * 100) if total > 0 else 0.0

    # Persist matched pairs in DB
    for tx_int, tx_bank, score in matched_pairs:
        supabase = _supabase()
        supabase.table("transactions").update(
            {"matched": True, "matched_to": tx_bank["id"], "match_score": round(score, 4)}
        ).eq("id", tx_int["id"]).execute()
        supabase.table("transactions").update(
            {"matched": True, "matched_to": tx_int["id"], "match_score": round(score, 4)}
        ).eq("id", tx_bank["id"]).execute()

    # ── Qwen3 anomaly analysis ────────────────────────────────────────────────
    anomaly_result = {}
    anomaly_summary = f"{len(unmatched)} unmatched transactions detected."
    systematic = False

    if unmatched:
        system, user = reconciliation_anomaly_prompt(unmatched, period)
        anomaly_result = qwen_json(system, user)
        anomaly_summary = anomaly_result.get("summary", anomaly_summary)
        systematic = bool(anomaly_result.get("systematic_issue", False))

    # ── Write reconciliation report ───────────────────────────────────────────
    supabase = _supabase()
    report_data = {
        "period":          period,
        "run_id":          run_id,
        "total_internal":  len(internal),
        "total_external":  len(bank),
        "matched_count":   len(matched_pairs),
        "unmatched_count": len(unmatched),
        "match_rate":      round(match_rate, 2),
        "discrepancies":   unmatched[:20],   # store first 20 for report
    }
    # upsert — if table exists
    try:
        supabase.table("reconciliation_reports").insert(report_data).execute()
    except Exception:
        pass  # table may not exist yet — created by schema.sql

    # ── XAI audit log ─────────────────────────────────────────────────────────
    db.log_agent_event(
        agent="reconciliation",
        event_type="reconciliation_complete",
        entity_id=run_id,
        details={
            "period":          period,
            "match_rate":      round(match_rate, 2),
            "matched_pairs":   len(matched_pairs),
            "unmatched":       len(unmatched),
            "systematic":      systematic,
            "patterns":        anomaly_result.get("patterns", []),
            "recommended":     anomaly_result.get("recommended_actions", []),
        },
        reasoning=anomaly_summary,
    )

    state = add_reasoning(
        state, "reconciliation", "matching",
        f"Period {period}: {match_rate:.1f}% match rate "
        f"({len(matched_pairs)} pairs matched, {len(unmatched)} unmatched). "
        f"Systematic issue: {systematic}. {anomaly_summary}",
    )

    # ── Cross-agent: if systematic anomaly found, trigger Credit agent ────────
    # Identify the customer associated with recurring anomalies
    customer_id = _find_anomaly_customer(unmatched)
    next_agent  = "credit" if systematic and customer_id else END
    if next_agent == "credit":
        state = add_reasoning(state, "reconciliation", "escalation",
                              f"Systematic payment delays detected → triggering Credit agent "
                              f"reassessment for customer {customer_id}")

    return {
        **state,
        "current_agent": "reconciliation",
        "next_agent":    next_agent,
        "trigger":       "customer_payment_check" if next_agent == "credit" else "done",
        "reconciliation": {
            "run_id":             run_id,
            "period":             period,
            "match_rate":         round(match_rate, 2),
            "unmatched_count":    len(unmatched),
            "anomalies_detected": unmatched[:10],
            "anomaly_summary":    anomaly_summary,
        },
        "credit": {
            **state.get("credit", {}),
            "customer_id": customer_id or "",
        },
    }


# ── TF-IDF cosine similarity implementation ───────────────────────────────────
# Implements thesis formula: sim(A,B) = (A·B) / (||A|| × ||B||)

def _tokenize(tx: dict) -> str:
    """Build composite text field from transaction for TF-IDF."""
    desc   = str(tx.get("description") or "").lower()
    amount = str(int(float(tx.get("amount", 0) or 0)))
    ref    = str(tx.get("reference") or "").lower()
    # Bucket date to week to handle 1-2 day timing differences
    try:
        d = date.fromisoformat(str(tx.get("transaction_date", "")))
        week = f"w{d.isocalendar()[1]}"
    except Exception:
        week = ""
    return f"{desc} {amount} {ref} {week}"


def _build_tfidf(corpus: list[str]) -> list[dict[str, float]]:
    """Build TF-IDF vectors for a list of documents."""
    # Term frequency per document
    tf_docs = []
    for doc in corpus:
        tokens = doc.split()
        counts: dict[str, int] = {}
        for t in tokens:
            counts[t] = counts.get(t, 0) + 1
        total = len(tokens) or 1
        tf_docs.append({t: c / total for t, c in counts.items()})

    # Inverse document frequency
    N = len(corpus)
    df: dict[str, int] = defaultdict(int)
    for tf in tf_docs:
        for term in tf:
            df[term] += 1
    idf = {term: math.log(N / (count + 1)) + 1 for term, count in df.items()}

    # TF-IDF vectors
    return [{term: tf_val * idf.get(term, 1)
             for term, tf_val in tf.items()} for tf in tf_docs]


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity between two sparse TF-IDF vectors."""
    dot   = sum(a.get(t, 0) * b.get(t, 0) for t in a)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _match_transactions(
    internal: list[dict], bank: list[dict]
) -> tuple[list[tuple], list[dict], list[dict]]:
    """
    Match internal transactions to bank records using TF-IDF cosine similarity.
    Returns (matched_pairs, unmatched_internal, unmatched_bank).
    Each matched_pair = (internal_tx, bank_tx, similarity_score).
    """
    if not internal or not bank:
        return [], internal, bank

    # Build corpus and vectors
    int_texts  = [_tokenize(t) for t in internal]
    bank_texts = [_tokenize(t) for t in bank]
    all_texts  = int_texts + bank_texts
    all_vecs   = _build_tfidf(all_texts)
    int_vecs   = all_vecs[:len(internal)]
    bank_vecs  = all_vecs[len(internal):]

    matched_pairs     = []
    used_internal     = set()
    used_bank         = set()

    # Greedy best-match: for each internal tx, find best bank match
    for i, (tx_i, vec_i) in enumerate(zip(internal, int_vecs)):
        best_score = 0.0
        best_j     = -1
        for j, (tx_b, vec_b) in enumerate(zip(bank, bank_vecs)):
            if j in used_bank:
                continue
            # Hard amount filter: must be within 1% to be a candidate
            amt_i = float(tx_i.get("amount", 0) or 0)
            amt_b = float(tx_b.get("amount", 0) or 0)
            if amt_i > 0 and abs(amt_i - amt_b) / amt_i > 0.01:
                continue
            score = _cosine(vec_i, vec_b)
            if score > best_score:
                best_score = score
                best_j     = j

        if best_j >= 0 and best_score >= MATCH_THRESHOLD:
            matched_pairs.append((tx_i, bank[best_j], best_score))
            used_internal.add(i)
            used_bank.add(best_j)

    unmatched_internal = [t for i, t in enumerate(internal) if i not in used_internal]
    unmatched_bank     = [t for j, t in enumerate(bank)     if j not in used_bank]
    return matched_pairs, unmatched_internal, unmatched_bank


def _find_anomaly_customer(unmatched: list[dict]) -> str | None:
    """
    Try to identify a customer linked to recurring unmatched transactions.
    Looks for a counterparty appearing 2+ times in unmatched records.
    """
    counts: dict[str, int] = defaultdict(int)
    for t in unmatched:
        cp = t.get("counterparty", "")
        if cp:
            counts[cp] += 1

    # Find most frequent counterparty with 2+ unmatched records
    candidates = [(cp, n) for cp, n in counts.items() if n >= 2]
    if not candidates:
        return None

    # Try to find a customer matching that counterparty name
    top_cp = max(candidates, key=lambda x: x[1])[0]
    customers = db.select("customers")
    for c in customers:
        if top_cp.lower() in c.get("name", "").lower():
            return c["id"]

    # Fallback: return first high-risk customer
    high_risk = [c for c in customers if c.get("risk_level") == "high"]
    return high_risk[0]["id"] if high_risk else None


def _current_period() -> str:
    today   = date.today()
    quarter = (today.month - 1) // 3 + 1
    return f"{today.year}-Q{quarter}"


def _supabase():
    from config import get_supabase
    return get_supabase()
