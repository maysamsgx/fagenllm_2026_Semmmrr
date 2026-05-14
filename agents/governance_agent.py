"""
agents/governance_agent.py
Governance Auditor Agent — The final "Safety Gate" of the system.
It reviews all decisions in the current run and cross-checks them against fiscal policy.
"""

from __future__ import annotations
import json
from langgraph.graph import END

from agents.state import FinancialState
from db.supabase_client import db
from utils.directives import inject_directive
from utils.llm import qwen_structured
from utils.contracts import GovernanceOutput

def governance_node(state: FinancialState) -> FinancialState:
    """
    Final governance pass to ensure cross-agent consistency (Objective 10).
    """
    # ── Perception: Collect all decisions from this run ──────────────────────
    decision_ids = state.get("decision_ids", {})
    trace = state.get("reasoning_trace", [])
    
    if not decision_ids and not trace:
        return {**state, "next_agent": END, "current_agent": "governance"}

    from utils.prompts import governance_audit_prompt
    
    # Construct a summary of what happened
    summary = "SUMMARY OF DECISIONS IN THIS RUN:\n"
    for step in trace:
        summary += f"- [{step['agent'].upper()}] {step['step']}: {step['business_explanation']}\n"

    system, user = governance_audit_prompt(summary)
    
    system = inject_directive(system, "governance")
    audit = qwen_structured(system, user, GovernanceOutput)
    
    # Determine the entity to link to based on the trigger
    trigger = state.get("trigger", "")
    entity_table = "system"
    if "invoice" in trigger:
        entity_table = "invoices"
    elif "reconciliation" in trigger:
        entity_table = "reconciliation_reports"
    elif "credit" in trigger or "payment" in trigger:
        entity_table = "customers"
        
    entity_id = state.get("trigger_entity_id")
    
    # Thesis V4: Ensure entity_id is a UUID if possible
    if entity_table == "reconciliation_reports" and state.get("reconciliation", {}).get("report_id"):
        entity_id = state["reconciliation"]["report_id"]
    
    # If it's still not a UUID (like a string trigger), use a dummy or skip
    import uuid
    def is_uuid(val):
        try:
            uuid.UUID(str(val))
            return True
        except:
            return False

    if not is_uuid(entity_id):
        # Default to a system-wide "Zero ID" for general audits
        entity_id = "00000000-0000-0000-0000-000000000000"

    # ── Explanation: Log the final audit decision ───────────────────────────
    audit_id = db.log_agent_decision(
        agent="governance",
        decision_type="compliance_audit",
        entity_table=entity_table,
        entity_id=entity_id,
        technical_explanation=audit.technical_explanation,
        business_explanation=audit.business_explanation,
        causal_explanation=audit.causal_explanation,
        input_state={"decision_ids": decision_ids, "trace_length": len(trace)},
        output_action={
            "compliance_score": audit.compliance_score,
            "status": audit.decision,
            "is_audit_safe": audit.is_audit_safe
        },
        confidence=audit.confidence
    )
    
    # ── Execution: Cross-Agent Conflict Detection (V4) ──────────────────────
    findings = audit.findings or []
    
    # 1. Budget vs Invoice: Hard stop but approval logic?
    budget_ctx = state.get("budget", {})
    invoice_ctx = state.get("invoice", {})
    if budget_ctx.get("hard_stop") and invoice_ctx.get("status") in ("approved", "awaiting_approval"):
        msg = f"CONFLICT: Budget issued a HARD STOP for {budget_ctx.get('department_id')}, but Invoice agent proceeded with approval logic."
        findings.append(msg)
        db.log_governance_violation(
            severity="high", category="policy_breach", agent="governance",
            details=msg, rule="BUDGET_HARD_STOP_ADHERENCE",
            entity_table="invoices", entity_id=invoice_ctx.get("invoice_id"),
            decision_id=audit_id
        )

    # 2. Credit vs Invoice: High risk customer but large invoice approved?
    credit_ctx = state.get("credit", {})
    if credit_ctx.get("risk_level") == "high" and invoice_ctx.get("status") == "approved" and invoice_ctx.get("amount", 0) > 5000:
        msg = f"CONFLICT: High-risk customer {credit_ctx.get('customer_id')} had a large invoice (${invoice_ctx.get('amount')}) auto-approved."
        findings.append(msg)
        db.log_governance_violation(
            severity="medium", category="risk_mismatch", agent="governance",
            details=msg, rule="HIGH_RISK_EXPOSURE_CONTROL",
            entity_table="invoices", entity_id=invoice_ctx.get("invoice_id"),
            decision_id=audit_id
        )

    # ── Update State ────────────────────────────────────────────────────────
    new_trace = trace + [{
        "agent": "governance",
        "step": "Compliance Audit",
        "technical_explanation": audit.technical_explanation,
        "business_explanation": audit.business_explanation,
        "causal_explanation": audit.causal_explanation,
        "findings": findings
    }]
    
    return {
        **state,
        "current_agent": "governance",
        "next_agent": END,
        "governance": {
            "compliance_score": audit.compliance_score,
            "status": audit.decision,
            "findings": audit.findings,
            "is_audit_safe": audit.is_audit_safe,
            "decision_id": audit_id
        },
        "reasoning_trace": new_trace
    }
