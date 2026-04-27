"""
agents/state.py
The shared "brain" of the system. This dict flows through all the agents.
"""

from typing import TypedDict, Literal, Any, List, Dict, Optional
from enum import Enum

AgentName = Literal["supervisor", "invoice", "budget", "reconciliation", "credit", "cash"]
AgentStatus = Literal["idle", "running", "done", "error"]

class TriggerType(str, Enum):
    INVOICE_UPLOADED = "invoice_uploaded"
    INVOICE_POST_CHECKS = "invoice_post_checks"
    CASH_POSITION_REFRESH = "cash_position_refresh"
    RECONCILIATION_REQUESTED = "reconciliation_requested"
    DAILY_RECONCILIATION = "daily_reconciliation"
    MANUAL_RECONCILIATION = "manual_reconciliation"
    CUSTOMER_PAYMENT_CHECK = "customer_payment_check"
    DONE = "done"

class InvoiceContext(TypedDict, total=False):
    """State populated by the Invoice agent."""
    invoice_id: str
    vendor_id: str
    vendor_name: str
    amount: float
    currency: str
    department_id: str
    due_date: str
    status: str
    extraction_confidence: float
    requires_approval: bool
    approval_reason: str
    decision_id: str             # ID from agent_decisions table


class BudgetContext(TypedDict, total=False):
    """State populated by the Budget agent."""
    department_id: str
    period: str
    utilisation_pct: float
    remaining_budget: float
    budget_breach: bool
    breach_message: str
    decision_id: str


class ReconciliationContext(TypedDict, total=False):
    """State populated by the Reconciliation agent."""
    run_id: str
    match_rate: float
    unmatched_count: int
    anomalies_detected: List[Dict[str, Any]]
    anomaly_summary: str
    decision_id: str


class CreditContext(TypedDict, total=False):
    """State populated by the Credit agent."""
    customer_id: str
    credit_score: float
    risk_level: str
    days_overdue: int
    risk_explanation: str
    decision_id: str


class CashContext(TypedDict, total=False):
    """State populated by the Cash agent."""
    total_balance: float
    projected_shortfall: bool
    shortfall_amount: float
    can_approve_payment: bool
    liquidity_note: str
    decision_id: str


class FinancialState(TypedDict, total=False):
    # This is the big one. It holds everything from control flow to agent-specific data.

    # Control flow
    next_agent: AgentName
    current_agent: AgentName

    # The triggering event
    trigger: str                 
    trigger_entity_id: str       

    # Agent-specific contexts
    invoice: InvoiceContext
    budget: BudgetContext
    reconciliation: ReconciliationContext
    credit: CreditContext
    cash: CashContext

    # Causal Graph tracking
    # Mapping of agent name -> last decision ID in this run
    decision_ids: Dict[str, str]

    # XAI: reasoning traces
    reasoning_trace: List[Dict[str, str]]

    # Error handling
    error: Optional[str]
    error_agent: Optional[AgentName]


def initial_state(trigger: str, entity_id: str) -> FinancialState:
    """Create a clean initial state for a new graph run."""
    return FinancialState(
        trigger=trigger,
        trigger_entity_id=entity_id,
        next_agent="supervisor",
        current_agent="supervisor",
        invoice={},
        budget={},
        reconciliation={},
        credit={},
        cash={},
        decision_ids={},
        reasoning_trace=[],
        error=None,
        error_agent=None,
    )


def add_reasoning(state: FinancialState, agent: str, step: str, reasoning: str) -> FinancialState:
    """Append a reasoning trace entry."""
    trace = state.get("reasoning_trace", [])
    trace.append({"agent": agent, "step": step, "reasoning": reasoning})
    # Return a new dict to ensure LangGraph state update
    new_state = state.copy()
    new_state["reasoning_trace"] = trace
    return new_state
