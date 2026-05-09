import pytest
from agents.budget_agent import _inv_decide
from agents.credit_agent import calculate_penalty
from agents.cash_agent import _decide as cash_decide
from agents.reconciliation_agent import _find_customers
from agents.invoice_agent import REQUIRED_FIELDS

def test_invoice_agent_isolated_logic():
    """Test small, isolated logic component: Invoice field requirements."""
    # Test that all required fields are present in a mock extraction
    extracted = {
        "vendor_name": "ACME",
        "invoice_number": "123",
        "invoice_date": "2026-05-01",
        "total_amount": 1000.0
    }
    missing = [f for f in REQUIRED_FIELDS if not extracted.get(f)]
    assert len(missing) == 0
    
    # Test missing field detection
    incomplete = {"vendor_name": "ACME"}
    missing_fields = [f for f in REQUIRED_FIELDS if not incomplete.get(f)]
    assert "invoice_number" in missing_fields
    assert len(missing_fields) == 3

def test_budget_agent_isolated_logic():
    """Test small, isolated logic component: Budget math and thresholds."""
    # 1. Valid Input - Threshold Breach
    percept = {
        "budget": {"allocated": 100000, "spent": 50000, "committed": 0},
        "amount": 45000,  # 50k + 45k = 95k (95% utilisation)
        "dept_id": "marketing", "period": "2026-Q1", "inv_id": "test_1"
    }
    verdict = _inv_decide(None, percept, None)
    assert verdict["utilisation_pct"] == 95.0
    assert verdict["breach"] is True
    assert verdict["hard_stop"] is False

    # 2. Invalid Input Handling - Zero Budget
    percept_invalid = {**percept, "budget": {"allocated": 0, "spent": 0, "committed": 0}}
    verdict_invalid = _inv_decide(None, percept_invalid, None)
    # If allocated is 0 and total_committed > 0, it should be 100% (breach)
    assert verdict_invalid["utilisation_pct"] == 100.0
    assert verdict_invalid["hard_stop"] is True

def test_cash_agent_isolated_logic():
    """Test small, isolated logic component: Cash liquidity formula C_{t+1}."""
    # Formula: balance_after = (balance + inflows - outflows) - invoice_amount
    percept = {
        "total_balance": 10000.0,
        "inflows": 5000.0,
        "outflows": 2000.0,
        "invoice_amount": 3000.0,
        "min_balance": 5000.0
    }
    # Projected: 10k + 5k - 2k = 13k. After 3k payment = 10k.
    # 10k > 5k (min_balance) -> Approved.
    verdict = cash_decide(None, percept, None)
    assert verdict["can_approve"] is True
    assert verdict["balance_after"] == 10000.0
    assert verdict["headroom"] == 5000.0

    # Test shortfall
    percept_tight = {**percept, "min_balance": 12000.0}
    verdict_tight = cash_decide(None, percept_tight, None)
    assert verdict_tight["can_approve"] is False
    assert verdict_tight["headroom"] == -2000.0

def test_reconciliation_agent_isolated_logic():
    """Test small, isolated logic component: Customer-anomaly matching."""
    # Mock database return for customers
    import db.supabase_client as db_module
    from unittest.mock import patch
    
    mock_customers = [
        {"id": "cust_1", "name": "Global Synergy"},
        {"id": "cust_2", "name": "Acme Corp"}
    ]
    
    anomalies = [
        {"description": "Payment from Global Synergy Dynamics", "id": "tx_1"},
        {"description": "Unknown transfer", "id": "tx_2"}
    ]
    
    with patch("db.supabase_client.db.select", return_value=mock_customers):
        found_ids = _find_customers(anomalies)
        assert "cust_1" in found_ids
        assert "cust_2" not in found_ids

def test_credit_agent_isolated_logic():
    """Test small, isolated logic component: Credit penalty math."""
    assert calculate_penalty("high", 15.0) == 20.0
    assert calculate_penalty("medium", 8.0) == 10.0
    assert calculate_penalty("low", 1.0) == 0.0
    assert calculate_penalty(None, -5.0) == 0.0

def test_agent_schema_conformance():
    """Verify that agent outputs conform to expected pydantic-like schemas."""
    from utils.contracts import DecisionOutput
    output = DecisionOutput(
        decision="approved",
        confidence=0.99,
        technical_explanation="Tech",
        business_explanation="Bus",
        causal_explanation="Cause"
    )
    assert output.decision in ["approved", "rejected", "escalate", "complete"]
    assert isinstance(output.confidence, float)
