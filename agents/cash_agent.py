"""
agents/cash_agent.py
Cash Management Agent.

Two modes depending on trigger:

1. invoice_post_checks (called from invoice_node):
   → reads invoice amount from state
   → computes C_{t+1} = C_t + I_t - O_t  (thesis Section 2.7.3)
   → sets state.cash.can_approve_payment
   → next_agent = "budget" (continue Scenario 1 chain)

2. cash_position_refresh (called after invoice approved):
   → updates 7-day forecast in cash_flow_forecasts table
   → next_agent = END

The formula C_{t+1} = C_t + I_t - O_t is implemented deterministically.
Qwen3 only adds the natural language explanation for XAI — it never
overrides the numeric result.
"""

from __future__ import annotations
from datetime import date, timedelta
from langgraph.graph import END

from agents.state import FinancialState, add_reasoning
from db.supabase_client import db
from utils.llm import qwen_json
from utils.prompts import cash_liquidity_prompt


MINIMUM_BALANCE_DEFAULT = 10_000.0   # fallback if no account sets a minimum


def cash_node(state: FinancialState) -> FinancialState:
    trigger = state.get("trigger", "cash_position_refresh")

    if trigger == "invoice_post_checks":
        return _liquidity_check(state)

    if trigger == "cash_position_refresh":
        return _refresh_forecast(state)

    return {**state, "next_agent": END, "current_agent": "cash",
            "error": f"cash_node: unknown trigger '{trigger}'"}


# ── Mode 1: liquidity gate for invoice approval ────────────────────────────────

def _liquidity_check(state: FinancialState) -> FinancialState:
    invoice_ctx = state.get("invoice", {})
    invoice_amount = float(invoice_ctx.get("amount", 0) or 0)
    invoice_id     = invoice_ctx.get("invoice_id", "unknown")

    # Aggregate all cash account balances
    accounts = db.get_cash_balances()
    total_balance  = sum(float(a.get("current_balance", 0) or 0) for a in accounts)
    minimum_balance = max(
        (float(a.get("minimum_balance", 0) or 0) for a in accounts),
        default=MINIMUM_BALANCE_DEFAULT,
    )

    # Projected inflows: open receivables due in next 7 days
    projected_inflows  = _projected_inflows(days=7)

    # Projected outflows: approved invoices not yet paid (excluding this one)
    projected_outflows = _projected_outflows(days=7, exclude_id=invoice_id)

    # C_{t+1} = C_t + I_t - O_t  (thesis formula 2.7.3)
    projected_next = total_balance + projected_inflows - projected_outflows

    # Call Qwen3 for assessment + XAI explanation
    system, user = cash_liquidity_prompt(
        total_balance, projected_inflows, projected_outflows,
        invoice_amount, minimum_balance,
    )
    assessment = qwen_json(system, user)

    can_approve   = bool(assessment.get("can_approve", projected_next - invoice_amount > minimum_balance))
    shortfall     = float(assessment.get("shortfall", 0) or 0)
    risk_level    = assessment.get("risk_level", "medium")
    reasoning     = assessment.get("reasoning", f"Projected balance after payment: ${projected_next - invoice_amount:,.2f}")

    # Log XAI event
    db.log_agent_event(
        agent="cash",
        event_type="liquidity_check",
        entity_id=invoice_id,
        details={
            "total_balance":       round(total_balance, 2),
            "projected_inflows":   round(projected_inflows, 2),
            "projected_outflows":  round(projected_outflows, 2),
            "projected_next":      round(projected_next, 2),
            "invoice_amount":      round(invoice_amount, 2),
            "minimum_balance":     round(minimum_balance, 2),
            "can_approve":         can_approve,
            "shortfall":           round(shortfall, 2),
            "risk_level":          risk_level,
        },
        reasoning=reasoning,
    )

    state = add_reasoning(
        state, "cash", "liquidity_check",
        f"C_{{t+1}} = {total_balance:,.0f} + {projected_inflows:,.0f} - {projected_outflows:,.0f} = "
        f"{projected_next:,.0f}. Payment of {invoice_amount:,.0f}: {'APPROVED' if can_approve else 'BLOCKED'}. "
        f"{reasoning}",
    )

    return {
        **state,
        "current_agent": "cash",
        "next_agent":    "budget",       # continue Scenario 1 chain
        "cash": {
            **state.get("cash", {}),
            "total_balance":       round(total_balance, 2),
            "projected_shortfall": not can_approve,
            "shortfall_amount":    round(shortfall, 2),
            "can_approve_payment": can_approve,
            "liquidity_note":      reasoning,
        },
    }


# ── Mode 2: refresh 7-day forecast after an invoice is approved ────────────────

def _refresh_forecast(state: FinancialState) -> FinancialState:
    accounts = db.get_cash_balances()
    total_balance = sum(float(a.get("current_balance", 0) or 0) for a in accounts)

    today = date.today()
    rows  = []
    running = total_balance

    for d in range(1, 8):
        forecast_date   = today + timedelta(days=d)
        day_inflows     = _projected_inflows(days=1, from_date=forecast_date)
        day_outflows    = _projected_outflows(days=1, from_date=forecast_date)
        running        += day_inflows - day_outflows

        rows.append({
            "forecast_date":      forecast_date.isoformat(),
            "projected_inflow":   round(day_inflows, 2),
            "projected_outflow":  round(day_outflows, 2),
            # net_position is a generated column in DB — no need to send
        })

    # Upsert forecast rows
    supabase = __import__("config", fromlist=["get_supabase"]).get_supabase()
    for row in rows:
        existing = supabase.table("cash_flow_forecasts") \
            .select("id").eq("forecast_date", row["forecast_date"]).execute().data
        if existing:
            supabase.table("cash_flow_forecasts") \
                .update({"projected_inflow": row["projected_inflow"],
                         "projected_outflow": row["projected_outflow"]}) \
                .eq("forecast_date", row["forecast_date"]).execute()
        else:
            supabase.table("cash_flow_forecasts").insert(row).execute()

    db.log_agent_event(
        "cash", "forecast_refreshed", "system",
        {"total_balance": round(total_balance, 2), "days_forecast": 7},
        reasoning=f"7-day forecast updated after invoice approval. Opening balance: ${total_balance:,.2f}",
    )

    state = add_reasoning(state, "cash", "forecast_refresh",
                          f"7-day cash forecast updated. Opening balance: ${total_balance:,.2f}")

    return {**state, "current_agent": "cash", "next_agent": END,
            "cash": {**state.get("cash", {}), "total_balance": round(total_balance, 2)}}


# ── Financial helpers ──────────────────────────────────────────────────────────

def _projected_inflows(days: int = 7, from_date: date | None = None) -> float:
    """
    Sum of open receivables due within `days` days from `from_date`.
    These are payments expected from customers — the I_t component.
    """
    start = (from_date or date.today()).isoformat()
    end   = ((from_date or date.today()) + timedelta(days=days)).isoformat()

    supabase = __import__("config", fromlist=["get_supabase"]).get_supabase()
    rows = (
        supabase.table("receivables")
        .select("amount")
        .eq("status", "open")
        .gte("due_date", start)
        .lte("due_date", end)
        .execute()
        .data
    )
    # Apply 80% collection rate — not all receivables will be collected on time
    collection_rate = 0.80
    return sum(float(r.get("amount", 0) or 0) for r in rows) * collection_rate


def _projected_outflows(days: int = 7, from_date: date | None = None,
                         exclude_id: str = "") -> float:
    """
    Sum of approved invoices due for payment within `days` days.
    These are payments we owe to vendors — the O_t component.
    """
    start = (from_date or date.today()).isoformat()
    end   = ((from_date or date.today()) + timedelta(days=days)).isoformat()

    supabase = __import__("config", fromlist=["get_supabase"]).get_supabase()
    rows = (
        supabase.table("invoices")
        .select("id, total_amount")
        .eq("status", "approved")
        .gte("due_date", start)
        .lte("due_date", end)
        .execute()
        .data
    )
    return sum(
        float(r.get("total_amount", 0) or 0)
        for r in rows
        if r.get("id") != exclude_id
    )
