"""routers/budget.py — Budget Management Agent endpoints (V2)."""

from datetime import date
from fastapi import APIRouter, BackgroundTasks, Query, HTTPException
from db.supabase_client import db
from config import get_supabase

router = APIRouter()


@router.post("/run")
def run_budget_review(background_tasks: BackgroundTasks,
                     department_id: str | None = Query(None),
                     period: str | None = Query(None)):
    """Trigger a budget review through the supervisor."""
    from agents.graph import graph
    from agents.state import initial_state

    run_period = period or current_period()
    entity = department_id or "all"

    def _run():
        state = initial_state("budget_review", entity)
        state["budget"] = {"department_id": department_id or "", "period": run_period}
        graph.invoke(state)

    background_tasks.add_task(_run)
    return {"message": "Budget review started", "department_id": department_id, "period": run_period}


def current_period() -> str:
    today = date.today()
    return f"{today.year}-Q{(today.month - 1) // 3 + 1}"


@router.get("/periods")
def list_periods():
    supabase = get_supabase()
    rows = supabase.table("budgets").select("period").execute().data
    periods = sorted({r["period"] for r in rows if r.get("period")}, reverse=True)
    return {"periods": periods, "current": current_period()}


@router.get("/")
def list_budgets(department_id: str = None, period: str = None):
    supabase = get_supabase()
    resolved_period = period or current_period()

    query = supabase.table("budgets").select("*, departments(name)").eq("period", resolved_period)
    if department_id:
        query = query.eq("department_id", department_id)
    data = query.execute().data

    if not data and not period:
        rows = supabase.table("budgets").select("period").execute().data
        if rows:
            resolved_period = max({r["period"] for r in rows if r.get("period")})
            query = supabase.table("budgets").select("*, departments(name)").eq("period", resolved_period)
            if department_id:
                query = query.eq("department_id", department_id)
            data = query.execute().data

    for item in data:
        item["department"] = item.get("department_id")
    return data

@router.get("/alerts/active")
def get_active_alerts():
    supabase = get_supabase()
    data = (supabase.table("budget_alerts")
            .select("*, budgets(department_id, period, allocated)")
            .eq("acknowledged", False)
            .order("created_at", desc=True).execute().data)
    for item in data:
        b = item.get("budgets") or {}
        item["department_id"] = b.get("department_id")
        item["department"] = b.get("department_id")
        item["period"] = b.get("period")
        item["allocated"] = b.get("allocated")
    return data

@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str):
    return db.update("budget_alerts", {"id": alert_id}, {"acknowledged": True})


@router.post("/reset-committed")
def reset_committed(period: str = Query(...)):
    """Zero out committed column for a period (admin/testing use only)."""
    supabase = get_supabase()
    supabase.table("budgets").update({"committed": 0.0}).eq("period", period).execute()
    return {"reset": True, "period": period}


@router.post("/whatif")
def budget_whatif(department_id: str = Query(...), amount: float = Query(...), period: str = Query(None)):
    """Hypothetical budget impact: what happens if we approve $amount for department?"""
    from directives.policies import BUDGET
    from utils.directives import load_directive
    from utils.llm import qwen_json

    resolved_period = period or current_period()
    budget = db.get_budget(department_id, resolved_period)
    if not budget:
        raise HTTPException(404, f"No budget found for {department_id} / {resolved_period}")

    allocated  = float(budget.get("allocated") or 0)
    spent      = float(budget.get("spent") or 0)
    committed  = float(budget.get("committed") or 0)

    if allocated == 0:
        raise HTTPException(400, "Budget has zero allocation")

    current_util  = (spent + committed) / allocated * 100
    hypo_util     = (spent + committed + amount) / allocated * 100
    remaining_after = max(0.0, allocated - spent - committed - amount)

    risk_level = (
        "critical" if hypo_util >= BUDGET.hard_stop_threshold else
        "high"     if hypo_util >= BUDGET.alert_threshold     else
        "medium"   if hypo_util >= BUDGET.auto_approve_below  else
        "low"
    )

    directive = load_directive("budget")
    analysis = qwen_json(
        f"## Policy\n{directive}\nYou are a financial analyst. Respond with valid JSON only.",
        f"Department '{department_id}' currently at {current_util:.1f}% utilisation "
        f"({spent + committed:,.0f} of {allocated:,.0f} allocated). "
        f"If we approve ${amount:,.2f}, utilisation rises to {hypo_util:.1f}%. "
        f"Remaining budget after approval: ${remaining_after:,.2f}. "
        f"Policy hard-stop: {BUDGET.hard_stop_threshold:.0f}%, alert: {BUDGET.alert_threshold:.0f}%. "
        f"Provide JSON with keys: recommendation (string), narrative (1 paragraph), "
        f"alternatives (list of 2-3 strings), risk_level (low/medium/high/critical)."
    )

    return {
        "department_id":            department_id,
        "period":                   resolved_period,
        "current_utilisation_pct":  round(current_util, 1),
        "hypothetical_utilisation_pct": round(hypo_util, 1),
        "remaining_after":          round(remaining_after, 2),
        "risk_level":               risk_level,
        "will_hard_stop":           hypo_util >= BUDGET.hard_stop_threshold,
        "analysis":                 analysis,
    }
