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
from datetime import date
from langgraph.graph import END

from agents.state import FinancialState
from db.supabase_client import db
from directives.policies import CREDIT
from utils.directives import inject_directive


def calculate_penalty(risk_level: str | None, delay_days: float) -> float:
    """
    Deterministic penalty calculation based on historical risk and current delays.
    Used to adjust the base credit score before final assessment.
    """
    if not risk_level or delay_days < 0:
        return 0.0
    
    # Penalties escalate based on existing risk tier
    if risk_level == "high":
        return 20.0
    if risk_level == "medium" and delay_days > 5:
        return 10.0
    
    return 0.0


def credit_node(state: FinancialState) -> FinancialState:
    trigger = state.get("trigger", "customer_payment_check")
    if trigger in ("customer_payment_check", "daily_reconciliation"):
        return _assess_customer(state)
    return {**state, "next_agent": END, "current_agent": "credit"}


def _assess_customer(state: FinancialState) -> FinancialState:
    credit_ctx  = state.get("credit", {})
    recon_ctx   = state.get("reconciliation", {})
    customer_id = credit_ctx.get("customer_id", "")

    if not customer_id:
        return _error(state, "No customer_id specified for credit assessment")

    customer = db.get_customer(customer_id)
    if not customer:
        return {**state, "next_agent": END, "error": "Customer not found"}

    from utils.contracts import DecisionOutput
    from utils.llm import qwen_structured

    # ── Deterministic scoring (Decision module) ───────────────────────────────
    f1 = float(customer.get("payment_delay_avg", 5.0))
    f2 = float(customer.get("total_outstanding", 5000.0)) / 1000.0
    
    # V3: Add reconciliation penalty (f3) if systematic issues were found for this customer
    f3 = 0.0
    recon_summary = None
    if recon_ctx.get("decision_id") and customer_id in recon_ctx.get("anomalous_customer_ids", []):
        # We apply the penalty logic based on current state
        f3 = calculate_penalty(customer.get("risk_level"), f1)
        # Ensure a minimum 20pt penalty if it's systematic
        f3 = max(f3, 20.0) 
        recon_summary = recon_ctx.get("anomaly_summary")

    score = max(0.0, min(100.0,
        CREDIT.base_score + (-CREDIT.delay_weight * f1) + (-CREDIT.outstanding_weight * f2) - f3
    ))
    risk_level = (
        "high"   if score < CREDIT.high_risk_below   else
        "medium" if score < CREDIT.medium_risk_below else
        "low"
    )

    # ── Adaptive feedback: write score back so future runs read real data ────
    db.update("customers", {"id": customer_id}, {
        "credit_score": round(score, 2),
        "risk_level":   risk_level,
    })

    # ── LLM reasoning (Orchestration — explanation only) ─────────────────────
    # Fetch REAL payment history from receivables to give the LLM accurate behavioral data
    from utils.prompts import credit_risk_prompt as _crp
    from db.supabase_client import db as _db
    
    payment_history = []
    try:
        receivables = _db.select("receivables", {"customer_id": customer_id})
        for r in receivables[-5:]:  # Last 5 receivables
            due = r.get("due_date")
            status = r.get("status")
            days_late = 0
            if due and status not in ("paid",):
                from datetime import date as _d
                try:
                    days_late = max(0, (_d.today() - _d.fromisoformat(due)).days)
                except Exception:
                    pass
            payment_history.append({
                "invoice_id": r.get("invoice_id", "?"),
                "due_date": due,
                "paid_date": "PAID" if status == "paid" else None,
                "days_late": days_late,
                "amount": r.get("amount"),
                "collection_stage": r.get("collection_stage"),
            })
    except Exception:
        pass  # graceful degradation

    base_system, user = _crp(customer, payment_history, score, recon_summary, f1, f2, f3)
    system = inject_directive(base_system, "credit")
    assessment = qwen_structured(system, user, DecisionOutput)

    input_state = {
        "current_score": score,
        "interpretable_model": {
            "formula": "R = min(100, max(0, base - delay_weight×f1 - outstanding_weight×f2 - recon_penalty))",
            "base_score": CREDIT.base_score,
            "weights": {
                "delay_weight":       CREDIT.delay_weight,
                "outstanding_weight": CREDIT.outstanding_weight,
                "recon_penalty_flat": 20.0 if f3 > 0 else 0.0,
            },
            "factors": {"f1_delay_days": f1, "f2_outstanding_k": f2, "f3_recon_issue": f3 > 0},
        }
    }

    # ── Explanation: log decision ────────────────────────────────────────────
    decision_id = db.log_agent_decision(
        agent="credit",
        decision_type="risk_assessed",
        entity_table="customers",
        entity_id=customer_id,
        technical_explanation=assessment.technical_explanation,
        business_explanation=assessment.business_explanation,
        causal_explanation=assessment.causal_explanation,
        input_state=input_state,
        output_action={"risk_level": risk_level, "decision": assessment.decision, "score": score},
        confidence=assessment.confidence
    )

    # V3 Causal Integrity: Link this assessment back to the reconciliation anomaly
    if recon_ctx.get("decision_id"):
        link_explanation = f"Systematic reconciliation anomalies for {customer.get('name')} triggered forensic risk reassessment."
        if f3 > 0:
            link_explanation = f"Cross-domain anomaly signal detected: 20pt risk penalty applied to {customer.get('name')} due to systematic settlement delays."
        
        db.log_causal_link(
            recon_ctx["decision_id"], 
            decision_id, 
            "elevates_risk",
            link_explanation
        )

    # ── Execution: autonomous policy enforcement ─────────────────────────────
    if risk_level == "high":
        # Slash credit limit by 50% immediately to prevent further exposure (Agentic Action)
        new_limit = float(customer.get("credit_limit", 10000.0)) * 0.5
        db.update("customers", {"id": customer_id}, {"credit_limit": round(new_limit, 2)})
        
        # Advance collection stages for all open invoices
        _advance_collection_stages(customer_id)

    # ── Communication: Append to reasoning trace for UI visibility ──────────
    trace = state.get("reasoning_trace", []) + [{
        "agent":                 "credit",
        "step":                  "Forensic Risk Assessment",
        "event_type":            "risk_assessed",
        "technical_explanation": assessment.technical_explanation,
        "business_explanation":  assessment.business_explanation,
        "causal_explanation":    assessment.causal_explanation,
        "risk_level":            risk_level,
        "confidence":            assessment.confidence
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
        # Step 6 (thesis): always hand off to Cash for AR forecast update when triggered
        # by reconciliation. For invoice checks, only hand off if high risk.
        "next_agent": "cash" if recon_ctx.get("decision_id") or risk_level == "high" else END,
        "trigger":    "ar_forecast_update" if recon_ctx.get("decision_id") else (
                      "cash_position_refresh" if risk_level == "high" else "done"
        ),
    }


def _advance_collection_stages(customer_id: str) -> None:
    """
    Advance the collection_stage on all open receivables for a high-risk customer.
    Pipeline: none → reminder → notice → escalated → legal
    Also stamps last_reminder_at so finance can track follow-up cadence.
    """
    import logging
    _STAGE_NEXT = {
        "none":      "reminder",
        "reminder":  "notice",
        "notice":    "escalated",
        "escalated": "legal",
        "legal":     "legal",   # terminal stage — no further escalation
    }
    try:
        open_receivables = [
            r for r in db.select("receivables", {"customer_id": customer_id})
            if r.get("status") == "open"
        ]
        for r in open_receivables:
            current_stage = r.get("collection_stage") or "none"
            next_stage    = _STAGE_NEXT.get(current_stage, "reminder")
            db.update("receivables", {"id": r["id"]}, {
                "collection_stage":  next_stage,
                "last_reminder_at":  date.today().isoformat(),
            })
    except Exception as exc:
        logging.getLogger("fagentllm").warning(
            "Collection stage advancement failed for customer %s: %s", customer_id, exc
        )


def _error(state: FinancialState, msg: str) -> FinancialState:
    return {**state, "next_agent": END, "error": msg, "current_agent": "credit"}
