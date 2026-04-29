"""routers/cash.py — Cash Management Agent endpoints (V2)."""

from fastapi import APIRouter, BackgroundTasks, Query
from db.supabase_client import db
from config import get_supabase

router = APIRouter()


@router.post("/run")
def run_cash_refresh(background_tasks: BackgroundTasks):
    """Trigger a cash position refresh through the supervisor."""
    from agents.graph import graph
    from agents.state import initial_state

    def _run():
        state = initial_state("cash_position_refresh", "cash-refresh")
        graph.invoke(state)

    background_tasks.add_task(_run)
    return {"message": "Cash refresh started"}

@router.get("/position")
def get_cash_position():
    accounts = db.get_cash_balances()
    total = sum(float(a.get("current_balance", 0) or 0) for a in accounts)
    return {"total_balance": round(total, 2), "accounts": accounts}

@router.get("/forecast")
def get_forecast(days: int = Query(7, le=30)):
    from datetime import date, timedelta
    supabase = get_supabase()
    start = date.today().isoformat()
    end   = (date.today() + timedelta(days=days)).isoformat()
    rows  = (supabase.table("cash_flow_forecasts").select("*")
             .gte("forecast_date", start).lte("forecast_date", end)
             .order("forecast_date").execute().data)
    return {"days": days, "forecast": rows}
