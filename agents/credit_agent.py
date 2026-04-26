"""
agents/credit_agent.py
Credit & Collection Agent — V2 (Causal-Reasoning-Ready).
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
        # Default to first customer for demo if none specified
        customers = db.select("customers")
        if not customers: return {**state, "next_agent": END}
        customer_id = customers[0]["id"]

    customer = db.get_customer(customer_id)
    if not customer: return {**state, "next_agent": END, "error": "Customer not found"}

    # Deterministic Score (thesis Section 2.7.2)
    score = float(customer.get("credit_score", 50.0))
    risk_level = "high" if score < 40 else "medium" if score < 70 else "low"

    # LLM Reasoning
    system, user = credit_risk_prompt(customer, [], score)
    assessment = qwen_json(system, user)
    reasoning  = assessment.get("reasoning", f"Risk assessed as {risk_level}.")

    # Log Decision (V2)
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
        "next_agent":    END,
        "credit": {
            "customer_id": customer_id,
            "credit_score": score,
            "risk_level": risk_level,
            "risk_explanation": reasoning,
            "decision_id": decision_id
        }
    }
