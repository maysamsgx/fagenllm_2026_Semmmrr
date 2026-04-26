"""
agents/cash_agent.py
Cash Management Agent — V2 (Causal-Reasoning-Ready).
"""

from __future__ import annotations
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

    # I_t - O_t simulation
    inflows  = _projected_inflows(days=7)
    outflows = _projected_outflows(days=7, exclude_id=invoice_id)
    projected_next = total_balance + inflows - outflows

    # Assessment logic
    can_approve = (projected_next - invoice_amount) > min_balance
    reasoning = f"Current balance: ${total_balance:,.0f}. Projected next 7d: +${inflows:,.0f} -${outflows:,.0f} = ${projected_next:,.0f}."
    
    # Log Decision (V2)
    decision_id = db.log_agent_decision(
        agent="cash",
        decision_type="liquidity_check",
        entity_table="cash_accounts",
        entity_id="consolidated",
        reasoning=reasoning,
        input_state={"balance": total_balance, "inflows": inflows, "outflows": outflows, "invoice": invoice_amount},
        output_action={"can_approve": can_approve}
    )

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
            "liquidity_note": reasoning,
            "decision_id": decision_id
        }
    }

def _refresh_forecast(state: FinancialState) -> FinancialState:
    # Simplified forecast logic for v2 demo
    db.log_agent_decision("cash", "forecast_refreshed", "system", "system", "7-day forecast updated.")
    return {**state, "current_agent": "cash", "next_agent": END}

# -- Internal Helpers --

def _projected_inflows(days: int = 7) -> float:
    start = date.today().isoformat()
    end   = (date.today() + timedelta(days=days)).isoformat()
    rows  = db.select("receivables", {"status": "open"})
    return sum(float(r.get("amount", 0)) for r in rows if start <= r["due_date"] <= end) * 0.8

def _projected_outflows(days: int = 7, exclude_id: str = "") -> float:
    start = date.today().isoformat()
    end   = (date.today() + timedelta(days=days)).isoformat()
    rows  = db.select("invoices", {"status": "approved"})
    return sum(float(r.get("total_amount", 0)) for r in rows if r["id"] != exclude_id and start <= (r.get("due_date") or "") <= end)
