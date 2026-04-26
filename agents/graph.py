"""
agents/graph.py
The FAgentLLM LangGraph StateGraph.

Architecture:
  - One node per agent (invoice, budget, reconciliation, credit, cash)
  - One supervisor node that routes between agents
  - Conditional edges: the supervisor reads state.next_agent to decide routing
  - All nodes share FinancialState — modifications propagate automatically

How a graph run works:
  1. Caller creates initial state with initial_state(trigger, entity_id)
  2. graph.invoke(state) starts at the supervisor
  3. Supervisor inspects the trigger and sets next_agent
  4. Graph routes to that agent node
  5. Agent does its work, updates state, and sets next_agent for follow-up
  6. Process repeats until next_agent == END

NOTE on node naming:
  LangGraph (>=0.2) forbids node names that clash with TypedDict state keys.
  FinancialState has keys: invoice, budget, cash, reconciliation, credit.
  Therefore nodes are prefixed with "agent_" (e.g. "agent_invoice").
  The AgentName Literal in state.py still uses the short names so existing
  agent code that sets next_agent="invoice" is translated here via NODE_MAP.
"""

from langgraph.graph import StateGraph, END
from agents.state import FinancialState

from agents.supervisor import supervisor_node
from agents.invoice_agent import invoice_node
from agents.budget_agent import budget_node
from agents.reconciliation_agent import reconciliation_node
from agents.credit_agent import credit_node
from agents.cash_agent import cash_node

# Maps the short logical names agents write into next_agent → actual node name
NODE_MAP = {
    "supervisor":     "agent_supervisor",
    "invoice":        "agent_invoice",
    "budget":         "agent_budget",
    "reconciliation": "agent_reconciliation",
    "credit":         "agent_credit",
    "cash":           "agent_cash",
}


def route(state: FinancialState) -> str:
    """
    Conditional edge function — called after every node to decide what runs next.
    Translates the logical next_agent name to the prefixed node name, or END.
    """
    # Stop immediately on any error
    if state.get("error"):
        return END

    next_agent = state.get("next_agent", "")
    return NODE_MAP.get(next_agent, END)


def build_graph() -> StateGraph:
    """
    Build and compile the FAgentLLM StateGraph.
    Called once at import time; the compiled graph is reused across all requests.
    """
    builder = StateGraph(FinancialState)

    # ── Register all nodes (prefixed to avoid clash with state keys) ─────────
    builder.add_node("agent_supervisor",     supervisor_node)
    builder.add_node("agent_invoice",        invoice_node)
    builder.add_node("agent_budget",         budget_node)
    builder.add_node("agent_reconciliation", reconciliation_node)
    builder.add_node("agent_credit",         credit_node)
    builder.add_node("agent_cash",           cash_node)

    # ── Entry point ───────────────────────────────────────────────────────────
    builder.set_entry_point("agent_supervisor")

    # ── Edges: every node can route to any other node or END ─────────────────
    all_edges = {**NODE_MAP, END: END}

    for node_name in list(NODE_MAP.values()):
        builder.add_conditional_edges(node_name, route, all_edges)

    return builder.compile()


# Compiled once at import; reused for all requests
graph = build_graph()
