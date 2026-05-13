import os
import uuid
import pytest
from db.supabase_client import db
from agents.graph import graph
from agents.state import initial_state
from langgraph.graph import END

def test_multi_customer_reconciliation_loop():
    """
    Test Phase 2/3: Verify that if reconciliation flags multiple customers, 
    the graph iterates through both of them for credit reassessment.
    """
    print("\n--- Testing Multi-Customer Reconciliation Loop ---")
    
    # 1. Setup: Create two customers
    c1_id = str(uuid.uuid4())
    c2_id = str(uuid.uuid4())
    db.insert("customers", {"id": c1_id, "name": f"Anomaly Corp A {c1_id[:8]}", "credit_score": 80})
    db.insert("customers", {"id": c2_id, "name": f"Anomaly Corp B {c2_id[:8]}", "credit_score": 80})
    
    # 2. Mock state with systematic anomalies for both
    # We'll skip the actual reconciliation node and mock its output
    state = initial_state("manual_reconciliation", "run-123")
    state["pending_risk_assessments"] = [c1_id, c2_id]
    state["reconciliation"] = {
        "anomalous_customer_ids": [c1_id, c2_id],
        "decision_id": str(uuid.uuid4()),
        "anomaly_summary": "Detected systematic delays across multiple entities."
    }
    
    # 3. Run graph starting from supervisor (which should route to credit because of pending list)
    # Actually, the supervisor routes based on trigger. 
    # If trigger is manual_reconciliation, it goes to reconciliation.
    # Let's start from reconciliation or just mock the state after reconciliation.
    state["next_agent"] = "credit"
    
    print(f"Starting loop with customers: {c1_id}, {c2_id}")
    
    # First iteration
    result = graph.invoke(state)
    
    # Check that it processed at least one and still has the other pending
    processed = result.get("processed_risk_assessments", [])
    print(f"Processed after iteration 1: {processed}")
    assert len(processed) >= 1
    
    # If the graph ran to completion, it should have processed both
    assert c1_id in processed
    assert c2_id in processed
    print("Multi-customer loop successful!")

def test_budget_reallocation_persistence():
    """Test Phase 1/3: Verify budget reallocations are persisted to DB."""
    print("\n--- Testing Budget Reallocation Persistence ---")
    
    from agents.budget_agent import budget_node
    
    # Create donor and at-risk budgets
    db.insert("departments", {"id": "donor_dept", "name": "Donor Dept"})
    db.insert("departments", {"id": "risk_dept", "name": "At Risk Dept"})
    
    period = "2026-Q2"
    db.upsert("budgets", {"department_id": "donor_dept", "period": period, "allocated": 100000, "spent": 10000})
    db.upsert("budgets", {"department_id": "risk_dept", "period": period, "allocated": 10000, "spent": 9500})
    
    state = initial_state("budget_review", "system")
    state["budget"] = {"period": period}
    
    # Run budget review
    result = budget_node(state)
    
    # Check DB for reallocation suggestions
    reallocs = db.select("budget_reallocations", {"period": period})
    print(f"Found {len(reallocs)} reallocations in DB.")
    assert len(reallocs) > 0
    print(f"First reallocation: {reallocs[0]['from_department_id']} -> {reallocs[0]['to_department_id']}")

def test_governance_conflict_detection():
    """Test Phase 3: Verify Auditor detects agent conflicts."""
    print("\n--- Testing Governance Conflict Detection ---")
    
    from agents.governance_agent import governance_node
    
    # Case: Budget Hard Stop + Invoice Approved
    inv_id = str(uuid.uuid4())
    state = initial_state("invoice_post_checks", inv_id)
    state["budget"] = {"hard_stop": True, "department_id": "marketing"}
    state["invoice"] = {"invoice_id": inv_id, "status": "approved", "amount": 1000}
    state["reasoning_trace"] = [
        {"agent": "budget", "step": "Check", "business_explanation": "Budget HARD STOP triggered."},
        {"agent": "invoice", "step": "Approval", "business_explanation": "Invoice AUTO-APPROVED."}
    ]
    
    result = governance_node(state)
    
    # Check for violation findings
    findings = result["governance"].get("findings", [])
    print(f"Findings: {findings}")
    assert any("HARD STOP" in f for f in findings)
    
    # Check DB
    violations = db.select("governance_violations", {"entity_id": inv_id})
    assert len(violations) > 0
    assert violations[0]["severity"] == "high"
    print("Conflict detection successful!")

if __name__ == "__main__":
    # Manual run if not using pytest
    test_multi_customer_reconciliation_loop()
    test_budget_reallocation_persistence()
    test_governance_conflict_detection()
