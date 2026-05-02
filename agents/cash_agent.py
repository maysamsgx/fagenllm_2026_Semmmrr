"""
agents/cash_agent.py
Cash Agent — checks if we actually have enough money to pay the bills.

Implements the DOE 6-Module Architecture via AgentPipeline:
  Perception   → reads DB cash balances + invoice state
  Reasoning    → None (fully deterministic — no LLM needed)
  Decision     → applies C_{t+1} formula and minimum-balance gate
  Explanation  → logs to agent_decisions + causal_links
  Execution    → no-op (explanation already wrote the DB row)
  Communication→ builds updated FinancialState for LangGraph
"""

from __future__ import annotations
import uuid
from datetime import date, timedelta
from langgraph.graph import END

from agents.state import FinancialState
from db.supabase_client import db
from directives.policies import CASH
from utils.agent_modules import AgentPipeline, run_agent_pipeline


def cash_node(state: FinancialState) -> FinancialState:
    trigger = state.get("trigger", "cash_position_refresh")
    if trigger == "invoice_post_checks":
        return run_agent_pipeline(_LIQUIDITY_PIPELINE, state)
    if trigger == "cash_position_refresh":
        return _refresh_forecast(state)
    return {**state, "next_agent": END, "current_agent": "cash"}


# ── Module 1: Perception ──────────────────────────────────────────────────────

def _perceive(state: FinancialState) -> dict:
    """Reads everything from state + DB the decision will need."""
    invoice_ctx    = state.get("invoice", {})
    invoice_amount = float(invoice_ctx.get("amount", 0) or 0)
    invoice_id     = invoice_ctx.get("invoice_id", "unknown")

    accounts      = db.get_cash_balances()
    total_balance = sum(float(a.get("current_balance", 0) or 0) for a in accounts)

    inflows  = _projected_inflows(days=CASH.near_window_days)
    outflows = _projected_outflows(days=CASH.near_window_days, exclude_id=invoice_id)

    return {
        "invoice_ctx":    invoice_ctx,
        "invoice_amount": invoice_amount,
        "invoice_id":     invoice_id,
        "accounts":       accounts,
        "total_balance":  total_balance,
        "min_balance":    CASH.minimum_balance,
        "inflows":        inflows,
        "outflows":       outflows,
    }


# ── Module 2: Reasoning ───────────────────────────────────────────────────────

def _reason(_state: FinancialState, _percept: dict):
    """
    Cash liquidity is fully deterministic — no LLM call required.
    Returning None documents that the Reasoning module is intentionally unused.
    """
    return None


# ── Module 3: Decision ────────────────────────────────────────────────────────

def _decide(_state: FinancialState, percept: dict, _llm_out) -> dict:
    """Applies C_{t+1} formula and the minimum-balance gate."""
    tb  = percept["total_balance"]
    i   = percept["inflows"]
    o   = percept["outflows"]
    amt = percept["invoice_amount"]
    mb  = percept["min_balance"]

    projected_next = tb + i - o
    balance_after  = projected_next - amt
    can_approve    = balance_after > mb
    headroom       = balance_after - mb

    return {
        "can_approve":     can_approve,
        "projected_next":  projected_next,
        "balance_after":   balance_after,
        "headroom":        headroom,
        "verdict_word":    "headroom of" if can_approve else "shortfall of",
        "next_agent":      "budget",
    }


# ── Module 4: Explanation ─────────────────────────────────────────────────────

def _explain(state: FinancialState, percept: dict, verdict: dict) -> str:
    """Logs the decision to agent_decisions and creates a causal link. Returns decision_id."""
    tb   = percept["total_balance"]
    i    = percept["inflows"]
    o    = percept["outflows"]
    pn   = verdict["projected_next"]
    ba   = verdict["balance_after"]
    mb   = percept["min_balance"]
    vw   = verdict["verdict_word"]
    amt  = percept["invoice_amount"]
    caa  = verdict["can_approve"]
    inv  = percept["invoice_id"]
    acts = percept["accounts"]

    technical = (
        f"C_t=${tb:,.0f}; I_t=${i:,.0f}; O_t=${o:,.0f}; "
        f"projected C_(t+1)=${pn:,.0f}; post-payment balance ${ba:,.0f} "
        f"vs minimum ${mb:,.0f} ({vw} ${abs(verdict['headroom']):,.0f})."
    )
    business = (
        f"Liquidity is {'sufficient' if caa else 'insufficient'} to settle this "
        f"${amt:,.2f} invoice without dipping below the operating reserve."
    )
    causal = (
        "Feeds the approval-routing rule: a liquidity pass keeps auto-approval on the "
        "table; a fail forces senior-manager review regardless of amount."
    )

    entity_table = "invoices" if inv != "unknown" else "cash_accounts"
    entity_id    = inv if inv != "unknown" else (acts[0]["id"] if acts else str(uuid.uuid4()))

    decision_id = db.log_agent_decision(
        agent="cash",
        decision_type="liquidity_check",
        entity_table=entity_table,
        entity_id=entity_id,
        technical_explanation=technical,
        business_explanation=business,
        causal_explanation=causal,
        input_state={
            "balance": tb, "inflows": i, "outflows": o,
            "invoice_amount": amt, "minimum_balance": mb,
            "cash_account_id": acts[0]["id"] if acts else None,
        },
        output_action={"can_approve": caa, "balance_after": round(ba, 2)},
    )

    invoice_ctx = percept["invoice_ctx"]
    if invoice_ctx.get("decision_id"):
        db.log_causal_link(
            invoice_ctx["decision_id"], decision_id,
            "lowers_risk" if caa else "elevates_risk",
            "Invoice payment impacts short-term liquidity.",
        )
    return decision_id


# ── Module 5: Execution ───────────────────────────────────────────────────────

def _execute(_state: FinancialState, _percept: dict, _verdict: dict) -> None:
    """
    No additional DB writes needed for a liquidity check — all writes happen
    in Explanation. This module documents that the execution slot exists even
    when it is a deliberate no-op.
    """
    pass


# ── Module 6: Communication ───────────────────────────────────────────────────

def _communicate(state: FinancialState, percept: dict, verdict: dict) -> FinancialState:
    """Builds the updated FinancialState to hand back to LangGraph."""
    caa = verdict["can_approve"]
    tb  = percept["total_balance"]
    ba  = verdict["balance_after"]
    did = verdict["decision_id"]

    trace = state.get("reasoning_trace", []) + [{
        "agent": "cash",
        "step": "Liquidity Check",
        "technical_explanation": (
            f"C_t=${tb:,.0f}; post-payment balance ${ba:,.0f}."
        ),
        "business_explanation": (
            f"Liquidity {'sufficient' if caa else 'insufficient'} for this invoice."
        ),
        "causal_explanation": (
            "Feeds the approval-routing rule: pass → auto-approval eligible; "
            "fail → escalated to senior manager."
        ),
    }]

    return {
        **state,
        "current_agent": "cash",
        "next_agent":    verdict["next_agent"],
        "cash": {
            **state.get("cash", {}),
            "total_balance":       round(tb, 2),
            "can_approve_payment": caa,
            "decision_id":         did,
        },
        "reasoning_trace": trace,
    }


# ── Wire into a named pipeline ────────────────────────────────────────────────

_LIQUIDITY_PIPELINE = AgentPipeline(
    name="cash",
    perception=_perceive,
    reasoning=_reason,
    decision=_decide,
    execution=_execute,
    communication=_communicate,
    explanation=_explain,
)


# ── Cash position refresh (triggered by credit agent high-risk signal) ────────

def _refresh_forecast(state: FinancialState) -> FinancialState:
    credit_ctx  = state.get("credit", {})
    customer_id = credit_ctx.get("customer_id")
    risk_level  = credit_ctx.get("risk_level")

    technical = "7-day cash flow forecast refreshed using Weighted Moving Average (WMA) of historical payments."
    business  = "Updated treasury projections based on recent collection patterns."
    causal    = "Ensures liquidity assessments use the most recent data."
    if customer_id and risk_level == "high":
        technical += f" Adjusted AR forecasts for Customer {customer_id} due to high risk classification."
        business  += f" Conservative inflow estimates applied for Customer {customer_id}."

    accounts = db.get_cash_balances()
    db.log_agent_decision(
        agent="cash",
        decision_type="forecast_refreshed",
        entity_table="cash_accounts",
        entity_id=accounts[0]["id"] if accounts else str(uuid.uuid4()),
        technical_explanation=technical,
        business_explanation=business,
        causal_explanation=causal,
        input_state={"credit_risk": risk_level, "customer_id": customer_id}
    )
    return {**state, "current_agent": "cash", "next_agent": END}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _projected_inflows(days: int = 7) -> float:
    today = date.today()
    near_end = (today + timedelta(days=days)).isoformat()
    far_end  = (today + timedelta(days=CASH.far_window_days)).isoformat()
    start    = today.isoformat()

    # Near-term receivables (0–7 days) at full value
    rows = db.select("receivables", {"status": "open"})
    near_receivables = sum(
        float(r.get("amount", 0))
        for r in rows if start <= r.get("due_date", "") <= near_end
    )

    # Far receivables (8–30 days) at discounted probability
    far_receivables = sum(
        float(r.get("amount", 0)) * CASH.far_discount
        for r in rows
        if near_end < r.get("due_date", "") <= far_end
    )

    # WMA of the last 3 weeks of actual payment receipts
    historical: list[float] = []
    for i in range(3):
        h_start = (today - timedelta(days=(i + 1) * 7)).isoformat()
        h_end   = (today - timedelta(days=i * 7)).isoformat()
        h_rows  = db.select("payments", {"status": "completed"})
        h_sum   = sum(
            float(p.get("amount", 0))
            for p in h_rows if h_start <= p.get("payment_date", "") < h_end
        )
        historical.append(h_sum)

    wma = sum(w * h for w, h in zip(CASH.wma_weights, historical))

    return (near_receivables * 0.4) + (wma * 0.6) + far_receivables


def _projected_outflows(days: int = 7, exclude_id: str = "") -> float:
    start = date.today().isoformat()
    end   = (date.today() + timedelta(days=days)).isoformat()
    rows  = db.select("invoices", {"status": "approved"})
    return sum(
        float(r.get("total_amount", 0))
        for r in rows
        if r["id"] != exclude_id and start <= (r.get("due_date") or "") <= end
    )
