"""routers/reconciliation.py — Reconciliation Agent endpoints."""

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
        state = initial_state("daily_reconciliation", f"recon-{run_period}")
        state["reconciliation"] = {"period": run_period}
        graph.invoke(state)

    background_tasks.add_task(_run)
    return {"message": "Reconciliation started", "period": run_period}


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
    """List unmatched transactions — the input to the next reconciliation run."""
    return db.get_unmatched_transactions(limit=limit)


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
