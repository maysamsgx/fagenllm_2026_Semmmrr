"""
agents/graph.py
Our LangGraph setup. This is where we wire all the agents together.

Architecture:
  - One node per agent (invoice, budget, reconciliation, credit, cash)
  - One supervisor node that routes between agents
  - Conditional edges: the supervisor reads state.next_agent to decide routing
  - All nodes share FinancialState — modifications propagate automatically

# How our graph works:
# 1. We start with an initial state based on what happened (the trigger).
# 2. The supervisor picks the first agent.
# 3. Agents do their thing and then say who should go next.
# 4. We keep going until an agent says "END".

NOTE on node naming:
  LangGraph (>=0.2) forbids node names that clash with TypedDict state keys.
  FinancialState has keys: invoice, budget, cash, reconciliation, credit.
  Therefore nodes are prefixed with "agent_" (e.g. "agent_invoice").
  The AgentName Literal in state.py still uses the short names so existing
  agent code that sets next_agent="invoice" is translated here via NODE_MAP.
"""

from langgraph.graph import StateGraph, END
from agents.state import FinancialState

from agents.supervisor import router_node
from agents.invoice_agent import invoice_node
from agents.budget_agent import budget_node
from agents.reconciliation_agent import reconciliation_node
from agents.credit_agent import credit_node
from agents.cash_agent import cash_node

# Mapping the short names we use in the code to the actual node names in the graph.
NODE_MAP = {
    "supervisor":     "agent_supervisor",
    "invoice":        "agent_invoice",
    "budget":         "agent_budget",
    "reconciliation": "agent_reconciliation",
    "credit":         "agent_credit",
    "cash":           "agent_cash",
}


def route(state: FinancialState) -> str:
    # This just looks at the state.next_agent and maps it to the right node.
    # Stop immediately on any error
    if state.get("error"):
        return END

    next_agent = state.get("next_agent", "")
    return next_agent if next_agent in NODE_MAP else END


def build_graph() -> StateGraph:
    # Setting up the graph structure. We only run this once when the app starts.
    builder = StateGraph(FinancialState)

    # ── Register all nodes (prefixed to avoid clash with state keys) ─────────
    builder.add_node("agent_supervisor",     router_node)
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
