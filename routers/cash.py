"""routers/cash.py — Cash Management Agent endpoints."""

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


@router.post("/scenario")
def cash_scenario(
    amount: float = Query(..., description="Proposed payment amount ($)"),
    label: str    = Query("Proposed payment", description="Human-readable label"),
):
    """
    What-If: what happens to liquidity if we pay $amount right now?
    Returns deterministic numbers + LLM narrative (mirrors /budget/whatif).
    """
    from agents.cash_agent import _projected_inflows, _projected_outflows
    from directives.policies import CASH
    from utils.directives import load_directive
    from utils.llm import qwen_json

    accounts      = db.get_cash_balances()
    total_balance = sum(float(a.get("current_balance", 0) or 0) for a in accounts)
    inflows       = _projected_inflows(days=CASH.near_window_days)
    outflows      = _projected_outflows(days=CASH.near_window_days)

    projected_next = total_balance + inflows - outflows
    balance_after  = projected_next - amount
    can_approve    = balance_after > CASH.minimum_balance
    headroom       = balance_after - CASH.minimum_balance

    risk_level = (
        "critical" if balance_after < 0                       else
        "high"     if balance_after < CASH.minimum_balance    else
        "medium"   if balance_after < CASH.minimum_balance * 2 else
        "low"
    )

    directive = load_directive("cash")
    analysis = qwen_json(
        f"## Policy\n{directive}\nYou are a treasury analyst. Respond with valid JSON only.",
        f"Current balance: ${total_balance:,.0f}. "
        f"Projected 7-day inflows: ${inflows:,.0f}, outflows: ${outflows:,.0f}. "
        f"Proposed payment '{label}': ${amount:,.2f}. "
        f"Balance after payment: ${balance_after:,.2f} vs minimum reserve ${CASH.minimum_balance:,.0f}. "
        f"Provide JSON with keys: recommendation (string), narrative (1 paragraph), "
        f"alternatives (list of 2-3 strings), risk_level (low/medium/high/critical).",
    )

    return {
        "label":           label,
        "amount":          round(amount, 2),
        "current_balance": round(total_balance, 2),
        "projected_next":  round(projected_next, 2),
        "balance_after":   round(balance_after, 2),
        "minimum_balance": CASH.minimum_balance,
        "headroom":        round(headroom, 2),
        "can_approve":     can_approve,
        "risk_level":      risk_level,
        "analysis":        analysis,
    }
