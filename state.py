"""
agents/state.py
Defines the shared FinancialState that flows through the entire LangGraph.

Every agent node reads from and writes to this state.
This is the "shared financial state"
that enables causal cross-domain reasoning between agents.

LangGraph persists this state between node calls, so each agent always
has the full context of what other agents have decided.
"""

from typing import TypedDict, Literal, Any


AgentName = Literal["supervisor", "invoice", "budget", "reconciliation", "credit", "cash"]

AgentStatus = Literal["idle", "running", "done", "error"]


class InvoiceContext(TypedDict, total=False):
    """State populated by the Invoice agent."""
    invoice_id: str
    vendor_name: str
    amount: float
    currency: str
    department: str
    due_date: str
    status: str                  # current workflow status
    extraction_confidence: float
    requires_approval: bool
    approval_reason: str         # Qwen3 explanation of why approval needed


class BudgetContext(TypedDict, total=False):
    """State populated by the Budget agent."""
    department: str
    period: str
    utilisation_pct: float       # 0–100
    remaining_budget: float
    budget_breach: bool          # True if utilisation > threshold
    breach_message: str
    forecast_overrun: bool


class ReconciliationContext(TypedDict, total=False):
    """State populated by the Reconciliation agent."""
    run_id: str
    period: str
    match_rate: float            # 0–100
    unmatched_count: int
    anomalies_detected: list[dict]
    anomaly_summary: str         # Qwen3 natural language summary


class CreditContext(TypedDict, total=False):
    """State populated by the Credit agent."""
    customer_id: str
    credit_score: float          # 0–100
    risk_level: str              # 'low' | 'medium' | 'high'
    days_overdue: int
    collection_stage: str
    risk_explanation: str        # Qwen3 explanation


class CashContext(TypedDict, total=False):
    """State populated by the Cash agent."""
    total_balance: float
    projected_shortfall: bool
    shortfall_amount: float
    shortfall_date: str
    can_approve_payment: bool    # KEY: used by Invoice agent to gate approvals
    liquidity_note: str          # Qwen3 explanation for the decision


class FinancialState(TypedDict, total=False):
    """
    The complete shared state passed through the LangGraph.

    `total=False` means all fields are optional — agents only populate
    the fields they're responsible for.

    Cross-agent causality examples:
      invoice.amount → cash.can_approve_payment
      reconciliation.anomalies → credit.risk_level
      budget.breach → invoice.requires_approval (escalation)
    """

    # Control flow — which agent to call next
    next_agent: AgentName
    current_agent: AgentName

    # The triggering event — what kicked off this graph run
    trigger: str                 # e.g. 'invoice_uploaded', 'daily_reconciliation', 'manual'
    trigger_entity_id: str       # ID of the entity that triggered this run

    # Agent-specific contexts
    invoice: InvoiceContext
    budget: BudgetContext
    reconciliation: ReconciliationContext
    credit: CreditContext
    cash: CashContext

    # XAI: accumulated reasoning traces from all agents in this run
    # Each entry: {"agent": str, "step": str, "reasoning": str}
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
        reasoning_trace=[],
        error=None,
        error_agent=None,
    )


def add_reasoning(state: FinancialState, agent: str, step: str, reasoning: str) -> FinancialState:
    """Append a reasoning trace entry. Called by every agent after an LLM decision."""
    trace = state.get("reasoning_trace", [])
    trace.append({"agent": agent, "step": step, "reasoning": reasoning})
    return {**state, "reasoning_trace": trace}
