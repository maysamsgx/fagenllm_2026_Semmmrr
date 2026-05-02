"""
directives/policies.py
Single source of truth for all numeric business-rule constants.

This is the machine-readable half of the Directive layer in the DOE framework.
The human-readable half lives in the companion *_policy.md files in this folder.

To change a threshold without touching agent code, update the value here and
restart the server. Non-engineers can propose changes by editing the .md files,
which then get reviewed and reflected here.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetPolicy:
    alert_threshold:     float = 95.0   # % utilisation — escalate to senior manager
    hard_stop_threshold: float = 100.0  # % utilisation — mandatory rejection, no override
    auto_approve_below:  float = 90.0   # % utilisation — eligible for auto-approval path


@dataclass(frozen=True)
class CashPolicy:
    minimum_balance:    float = 10_000.0  # operating reserve floor ($)
    forecast_days:      int   = 7         # default look-ahead window
    wma_weights:        tuple = (0.5, 0.3, 0.2)  # most-recent → oldest weekly weight
    near_window_days:   int   = 7         # receivables counted at full weight
    far_window_days:    int   = 30        # receivables counted at discount factor
    far_discount:       float = 0.7       # probability factor for 8–30 day receivables


@dataclass(frozen=True)
class InvoicePolicy:
    auto_approve_max: float = 5_000.0   # < this amount can auto-approve (if checks pass)
    manager_max:      float = 50_000.0  # 5k–50k → manager; > 50k → senior manager


@dataclass(frozen=True)
class CreditPolicy:
    delay_weight:       float = 2.0   # score penalty per day of average payment delay
    outstanding_weight: float = 1.5   # score penalty per $1,000 outstanding
    base_score:         float = 100.0
    high_risk_below:    int   = 40    # score < 40 → high risk
    medium_risk_below:  int   = 70    # score 40–69 → medium risk; ≥70 → low


@dataclass(frozen=True)
class ReconciliationPolicy:
    match_threshold:     float = 0.8   # cosine similarity — below this = unmatched
    systematic_keywords: tuple = ("systematic", "pattern", "recurring", "repeated")
    max_fetch:           int   = 100   # max unmatched rows per reconciliation run


# Module-level singletons — import these in agent files
BUDGET  = BudgetPolicy()
CASH    = CashPolicy()
INVOICE = InvoicePolicy()
CREDIT  = CreditPolicy()
RECON   = ReconciliationPolicy()
