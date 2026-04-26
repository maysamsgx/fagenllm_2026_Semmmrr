
from agents.state import FinancialState, AgentName
from langgraph.graph import END

def supervisor_node(state: FinancialState) -> FinancialState:
    """
    Supervisor node that routes the initial trigger.
    """
    trigger = state.get("trigger")
    
    if trigger == "invoice_uploaded":
        return {**state, "next_agent": "invoice", "current_agent": "supervisor"}
    
    # Default to ending if unknown trigger
    return {**state, "next_agent": END, "current_agent": "supervisor"}
