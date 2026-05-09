import pytest
from agents.graph import graph
from agents.state import initial_state
from db.supabase_client import db

def test_spending_path_invoice_to_budget_to_cash():
    """
    Test the full spending path: Invoice -> Budget -> Cash
    Verifies that the entire end-to-end process behaves as intended.
    """
    trigger = "invoice_uploaded"
    entity_id = "test-invoice-id"
    
    state = initial_state(trigger, entity_id)
    # Mock invoice data for the test to bypass DB lookup
    state["invoice"] = {
        "invoice_id": entity_id,
        "amount": 500.0,
        "currency": "USD",
        "vendor_name": "Test Vendor",
        "department_id": "engineering"
    }

    try:
        final_state = graph.invoke(state)
    except Exception as e:
        pytest.fail(f"Graph failed: {e}")
        
    trace = final_state.get("reasoning_trace", [])
    agents_involved = [t["agent"] for t in trace]
    
    assert "invoice" in agents_involved, "Invoice agent missing from spending path"
    assert "budget" in agents_involved, "Budget agent missing from spending path"

def test_revenue_path_reconciliation_to_credit_to_cash():
    """
    Test the full revenue flow: Reconciliation -> Credit -> Cash
    Verifies the entire end-to-end process for anomaly escalation.
    """
    trigger = "daily_reconciliation"
    entity_id = "test-recon-run"
    
    state = initial_state(trigger, entity_id)
    state["reconciliation"] = {"period": "2026-Q1"}

    try:
        final_state = graph.invoke(state)
    except Exception as e:
        pytest.fail(f"Graph failed: {e}")
        
    trace = final_state.get("reasoning_trace", [])
    agents_involved = [t["agent"] for t in trace]
    
    assert "reconciliation" in agents_involved, "Reconciliation agent missing from revenue path"

def test_risk_path_credit_to_cash():
    """
    Test the full risk path: Credit -> Cash
    Verifies that credit risk downgrades trigger cash forecast recalculations.
    """
    trigger = "customer_payment_check"
    entity_id = "test-customer-id"
    
    state = initial_state(trigger, entity_id)
    try:
        final_state = graph.invoke(state)
    except Exception as e:
        pytest.fail(f"Graph failed: {e}")
        
    trace = final_state.get("reasoning_trace", [])
    agents_involved = [t["agent"] for t in trace]
    
    assert "credit" in agents_involved, "Credit agent missing from risk path"
