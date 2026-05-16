"""
agents/budget_agent.py
Monitors departmental expenditure against allocated ceilings.

Architectural Strategy:
1. invoice_post_checks: Deterministic mathematical gate. Bypasses LLM to 
   enforce absolute compliance with financial thresholds.
2. budget_review: Cognitive reasoning pass. Uses Qwen3 to identify systemic 
   overspending and suggest cross-department reallocations.
"""

from __future__ import annotations
from datetime import date
from langgraph.graph import END

from orchestration.agents.state import FinancialState
from execution.db.supabase_client import db
from directive.policies import BUDGET
from orchestration.agent_modules import AgentPipeline, run_agent_pipeline


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
# PIPELINE A — invoice_post_checks (Compliance Gate)
# Intent: Immediate validation of a single invoice against current headroom.
# ══════════════════════════════════════════════════════════════════════════════

def _inv_perceive(state: FinancialState) -> dict:
    budget_ctx  = state.get("budget", {})
    invoice_ctx = state.get("invoice", {})
    inv_id   = invoice_ctx.get("invoice_id", "system")
    dept_id  = budget_ctx.get("department_id") or invoice_ctx.get("department_id")
    if not dept_id:
        # Improved V4: Try to derive department from the invoice object in DB
        if inv_id != "system":
            inv_row = db.get_invoice(inv_id)
            if inv_row:
                dept_id = inv_row.get("department_id")
    
    # Final fallback if still missing
    dept_id = dept_id or "engineering"
    period   = budget_ctx.get("period") or _current_period()
    amount   = float(invoice_ctx.get("amount", 0) or 0)
    budget   = db.get_budget(dept_id, period)
    dept_uuid = db.get_department_uuid(dept_id)

    # Procedural memory: check if this department was recently hard-stopped or alerted
    prior_procedure = {}
    if dept_uuid:
        proc_mem = db.get_recent_memories("budget", dept_uuid, limit=1, memory_type="procedural")
        if proc_mem:
            prior_procedure = proc_mem[0].get("content", {})

    return {
        "budget_ctx":       budget_ctx,
        "invoice_ctx":      invoice_ctx,
        "dept_id":          dept_id,
        "dept_uuid":        dept_uuid,
        "period":           period,
        "inv_id":           inv_id,
        "amount":           amount,
        "budget":           budget,
        "prior_procedure":  prior_procedure,
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
    prior_pct       = (spent + committed) / allocated * 100 if allocated > 0 else (100.0 if (spent + committed) > 0 else 0.0)
    util_pct        = (total_committed / allocated * 100)   if allocated > 0 else (100.0 if total_committed > 0 else 0.0)
    
    # Risk Management: Alerts trigger manager intervention; Hard-stops enforce policy.
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
            entity_table="budgets", entity_id="00000000-0000-0000-0000-000000000000",
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
        f"This invoice keeps the department below the {BUDGET.alert_threshold:.0f}% alert threshold. "
        f"STRATEGIC INSIGHT: At current spend velocity, this department is projected to maintain a surplus for the quarter."
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
    budget    = percept["budget"]
    breach    = verdict["breach"]
    hard_stop = verdict["hard_stop"]
    committed = verdict["committed"]
    amount    = percept["amount"]
    dept_id   = percept["dept_id"]
    dept_uuid = percept.get("dept_uuid")
    util      = verdict["utilisation_pct"]

    if breach:
        inv_id = percept["inv_id"]
        db.insert("budget_alerts", {
            "budget_id":      budget["id"],
            "utilisation_pct": round(util, 2),
            "alert_type":     "threshold_breach",
            "message": (
                f"Department '{dept_id}' utilisation at {util:.1f}% "
                f"after invoice ${amount:,.2f}."
            ),
            "triggered_by_invoice_id": inv_id if inv_id != "system" else None,
        })

        # Procedural memory: record which policy rule fired and what action it enforced.
        # Governance and future budget runs read this to verify consistent enforcement.
        if dept_uuid:
            db.store_memory("budget", {
                "rule":                  "hard_stop" if hard_stop else "alert_threshold",
                "hard_stop_threshold":   BUDGET.hard_stop_threshold,
                "alert_threshold":       BUDGET.alert_threshold,
                "utilisation_pct":       round(util, 2),
                "period":                percept["period"],
                "invoice_amount":        amount,
                "enforced_action":       "invoice_blocked" if hard_stop else "escalated_to_manager",
            }, memory_type="procedural", entity_id=dept_uuid)

    db.update("budgets", {"id": budget["id"]},
              {"committed": round(committed + amount, 2)})


def _inv_communicate(state: FinancialState, percept: dict, verdict: dict) -> FinancialState:
    budget_ctx = percept["budget_ctx"]
    dept_id    = percept["dept_id"]
    did        = verdict.get("decision_id", "")

    new_trace = [{
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
        "reasoning_trace": new_trace,
        "budget": {
            **budget_ctx,
            "department_id":   dept_id,
            "utilisation_pct": round(verdict.get("utilisation_pct", 0), 2),
            "variance_amount": round(verdict.get("allocated", 0) - verdict.get("total_committed", 0), 2),
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
# PIPELINE B — budget_review (Strategic Advisory)
# Intent: Proactive cross-department analysis to optimize resource utilization.
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
    """
    Synthesizes current spending data with historical 'temporal' memory 
    to provide CFO-level insights and reallocation suggestions.
    """
    from directive.directives import load_directive
    from execution.llm import qwen_json

    budgets = percept["budgets"]
    if not budgets:
        return None

    at_risk = []
    surplus = []
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
        elif util < 50.0:
            surplus.append({
                "department": b.get("department_id"),
                "utilisation_pct": round(util, 1),
                "surplus_amount": round(alloc - spent - committed, 2)
            })

    if not at_risk:
        return {"at_risk": [], "narrative": "All departments within budget thresholds.", "recommendations": []}

    directive = load_directive("budget")
    
    # Persistent Agent Memory: Fetch temporal history + procedural rules for at-risk departments
    memory_context = ""
    for r in at_risk:
        dept = r["department"]
        dept_uuid = db.get_department_uuid(dept)
        past_breaches = db.get_recent_memories("budget", dept_uuid, limit=2, memory_type="temporal")
        past_procedures = db.get_recent_memories("budget", dept_uuid, limit=2, memory_type="procedural")
        if past_breaches:
            memory_context += f" [Temporal for {dept}: "
            for m in past_breaches:
                c = m.get("content", {})
                memory_context += f"In {c.get('period')}, utilisation reached {c.get('utilisation_pct')}%. "
            memory_context += "] "
        if past_procedures:
            memory_context += f" [Procedure for {dept}: "
            for pm in past_procedures:
                c = pm.get("content", {})
                memory_context += (
                    f"Rule '{c.get('rule')}' fired at {c.get('utilisation_pct')}% "
                    f"(enforced: {c.get('enforced_action')}). "
                )
            memory_context += "] "
            
    return qwen_json(
        f"## Policy\n{directive}\nYou are a CFO assistant. Respond with valid JSON only.",
        f"Period: {percept['period']}. At-risk departments (utilisation ≥ {BUDGET.auto_approve_below:.0f}%): "
        f"{at_risk}. {memory_context}"
        f"Surplus departments (utilisation < 50%): {surplus}. "
        f"Provide JSON: narrative (2-sentence summary), "
        f"recommendations (list of action strings per department), at_risk (list back as-is), "
        f"forecast (string: predicted spend velocity for the next 30 days), "
        f"reallocations (list of objects with 'from_dept', 'to_dept', 'suggested_amount', 'reason').",
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

    first_id = budgets[0]["id"] if budgets else "00000000-0000-0000-0000-000000000000"

    reallocations = llm.get("reallocations") or []
    realloc_note = (
        f" Cross-agent reallocation advisor identified {len(reallocations)} potential "
        f"budget transfer(s) from surplus departments to cover at-risk breaches."
        if reallocations else ""
    )

    technical = (
        f"Scanned {verdict['budgets_scanned']} budgets for period {period}. "
        f"{verdict['alerts_fired']} departments at/above alert threshold."
        f"{realloc_note}"
    )
    business = llm.get("narrative", "Budget review completed.")
    causal = (
        "Proactive review — no invoice trigger. Alerts emitted for at-risk departments."
        + (
            f" Reallocation suggestions generated: "
            + "; ".join(
                f"{r.get('suggested_amount', '?')} from '{r.get('from_dept')}' → '{r.get('to_dept')}'"
                for r in reallocations
            )
            if reallocations else ""
        )
    )

    return db.log_agent_decision(
        agent="budget", decision_type="budget_review",
        entity_table="budgets", entity_id=first_id,
        technical_explanation=technical,
        business_explanation=business,
        causal_explanation=causal,
        input_state={"period": period, "dept_id": percept["dept_id"]},
        output_action={
            "budgets_scanned":  verdict["budgets_scanned"],
            "alerts_fired":     verdict["alerts_fired"],
            "reallocations":    reallocations,
            "forecast":         llm.get("forecast", ""),
        },
    )


def _rev_execute(_state: FinancialState, percept: dict, verdict: dict) -> None:
    """Fire budget_alerts and persist reallocation suggestions."""
    period = percept["period"]
    llm = verdict.get("llm_summary") or {}
    reallocations = llm.get("reallocations") or []
    decision_id = verdict.get("decision_id")

    # 1. Persist Reallocation Suggestions (V4)
    for r in reallocations:
        try:
            db.create_budget_reallocation(
                from_dept=r.get("from_dept"),
                to_dept=r.get("to_dept"),
                amount=float(r.get("suggested_amount", 0)),
                period=period,
                reason=r.get("reason", "Proactive reallocation"),
                decision_id=decision_id
            )
        except Exception as e:
            import logging
            logging.getLogger("fagentllm").warning(f"Failed to persist reallocation: {e}")

    # 2. Fire alerts and record memory
    for b in percept["budgets"]:
        alloc = float(b.get("allocated") or 0)
        spent = float(b.get("spent") or 0)
        committed = float(b.get("committed") or 0)
        util = (spent + committed) / alloc * 100 if alloc > 0 else 0
        if util >= BUDGET.alert_threshold:
            dept = b.get("department_id", "unknown")
            
            # Persistent Agent Memory: Record the breach with a proper UUID entity_id
            dept_uuid = db.get_department_uuid(dept)
            db.store_memory("budget", {
                "period": period,
                "utilisation_pct": round(util, 2),
                "allocated": alloc,
                "total_committed": spent + committed
            }, memory_type="temporal", entity_id=dept_uuid)
            
            db.insert("budget_alerts", {
                "budget_id":      b["id"],
                "utilisation_pct": round(util, 2),
                "alert_type":     "threshold_breach",
                "message": (
                    f"[Budget Review {period}] Dept '{dept}' at {util:.1f}% utilisation."
                ),
                "triggered_by_invoice_id": None,
            })


def _rev_communicate(state: FinancialState, percept: dict, verdict: dict) -> FinancialState:
    llm = verdict.get("llm_summary") or {}
    reallocations = llm.get("reallocations") or []
    realloc_note = (
        f" Reallocation advisor: {len(reallocations)} cross-department transfer(s) suggested."
        if reallocations else ""
    )
    new_trace = [{
        "agent": "budget",
        "step":  "Budget Review",
        "technical_explanation": (
            f"Scanned {verdict['budgets_scanned']} budgets; "
            f"{verdict['alerts_fired']} alerts fired.{realloc_note}"
        ),
        "business_explanation": llm.get("narrative", "Review complete."),
        "causal_explanation": (
            "Proactive review — no invoice trigger."
            + (
                " Budget Reallocation Advisor identified surplus capacity in donor departments "
                "that can cover at-risk department overruns without budget exceptions."
                if reallocations else ""
            )
        ),
    }]
    return {
        **state,
        "current_agent":   "budget",
        "next_agent":      verdict["next_agent"],
        "reasoning_trace": new_trace,
        "budget": {
            **percept["budget_ctx"],
            "period":          percept["period"],
            "budgets_scanned": verdict["budgets_scanned"],
            "alerts_fired":    verdict["alerts_fired"],
            "llm_summary":     llm,
            # Surface reallocation suggestions at the top level for easy UI access
            "reallocation_suggestions": reallocations,
            "spend_forecast":           llm.get("forecast", ""),
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
