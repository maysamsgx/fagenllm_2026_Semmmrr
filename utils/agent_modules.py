"""
utils/agent_modules.py
Formal 6-Module Agent Architecture for FAgentLLM.

Maps directly to the DOE (Directive–Orchestration–Execution) framework:

  DOE Layer      │  Module
  ───────────────┼──────────────────────────────────────────
  Directive      │  Loaded during Perception; injected into Reasoning
  Orchestration  │  Perception · Reasoning · Decision · Communication
  Execution      │  Execution · Explanation (DB writes)

Each agent is decomposed into six named, testable functions:

  1. Perception   — reads from FinancialState + DB; returns a percept dict
  2. Reasoning    — calls LLM with directive context; returns LLM output or None
  3. Decision     — applies deterministic business rules to LLM output; returns verdict dict
  4. Execution    — performs all DB writes / API calls (side-effects only, no return value)
  5. Communication— builds the updated FinancialState to hand back to LangGraph
  6. Explanation  — logs to agent_decisions and causal_links; returns decision_id

The pipeline runner enforces the correct execution order and ensures the
decision_id is available in the verdict dict before Execution runs.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Callable, Any

from agents.state import FinancialState

logger = logging.getLogger("fagentllm")

# Typed aliases for the six module callables
PerceptionFn    = Callable[[FinancialState], dict]
ReasoningFn     = Callable[[FinancialState, dict], Any]
DecisionFn      = Callable[[FinancialState, dict, Any], dict]
ExecutionFn     = Callable[[FinancialState, dict, dict], None]
CommunicationFn = Callable[[FinancialState, dict, dict], FinancialState]
ExplanationFn   = Callable[[FinancialState, dict, dict], str]


@dataclass(frozen=True)
class AgentPipeline:
    """
    Encapsulates the six design modules for one agent domain.

    Pass an instance to run_agent_pipeline() to execute the full pipeline.
    The dataclass is frozen so pipelines act as singletons — define them
    once at module level and reuse across every LangGraph invocation.
    """
    name:          str
    perception:    PerceptionFn
    reasoning:     ReasoningFn
    decision:      DecisionFn
    execution:     ExecutionFn
    communication: CommunicationFn
    explanation:   ExplanationFn


def run_agent_pipeline(pipeline: AgentPipeline, state: FinancialState) -> FinancialState:
    """
    Execute the six modules in the correct DOE-compliant order:

        perception → reasoning → decision → explanation → execution → communication

    Explanation runs BEFORE execution so the decision_id is available inside
    execution for any causal links that need to reference it. Execution runs
    BEFORE communication so all DB state is committed before the graph moves on.

    Parameters
    ----------
    pipeline : AgentPipeline
        The fully-wired pipeline for this agent domain.
    state : FinancialState
        The current shared LangGraph state dict.

    Returns
    -------
    FinancialState
        The updated state dict to hand back to the LangGraph supervisor.
    """
    logger.debug("[%s] Pipeline start", pipeline.name)

    percept:  dict = pipeline.perception(state)
    llm_out:  Any  = pipeline.reasoning(state, percept)
    verdict:  dict = pipeline.decision(state, percept, llm_out)

    # Explanation first so decision_id is in verdict before execution
    did: str = pipeline.explanation(state, percept, verdict)
    verdict["decision_id"] = did

    pipeline.execution(state, percept, verdict)
    new_state: FinancialState = pipeline.communication(state, percept, verdict)

    logger.debug("[%s] Pipeline complete → next_agent=%s", pipeline.name, new_state.get("next_agent"))
    return new_state
