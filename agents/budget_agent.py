"""
agents/budget_agent.py
Budget Management Agent — V2 (Causal-Reasoning-Ready).
"""

from __future__ import annotations
from datetime import date
from langgraph.graph import END

from agents.state import FinancialState, add_reasoning
from db.supabase_client import db
from utils.llm import qwen_explain

ALERT_THRESHOLD  = 90.0
HARD_STOP_THRESHOLD = 100.0

def budget_node(state: FinancialState) -> FinancialState:
    trigger = state.get("trigger", "budget_review")
    if trigger in ("invoice_post_checks", "budget_review"):
        return _check_budget(state)
    return {**state, "next_agent": END, "current_agent": "budget"}

def _check_budget(state: FinancialState) -> FinancialState:
    budget_ctx  = state.get("budget", {})
    invoice_ctx = state.get("invoice", {})

    dept_id    = budget_ctx.get("department_id") or invoice_ctx.get("department_id") or "engineering"
    period     = budget_ctx.get("period") or _current_period()
    invoice_id = invoice_ctx.get("invoice_id", "system")
    amount     = float(invoice_ctx.get("amount", 0) or 0)

    budget = db.get_budget(dept_id, period)

    if not budget:
        note = f"No budget defined for {dept_id} / {period}."
        decision_id = db.log_agent_decision("budget", "no_budget", "budgets", "none", note)
        return {
            **state,
            "current_agent": "budget",
            "next_agent":    "invoice",
            "budget": { **budget_ctx, "budget_breach": False, "decision_id": decision_id }
        }

    allocated  = float(budget.get("allocated", 0) or 0)
    spent      = float(budget.get("spent", 0) or 0)
    committed  = float(budget.get("committed", 0) or 0)

    total_committed = spent + committed + amount
    utilisation_pct = (total_committed / allocated * 100) if allocated > 0 else 0.0
    breach = utilisation_pct >= ALERT_THRESHOLD

    # XAI Reasoning
    reasoning = f"Utilisation for {dept_id} is {utilisation_pct:.1f}% (${total_committed:,.2f} of ${allocated:,.2f})."
    if breach:
        reasoning += " Threshold breached."

    # Log Decision (V2)
    decision_id = db.log_agent_decision(
        agent="budget",
        decision_type="budget_checked",
        entity_table="budgets",
        entity_id=budget["id"],
        reasoning=reasoning,
        input_state={"allocated": allocated, "spent": spent, "committed": committed, "new_invoice": amount},
        output_action={"utilisation_pct": utilisation_pct, "breach": breach}
    )

    # Causal Link: Invoice validation triggers budget check
    if invoice_ctx.get("decision_id"):
        db.log_causal_link(invoice_ctx["decision_id"], decision_id, "breaches_budget" if breach else "enables_approval", 
                          "Invoice amount increases department budget utilisation.")

    # Write alert if breached
    if breach:
        db.insert("budget_alerts", {
            "budget_id": budget["id"],
            "utilisation_pct": round(utilisation_pct, 2),
            "alert_type": "threshold_breach",
            "message": reasoning,
            "triggered_by_invoice_id": invoice_id if invoice_id != "system" else None
        })

    # Update committed amount
    db.update("budgets", {"id": budget["id"]}, {"committed": round(committed + amount, 2)})

    return {
        **state,
        "current_agent": "budget",
        "next_agent":    "invoice",
        "budget": {
            **budget_ctx,
            "department_id": dept_id,
            "utilisation_pct": round(utilisation_pct, 2),
            "budget_breach": breach,
            "decision_id": decision_id
        }
    }

def _current_period() -> str:
    t = date.today()
    return f"{t.year}-Q{(t.month-1)//3+1}"
