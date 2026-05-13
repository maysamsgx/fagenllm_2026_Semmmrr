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
        
    entity_id = state.get("trigger_entity_id", "governance_gate")

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
    
    # ── Update State ────────────────────────────────────────────────────────
    new_trace = trace + [{
        "agent": "governance",
        "step": "Compliance Audit",
        "technical_explanation": audit.technical_explanation,
        "business_explanation": audit.business_explanation,
        "causal_explanation": audit.causal_explanation
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
