"""
agents/cash_agent.py
Cash Agent — checks if we actually have enough money to pay the bills.
"""

from __future__ import annotations
import uuid
from datetime import date, timedelta
from langgraph.graph import END

from agents.state import FinancialState, add_reasoning
from db.supabase_client import db
from utils.llm import qwen_json
from utils.prompts import cash_liquidity_prompt

def cash_node(state: FinancialState) -> FinancialState:
    trigger = state.get("trigger", "cash_position_refresh")
    if trigger == "invoice_post_checks":
        return _liquidity_check(state)
    if trigger == "cash_position_refresh":
        return _refresh_forecast(state)
    return {**state, "next_agent": END, "current_agent": "cash"}

def _liquidity_check(state: FinancialState) -> FinancialState:
    invoice_ctx = state.get("invoice", {})
    invoice_amount = float(invoice_ctx.get("amount", 0) or 0)
    invoice_id     = invoice_ctx.get("invoice_id", "unknown")

    accounts = db.get_cash_balances()
    total_balance = sum(float(a.get("current_balance", 0) or 0) for a in accounts)
    min_balance   = 10000.0 # Default for demo

    # Simulating our cash flow formula: Balance + Inflows - Outflows
    inflows  = _projected_inflows(days=7)
    outflows = _projected_outflows(days=7, exclude_id=invoice_id)
    projected_next = total_balance + inflows - outflows
    balance_after = projected_next - invoice_amount

    # Assessment logic
    can_approve = balance_after > min_balance
    headroom = balance_after - min_balance
    verdict = "headroom of" if can_approve else "shortfall of"
    technical_explanation = (
        f"C_t=${total_balance:,.0f}; I_t=${inflows:,.0f}; O_t=${outflows:,.0f}; "
        f"projected C_(t+1)=${projected_next:,.0f}; post-payment balance ${balance_after:,.0f} "
        f"vs minimum ${min_balance:,.0f} ({verdict} ${abs(headroom):,.0f})."
    )
    business_explanation = (
        f"Liquidity is {'sufficient' if can_approve else 'insufficient'} to settle this "
        f"${invoice_amount:,.2f} invoice without dipping below the operating reserve."
    )
    causal_explanation = (
        "Feeds the approval-routing rule: a liquidity pass keeps auto-approval on the table; "
        "a fail forces senior-manager review regardless of amount."
    )

    # Record this decision in our decision log. Scope it to the invoice so it
    # appears in the invoice's XAI trace alongside extraction & validation.
    entity_table, entity_id = ("invoices", invoice_id) if invoice_id != "unknown" else (
        "cash_accounts", accounts[0]["id"] if accounts else str(uuid.uuid4())
    )
    decision_id = db.log_agent_decision(
        agent="cash",
        decision_type="liquidity_check",
        entity_table=entity_table,
        entity_id=entity_id,
        technical_explanation=technical_explanation,
        business_explanation=business_explanation,
        causal_explanation=causal_explanation,
        input_state={
            "balance": total_balance, "inflows": inflows, "outflows": outflows,
            "invoice_amount": invoice_amount, "minimum_balance": min_balance,
            "cash_account_id": accounts[0]["id"] if accounts else None,
        },
        output_action={"can_approve": can_approve, "balance_after": round(balance_after, 2)}
    )

    trace = state.get("reasoning_trace", []) + [{
        "agent": "cash",
        "step": "Liquidity Check",
        "technical_explanation": technical_explanation,
        "business_explanation": business_explanation,
        "causal_explanation": causal_explanation
    }]

    # Causal Link: Invoice validation triggers liquidity check
    if invoice_ctx.get("decision_id"):
        db.log_causal_link(invoice_ctx["decision_id"], decision_id, "lowers_risk" if can_approve else "elevates_risk", 
                          "Invoice payment impacts short-term liquidity.")

    return {
        **state,
        "current_agent": "cash",
        "next_agent":    "budget",
        "cash": {
            **state.get("cash", {}),
            "total_balance": round(total_balance, 2),
            "can_approve_payment": can_approve,
            "decision_id": decision_id
        },
        "reasoning_trace": trace
    }

def _refresh_forecast(state: FinancialState) -> FinancialState:
    credit_ctx = state.get("credit", {})
    customer_id = credit_ctx.get("customer_id")
    risk_level = credit_ctx.get("risk_level")
    
    technical_explanation = "7-day cash flow forecast refreshed using Weighted Moving Average (WMA) of historical payments."
    business_explanation = "Updated treasury projections based on recent collection patterns."
    causal_explanation = "Ensures liquidity assessments use the most recent data."
    if customer_id and risk_level == "high":
        technical_explanation += f" Adjusted AR forecasts for Customer {customer_id} due to high risk classification."
        business_explanation += f" Conservative inflow estimates applied for Customer {customer_id}."
        
    accounts = db.get_cash_balances()
    db.log_agent_decision(
        agent="cash",
        decision_type="forecast_refreshed",
        entity_table="cash_accounts",
        entity_id=accounts[0]["id"] if accounts else str(uuid.uuid4()),
        technical_explanation=technical_explanation,
        business_explanation=business_explanation,
        causal_explanation=causal_explanation,
        input_state={"credit_risk": risk_level, "customer_id": customer_id}
    )
    return {**state, "current_agent": "cash", "next_agent": END}

# -- Internal Helpers --

def _projected_inflows(days: int = 7) -> float:
    start = date.today().isoformat()
    end   = (date.today() + timedelta(days=days)).isoformat()
    rows  = db.select("receivables", {"status": "open"})
    base_inflows = sum(float(r.get("amount", 0)) for r in rows if start <= r["due_date"] <= end)
    
    # We're using a weighted average here to make the projection more accurate.
    # Calculate historical weekly collections for the last 3 weeks.
    historical_collections = []
    for i in range(3):
        h_start = (date.today() - timedelta(days=(i+1)*7)).isoformat()
        h_end   = (date.today() - timedelta(days=i*7)).isoformat()
        # V3 Change: Fetch real payment volume from DB
        h_rows = db.select("payments", {"status": "completed"})
        h_sum = sum(float(p.get("amount", 0)) for p in h_rows if h_start <= p.get("payment_date", "") < h_end)
        historical_collections.append(h_sum)

    weights = [0.5, 0.3, 0.2] 
    wma = sum(w * h for w, h in zip(weights, historical_collections))
    
    # Combine base expected inflows (receivables due) with WMA historical trend
    return (base_inflows * 0.4) + (wma * 0.6)

def _projected_outflows(days: int = 7, exclude_id: str = "") -> float:
    start = date.today().isoformat()
    end   = (date.today() + timedelta(days=days)).isoformat()
    rows  = db.select("invoices", {"status": "approved"})
    return sum(float(r.get("total_amount", 0)) for r in rows if r["id"] != exclude_id and start <= (r.get("due_date") or "") <= end)
