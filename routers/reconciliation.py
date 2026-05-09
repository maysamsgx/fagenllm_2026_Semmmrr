"""
routers/reconciliation.py
Endpoints for the reconciliation agent.
Handles triggering runs and pulling the latest match reports.
"""

from fastapi import APIRouter, Query, BackgroundTasks
from db.supabase_client import db
from config import get_supabase

router = APIRouter()


@router.post("/run")
def run_reconciliation(background_tasks: BackgroundTasks,
                        period: str | None = Query(None)):
    """Trigger a reconciliation run. Fires LangGraph in background."""
    from datetime import date
    from agents.graph import graph
    from agents.state import initial_state

    run_period = period or f"{date.today().year}-Q{(date.today().month-1)//3+1}"

    def _run():
        # Setting up the initial state for the reconciliation flow.
        state = initial_state("daily_reconciliation", f"recon-{run_period}")
        state["reconciliation"] = {"period": run_period}
        graph.invoke(state)

    background_tasks.add_task(_run)
    return {"message": "Reconciliation started", "period": run_period}


@router.get("/reports")
def get_all_reports():
    """Get all reconciliation reports ordered by date (newest first)."""
    supabase = get_supabase()
    rows = (supabase.table("reconciliation_reports")
            .select("*").order("generated_at", desc=True).execute().data)
    return rows or []


@router.get("/report")
def get_latest_report():
    """Get the most recent reconciliation report."""
    supabase = get_supabase()
    rows = (supabase.table("reconciliation_reports")
            .select("*").order("generated_at", desc=True).limit(1).execute().data)
    if not rows:
        return {"message": "No reports yet — run POST /reconciliation/run first"}
    return rows[0]


@router.get("/report/{period}")
def get_report_by_period(period: str):
    supabase = get_supabase()
    rows = (supabase.table("reconciliation_reports")
            .select("*").eq("period", period)
            .order("generated_at", desc=True).limit(1).execute().data)
    if not rows:
        from fastapi import HTTPException
        raise HTTPException(404, f"No report for period {period}")
    return rows[0]


@router.get("/unmatched")
def get_unmatched(limit: int = Query(50, le=200)):
    """List unmatched transactions enriched with match_type from the latest reconciliation run."""
    import re
    transactions = db.get_unmatched_transactions(limit=limit)
    if not transactions:
        return []

    supabase = get_supabase()
    tx_ids = [tx["id"] for tx in transactions]

    latest = (supabase.table("reconciliation_reports")
              .select("id").order("generated_at", desc=True).limit(1).execute().data)
    _type_re = re.compile(r'\((tfidf|semantic)\)', re.IGNORECASE)
    if latest:
        report_id = latest[0]["id"]
        items = (supabase.table("reconciliation_report_items")
                 .select("transaction_id,notes")
                 .eq("report_id", report_id)
                 .in_("transaction_id", tx_ids)
                 .execute().data or [])
        item_map = {row["transaction_id"]: row.get("notes", "") for row in items}
        for tx in transactions:
            m = _type_re.search(item_map.get(tx["id"], ""))
            tx["match_type"] = m.group(1) if m else None
    else:
        for tx in transactions:
            tx["match_type"] = None

    return transactions


@router.get("/stats")
def get_stats():
    """Quick stats: total, matched, unmatched counts."""
    supabase = get_supabase()
    total    = supabase.table("transactions").select("id", count="exact").execute().count
    matched  = supabase.table("transactions").select("id", count="exact").eq("matched", True).execute().count
    return {
        "total_transactions": total,
        "matched":            matched,
        "unmatched":          total - matched,
        "match_rate_pct":     round(matched / total * 100, 2) if total else 0,
    }

@router.get("/report/{report_id}/causal-trace")
def get_recon_causal_trace(report_id: str):
    """
    Full causal trail for a reconciliation run.
    
    Architecture (matches thesis Section on Causal Domain Reasoning):
    - Step 1: Fetch the reconciliation decision for this report.
    - Step 2: Follow explicit causal_links to find downstream effects
              (e.g. Credit risk reassessment triggered by systematic anomaly).
    - Step 3: Follow further causal_links from those decisions (e.g. Cash AR update).
    
    This strictly uses causal_links — NOT temporal proximity —
    so only decisions that are causally related to THIS run appear.
    """
    report = db.select("reconciliation_reports", {"id": report_id})
    if not report:
        from fastapi import HTTPException
        raise HTTPException(404, "Report not found")
    
    report = report[0]
    decision_id = report.get("generated_by_decision_id")
    
    decisions = []
    if not decision_id:
        return {"decisions": [], "links": [], "trace": [], "name": f"Reconciliation Report — {report.get('period')}"}
    
    # Step 1: The root reconciliation decision
    root = db.select("agent_decisions", {"id": decision_id})
    if not root:
        return {"decisions": [], "links": [], "trace": [], "name": f"Reconciliation Report — {report.get('period')}"}
    
    decisions = list(root)
    supabase = get_supabase()
    
    # Step 2 & 3: Recursively follow all causal links (BFS, max depth 3)
    all_links = []
    visited_ids = {decision_id}
    frontier = [decision_id]
    
    for _ in range(3):  # max 3 hops (recon → credit → cash)
        next_frontier = []
        for dec_id in frontier:
            links = (supabase.table("causal_links")
                     .select("*")
                     .or_(f"cause_decision_id.eq.{dec_id},effect_decision_id.eq.{dec_id}")
                     .execute().data) or []
            all_links.extend(links)
            
            for link in links:
                # Follow downstream (cause → effect)
                if link["cause_decision_id"] == dec_id:
                    other_id = link["effect_decision_id"]
                    if other_id not in visited_ids:
                        visited_ids.add(other_id)
                        other_dec = db.select("agent_decisions", {"id": other_id})
                        if other_dec:
                            decisions.extend(other_dec)
                            next_frontier.append(other_id)
        frontier = next_frontier
        if not frontier:
            break

    decisions = sorted(decisions, key=lambda d: d["created_at"])
    
    trace = [
        {
            "agent": d.get("agent"),
            "event_type": d.get("decision_type"),
            "timestamp": d.get("created_at"),
            "reasoning": d.get("technical_explanation") or d.get("reasoning") or "",
            "technical_explanation": d.get("technical_explanation"),
            "business_explanation": d.get("business_explanation"),
            "causal_explanation": d.get("causal_explanation"),
            "details": {
                "input": d.get("input_state") or {},
                "output": d.get("output_action") or {},
                "confidence": d.get("confidence"),
            },
        }
        for d in decisions
    ]

    return {
        "decisions": decisions,
        "links": all_links,
        "trace": trace,
        "name": f"Reconciliation Report — {report.get('period')}"
    }


