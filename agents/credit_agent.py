"""
agents/credit_agent.py
Credit & Collection Agent — Scenario 2 downstream handler.

Risk formula (thesis Section 2.7.2):
  R = Σ(w_i × f_i)  where:
    f_1 = payment_delay_norm   (normalised avg days late, weight 0.40)
    f_2 = outstanding_ratio    (outstanding / credit_limit,  weight 0.35)
    f_3 = dispute_frequency    (disputes per invoice,        weight 0.25)
  R ∈ [0, 100] — higher = higher risk

Qwen3 generates the XAI explanation AFTER the score is computed deterministically.
The LLM never overrides the numeric score — it only explains it in natural language.

Collection stage progression:
  none → reminder → formal_notice → escalated → legal_referral
  (progresses automatically based on days_overdue + risk_level)
"""

from __future__ import annotations
from datetime import date
from langgraph.graph import END

from agents.state import FinancialState, add_reasoning
from db.supabase_client import db
from utils.llm import qwen_json
from utils.prompts import credit_risk_prompt

# Risk formula weights (must sum to 1.0)
W_PAYMENT_DELAY  = 0.40
W_OUTSTANDING    = 0.35
W_DISPUTE_FREQ   = 0.25

# Risk thresholds
RISK_HIGH_THRESHOLD   = 65.0
RISK_MEDIUM_THRESHOLD = 40.0

# Collection stage escalation rules (days_overdue → minimum stage)
COLLECTION_RULES = [
    (0,   "none"),
    (7,   "reminder"),
    (30,  "formal_notice"),
    (60,  "escalated"),
    (90,  "legal_referral"),
]


def credit_node(state: FinancialState) -> FinancialState:
    trigger = state.get("trigger", "customer_payment_check")
    if trigger in ("customer_payment_check", "daily_reconciliation"):
        return _assess_customer(state)
    return {**state, "next_agent": END, "current_agent": "credit",
            "error": f"credit_node: unknown trigger '{trigger}'"}


def _assess_customer(state: FinancialState) -> FinancialState:
    credit_ctx  = state.get("credit", {})
    customer_id = credit_ctx.get("customer_id", "")

    # If no specific customer, assess all high-risk customers
    if not customer_id:
        return _assess_all_high_risk(state)

    customer = db.get_customer(customer_id)
    if not customer:
        return {**state, "current_agent": "credit", "next_agent": END,
                "error": f"Customer {customer_id} not found"}

    return _assess_one(state, customer)


def _assess_one(state: FinancialState, customer: dict) -> FinancialState:
    customer_id = customer["id"]

    # ── Step 1: Compute R = Σ(w_i × f_i) deterministically ──────────────────
    credit_limit    = float(customer.get("credit_limit", 1) or 1)
    outstanding     = float(customer.get("total_outstanding", 0) or 0)
    payment_delay   = float(customer.get("payment_delay_avg", 0) or 0)
    dispute_freq    = float(customer.get("dispute_frequency", 0) or 0)

    # Normalise each factor to [0, 1]
    f1 = min(payment_delay / 90.0, 1.0)          # 90 days max delay
    f2 = min(outstanding / credit_limit, 1.0)     # outstanding ratio
    f3 = min(dispute_freq / 0.5, 1.0)             # 50% dispute rate = max

    R = (W_PAYMENT_DELAY * f1 + W_OUTSTANDING * f2 + W_DISPUTE_FREQ * f3) * 100

    # Risk level classification
    if R >= RISK_HIGH_THRESHOLD:
        risk_level = "high"
    elif R >= RISK_MEDIUM_THRESHOLD:
        risk_level = "medium"
    else:
        risk_level = "low"

    # ── Step 2: Get payment history for Qwen3 context ────────────────────────
    receivables = db.select("receivables", {"customer_id": customer_id})
    payment_history = [
        {
            "invoice_id":   r.get("id"),
            "due_date":     r.get("due_date"),
            "paid_date":    None,   # not tracked in prototype — receivables table
            "days_late":    max(0, (date.today() - date.fromisoformat(
                                str(r.get("due_date", date.today()))
                            )).days) if r.get("status") == "open" else 0,
        }
        for r in receivables[-10:]  # last 10 receivables
    ]

    # ── Step 3: Qwen3 XAI explanation ─────────────────────────────────────────
    system, user = credit_risk_prompt(customer, payment_history, R)
    assessment   = qwen_json(system, user)

    qwen_risk_level    = assessment.get("risk_level", risk_level)
    recommended_action = assessment.get("recommended_action", "monitor")
    reasoning          = assessment.get("reasoning", f"Risk score R={R:.1f}")
    collection_urgency = assessment.get("collection_urgency", "low")
    key_factors        = assessment.get("key_risk_factors", [])

    # Qwen3 can escalate risk level but not downgrade beyond one tier
    # (prevents LLM from overriding a formula-driven high-risk to low)
    final_risk = _merge_risk(risk_level, qwen_risk_level)

    # ── Step 4: Determine collection stage ────────────────────────────────────
    max_overdue = 0
    for r in receivables:
        if r.get("status") == "open":
            try:
                due    = date.fromisoformat(str(r["due_date"]))
                overdue = max(0, (date.today() - due).days)
                max_overdue = max(max_overdue, overdue)
            except Exception:
                pass

    new_stage = _collection_stage(max_overdue, final_risk)

    # ── Step 5: Update customer + receivables in DB ───────────────────────────
    db.update_credit_score(customer_id, round(R, 2), final_risk)

    # Update collection stage on open receivables
    _supabase = __import__("config", fromlist=["get_supabase"]).get_supabase()
    open_receivables = [r for r in receivables if r.get("status") == "open"]
    for r in open_receivables:
        try:
            due     = date.fromisoformat(str(r["due_date"]))
            overdue = max(0, (date.today() - due).days)
            stage   = _collection_stage(overdue, final_risk)
            _supabase.table("receivables").update(
                {"collection_stage": stage}
            ).eq("id", r["id"]).execute()
        except Exception:
            pass

    # ── Step 6: XAI audit log ─────────────────────────────────────────────────
    db.log_agent_event(
        agent="credit",
        event_type="risk_assessed",
        entity_id=customer_id,
        details={
            "customer_name":     customer.get("name"),
            "risk_score_R":      round(R, 2),
            "f1_payment_delay":  round(f1, 4),
            "f2_outstanding":    round(f2, 4),
            "f3_dispute_freq":   round(f3, 4),
            "risk_level":        final_risk,
            "collection_stage":  new_stage,
            "max_days_overdue":  max_overdue,
            "recommended":       recommended_action,
            "key_factors":       key_factors,
        },
        reasoning=reasoning,
    )

    state = add_reasoning(
        state, "credit", "risk_assessment",
        f"Customer '{customer.get('name')}': R = {W_PAYMENT_DELAY}×{f1:.2f} + "
        f"{W_OUTSTANDING}×{f2:.2f} + {W_DISPUTE_FREQ}×{f3:.2f} = {R:.1f}/100 "
        f"→ {final_risk.upper()} risk. Stage: {new_stage}. {reasoning}",
    )

    return {
        **state,
        "current_agent": "credit",
        "next_agent":    END,
        "credit": {
            "customer_id":    customer_id,
            "credit_score":   round(R, 2),
            "risk_level":     final_risk,
            "days_overdue":   max_overdue,
            "collection_stage": new_stage,
            "risk_explanation": reasoning,
        },
    }


def _assess_all_high_risk(state: FinancialState) -> FinancialState:
    """Batch mode: assess all customers with risk_level='high' or score > 60."""
    customers = db.select("customers")
    high_risk  = [c for c in customers
                  if c.get("risk_level") == "high"
                  or float(c.get("credit_score", 0) or 0) > 60]

    if not high_risk:
        return {**state, "current_agent": "credit", "next_agent": END}

    # Assess the riskiest customer and log the rest
    riskiest = max(high_risk, key=lambda c: float(c.get("credit_score", 0) or 0))
    state    = {**state, "credit": {**state.get("credit", {}),
                                     "customer_id": riskiest["id"]}}
    return _assess_one(state, riskiest)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _collection_stage(days_overdue: int, risk_level: str) -> str:
    """
    Determine collection stage from days overdue + risk level.
    High-risk customers escalate one stage faster.
    """
    effective_days = days_overdue
    if risk_level == "high":
        effective_days = int(days_overdue * 1.5)   # accelerate escalation

    stage = "none"
    for threshold, s in COLLECTION_RULES:
        if effective_days >= threshold:
            stage = s
    return stage


def _merge_risk(formula_risk: str, qwen_risk: str) -> str:
    """
    Merge deterministic formula risk with Qwen3 assessment.
    Rule: Qwen3 can escalate by one tier but cannot downgrade by more than one tier.
    This protects against hallucinated downgrades on genuinely high-risk customers.
    """
    order = {"low": 0, "medium": 1, "high": 2}
    f = order.get(formula_risk, 1)
    q = order.get(qwen_risk, 1)
    # Allow ±1 tier influence from Qwen3
    merged = max(f - 1, min(f + 1, q))
    reverse = {0: "low", 1: "medium", 2: "high"}
    return reverse[max(0, min(2, merged))]
