from typing import Any
from agents.state import FinancialState
from langgraph.graph import END

def router_node(state: FinancialState) -> Any:
    # The supervisor is like the traffic cop — it looks at the trigger and decides which agent starts first.
    trigger = state.get("trigger")
    
    if trigger == "invoice_uploaded":
        return {**state, "next_agent": "invoice", "current_agent": "supervisor"}
    
    if trigger == "reconciliation_requested":
        return {**state, "next_agent": "reconciliation", "current_agent": "supervisor"}

    # Default to ending if unknown trigger
    return {**state, "next_agent": END, "current_agent": "supervisor"}
