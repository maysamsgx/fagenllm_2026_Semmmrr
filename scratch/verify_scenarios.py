import sys
import os

# Add the current directory to sys.path so we can import our modules
sys.path.append(os.getcwd())

from agents.graph import graph
from agents.state import initial_state
from db.supabase_client import db

def test_scenario_1():
    print("\n--- Testing Scenario 1: Invoice Approval with Liquidity-Aware Decision Support ---")
    # 1. Find an invoice that is 'awaiting_approval'
    invoices = db.select("invoices", {"status": "awaiting_approval"})
    if not invoices:
        print("No invoices awaiting approval found. Please run seed.py first.")
        return
    
    invoice_id = invoices[0]["id"]
    print(f"Testing with Invoice ID: {invoice_id}")
    
    # 2. Run the graph with 'invoice_post_checks' trigger
    state = initial_state("invoice_post_checks", invoice_id)
    # Populate context manually since we skip the upload step
    state["invoice"] = {
        "invoice_id": invoice_id,
        "amount": float(invoices[0].get("total_amount") or 0),
        "department_id": invoices[0].get("department_id") or "engineering"
    }
    
    # Run
    final_state = graph.invoke(state)
    
    # 3. Verify
    print(f"Final Status: {final_state.get('invoice', {}).get('status')}")
    print(f"Next Agent: {final_state.get('next_agent')}")
    
    # Check decisions
    decisions = db.select("agent_decisions", {"entity_id": invoice_id})
    print(f"Decisions logged: {len(decisions)}")
    for d in decisions:
        print(f"  - {d['agent']}: {d['decision_type']} -> {d['reasoning'][:100]}...")

def test_scenario_2():
    print("\n--- Testing Scenario 2: Reconciliation Discrepancy Triggering Credit Risk ---")
    # 1. Trigger manual reconciliation
    import uuid
    run_id = str(uuid.uuid4())
    state = initial_state("manual_reconciliation", run_id)
    
    # Run
    final_state = graph.invoke(state)
    
    # 2. Verify
    print(f"Final Agent: {final_state.get('current_agent')}")
    print(f"Next Agent: {final_state.get('next_agent')}")
    print(f"Summary: {final_state.get('reconciliation', {}).get('anomaly_summary')}")
    print(f"Credit Score: {final_state.get('credit', {}).get('credit_score')}")
    print(f"Risk Level: {final_state.get('credit', {}).get('risk_level')}")
    
    # Check if cash agent was called after credit if risk is high
    trace = final_state.get("reasoning_trace", [])
    agents_called = [t["agent"] for t in trace]
    print(f"Agents called: {agents_called}")

def test_scenario_2_propagation():
    print("\n--- Testing Scenario 2 (Part 2): Credit Risk influencing Cash Forecast ---")
    # 1. Trigger credit check with high risk factors
    customers = db.select("customers")
    if not customers: return
    customer_id = customers[0]["id"]
    
    # Mocking high risk factors in DB for this customer
    db.update("customers", {"id": customer_id}, {"total_outstanding": 100000})
    
    state = initial_state("customer_payment_check", customer_id)
    state["credit"] = {"customer_id": customer_id}
    
    # Run
    final_state = graph.invoke(state)
    
    # 2. Verify
    print(f"Risk Level: {final_state.get('credit', {}).get('risk_level')}")
    print(f"Next Agent (after credit): {final_state.get('next_agent')}")
    
    # Check if Cash Agent logged the adjustment
    decisions = db.select("agent_decisions", {"agent": "cash", "decision_type": "forecast_refreshed"})
    if decisions:
        latest = sorted(decisions, key=lambda d: d["created_at"])[-1]
        print(f"Cash Agent Adjustment: {latest['reasoning']}")

def test_scenario_3():
    print("\n--- Testing Scenario 3: Budget Threshold Breach ---")
    # 1. Find a budget that is near or over threshold
    budgets = db.select("budgets")
    target_budget = None
    for b in budgets:
        util = (float(b["spent"]) + float(b["committed"])) / float(b["allocated"]) * 100
        if util > 80:
            target_budget = b
            break
    
    if not target_budget:
        print("No budget near threshold found. Forcing a test case.")
        target_budget = budgets[0]
        # Temporarily increase committed to trigger breach
        db.update("budgets", {"id": target_budget["id"]}, {"committed": float(target_budget["allocated"]) * 0.96})
        target_budget["committed"] = float(target_budget["allocated"]) * 0.96

    print(f"Testing with Budget ID: {target_budget['id']} for Dept: {target_budget['department_id']}")
    
    # 2. Trigger invoice check for this department
    invoices = db.select("invoices")
    test_inv_id = invoices[0]["id"]
    state = initial_state("invoice_post_checks", test_inv_id)
    state["invoice"] = {
        "invoice_id": test_inv_id,
        "amount": 1000.0,
        "department_id": target_budget["department_id"]
    }
    
    # Run
    final_state = graph.invoke(state)
    
    # 3. Verify
    print(f"Budget Breach: {final_state.get('budget', {}).get('budget_breach')}")
    print(f"Approval Status: {final_state.get('invoice', {}).get('status')}")

if __name__ == "__main__":
    test_scenario_1()
    test_scenario_2()
    test_scenario_2_propagation()
    test_scenario_3()
