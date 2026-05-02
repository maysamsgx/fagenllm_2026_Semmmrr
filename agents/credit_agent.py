"""
agents/credit_agent.py
Credit Agent — checks if our customers are actually paying on time
and flags them if they're becoming a risk.

DOE Layer: Orchestration.
  - Decision is deterministic (formula from directives/policies.py CREDIT)
  - LLM generates the explanation only (Execution layer stays clean)
  - Directive injected into LLM prompt via utils/directives.inject_directive
"""

from __future__ import annotations
from langgraph.graph import END

from agents.state import FinancialState
from db.supabase_client import db
from directives.policies import CREDIT
from utils.directives import inject_directive


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
    if not customer:
        return {**state, "next_agent": END, "error": "Customer not found"}

    from utils.contracts import DecisionOutput
    from utils.llm import qwen_structured
    from utils.prompts import credit_risk_prompt

    # ── Deterministic scoring (Decision module) ───────────────────────────────
    f1 = float(customer.get("payment_delay_avg", 5.0))
    f2 = float(customer.get("total_outstanding", 5000.0)) / 1000.0
    score = max(0.0, min(100.0,
        CREDIT.base_score + (-CREDIT.delay_weight * f1) + (-CREDIT.outstanding_weight * f2)
    ))
    risk_level = (
        "high"   if score < CREDIT.high_risk_below   else
        "medium" if score < CREDIT.medium_risk_below else
        "low"
    )

    # ── LLM reasoning (Orchestration — explanation only) ─────────────────────
    # Inject the credit directive so the LLM explains within policy boundaries.
    from utils.prompts import credit_risk_prompt as _crp
    base_system, user = _crp(customer, [], score)
    system = inject_directive(base_system, "credit")
    assessment = qwen_structured(system, user, DecisionOutput)

    input_state = {
        "current_score": score,
        "interpretable_model": {
            "formula": "R = min(100, max(0, base - delay_weight×f1 - outstanding_weight×f2))",
            "base_score": CREDIT.base_score,
            "weights": {
                "delay_weight":       CREDIT.delay_weight,
                "outstanding_weight": CREDIT.outstanding_weight,
            },
            "factors": {"f1_delay_days": f1, "f2_outstanding_k": f2},
        }
    }

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

    recon_ctx = state.get("reconciliation", {})
    if recon_ctx.get("decision_id"):
        db.log_causal_link(
            recon_ctx["decision_id"], decision_id, "elevates_risk",
            "Systematic payment delays detected in reconciliation trigger risk reassessment."
        )

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
            "customer_id":  customer_id,
            "credit_score": score,
            "risk_level":   risk_level,
            "decision_id":  decision_id,
        },
        "reasoning_trace": trace,
        "next_agent": "cash" if risk_level == "high" else END,
        "trigger":    "cash_position_refresh" if risk_level == "high" else "done",
    }


def _error(state: FinancialState, msg: str) -> FinancialState:
    return {**state, "next_agent": END, "error": msg, "current_agent": "credit"}
