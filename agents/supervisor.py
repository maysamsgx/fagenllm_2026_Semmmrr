from typing import Any
from agents.state import FinancialState
from langgraph.graph import END

def router_node(state: FinancialState) -> Any:
    # The supervisor is like the traffic cop — it looks at the trigger and decides which agent starts first.
    trigger = state.get("trigger")
    
    if trigger == "invoice_uploaded":
        return {**state, "next_agent": "invoice", "current_agent": "supervisor"}
    
    if trigger == "invoice_post_checks":
        # Usually starts with cash or budget check before returning to invoice
        return {**state, "next_agent": "cash", "current_agent": "supervisor"}
    
    if trigger in ("reconciliation_requested", "daily_reconciliation", "manual_reconciliation"):
        return {**state, "next_agent": "reconciliation", "current_agent": "supervisor"}

    if trigger == "budget_review":
        return {**state, "next_agent": "budget", "current_agent": "supervisor"}

    if trigger == "cash_position_refresh":
        return {**state, "next_agent": "cash", "current_agent": "supervisor"}

    if trigger == "customer_payment_check":
        return {**state, "next_agent": "credit", "current_agent": "supervisor"}

    # Default to ending if unknown trigger
    return {**state, "next_agent": END, "current_agent": "supervisor"}
