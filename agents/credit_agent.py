"""
agents/credit_agent.py
Credit Agent — this guy checks if our customers are actually paying on time
and flags them if they're becoming a risk.
"""

from __future__ import annotations
from datetime import date
from langgraph.graph import END

from agents.state import FinancialState, add_reasoning
from db.supabase_client import db
from utils.llm import qwen_json
from utils.prompts import credit_risk_prompt

def credit_node(state: FinancialState) -> FinancialState:
    trigger = state.get("trigger", "customer_payment_check")
    if trigger in ("customer_payment_check", "daily_reconciliation"):
        return _assess_customer(state)
    return {**state, "next_agent": END, "current_agent": "credit"}

def _assess_customer(state: FinancialState) -> FinancialState:
    credit_ctx  = state.get("credit", {})
    customer_id = credit_ctx.get("customer_id", "")

    if not customer_id:
        return _error(state, "No customer_id specified for credit assessment")

    customer = db.get_customer(customer_id)
    if not customer: return {**state, "next_agent": END, "error": "Customer not found"}

    # We're calculating a risk score here. The formula is basically a weighted sum of delays and outstanding debt.
    f1 = float(customer.get("payment_delay_avg", 5.0))
    f2 = float(customer.get("total_outstanding", 5000.0)) / 1000.0
    w1, w2 = -2.0, -1.5
    base_score = 100.0
    score = max(0.0, min(100.0, base_score + (w1 * f1) + (w2 * f2)))
    
    risk_level = "high" if score < 40 else "medium" if score < 70 else "low"
    # LLM Reasoning
    system, user = credit_risk_prompt(customer, [], score)
    assessment = qwen_json(system, user)
    reasoning  = assessment.get("reasoning", f"Risk assessed as {risk_level}.")

    # Logging the risk assessment so the group can see the reasoning in the dashboard.
    decision_id = db.log_agent_decision(
        agent="credit",
        decision_type="risk_assessed",
        entity_table="customers",
        entity_id=customer_id,
        reasoning=reasoning,
        input_state={"current_score": score},
        output_action={"risk_level": risk_level}
    )

    # Causal Link: If triggered by reconciliation
    recon_ctx = state.get("reconciliation", {})
    if recon_ctx.get("decision_id"):
        db.log_causal_link(recon_ctx["decision_id"], decision_id, "elevates_risk", 
                          "Systematic payment delays detected in reconciliation trigger risk reassessment.")

    return {
        **state,
        "current_agent": "credit",
        "credit": {
            "customer_id": customer_id,
            "credit_score": score,
            "risk_level": risk_level,
            "risk_explanation": reasoning,
            "decision_id": decision_id
        },
        "next_agent": "cash" if risk_level == "high" else END,
        "trigger": "cash_position_refresh" if risk_level == "high" else "done"
    }

def _error(state: FinancialState, msg: str) -> FinancialState:
    return {**state, "next_agent": END, "error": msg, "current_agent": "credit"}
