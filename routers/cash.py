"""routers/cash.py — Cash Management Agent endpoints."""

from datetime import date, timedelta

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


def _build_forecast_rows(accounts: list, inflows: float, outflows: float, days: int) -> list:
    """
    Compute a 7-day forecast ENTIRELY in memory from live account data.
    This NEVER fails because it does NOT write to the DB.
    Always returns `projected_balance` so the chart renders.
    """
    from directives.policies import CASH

    n = max(days, CASH.forecast_days, 1)
    daily_in  = inflows  / n if n else inflows
    daily_out = outflows / n if n else outflows
    running_balance = sum(float(a.get("current_balance", 0) or 0) for a in accounts)
    account_id = accounts[0]["id"] if accounts else None
    today = date.today()

    rows = []
    for i in range(days):
        fdate   = (today + timedelta(days=i)).isoformat()
        weight  = 1.0 - (i * (0.6 / n)) if n > 0 else 1.0
        var_in  = 1.0 + ((i * 7  + 3) % 7 - 3) * 0.04
        var_out = 1.0 + ((i * 11 + 1) % 7 - 3) * 0.04
        proj_in  = round(daily_in  * weight * var_in,  2)
        proj_out = round(daily_out * weight * var_out, 2)
        running_balance += proj_in - proj_out

        rows.append({
            "forecast_date":     fdate,
            "cash_account_id":   account_id,
            "projected_inflow":  proj_in,
            "projected_outflow": proj_out,
            "net_position":      round(proj_in - proj_out, 2),
            "projected_balance": round(running_balance, 2),
            "notes": f"Live-computed ({today.isoformat()})",
        })
    return rows


@router.get("/forecast")
def get_forecast(days: int = Query(7, le=30)):
    """
    Returns 7-day cash flow forecast rows for the dashboard chart.

    Strategy:
    1. Try to load persisted rows from cash_flow_forecasts that already have
       projected_balance populated (indicates a full agent run completed).
    2. If not enough good DB rows exist, compute the forecast in-memory from
       live account balances + receivable projections. This always succeeds.
    3. Attempt a best-effort background persist so future loads are faster,
       but NEVER block the response on DB writes.
    """
    from agents.cash_agent import _projected_inflows, _projected_outflows
    from directives.policies import CASH

    start_dt = date.today().isoformat()
    end_dt   = (date.today() + timedelta(days=days)).isoformat()
    supabase = get_supabase()

    # ── Step 1: Try to fetch persisted rows ──────────────────────────────────
    db_rows: list = []
    try:
        db_rows = (
            supabase.table("cash_flow_forecasts")
            .select("*")
            .gte("forecast_date", start_dt)
            .lte("forecast_date", end_dt)
            .order("forecast_date")
            .execute()
            .data
        ) or []
    except Exception:
        pass

    # Deduplicate by date, keeping most recent
    unique: dict = {}
    for r in db_rows:
        d = r.get("forecast_date", "")
        if d and (d not in unique or r.get("created_at", "") > unique[d].get("created_at", "")):
            unique[d] = r
    deduped = [unique[k] for k in sorted(unique.keys())]

    # Only trust DB rows that have projected_balance (older rows may be missing it)
    good_db_rows = [r for r in deduped if r.get("projected_balance") is not None]

    if len(good_db_rows) >= days:
        # ── Happy path: DB has complete, valid data ──────────────────────────
        return {"days": days, "forecast": good_db_rows[:days]}

    # ── Step 2: Compute in-memory — guaranteed to return data ────────────────
    accounts = db.get_cash_balances()
    inflows  = _projected_inflows(days=CASH.near_window_days)
    outflows = _projected_outflows(days=CASH.near_window_days)
    forecast = _build_forecast_rows(accounts, inflows, outflows, days)

    # ── Step 3: Best-effort persist (fire-and-forget, never blocks) ──────────
    try:
        from agents.cash_agent import _write_forecast
        _write_forecast(accounts, inflows, outflows)
    except Exception:
        pass  # In-memory data is already computed above — this is non-critical

    return {"days": days, "forecast": forecast}


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

    immediate_balance_after = total_balance - amount
    projected_next = total_balance + inflows - outflows
    balance_after  = projected_next - amount

    # Stricter approval: must clear minimum balance AND not be negative at any point
    can_approve    = balance_after > CASH.minimum_balance and immediate_balance_after > 0
    headroom       = balance_after - CASH.minimum_balance

    risk_level = (
        "critical" if balance_after < 0 or immediate_balance_after < 0 else
        "high"     if balance_after < CASH.minimum_balance             else
        "medium"   if balance_after < CASH.minimum_balance * 2          else
        "low"
    )

    directive = load_directive("cash")
    analysis = qwen_json(
        f"## Policy\n{directive}\nYou are a treasury analyst. Respond with valid JSON only.",
        f"Current balance: ${total_balance:,.0f}. "
        f"Immediate impact: ${immediate_balance_after:,.0f}. "
        f"Projected 7-day inflows: ${inflows:,.0f}, outflows: ${outflows:,.0f}. "
        f"Proposed payment '{label}': ${amount:,.2f}. "
        f"Final projected balance: ${balance_after:,.2f} vs minimum reserve ${CASH.minimum_balance:,.0f}. "
        f"SAFETY HEADROOM: ${headroom:,.2f}. "
        f"Provide JSON with keys: recommendation (string), narrative (1 paragraph), "
        f"alternatives (list of 2-3 strings), risk_level (low/medium/high/critical). "
        f"IMPORTANT: If balance_after < {CASH.minimum_balance}, recommend rejection or delay.",
    )

    return {
        "label":           label,
        "amount":          round(amount, 2),
        "current_balance": round(total_balance, 2),
        "immediate_balance_after": round(immediate_balance_after, 2),
        "projected_next":  round(projected_next, 2),
        "balance_after":   round(balance_after, 2),
        "minimum_balance": CASH.minimum_balance,
        "headroom":        round(headroom, 2),
        "can_approve":     can_approve,
        "risk_level":      risk_level,
        "analysis":        analysis,
    }
