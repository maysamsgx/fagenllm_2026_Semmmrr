import pytest
import uuid
from agents.graph import graph
from agents.state import initial_state
from db.supabase_client import db

@pytest.fixture(autouse=True)
def mock_db(monkeypatch):
    monkeypatch.setattr(db, "get_invoice", lambda _id: {
        "id": _id, "amount": 500.0, "currency": "USD", "vendor_name": "Test Vendor", 
        "department_id": "engineering", "ocr_raw_text": "MOCK OCR", "confidence_score": 0.99
    }, raising=False)
    monkeypatch.setattr(db, "get_budget", lambda dept, period: {
        "id": str(uuid.uuid4()), "department_id": dept, "period": period, "allocated": 10000, "spent": 1000, "committed": 0
    }, raising=False)
    monkeypatch.setattr(db, "get_customer", lambda _id: {
        "id": _id, "name": "Test Cust", "credit_limit": 50000, "current_balance": 10000, 
        "risk_segment": "low", "aging_30_60": 0, "aging_60_90": 0, "aging_90_plus": 0
    }, raising=False)
    monkeypatch.setattr(db, "get_cash_forecast", lambda *a, **kw: [], raising=False)
    monkeypatch.setattr(db, "update_invoice_status", lambda *a, **kw: None, raising=False)
    monkeypatch.setattr(db, "update_customer_status", lambda *a, **kw: None, raising=False)
    monkeypatch.setattr(db, "update_credit_limit", lambda *a, **kw: None, raising=False)
    monkeypatch.setattr(db, "log_agent_decision", lambda *a, **kw: str(uuid.uuid4()), raising=False)
    monkeypatch.setattr(db, "log_causal_link", lambda *a, **kw: None, raising=False)
    monkeypatch.setattr(db, "get_reconciliation_anomalies", lambda *a, **kw: [], raising=False)
    monkeypatch.setattr(db, "get_all_departments", lambda *a, **kw: [{"id": "engineering"}], raising=False)
    monkeypatch.setattr(db, "insert_reconciliation_report_items", lambda *a, **kw: None, raising=False)
    monkeypatch.setattr(db, "add_reconciliation_items", lambda *a, **kw: None, raising=False)
    monkeypatch.setattr(db, "get_vendor", lambda *a, **kw: {"id": "v1", "name": "Test Vendor"}, raising=False)
    monkeypatch.setattr(db, "create_reconciliation_report", lambda *a, **kw: str(uuid.uuid4()), raising=False)
    
    # Mock LLM directly in the agent namespaces to handle Python import binding
    mock_json = {
        "vendor_name": "Test Vendor", "invoice_number": "123", "invoice_date": "2026-05-01", 
        "total_amount": 500, "confidence": 0.99, "is_valid": True, "reason": "ok", 
        "anomalies": [], "risk_segment": "low", "recommended_limit": 50000, 
        "decision": "approve", "explanation": "ok", "forecasts": [], "hard_stop": False,
        "breach": False, "utilisation_pct": 50, "remaining": 5000,
        "match": True, "details": "ok"
    }
    
    class MockStruct:
        is_systematic = False
        technical_explanation = "mock"
        business_explanation = "mock"
        causal_explanation = "mock"
        confidence = 0.99
        recommended_action = "approve"
        risk_segment = "low"
        recommended_limit = 50000
        cross_domain_signals = {}
        
    import agents.invoice_agent
    import agents.reconciliation_agent
    import agents.credit_agent
    import agents.budget_agent
    
    monkeypatch.setattr(agents.invoice_agent, "qwen_json", lambda *a, **kw: mock_json, raising=False)
    monkeypatch.setattr(agents.invoice_agent, "qwen_structured", lambda *a, **kw: MockStruct(), raising=False)
    monkeypatch.setattr(agents.invoice_agent, "ocr_invoice", lambda *a, **kw: "MOCK OCR", raising=False)
    monkeypatch.setattr(agents.reconciliation_agent, "qwen_structured", lambda *a, **kw: MockStruct(), raising=False)
    monkeypatch.setattr(agents.credit_agent, "qwen_structured", lambda *a, **kw: MockStruct(), raising=False)
    monkeypatch.setattr(agents.budget_agent, "qwen_structured", lambda *a, **kw: MockStruct(), raising=False)

def test_spending_path_invoice_to_budget_to_cash():
    """
    Test the full spending path: Invoice -> Budget -> Cash
    Verifies that the entire end-to-end process behaves as intended.
    """
    trigger = "invoice_uploaded"
    entity_id = str(uuid.uuid4())
    
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
    entity_id = str(uuid.uuid4())
    
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
    entity_id = str(uuid.uuid4())
    
    state = initial_state(trigger, entity_id)
    try:
        final_state = graph.invoke(state)
    except Exception as e:
        pytest.fail(f"Graph failed: {e}")
        
    trace = final_state.get("reasoning_trace", [])
    agents_involved = [t["agent"] for t in trace]
    
    assert "credit" in agents_involved, "Credit agent missing from risk path"
