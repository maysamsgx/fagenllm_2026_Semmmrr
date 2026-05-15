"""
routers/reconciliation.py
Endpoints for the reconciliation agent.
Handles triggering runs and pulling the latest match reports.
"""

from fastapi import APIRouter, Query, BackgroundTasks
from pydantic import BaseModel
from db.supabase_client import db
from config import get_supabase

class ResolveRequest(BaseModel):
    action: str  # 'match', 'ignore', 'escalate'

router = APIRouter()


@router.post("/run")
def run_reconciliation(background_tasks: BackgroundTasks,
                        period: str | None = Query(None)):
    """Trigger a reconciliation run. Fires LangGraph in background."""
    import logging
    logger = logging.getLogger("fagentllm")
    logger.info("RECEIVED POST /api/reconciliation/run")
    from datetime import date
    from agents.graph import graph
    from agents.state import initial_state

    run_period = period or f"{date.today().year}-Q{(date.today().month-1)//3+1}"

    def _run():
        # Setting up the initial state for the reconciliation flow.
        state = initial_state("daily_reconciliation", f"recon-{run_period}")
        state["reconciliation"] = {"period": run_period}
        graph.invoke(state)

    logger.info(f"Queuing background task for period: {run_period}")
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
    if latest and len(latest) > 0:
        report_id = latest[0]["id"]
        items = (supabase.table("reconciliation_report_items")
                 .select("transaction_id,notes")
                 .eq("report_id", report_id)
                 .in_("transaction_id", tx_ids)
                 .execute().data or [])
        item_map = {row["transaction_id"]: (row.get("notes") or "") for row in items}
        for tx in transactions:
            notes = item_map.get(tx["id"], "")
            m = _type_re.search(notes) if notes else None
            tx["match_type"] = m.group(1) if m else None
    else:
        for tx in transactions:
            tx["match_type"] = None

    return transactions


@router.get("/stats")
def get_stats():
    """Quick stats: total, matched, unmatched counts."""
    supabase = get_supabase()
    total_res = supabase.table("transactions").select("id", count="exact").execute()
    matched_res = supabase.table("transactions").select("id", count="exact").eq("matched", True).execute()
    
    total = total_res.count or 0
    matched = matched_res.count or 0
    
    return {
        "total_transactions": total,
        "matched":            matched,
        "unmatched":          max(0, total - matched),
        "match_rate_pct":     round(matched / total * 100, 2) if total > 0 else 0,
    }

@router.get("/report/{report_id}/causal-trace")
def get_recon_causal_trace(report_id: str):
    """
    Standardized trace for reconciliation. 
    Recursively follows causal links starting from the decision that generated the report.
    """
    supabase = get_supabase()
    
    # Step 1: Find the report and its root decision
    report = db.select("reconciliation_reports", {"id": report_id})
    if not report:
        from fastapi import HTTPException
        raise HTTPException(404, "Report not found")
    
    report = report[0]
    decision_id = report.get("generated_by_decision_id")
    
    if not decision_id:
        return {"decisions": [], "links": [], "trace": [], "name": f"Reconciliation Report — {report.get('period')}"}
    
    # Step 2: Fetch the root decision
    root = db.select("agent_decisions", {"id": decision_id})
    if not root:
        return {"decisions": [], "links": [], "trace": [], "name": f"Reconciliation Report — {report.get('period')}"}
    
    # Step 3: Fetch all decisions with the same entity_id (captures perception + complete from same run)
    run_id = root[0].get("entity_id")
    if run_id:
        decisions = db.select("agent_decisions", {"entity_id": run_id})
    else:
        decisions = list(root)
    
    visited_ids = {d["id"] for d in decisions}
    all_links = []
    
    # Step 4: BFS to find downstream/upstream effects
    frontier = list(visited_ids)
    for _ in range(3): # max 3 hops
        if not frontier: break
        next_frontier = []
        
        for dec_id in frontier:
            links = (supabase.table("causal_links")
                     .select("id, cause_decision_id, effect_decision_id, relationship_type, strength, explanation, created_at")
                     .or_(f"cause_decision_id.eq.{dec_id},effect_decision_id.eq.{dec_id}")
                     .execute().data) or []
            
            for link in links:
                if link["id"] not in [l["id"] for l in all_links]:
                    all_links.append(link)
                    
                    # Bi-directional follow
                    cause_id = link["cause_decision_id"]
                    effect_id = link["effect_decision_id"]
                    other_id = effect_id if cause_id == dec_id else cause_id
                    
                    if other_id not in visited_ids:
                        visited_ids.add(other_id)
                        other_dec = db.select("agent_decisions", {"id": other_id})
                        if other_dec:
                            decisions.extend(other_dec)
                            next_frontier.append(other_id)
        
        frontier = next_frontier

    # Step 5: Format for TracePanel
    decisions = sorted(decisions, key=lambda d: d.get("created_at") or "")
    
    trace = [
        {
            "agent": d.get("agent") or "unknown",
            "event_type": d.get("decision_type") or "unknown",
            "timestamp": d.get("created_at"),
            "reasoning": d.get("technical_explanation") or d.get("reasoning") or "",
            "technical_explanation": d.get("technical_explanation") or "",
            "business_explanation": d.get("business_explanation") or "",
            "causal_explanation": d.get("causal_explanation") or "",
            "details": {
                "input": d.get("input_state") or {},
                "output": d.get("output_action") or {},
                "confidence": d.get("confidence") or 0.0,
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


@router.post("/resolve/{tx_id}")
def resolve_dispute(tx_id: str, req: ResolveRequest):
    """
    Manual Stakeholder Resolution Portal — satisfying V3 requirement for
    stakeholder collaboration in dispute resolution.
    """
    if req.action == "match":
        db.update("transactions", {"id": tx_id}, {"matched": True, "match_score": 1.0})
    elif req.action == "escalate":
        # Log a manual decision indicating stakeholder escalation
        db.log_agent_decision(
            agent="reconciliation",
            decision_type="stakeholder_escalation",
            entity_table="transactions",
            entity_id=tx_id,
            technical_explanation="Stakeholder manually flagged transaction for higher-level audit.",
            business_explanation="This transaction requires external validation with the vendor/bank.",
            causal_explanation="Payment lifecycle paused until manual resolution.",
            confidence=1.0
        )
    return {"status": "success", "id": tx_id, "action": req.action}
