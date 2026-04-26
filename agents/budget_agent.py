"""
agents/budget_agent.py
Budget Management Agent.

Called during Scenario 1 (invoice approval chain) after the Cash agent.
Also called independently for scheduled budget reviews.

Responsibilities:
  1. Check department budget utilisation for the invoice's department
  2. Detect threshold breaches (default: 90% alert, 100% hard stop)
  3. Compute simple moving-average forecast for the period
  4. Write budget_alerts if breached
  5. Set state.budget fields for invoice_agent to use in routing decision

Scenario 3 trigger: budget breach → invoice approval escalated to senior manager.
This happens automatically because invoice_agent reads budget_ctx.budget_breach.
"""

from __future__ import annotations
from datetime import date
from langgraph.graph import END

from agents.state import FinancialState, add_reasoning
from db.supabase_client import db
from utils.llm import qwen_explain


ALERT_THRESHOLD  = 90.0   # % utilisation → alert
HARD_STOP_THRESHOLD = 100.0


def budget_node(state: FinancialState) -> FinancialState:
    trigger = state.get("trigger", "budget_review")

    if trigger in ("invoice_post_checks", "budget_review"):
        return _check_budget(state)

    return {**state, "next_agent": END, "current_agent": "budget",
            "error": f"budget_node: unknown trigger '{trigger}'"}


def _check_budget(state: FinancialState) -> FinancialState:
    budget_ctx  = state.get("budget", {})
    invoice_ctx = state.get("invoice", {})

    department = budget_ctx.get("department") or invoice_ctx.get("department") or "general"
    period     = budget_ctx.get("period") or _current_period()
    invoice_id = invoice_ctx.get("invoice_id", "system")
    amount     = float(invoice_ctx.get("amount", 0) or 0)

    # Load budget row for this department + period
    budget = db.get_budget(department, period)

    if not budget:
        # No budget defined — log warning, allow invoice to proceed
        note = f"No budget defined for {department} / {period}. Invoice allowed to proceed."
        db.log_agent_event("budget", "no_budget_found", invoice_id,
                           {"department": department, "period": period}, reasoning=note)
        state = add_reasoning(state, "budget", "check", note)
        return {
            **state,
            "current_agent": "budget",
            "next_agent":    "invoice",      # return to invoice for final routing
            "trigger":       "invoice_post_checks",
            "budget": {
                **budget_ctx,
                "department":      department,
                "period":          period,
                "utilisation_pct": 0.0,
                "remaining_budget": 0.0,
                "budget_breach":   False,
                "forecast_overrun": False,
            },
        }

    allocated  = float(budget.get("allocated", 0) or 0)
    spent      = float(budget.get("spent", 0) or 0)
    committed  = float(budget.get("committed", 0) or 0)
    threshold  = float(budget.get("alert_threshold", ALERT_THRESHOLD) or ALERT_THRESHOLD)

    # Utilisation including this invoice as a new commitment
    total_committed = spent + committed + amount
    utilisation_pct = (total_committed / allocated * 100) if allocated > 0 else 0.0
    remaining       = max(0.0, allocated - total_committed)

    # Breach detection
    breach      = utilisation_pct >= threshold
    hard_stop   = utilisation_pct >= HARD_STOP_THRESHOLD

    # Simple moving-average forecast (3-month lookback)
    forecast_overrun = _forecast_overrun(department, period, allocated)

    # Build XAI explanation via Qwen3
    context = (
        f"Department: {department}, Period: {period}\n"
        f"Allocated: ${allocated:,.2f}, Spent: ${spent:,.2f}, "
        f"Committed: ${committed:,.2f}, New invoice: ${amount:,.2f}\n"
        f"Utilisation after this invoice: {utilisation_pct:.1f}%\n"
        f"Alert threshold: {threshold:.0f}%"
    )
    if breach:
        reasoning = qwen_explain(
            context,
            f"Explain in 2 sentences why this budget alert was triggered and what finance should do.",
        )
    else:
        reasoning = (
            f"Budget utilisation for {department} is {utilisation_pct:.1f}% "
            f"(${total_committed:,.2f} of ${allocated:,.2f} allocated). "
            f"Remaining: ${remaining:,.2f}. No breach."
        )

    # Write alert to DB if breached
    if breach:
        alert_type = "threshold_breach" if not hard_stop else "hard_stop"
        db.insert("budget_alerts", {
            "budget_id":       budget["id"],
            "department":      department,
            "period":          period,
            "utilisation_pct": round(utilisation_pct, 2),
            "alert_type":      alert_type,
            "message":         reasoning,
        })

    # Update committed amount on the budget row
    db.update("budgets", {"id": budget["id"]}, {
        "committed": round(committed + amount, 2),
    })

    db.log_agent_event(
        agent="budget",
        event_type="budget_checked",
        entity_id=invoice_id,
        details={
            "department":      department,
            "period":          period,
            "allocated":       round(allocated, 2),
            "spent":           round(spent, 2),
            "committed_after": round(total_committed, 2),
            "utilisation_pct": round(utilisation_pct, 2),
            "breach":          breach,
            "hard_stop":       hard_stop,
            "forecast_overrun": forecast_overrun,
        },
        reasoning=reasoning,
    )

    state = add_reasoning(
        state, "budget", "utilisation_check",
        f"{department} budget: {utilisation_pct:.1f}% utilised "
        f"({'BREACH' if breach else 'OK'}). {reasoning}",
    )

    return {
        **state,
        "current_agent": "budget",
        "next_agent":    "invoice",      # return to invoice for final routing
        "trigger":       "invoice_post_checks",
        "budget": {
            **budget_ctx,
            "department":       department,
            "period":           period,
            "utilisation_pct":  round(utilisation_pct, 2),
            "remaining_budget": round(remaining, 2),
            "budget_breach":    breach,
            "forecast_overrun": forecast_overrun,
        },
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _forecast_overrun(department: str, period: str, allocated: float) -> bool:
    """
    Simple 3-month moving average forecast.
    Returns True if projected spend for this period will exceed allocation.
    """
    supabase = __import__("config", fromlist=["get_supabase"]).get_supabase()

    # Get last 3 periods' actual spend for this department
    rows = (
        supabase.table("budgets")
        .select("spent, period")
        .eq("department", department)
        .neq("period", period)
        .order("period", desc=True)
        .limit(3)
        .execute()
        .data
    )
    if not rows:
        return False

    avg_spend = sum(float(r.get("spent", 0) or 0) for r in rows) / len(rows)
    return avg_spend > allocated


def _current_period() -> str:
    today   = date.today()
    quarter = (today.month - 1) // 3 + 1
    return f"{today.year}-Q{quarter}"
