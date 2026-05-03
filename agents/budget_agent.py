"""
agents/budget_agent.py
Budget Agent — keeps an eye on department spending so we don't go over budget.

DOE Layer: Orchestration.
  - invoice_post_checks trigger: fully deterministic (no LLM needed).
  - budget_review trigger: LLM reasoning module generates narrative + recommendation.

Numeric thresholds come from directives/policies.py (BUDGET).
Human-readable rules live in directives/budget_policy.md.
"""

from __future__ import annotations
from datetime import date
from langgraph.graph import END

from agents.state import FinancialState
from db.supabase_client import db
from directives.policies import BUDGET
from utils.agent_modules import AgentPipeline, run_agent_pipeline


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

def budget_node(state: FinancialState) -> FinancialState:
    trigger = state.get("trigger", "budget_review")
    if trigger == "invoice_post_checks":
        return run_agent_pipeline(_INVOICE_CHECK_PIPELINE, state)
    if trigger == "budget_review":
        return run_agent_pipeline(_REVIEW_PIPELINE, state)
    return {**state, "next_agent": END, "current_agent": "budget"}


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE A — invoice_post_checks (deterministic, no LLM)
# ══════════════════════════════════════════════════════════════════════════════

def _inv_perceive(state: FinancialState) -> dict:
    budget_ctx  = state.get("budget", {})
    invoice_ctx = state.get("invoice", {})
    dept_id  = budget_ctx.get("department_id") or invoice_ctx.get("department_id") or "engineering"
    period   = budget_ctx.get("period") or _current_period()
    inv_id   = invoice_ctx.get("invoice_id", "system")
    amount   = float(invoice_ctx.get("amount", 0) or 0)
    budget   = db.get_budget(dept_id, period)
    return {
        "budget_ctx":  budget_ctx,
        "invoice_ctx": invoice_ctx,
        "dept_id":     dept_id,
        "period":      period,
        "inv_id":      inv_id,
        "amount":      amount,
        "budget":      budget,
    }


def _inv_reason(_state, _percept):
    return None  # fully deterministic


def _inv_decide(_state: FinancialState, percept: dict, _llm) -> dict:
    budget = percept["budget"]
    if not budget:
        return {
            "no_budget": True,
            "breach": False, "hard_stop": False,
            "utilisation_pct": 0.0, "remaining": 0.0,
            "next_agent": "invoice",
        }

    allocated = float(budget.get("allocated", 0) or 0)
    spent     = float(budget.get("spent", 0) or 0)
    committed = float(budget.get("committed", 0) or 0)
    amount    = percept["amount"]

    total_committed = spent + committed + amount
    prior_pct       = (spent + committed) / allocated * 100 if allocated > 0 else 0.0
    util_pct        = (total_committed / allocated * 100)   if allocated > 0 else 0.0
    breach          = util_pct >= BUDGET.alert_threshold
    hard_stop       = util_pct >= BUDGET.hard_stop_threshold
    remaining       = max(0.0, allocated - total_committed)

    return {
        "no_budget":       False,
        "allocated":       allocated,
        "spent":           spent,
        "committed":       committed,
        "total_committed": total_committed,
        "prior_pct":       prior_pct,
        "utilisation_pct": util_pct,
        "breach":          breach,
        "hard_stop":       hard_stop,
        "remaining":       remaining,
        "next_agent":      "invoice",
    }


def _inv_explain(state: FinancialState, percept: dict, verdict: dict) -> str:
    dept_id    = percept["dept_id"]
    inv_id     = percept["inv_id"]
    invoice_ctx = percept["invoice_ctx"]
    budget     = percept["budget"]

    if verdict.get("no_budget"):
        note = f"No budget defined for {dept_id} / {percept['period']}."
        return db.log_agent_decision(
            agent="budget", decision_type="no_budget",
            entity_table="budgets", entity_id="none",
            technical_explanation=note,
            business_explanation="Could not find a budget allocation for this department.",
            causal_explanation="Bypasses budget breach checks and proceeds to invoice approval.",
        )

    util = verdict["utilisation_pct"]
    prior = verdict["prior_pct"]
    alloc = verdict["allocated"]
    total = verdict["total_committed"]
    rem   = verdict["remaining"]
    breach = verdict["breach"]
    hard_stop = verdict["hard_stop"]
    amount = percept["amount"]

    technical = (
        f"Department '{dept_id}' utilisation rises from {prior:.1f}% to {util:.1f}% "
        f"if approved (${total:,.2f} of ${alloc:,.2f}; remaining ${rem:,.2f})."
    )
    business = (
        f"This invoice would consume the department's remaining headroom and "
        f"{'exceed' if hard_stop else 'breach'} the "
        f"{BUDGET.hard_stop_threshold:.0f}% hard-stop threshold."
        if hard_stop else
        f"This invoice would breach the {BUDGET.alert_threshold:.0f}% alert threshold."
        if breach else
        f"This invoice keeps the department below the {BUDGET.alert_threshold:.0f}% alert threshold."
    )
    causal = (
        f"Hard-stop (≥{BUDGET.hard_stop_threshold:.0f}%) forces rejection; "
        f"alert (≥{BUDGET.alert_threshold:.0f}%) escalates to senior manager; "
        f"otherwise continues toward auto-approval."
    )

    entity_table = "invoices" if inv_id != "system" else "budgets"
    entity_id    = inv_id if inv_id != "system" else budget["id"]

    decision_id = db.log_agent_decision(
        agent="budget", decision_type="budget_checked",
        entity_table=entity_table, entity_id=entity_id,
        technical_explanation=technical,
        business_explanation=business,
        causal_explanation=causal,
        input_state={
            "allocated": alloc, "spent": verdict["spent"],
            "committed": verdict["committed"],
            "new_invoice": amount, "budget_id": budget["id"],
            "department_id": dept_id, "period": percept["period"],
        },
        output_action={
            "utilisation_pct": round(util, 2),
            "remaining": round(rem, 2),
            "breach": breach, "hard_stop": hard_stop,
        },
    )

    if invoice_ctx.get("decision_id"):
        db.log_causal_link(
            invoice_ctx["decision_id"], decision_id,
            "breaches_budget" if breach else "enables_approval",
            "Invoice amount increases department budget utilisation.",
        )
    return decision_id


def _inv_execute(_state: FinancialState, percept: dict, verdict: dict) -> None:
    if verdict.get("no_budget"):
        return
    budget = percept["budget"]
    breach = verdict["breach"]
    committed = verdict["committed"]
    amount = percept["amount"]

    if breach:
        dept_id = percept["dept_id"]
        util    = verdict["utilisation_pct"]
        inv_id  = percept["inv_id"]
        db.insert("budget_alerts", {
            "budget_id":      budget["id"],
            "utilisation_pct": round(util, 2),
            "alert_type":     "threshold_breach",
            "message": (
                f"Department '{dept_id}' utilisation at {util:.1f}% "
                f"after invoice ${percept['amount']:,.2f}."
            ),
            "triggered_by_invoice_id": inv_id if inv_id != "system" else None,
        })

    db.update("budgets", {"id": budget["id"]},
              {"committed": round(committed + amount, 2)})


def _inv_communicate(state: FinancialState, percept: dict, verdict: dict) -> FinancialState:
    budget_ctx = percept["budget_ctx"]
    dept_id    = percept["dept_id"]
    did        = verdict.get("decision_id", "")

    trace = state.get("reasoning_trace", []) + [{
        "agent": "budget",
        "step":  "Checked Budget",
        "technical_explanation": (
            f"Dept '{dept_id}' utilisation: {verdict.get('utilisation_pct', 0):.1f}%."
        ),
        "business_explanation": (
            "Hard stop." if verdict.get("hard_stop") else
            "Alert threshold breached." if verdict.get("breach") else
            "Within budget."
        ),
        "causal_explanation": "Feeds invoice approval routing.",
    }]

    return {
        **state,
        "current_agent": "budget",
        "next_agent":    verdict["next_agent"],
        "reasoning_trace": trace,
        "budget": {
            **budget_ctx,
            "department_id":   dept_id,
            "utilisation_pct": round(verdict.get("utilisation_pct", 0), 2),
            "budget_breach":   verdict.get("breach", False),
            "hard_stop":       verdict.get("hard_stop", False),
            "decision_id":     did,
        },
    }


_INVOICE_CHECK_PIPELINE = AgentPipeline(
    name="budget_invoice_check",
    perception=_inv_perceive,
    reasoning=_inv_reason,
    decision=_inv_decide,
    explanation=_inv_explain,
    execution=_inv_execute,
    communication=_inv_communicate,
)


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE B — budget_review (LLM reasoning: proactive scan of all depts)
# ══════════════════════════════════════════════════════════════════════════════

def _rev_perceive(state: FinancialState) -> dict:
    budget_ctx = state.get("budget", {})
    dept_id    = budget_ctx.get("department_id") or None
    period     = budget_ctx.get("period") or _current_period()

    from config import get_supabase
    supabase = get_supabase()
    query = supabase.table("budgets").select("*, departments(name)").eq("period", period)
    if dept_id:
        query = query.eq("department_id", dept_id)
    budgets = query.execute().data

    return {"budget_ctx": budget_ctx, "period": period, "dept_id": dept_id, "budgets": budgets}


def _rev_reason(_state: FinancialState, percept: dict):
    """LLM generates narrative summary + recommendations for at-risk departments."""
    from utils.directives import load_directive
    from utils.llm import qwen_json

    budgets = percept["budgets"]
    if not budgets:
        return None

    at_risk = []
    for b in budgets:
        alloc   = float(b.get("allocated") or 0)
        spent   = float(b.get("spent") or 0)
        committed = float(b.get("committed") or 0)
        util = (spent + committed) / alloc * 100 if alloc > 0 else 0
        if util >= BUDGET.auto_approve_below:
            at_risk.append({
                "department": b.get("department_id"),
                "utilisation_pct": round(util, 1),
                "allocated": alloc,
                "spent": spent,
                "committed": committed,
                "remaining": round(max(0, alloc - spent - committed), 2),
            })

    if not at_risk:
        return {"at_risk": [], "narrative": "All departments within budget thresholds.", "recommendations": []}

    directive = load_directive("budget")
    return qwen_json(
        f"## Policy\n{directive}\nYou are a CFO assistant. Respond with valid JSON only.",
        f"Period: {percept['period']}. At-risk departments (utilisation ≥ {BUDGET.auto_approve_below:.0f}%): "
        f"{at_risk}. "
        f"Provide JSON: narrative (2-sentence summary), "
        f"recommendations (list of action strings per department), at_risk (list back as-is).",
    )


def _rev_decide(_state: FinancialState, percept: dict, llm_out) -> dict:
    budgets = percept["budgets"]
    alerts_fired = 0
    for b in budgets:
        alloc = float(b.get("allocated") or 0)
        spent = float(b.get("spent") or 0)
        committed = float(b.get("committed") or 0)
        util = (spent + committed) / alloc * 100 if alloc > 0 else 0
        if util >= BUDGET.alert_threshold:
            alerts_fired += 1

    return {
        "budgets_scanned": len(budgets),
        "alerts_fired":    alerts_fired,
        "llm_summary":     llm_out or {},
        "next_agent":      END,
    }


def _rev_explain(state: FinancialState, percept: dict, verdict: dict) -> str:
    budgets = percept["budgets"]
    period  = percept["period"]
    llm     = verdict.get("llm_summary") or {}

    from config import get_supabase
    first_id = budgets[0]["id"] if budgets else "none"

    technical = (
        f"Scanned {verdict['budgets_scanned']} budgets for period {period}. "
        f"{verdict['alerts_fired']} departments at/above alert threshold."
    )
    business = llm.get("narrative", "Budget review completed.")
    causal   = "Proactive review — no invoice trigger. Alerts emitted for at-risk departments."

    return db.log_agent_decision(
        agent="budget", decision_type="budget_review",
        entity_table="budgets", entity_id=first_id,
        technical_explanation=technical,
        business_explanation=business,
        causal_explanation=causal,
        input_state={"period": period, "dept_id": percept["dept_id"]},
        output_action={"budgets_scanned": verdict["budgets_scanned"],
                       "alerts_fired": verdict["alerts_fired"]},
    )


def _rev_execute(_state: FinancialState, percept: dict, verdict: dict) -> None:
    """Fire budget_alerts for any department at or above the alert threshold."""
    period = percept["period"]
    for b in percept["budgets"]:
        alloc = float(b.get("allocated") or 0)
        spent = float(b.get("spent") or 0)
        committed = float(b.get("committed") or 0)
        util = (spent + committed) / alloc * 100 if alloc > 0 else 0
        if util >= BUDGET.alert_threshold:
            dept = b.get("department_id", "unknown")
            db.insert("budget_alerts", {
                "budget_id":      b["id"],
                "utilisation_pct": round(util, 2),
                "alert_type":     "proactive_review",
                "message": (
                    f"[Budget Review {period}] Dept '{dept}' at {util:.1f}% utilisation."
                ),
                "triggered_by_invoice_id": None,
            })


def _rev_communicate(state: FinancialState, percept: dict, verdict: dict) -> FinancialState:
    llm = verdict.get("llm_summary") or {}
    trace = state.get("reasoning_trace", []) + [{
        "agent": "budget",
        "step":  "Budget Review",
        "technical_explanation": (
            f"Scanned {verdict['budgets_scanned']} budgets; "
            f"{verdict['alerts_fired']} alerts fired."
        ),
        "business_explanation": llm.get("narrative", "Review complete."),
        "causal_explanation":   "Proactive review — no invoice trigger.",
    }]
    return {
        **state,
        "current_agent":   "budget",
        "next_agent":      verdict["next_agent"],
        "reasoning_trace": trace,
        "budget": {
            **percept["budget_ctx"],
            "period":          percept["period"],
            "budgets_scanned": verdict["budgets_scanned"],
            "alerts_fired":    verdict["alerts_fired"],
            "llm_summary":     llm,
        },
    }


_REVIEW_PIPELINE = AgentPipeline(
    name="budget_review",
    perception=_rev_perceive,
    reasoning=_rev_reason,
    decision=_rev_decide,
    explanation=_rev_explain,
    execution=_rev_execute,
    communication=_rev_communicate,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _current_period() -> str:
    t = date.today()
    return f"{t.year}-Q{(t.month-1)//3+1}"
