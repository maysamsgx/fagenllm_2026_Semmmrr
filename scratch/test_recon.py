import os
import sys

# Set up path
sys.path.append(os.getcwd())

from agents.reconciliation_agent import reconciliation_node
from agents.state import initial_state

def test_recon():
    print("Starting manual reconciliation test...")
    state = initial_state("daily_reconciliation", "manual-test")
    state["reconciliation"] = {"period": "2026-Q2"}
    
    # Run node
    new_state = reconciliation_node(state)
    
    print("\n--- RESULTS ---")
    print(f"Current Agent: {new_state['current_agent']}")
    print(f"Next Agent:    {new_state['next_agent']}")
    print(f"Trigger:       {new_state['trigger']}")
    
    recon = new_state.get("reconciliation", {})
    print(f"Report ID:     {recon.get('report_id')}")
    print(f"Decision ID:   {recon.get('decision_id')}")
    print(f"Anomalous IDs: {recon.get('anomalous_customer_ids')}")
    
    if new_state['next_agent'] == "credit":
        from agents.credit_agent import credit_node
        print("\nEscalating to Credit Agent...")
        final_state = credit_node(new_state)
        print(f"Credit Score:  {final_state['credit'].get('credit_score')}")
        print(f"Risk Level:    {final_state['credit'].get('risk_level')}")
        print(f"Credit Decision ID: {final_state['credit'].get('decision_id')}")

if __name__ == "__main__":
    test_recon()
