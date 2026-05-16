from fastapi import APIRouter, BackgroundTasks
from db.supabase_client import db
from datetime import date
import json
from config import get_supabase

router = APIRouter()

@router.post("/run-evaluation")
def trigger_evaluation(background_tasks: BackgroundTasks):
    from evaluation.evaluator import run_evaluation
    import asyncio
    def _run():
        try:
            asyncio.run(run_evaluation("UI Triggered Scientific Run"))
        except Exception as e:
            print(f"Eval Run Error: {e}")
    background_tasks.add_task(_run)
    return {"status": "started"}

@router.get("/evaluation-runs")
def list_evaluation_runs():
    """List all scientific evaluation runs (newest first) for the run-selector dropdown."""
    import os, json
    runs_file = os.path.join(os.path.dirname(__file__), "..", "evaluation", "evaluation_runs.json")
    if not os.path.exists(runs_file): return []
    with open(runs_file, "r", encoding="utf-8") as f:
        runs = json.load(f)
    runs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return runs


@router.get("/scientific-evaluation")
def get_scientific_evaluation(run_id: str = None):
    """
    Full metrics payload for the Held-Out Scientific Evaluation tab.

    Returns:
      run          — run summary row
      results      — per-case detail rows
      metrics      — scalar KPIs (accuracy, F1, latency, …)
      confusion_matrix — TP/FP/FN/TN
      per_category — accuracy broken down by category
      sensitivity_curves — detection-rate vs deception-level for adversarial cases
      baseline_comparison — FAgentLLM accuracy vs deterministic baseline
    """
    client = db._ensure_client()

    # ── Resolve run ───────────────────────────────────────────────────────────
    import os, json
    runs_file = os.path.join(os.path.dirname(__file__), "..", "evaluation", "evaluation_runs.json")
    res_file = os.path.join(os.path.dirname(__file__), "..", "evaluation", "evaluation_results.json")
    
    if not os.path.exists(runs_file) or not os.path.exists(res_file):
        return {"error": "No evaluation runs found. Run python -m evaluation.evaluator first."}
        
    with open(runs_file, "r", encoding="utf-8") as f:
        all_runs = json.load(f)
    with open(res_file, "r", encoding="utf-8") as f:
        all_results = json.load(f)
        
    if not run_id:
        all_runs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        if not all_runs:
            return {"error": "No evaluation runs found."}
        run_id = all_runs[0]["id"]

    run = next((r for r in all_runs if r["id"] == run_id), {})
    results = [r for r in all_results if r.get("run_id") == run_id]

    # ── Confusion matrix (PASSED = Positive) ─────────────────────────────────
    def _pos(v: str) -> bool:
        return any(x in str(v).upper() for x in ["PASSED", "APPROVED", "SAFE", "COMPLIANT"])

    tp = sum(1 for r in results if r["status"] == "pass" and _pos(r.get("expected_verdict", "")))
    fp = sum(1 for r in results if r["status"] == "fail" and not _pos(r.get("expected_verdict", "")))
    fn = sum(1 for r in results if r["status"] == "fail" and _pos(r.get("expected_verdict", "")))
    tn = max(0, len(results) - tp - fp - fn)

    precision = round(tp / (tp + fp), 3) if (tp + fp) > 0 else 0.0
    recall    = round(tp / (tp + fn), 3) if (tp + fn) > 0 else 0.0
    f1        = round(2 * precision * recall / (precision + recall), 3) if (precision + recall) > 0 else 0.0

    # ── Per-category accuracy ─────────────────────────────────────────────────
    categories = list({r.get("category", "general") for r in results})
    per_category = []
    for cat in sorted(categories):
        cat_rows  = [r for r in results if r.get("category", "general") == cat]
        cat_pass  = sum(1 for r in cat_rows if r["status"] == "pass")
        per_category.append({
            "category": cat,
            "total":    len(cat_rows),
            "passed":   cat_pass,
            "accuracy": round(cat_pass / len(cat_rows) * 100, 1) if cat_rows else 0,
        })

    # ── Sensitivity curves ────────────────────────────────────────────────────
    # Group adversarial_sensitivity cases by sensitivity_group and build detection
    # rate vs level curves (one point per sensitivity level).
    sens_rows = [r for r in results if r.get("category") == "adversarial_sensitivity"]
    groups: dict = {}
    for r in sens_rows:
        # The test_case_id suffix encodes the level (e.g. TC-039 → level 1)
        # Retrieve grouping info from the run metrics JSONB if available
        meta = run.get("metrics") or {}
        curves = meta.get("sensitivity_curves", {})
        # If the evaluator stored curves directly, use them
        if curves:
            groups = curves
            break
    else:
        # Fallback: reconstruct from result rows using category naming
        for r in sens_rows:
            grp = "threshold_proximity" if r.get("test_case_id", "") in [
                "TC-039", "TC-040", "TC-041", "TC-042"
            ] else "vendor_risk"
            if grp not in groups:
                groups[grp] = []
            groups[grp].append({
                "test_case_id":   r.get("test_case_id"),
                "passed":         r["status"] == "pass",
                "baseline_passed": r.get("baseline_passed", True),
            })

    sensitivity_curves = [
        {"group": grp, "points": pts} for grp, pts in groups.items()
    ]

    # ── Baseline comparison ───────────────────────────────────────────────────
    n = len(results)
    baseline_passed_count   = sum(1 for r in results if r.get("baseline_passed", True))
    fagentllm_passed_count  = sum(1 for r in results if r["status"] == "pass")
    advantage_cases         = sum(1 for r in results if r.get("fagentllm_advantage", False))

    baseline_accuracy    = round(baseline_passed_count  / n * 100, 1) if n else 0
    fagentllm_accuracy   = round(fagentllm_passed_count / n * 100, 1) if n else 0
    accuracy_improvement = round(fagentllm_accuracy - baseline_accuracy, 1)

    # ── Aggregate scalar metrics ──────────────────────────────────────────────
    gov_pass_rate    = round(sum(1 for r in results if r.get("governance_passed",  False)) / n * 100, 1) if n else 0
    causal_succ_rate = round(sum(1 for r in results if r.get("causal_links_present", False)) / n * 100, 1) if n else 0
    avg_latency      = round(sum(float(r.get("latency") or 0) for r in results) / n, 2) if n else 0
    avg_rq           = round(sum(int(r.get("reasoning_quality") or 0) for r in results) / n, 1) if n else 0
    hallucination_rate = round(
        sum(1 for r in results if (r.get("reasoning_quality") or 100) < 30 and r["status"] == "fail") / n * 100, 1
    ) if n else 0

    # Prefer metrics persisted by the evaluator (most accurate) over re-computed values
    stored = run.get("metrics") or {}
    metrics = {
        "accuracy":              stored.get("accuracy",            run.get("accuracy", fagentllm_accuracy)),
        "precision":             stored.get("precision",           precision) ,
        "recall":                stored.get("recall",              recall),
        "f1":                    stored.get("f1",                  f1),
        "f1_pct":                round(stored.get("f1", f1) * 100, 1),
        "latency_avg":           stored.get("latency_avg",         avg_latency),
        "governance_pass_rate":  stored.get("gov_pass_rate",       gov_pass_rate),
        "causal_success_rate":   stored.get("causal_success_rate", causal_succ_rate),
        "hallucination_rate":    stored.get("hallucination_rate",  hallucination_rate),
        "avg_reasoning_quality": stored.get("avg_reasoning_quality", avg_rq),
        "baseline_accuracy":     stored.get("baseline_accuracy",  baseline_accuracy),
        "accuracy_improvement":  accuracy_improvement,
        "total_cases":           n,
        "passed_cases":          fagentllm_passed_count,
    }

    # ── Per-agent performance (from results + decision data) ──────────────────
    agent_categories = {
        "invoice":        ["clean_invoice", "duplicate_detection", "budget_enforcement", "liquidity_gate"],
        "reconciliation": ["reconciliation_credit"],
        "credit":         ["reconciliation_credit"],
        "governance":     ["governance_compliance"],
        "budget":         ["budget_enforcement"],
        "cash":           ["liquidity_gate"],
    }
    per_agent_metrics = []
    for agent, cats in agent_categories.items():
        agent_rows = [r for r in results if r.get("category") in cats]
        if not agent_rows:
            continue
        agent_pass = sum(1 for r in agent_rows if r["status"] == "pass")
        per_agent_metrics.append({
            "agent":    agent,
            "cases":    len(agent_rows),
            "passed":   agent_pass,
            "accuracy": round(agent_pass / len(agent_rows) * 100, 1),
            "gov_rate": round(sum(1 for r in agent_rows if r.get("governance_passed")) / len(agent_rows) * 100, 1),
        })

    return {
        "run":               run,
        "results":           results,
        "metrics":           metrics,
        "confusion_matrix":  {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "per_category":      per_category,
        "per_agent":         per_agent_metrics,
        "sensitivity_curves": sensitivity_curves,
        "baseline_comparison": {
            "baseline_accuracy":    baseline_accuracy,
            "fagentllm_accuracy":   fagentllm_accuracy,
            "accuracy_improvement": accuracy_improvement,
            "advantage_cases":      advantage_cases,
            "chart": [
                {"system": "Baseline (Rule-Only)",    "accuracy": baseline_accuracy,  "color": "#fb7185"},
                {"system": "FAgentLLM (Causal+Gov)",  "accuracy": fagentllm_accuracy, "color": "#34d399"},
            ],
        },
    }

@router.get("/aging")
def get_aging_analysis():
    """Calculate aging buckets for all open receivables."""
    receivables = db.select("receivables", {"status": "open"})
    today = date.today()
    
    buckets = {
        "current": 0.0,
        "31-60": 0.0,
        "61-90": 0.0,
        "90+": 0.0
    }
    
    for r in receivables:
        due_date = date.fromisoformat(r["due_date"])
        amount = float(r["amount"])
        
        if due_date >= today:
            buckets["current"] += amount
        else:
            days_overdue = (today - due_date).days
            if days_overdue <= 30:
                buckets["current"] += amount # 0-30 is usually considered 'current' or 'near current'
            elif days_overdue <= 60:
                buckets["31-60"] += amount
            elif days_overdue <= 90:
                buckets["61-90"] += amount
            else:
                buckets["90+"] += amount
                
    return [
        {"name": k, "value": round(v, 2)} for k, v in buckets.items()
    ]

@router.get("/performance")
def get_performance_metrics():
    """Calculate DSO and Recovery Rate."""
    # Simplified DSO calculation
    all_receivables = db.select("receivables")
    open_receivables = [r for r in all_receivables if r["status"] in ("open", "partial")]
    paid_receivables = [r for r in all_receivables if r["status"] == "paid"]
    
    total_open = sum(float(r["amount"]) for r in open_receivables)
    total_paid = sum(float(r["amount"]) for r in paid_receivables)
    total_sales = total_open + total_paid
    
    # DSO = (AR / Sales) * 365 (assuming annualised or total period)
    # Here we'll use a 90 day window for relevance
    dso = (total_open / max(1, total_sales)) * 90 
    
    # Recovery Rate = (Paid / Total Due) * 100
    recovery_rate = (total_paid / max(1, total_sales)) * 100
    
    return {
        "dso": round(dso, 1),
        "recovery_rate": round(recovery_rate, 1),
        "total_receivables": round(total_sales, 2),
        "collected_amount": round(total_paid, 2),
        "outstanding_amount": round(total_open, 2)
    }

@router.get("/disputes")
def get_disputes():
    """Stakeholder portal: list receivables in 'notice' or 'escalated' stage for dispute resolution."""
    # We'll treat receivables with specific collection stages as 'disputed' or needing resolution
    disputes = db.select("receivables")
    filtered = [d for d in disputes if d["collection_stage"] in ("notice", "escalated")]
    
    # Enrich with customer names
    customers = {c["id"]: c["name"] for c in db.select("customers")}
    for d in filtered:
        d["customer_name"] = customers.get(d["customer_id"], "Unknown")
        
    return filtered

@router.get("/reconciliation")
def get_reconciliation_analytics():
    """Fetch the last 10 reconciliation cycles for historical trend visualization."""
    reports = db.select("reconciliation_reports")
    # Sort by creation time (latest first) and take the last 10
    sorted_reports = sorted(reports, key=lambda x: x.get("generated_at", ""), reverse=True)[:10]
    # Reverse back for chronological chart display
    sorted_reports.reverse()
    
    # Enrich with narratives from agent_decisions and linked causal chains
    for r in sorted_reports:
        dec_id = r.get("generated_by_decision_id")
        if dec_id:
            decision = db.select("agent_decisions", {"id": dec_id})
            if decision:
                main_narrative = (decision[0].get("causal_explanation") or 
                                  decision[0].get("business_explanation") or "")
                r["narrative"] = main_narrative
                
                # V3 Causal Enrichment: Find downstream effects (e.g. Credit/Budget hits)
                links = db.select("causal_links", {"cause_decision_id": dec_id})
                if links:
                    for link in links:
                        effect_dec = db.select("agent_decisions", {"id": link["effect_decision_id"]})
                        if effect_dec:
                            ed = effect_dec[0]
                            # Append the cross-domain signal to the narrative
                            # Safely handle potential None in ed['agent']
                            agent_name = (ed.get('agent') or 'unknown').upper()
                            signal = f"\n\n[Cross-Domain Signal: {agent_name}] {ed.get('business_explanation') or ''}"
                            # Ensure r["narrative"] is a string before appending
                            if r.get("narrative") is None:
                                r["narrative"] = signal
                            else:
                                r["narrative"] += signal
                
    return sorted_reports


@router.get("/evaluation")
def get_evaluation_metrics():
    """
    Comprehensive real-time evaluation metrics across all five agents.
    All values are computed from live Supabase tables — nothing is hardcoded.
    """
    client = get_supabase()

    # ─── Invoice Agent ────────────────────────────────────────────────────────
    invoices = client.table("invoices").select(
        "status, extraction_confidence"
    ).execute().data or []

    total_inv = len(invoices)
    approved  = sum(1 for i in invoices if i.get("status") in ("approved", "paid"))
    rejected  = sum(1 for i in invoices if i.get("status") == "rejected")

    # Confidence-based confusion matrix
    # A high-confidence extraction (>=85%) that the agent approved = TP
    # A high-confidence extraction that was rejected  = FP (agent over-committed)
    # A low-confidence extraction that still got approved = FN (agent under-detected)
    # A low-confidence extraction that was rejected = TN
    threshold = 85.0
    high_conf = [i for i in invoices if (i.get("extraction_confidence") or 0) >= threshold]
    low_conf  = [i for i in invoices if (i.get("extraction_confidence") or 0) <  threshold]

    inv_tp = sum(1 for i in high_conf if i.get("status") in ("approved", "paid"))
    inv_fp = sum(1 for i in high_conf if i.get("status") == "rejected")
    inv_fn = sum(1 for i in low_conf  if i.get("status") in ("approved", "paid"))
    inv_tn = sum(1 for i in low_conf  if i.get("status") == "rejected")

    inv_precision = inv_tp / max(1, inv_tp + inv_fp)
    inv_recall    = inv_tp / max(1, inv_tp + inv_fn)
    inv_f1        = (
        2 * inv_precision * inv_recall / max(0.001, inv_precision + inv_recall)
    )
    avg_conf = (
        sum(i.get("extraction_confidence") or 0 for i in invoices) / max(1, total_inv)
    )

    # Status distribution for chart
    status_counts = {}
    for i in invoices:
        s = i.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    # ─── Reconciliation Agent (direct from DB — 100% real) ───────────────────
    recon_reports = (
        client.table("reconciliation_reports")
        .select("match_rate, matched_count, unmatched_count, generated_at")
        .order("generated_at", desc=True)
        .limit(12)
        .execute()
        .data or []
    )
    latest_recon = recon_reports[0] if recon_reports else {}

    all_txs  = client.table("transactions").select("matched").execute().data or []
    tx_match = sum(1 for t in all_txs if t.get("matched"))
    tx_total = len(all_txs)
    tx_unmatch = tx_total - tx_match
    raw_match_rate = tx_match / max(1, tx_total) * 100

    recon_history = [
        {
            "date":       r["generated_at"][:10],
            "match_rate": round(float(r.get("match_rate") or 0), 2),
            "matched":    r.get("matched_count") or 0,
            "unmatched":  r.get("unmatched_count") or 0,
        }
        for r in reversed(recon_reports)  # chronological
    ]

    # ─── Credit Agent ─────────────────────────────────────────────────────────
    customers = (
        client.table("customers")
        .select("credit_score, risk_level, total_outstanding")
        .execute()
        .data or []
    )
    n_cust = max(1, len(customers))
    high_risk = sum(1 for c in customers if c.get("risk_level") == "high")
    med_risk  = sum(1 for c in customers if c.get("risk_level") == "medium")
    low_risk  = sum(1 for c in customers if c.get("risk_level") == "low")
    avg_score = sum(c.get("credit_score") or 0 for c in customers) / n_cust

    # Credit score histogram (bins of 20)
    score_bins = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
    for c in customers:
        s = float(c.get("credit_score") or 0)
        if   s <= 20:  score_bins["0-20"]   += 1
        elif s <= 40:  score_bins["21-40"]  += 1
        elif s <= 60:  score_bins["41-60"]  += 1
        elif s <= 80:  score_bins["61-80"]  += 1
        else:          score_bins["81-100"] += 1

    # DSO & recovery rate from receivables
    all_recv  = client.table("receivables").select("amount, status, days_overdue").execute().data or []
    avg_delay = sum(float(r.get("days_overdue") or 0) for r in all_recv) / max(1, len(all_recv))
    open_recv = [r for r in all_recv if r.get("status") in ("open", "partial")]
    paid_recv = [r for r in all_recv if r.get("status") == "paid"]
    total_open_amt = sum(float(r.get("amount") or 0) for r in open_recv)
    total_paid_amt = sum(float(r.get("amount") or 0) for r in paid_recv)
    total_sales    = total_open_amt + total_paid_amt
    dso            = (total_open_amt / max(1, total_sales)) * 90
    recovery_rate  = (total_paid_amt / max(1, total_sales)) * 100

    # ─── Cash Agent ───────────────────────────────────────────────────────────
    accounts   = client.table("cash_accounts").select("current_balance").execute().data or []
    total_cash = sum(float(a.get("current_balance") or 0) for a in accounts)

    snapshots = (
        client.table("financial_state_snapshots")
        .select("snapshot_time, total_cash, system_risk_score")
        .order("snapshot_time", desc=False)
        .limit(12)
        .execute()
        .data or []
    )
    snap_history = [
        {
            "date":       s["snapshot_time"][:10],
            "total_cash": round(float(s.get("total_cash") or 0) / 1_000_000, 2),
            "risk_score": round(float(s.get("system_risk_score") or 0), 1),
        }
        for s in snapshots
    ]

    # Forecast accuracy: compare last cash forecast vs snapshot actuals
    # forecast rows are in cash_flow_forecasts; actuals from snapshots
    forecasts = (
        client.table("cash_flow_forecasts")
        .select("forecast_date, projected_inflow, projected_outflow, net_position")
        .order("forecast_date", desc=False)
        .limit(13)
        .execute()
        .data or []
    )

    # Compute MAPE between projected net and snapshot actuals where dates match
    snap_by_date = {s["snapshot_time"][:10]: float(s.get("total_cash") or 0) for s in snapshots}
    mape_terms = []
    for f in forecasts:
        fdate = str(f.get("forecast_date", ""))[:10]
        if fdate in snap_by_date:
            projected = float(f.get("net_position") or 0)
            actual    = snap_by_date[fdate]
            if actual != 0:
                mape_terms.append(abs(projected - actual) / abs(actual))
    cash_mape = (sum(mape_terms) / len(mape_terms) * 100) if mape_terms else None

    # ─── Budget Agent ─────────────────────────────────────────────────────────
    budgets = (
        client.table("budgets")
        .select("department_id, allocated, spent, committed, period")
        .execute()
        .data or []
    )
    departments = client.table("departments").select("id, name").execute().data or []
    dept_names  = {d["id"]: d["name"] for d in departments}

    budget_rows   = []
    util_vals     = []
    over_budget   = 0
    at_risk       = 0

    for b in budgets:
        alloc = float(b.get("allocated") or 0)
        spent_v = float(b.get("spent") or 0)
        committed_v = float(b.get("committed") or 0)
        util_pct = ((spent_v + committed_v) / alloc * 100) if alloc > 0 else 0
        util_vals.append(util_pct)
        if util_pct >= 100: over_budget += 1
        if util_pct >= 80:  at_risk += 1
        budget_rows.append({
            "dept": dept_names.get(b.get("department_id"), b.get("department_id", "?")),
            "utilization": round(util_pct, 1),
            "period": b.get("period", ""),
        })

    avg_util = sum(util_vals) / max(1, len(util_vals))

    # Budget alert count
    alerts = client.table("budget_alerts").select("id, alert_type").eq("acknowledged", False).execute().data or []
    alert_types = {}
    for a in alerts:
        t = a.get("alert_type", "unknown")
        alert_types[t] = alert_types.get(t, 0) + 1

    # ─── System / Agent-level metrics ─────────────────────────────────────────
    all_decisions = (
        client.table("agent_decisions")
        .select("agent, confidence, decision_type, created_at, output_action")
        .execute()
        .data or []
    )
    agents_list = ["invoice", "budget", "reconciliation", "credit", "cash", "governance"]
    per_agent = {}
    for ag in agents_list:
        ag_decs = [d for d in all_decisions if d.get("agent") == ag]
        n = max(1, len(ag_decs))
        per_agent[ag] = {
            "count":          len(ag_decs),
            "avg_confidence": round(
                sum(d.get("confidence") or 0 for d in ag_decs) / n, 1
            ),
        }
    total_decisions = len(all_decisions)

    # Decision type distribution per agent (top 3)
    decision_type_dist: dict = {}
    for d in all_decisions:
        ag = d.get("agent", "unknown")
        dt = d.get("decision_type", "unknown")
        if ag not in decision_type_dist:
            decision_type_dist[ag] = {}
        decision_type_dist[ag][dt] = decision_type_dist[ag].get(dt, 0) + 1

    top_decision_types = {
        ag: sorted(types.items(), key=lambda x: x[1], reverse=True)[:4]
        for ag, types in decision_type_dist.items()
    }

    # Decision timeline: count per day (last 14 days)
    from datetime import timedelta
    today_dt = date.today()
    timeline_days = 14
    day_counts: dict = {}
    for offset in range(timeline_days, -1, -1):
        d = (today_dt - timedelta(days=offset)).isoformat()
        day_counts[d] = {"date": d, "total": 0}
        for ag in agents_list:
            day_counts[d][ag] = 0
    for d in all_decisions:
        ts = str(d.get("created_at", ""))[:10]
        if ts in day_counts:
            day_counts[ts]["total"] = day_counts[ts].get("total", 0) + 1
            ag = d.get("agent", "unknown")
            if ag in agents_list:
                day_counts[ts][ag] = day_counts[ts].get(ag, 0) + 1
    decision_timeline = list(day_counts.values())

    causal_links = (
        client.table("causal_links")
        .select("relationship_type, strength")
        .execute()
        .data or []
    )
    total_links = len(causal_links)
    link_types: dict = {}
    for lk in causal_links:
        rt = lk.get("relationship_type", "unknown")
        link_types[rt] = link_types.get(rt, 0) + 1

    coord_rate = total_links / max(1, total_decisions) * 100

    # ─── Governance Agent ─────────────────────────────────────────────────────
    violations = client.table("governance_violations").select("*").execute().data or []
    gov_audits = [d for d in all_decisions if d.get("agent") == "governance"]
    
    avg_compliance = 0
    if gov_audits:
        scores = []
        for a in gov_audits:
            oa = a.get("output_action")
            if isinstance(oa, dict):
                scores.append(float(oa.get("compliance_score") or 0))
            elif isinstance(oa, str):
                try:
                    scores.append(float(json.loads(oa).get("compliance_score") or 0))
                except: pass
        if scores:
            avg_compliance = sum(scores) / len(scores)

    return {
        "generated_at": date.today().isoformat(),
        "invoice": {
            "total":         total_inv,
            "approved":      approved,
            "rejected":      rejected,
            "pending":       total_inv - approved - rejected,
            "status_dist":   status_counts,
            "avg_confidence": round(avg_conf, 1),
            "approval_rate": round(approved / max(1, approved + rejected) * 100, 1),
            "tp": inv_tp, "fp": inv_fp, "fn": inv_fn, "tn": inv_tn,
            "precision": round(inv_precision * 100, 1),
            "recall":    round(inv_recall    * 100, 1),
            "f1":        round(inv_f1        * 100, 1),
        },
        "reconciliation": {
            "match_rate":         round(float(latest_recon.get("match_rate") or raw_match_rate), 1),
            "matched":            int(latest_recon.get("matched_count") or tx_match),
            "unmatched":          int(latest_recon.get("unmatched_count") or tx_unmatch),
            "total_transactions": tx_total,
            "report_count":       len(recon_reports),
            "history":            recon_history,
        },
        "credit": {
            "total_customers":       len(customers),
            "high_risk":             high_risk,
            "medium_risk":           med_risk,
            "low_risk":              low_risk,
            "avg_credit_score":      round(avg_score, 1),
            "avg_payment_delay_days": round(avg_delay, 1),
            "score_histogram":        [{"bin": k, "count": v} for k, v in score_bins.items()],
            "dso_days":              round(dso, 1),
            "recovery_rate_pct":     round(recovery_rate, 1),
            "total_receivables":     round(total_sales, 2),
            "collected_amount":      round(total_paid_amt, 2),
            "outstanding_amount":    round(total_open_amt, 2),
        },
        "cash": {
            "total_balance":  round(total_cash, 2),
            "account_count":  len(accounts),
            "snapshot_history": snap_history,
            "cash_mape_pct":  round(cash_mape, 1) if cash_mape is not None else None,
        },
        "budget": {
            "total_departments":  len(budgets),
            "avg_utilization_pct": round(avg_util, 1),
            "over_budget_count":  over_budget,
            "at_risk_count":      at_risk,
            "department_rows":    budget_rows,
            "active_alerts":      len(alerts),
            "alert_type_dist":    alert_types,
        },
        "system": {
            "total_decisions":       total_decisions,
            "total_causal_links":    total_links,
            "coordination_rate_pct": round(coord_rate, 1),
            "per_agent":             per_agent,
            "relationship_type_distribution": link_types,
            "decision_timeline":      decision_timeline,
            "top_decision_types":     {ag: [{"type": t, "count": c} for t, c in items]
                                       for ag, items in top_decision_types.items()},
        },
        "governance": {
            "compliance_score": round(avg_compliance, 1),
            "violation_count": len(violations),
            "violation_rate": round((len(violations) / max(1, len(gov_audits))) * 100, 1),
            "audit_count": len(gov_audits),
            "severity_dist": {
                "high": len([v for v in violations if v.get("severity") == "high"]),
                "medium": len([v for v in violations if v.get("severity") == "medium"]),
                "low": len([v for v in violations if v.get("severity") == "low"])
            }
        }
    }

