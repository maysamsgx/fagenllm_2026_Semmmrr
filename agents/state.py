"""
agents/state.py
Defines the shared FinancialState that flows through the entire LangGraph.
(V2 - Causal-Reasoning-Ready)
"""

from typing import TypedDict, Literal, Any


AgentName = Literal["supervisor", "invoice", "budget", "reconciliation", "credit", "cash"]
AgentStatus = Literal["idle", "running", "done", "error"]


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
    anomalies_detected: list[dict]
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
    """
    The complete shared state passed through the LangGraph.
    V2 adds decision_ids to support the causal relationship graph (Schema v2).
    """

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
    decision_ids: dict[str, str]

    # XAI: reasoning traces
    reasoning_trace: list[dict[str, str]]

    # Error handling
    error: str | None
    error_agent: AgentName | None


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
    return {**state, "reasoning_trace": trace}
