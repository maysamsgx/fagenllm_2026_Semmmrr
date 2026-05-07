"""
Unit tests for every deterministic calculation in FAgentLLM.
No DB, no LLM calls — pure math verified against known inputs.
"""
import pytest
from directives.policies import CASH, CREDIT, BUDGET, INVOICE


# ── Cash Agent: C_(t+1) formula ───────────────────────────────────────────────

def _cash_decision(balance, inflows, outflows, invoice_amount):
    """Mirrors _decide() in cash_agent.py."""
    projected_next = balance + inflows - outflows
    balance_after  = projected_next - invoice_amount
    can_approve    = balance_after > CASH.minimum_balance
    headroom       = balance_after - CASH.minimum_balance
    return can_approve, round(balance_after, 2), round(headroom, 2)


def test_cash_approves_when_sufficient():
    can_approve, balance_after, headroom = _cash_decision(
        balance=500_000, inflows=50_000, outflows=20_000, invoice_amount=10_000
    )
    assert can_approve is True
    assert balance_after == 520_000.0
    assert headroom > 0


def test_cash_rejects_when_shortfall():
    # After payment, balance would drop below the minimum_balance floor
    can_approve, balance_after, _ = _cash_decision(
        balance=15_000, inflows=0, outflows=0, invoice_amount=10_000
    )
    assert can_approve is False
    assert balance_after == 5_000.0


def test_cash_exact_minimum_is_rejected():
    # balance_after == minimum_balance → strictly-greater check fails
    can_approve, balance_after, _ = _cash_decision(
        balance=CASH.minimum_balance, inflows=0, outflows=0, invoice_amount=0
    )
    assert can_approve is False
    assert balance_after == CASH.minimum_balance


def test_cash_one_cent_above_minimum_approves():
    can_approve, _, _ = _cash_decision(
        balance=CASH.minimum_balance + 0.01, inflows=0, outflows=0, invoice_amount=0
    )
    assert can_approve is True


# ── Credit Agent: risk scoring formula ───────────────────────────────────────

def _credit_score(delay_days, outstanding, recon_penalty=0.0):
    """Mirrors the formula in credit_agent.py _assess_customer()."""
    f1 = float(delay_days)
    f2 = float(outstanding) / 1000.0
    raw = CREDIT.base_score - (CREDIT.delay_weight * f1) - (CREDIT.outstanding_weight * f2) - recon_penalty
    return max(0.0, min(100.0, raw))


def _risk_level(score):
    if score < CREDIT.high_risk_below:   return "high"
    if score < CREDIT.medium_risk_below: return "medium"
    return "low"


def test_credit_ecem_low_risk():
    score = _credit_score(delay_days=2.0, outstanding=1000.0)
    assert score == pytest.approx(94.5)
    assert _risk_level(score) == "low"


def test_credit_misem_medium_risk():
    score = _credit_score(delay_days=15.0, outstanding=10000.0)
    assert score == pytest.approx(55.0)
    assert _risk_level(score) == "medium"


def test_credit_anas_high_risk_without_recon():
    score = _credit_score(delay_days=25.0, outstanding=12000.0)
    assert score == pytest.approx(32.0)
    assert _risk_level(score) == "high"


def test_credit_anas_recon_penalty_deepens_risk():
    # Recon penalty of 20 pts should drive score even lower, not change the bucket
    score_base  = _credit_score(delay_days=25.0, outstanding=12000.0)
    score_recon = _credit_score(delay_days=25.0, outstanding=12000.0, recon_penalty=20.0)
    assert score_recon == pytest.approx(12.0)
    assert score_recon < score_base
    assert _risk_level(score_recon) == "high"


def test_credit_score_clamps_at_zero():
    score = _credit_score(delay_days=200.0, outstanding=100_000.0)
    assert score == 0.0


def test_credit_score_clamps_at_hundred():
    score = _credit_score(delay_days=0.0, outstanding=0.0)
    assert score == 100.0


# ── Budget Agent: utilisation & threshold logic ───────────────────────────────

def _budget_decision(allocated, spent, committed, new_invoice):
    """Mirrors _inv_decide() in budget_agent.py."""
    total_committed = spent + committed + new_invoice
    util_pct        = (total_committed / allocated * 100) if allocated > 0 else 0.0
    breach          = util_pct >= BUDGET.alert_threshold
    hard_stop       = util_pct >= BUDGET.hard_stop_threshold
    remaining       = max(0.0, allocated - total_committed)
    return round(util_pct, 2), breach, hard_stop, round(remaining, 2)


def test_budget_within_limits():
    util, breach, hard_stop, remaining = _budget_decision(
        allocated=100_000, spent=40_000, committed=10_000, new_invoice=5_000
    )
    assert util == 55.0
    assert breach is False
    assert hard_stop is False
    assert remaining == 45_000.0


def test_budget_breach_at_alert_threshold():
    # Exactly 95% → breach = True, hard_stop = False
    util, breach, hard_stop, _ = _budget_decision(
        allocated=100_000, spent=90_000, committed=0, new_invoice=5_000
    )
    assert util == 95.0
    assert breach is True
    assert hard_stop is False


def test_budget_hard_stop_at_100_percent():
    util, breach, hard_stop, remaining = _budget_decision(
        allocated=100_000, spent=95_000, committed=0, new_invoice=5_000
    )
    assert util == 100.0
    assert hard_stop is True
    assert remaining == 0.0


def test_budget_marketing_breach_scenario():
    # The seeded scenario: $95k invoice against $100k marketing budget
    util, breach, hard_stop, _ = _budget_decision(
        allocated=100_000, spent=0, committed=0, new_invoice=95_000
    )
    assert util == 95.0
    assert breach is True
    assert hard_stop is False  # 95% triggers alert, not hard-stop


def test_budget_remaining_never_negative():
    _, _, _, remaining = _budget_decision(
        allocated=100_000, spent=90_000, committed=20_000, new_invoice=5_000
    )
    assert remaining == 0.0  # clamped at 0, not -15_000
