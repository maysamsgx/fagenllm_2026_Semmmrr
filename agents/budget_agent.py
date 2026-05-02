"""
agents/budget_agent.py
Budget Agent — keeps an eye on department spending so we don't go over budget.

DOE Layer: Orchestration (deterministic — no LLM).
All numeric thresholds come from directives/policies.py (BUDGET).
Human-readable rules live in directives/budget_policy.md.
"""

from __future__ import annotations
from datetime import date
from langgraph.graph import END

from agents.state import FinancialState, add_reasoning
from db.supabase_client import db
from directives.policies import BUDGET


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
        decision_id = db.log_agent_decision(
            agent="budget", decision_type="no_budget", entity_table="budgets", entity_id="none",
            technical_explanation=note,
            business_explanation="Could not find a budget allocation for this department.",
            causal_explanation="Bypasses budget breach checks and proceeds to invoice approval.",
        )
        return {
            **state,
            "current_agent": "budget",
            "next_agent":    "invoice",
            "budget": { **budget_ctx, "budget_breach": False, "hard_stop": False, "decision_id": decision_id }
        }

    allocated  = float(budget.get("allocated", 0) or 0)
    spent      = float(budget.get("spent", 0) or 0)
    committed  = float(budget.get("committed", 0) or 0)

    total_committed = spent + committed + amount
    prior_pct       = (spent + committed) / allocated * 100 if allocated > 0 else 0.0
    utilisation_pct = (total_committed / allocated * 100) if allocated > 0 else 0.0
    breach          = utilisation_pct >= BUDGET.alert_threshold
    hard_stop       = utilisation_pct >= BUDGET.hard_stop_threshold
    remaining       = max(0.0, allocated - total_committed)

    technical_explanation = (
        f"Department '{dept_id}' utilisation rises from {prior_pct:.1f}% to {utilisation_pct:.1f}% "
        f"if approved (${total_committed:,.2f} of ${allocated:,.2f}; remaining ${remaining:,.2f})."
    )
    business_explanation = (
        f"This invoice would consume the department's remaining headroom and "
        f"{'exceed' if hard_stop else 'breach'} the "
        f"{BUDGET.hard_stop_threshold:.0f}% hard-stop threshold."
        if hard_stop else
        f"This invoice would consume the department's remaining headroom and breach "
        f"the {BUDGET.alert_threshold:.0f}% alert threshold."
        if breach else
        f"This invoice keeps the department comfortably below the {BUDGET.alert_threshold:.0f}% alert threshold."
    )
    causal_explanation = (
        f"A hard-stop breach (≥{BUDGET.hard_stop_threshold:.0f}%) forces rejection; "
        f"an alert breach (≥{BUDGET.alert_threshold:.0f}%) escalates to senior-manager review; "
        f"otherwise the invoice continues toward auto-approval."
    )

    entity_table, entity_id = ("invoices", invoice_id) if invoice_id != "system" else ("budgets", budget["id"])
    decision_id = db.log_agent_decision(
        agent="budget",
        decision_type="budget_checked",
        entity_table=entity_table,
        entity_id=entity_id,
        technical_explanation=technical_explanation,
        business_explanation=business_explanation,
        causal_explanation=causal_explanation,
        input_state={
            "allocated": allocated, "spent": spent, "committed": committed,
            "new_invoice": amount, "budget_id": budget["id"],
            "department_id": dept_id, "period": period,
        },
        output_action={
            "utilisation_pct": round(utilisation_pct, 2),
            "remaining": round(remaining, 2),
            "breach": breach, "hard_stop": hard_stop,
        }
    )

    if invoice_ctx.get("decision_id"):
        db.log_causal_link(
            invoice_ctx["decision_id"], decision_id,
            "breaches_budget" if breach else "enables_approval",
            "Invoice amount increases department budget utilisation."
        )

    if breach:
        db.insert("budget_alerts", {
            "budget_id": budget["id"],
            "utilisation_pct": round(utilisation_pct, 2),
            "alert_type": "threshold_breach",
            "message": technical_explanation,
            "triggered_by_invoice_id": invoice_id if invoice_id != "system" else None
        })

    db.update("budgets", {"id": budget["id"]}, {"committed": round(committed + amount, 2)})

    trace = state.get("reasoning_trace", []) + [{
        "agent": "budget",
        "step": "Checked Budget",
        "technical_explanation": technical_explanation,
        "business_explanation": business_explanation,
        "causal_explanation": causal_explanation
    }]

    return {
        **state,
        "current_agent": "budget",
        "next_agent":    "invoice",
        "reasoning_trace": trace,
        "budget": {
            **budget_ctx,
            "department_id":   dept_id,
            "utilisation_pct": round(utilisation_pct, 2),
            "budget_breach":   breach,
            "hard_stop":       hard_stop,
            "decision_id":     decision_id,
        }
    }


def _current_period() -> str:
    t = date.today()
    return f"{t.year}-Q{(t.month-1)//3+1}"
