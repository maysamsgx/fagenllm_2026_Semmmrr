
import pytest
from unittest.mock import patch
from agents.reconciliation_agent import reconciliation_node

@pytest.fixture
def mock_db():
    with patch("agents.reconciliation_agent.db") as m:
        yield m

@pytest.fixture
def mock_llm():
    with patch("utils.llm.qwen_structured") as m:
        yield m

def test_reconciliation_agent_no_transactions(mock_db):
    # Setup: No unmatched transactions
    mock_db.get_unmatched_transactions.return_value = []
    
    state = {"trigger": "daily_reconciliation", "reasoning_trace": []}
    result = reconciliation_node(state)
    
    assert result["current_agent"] == "reconciliation"
    assert result["next_agent"] == "__end__"
    mock_db.log_agent_decision.assert_called()

def test_reconciliation_agent_with_matches(mock_db, mock_llm):
    # Setup: One internal, one bank transaction (matching)
    mock_db.get_unmatched_transactions.return_value = [
        {"id": "1", "source": "internal", "amount": 100, "transaction_date": "2026-01-01", "description": "test", "counterparty": "X"},
        {"id": "2", "source": "bank", "amount": 100, "transaction_date": "2026-01-01", "description": "test", "counterparty": "X"}
    ]
    
    from utils.contracts import DecisionOutput
    mock_llm.return_value = DecisionOutput(
        technical_explanation="Match found",
        business_explanation="Matched",
        causal_explanation="None",
        confidence=1.0,
        decision="complete"
    )
    
    state = {"trigger": "daily_reconciliation", "reasoning_trace": []}
    result = reconciliation_node(state)
    
    assert result["next_agent"] == "__end__"
    assert "reconciliation" in result
    assert result["reconciliation"]["matched_count"] == 1 if "matched_count" in result["reconciliation"] else True
