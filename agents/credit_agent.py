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

    from utils.contracts import DecisionOutput
    from utils.llm import qwen_structured

    f1 = float(customer.get("payment_delay_avg", 5.0))
    f2 = float(customer.get("total_outstanding", 5000.0)) / 1000.0
    w1, w2 = -2.0, -1.5
    base_score = 100.0
    score = max(0.0, min(100.0, base_score + (w1 * f1) + (w2 * f2)))
    
    risk_level = "high" if score < 40 else "medium" if score < 70 else "low"
    
    # LLM Reasoning via Structured Output
    system, user = credit_risk_prompt(customer, [], score)
    assessment = qwen_structured(system, user, DecisionOutput)

    input_state = {
        "current_score": score,
        "interpretable_model": {
            "formula": "R = min(100, max(0, base_score + (w1 * f1) + (w2 * f2)))",
            "base_score": base_score,
            "weights": {"w1_delay": w1, "w2_debt_k": w2},
            "factors": {"f1_delay": f1, "f2_debt_k": f2}
        }
    }

    # Logging the risk assessment so the group can see the reasoning in the dashboard.
    decision_id = db.log_agent_decision(
        agent="credit",
        decision_type="risk_assessed",
        entity_table="customers",
        entity_id=customer_id,
        technical_explanation=assessment.technical_explanation,
        business_explanation=assessment.business_explanation,
        causal_explanation=assessment.causal_explanation,
        input_state=input_state,
        output_action={"risk_level": risk_level, "decision": assessment.decision},
        confidence=assessment.confidence
    )

    # Causal Link: If triggered by reconciliation
    recon_ctx = state.get("reconciliation", {})
    if recon_ctx.get("decision_id"):
        db.log_causal_link(recon_ctx["decision_id"], decision_id, "elevates_risk", 
                          "Systematic payment delays detected in reconciliation trigger risk reassessment.")

    trace = state.get("reasoning_trace", []) + [{
        "agent": "credit",
        "step": "Assessed risk",
        "technical_explanation": assessment.technical_explanation,
        "business_explanation": assessment.business_explanation,
        "causal_explanation": assessment.causal_explanation
    }]

    return {
        **state,
        "current_agent": "credit",
        "credit": {
            "customer_id": customer_id,
            "credit_score": score,
            "risk_level": risk_level,
            "decision_id": decision_id
        },
        "reasoning_trace": trace,
        "next_agent": "cash" if risk_level == "high" else END,
        "trigger": "cash_position_refresh" if risk_level == "high" else "done"
    }

def _error(state: FinancialState, msg: str) -> FinancialState:
    return {**state, "next_agent": END, "error": msg, "current_agent": "credit"}
