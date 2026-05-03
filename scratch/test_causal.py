from db.supabase_client import db
from agents.reconciliation_agent import reconciliation_node
from agents.credit_agent import credit_node
from agents.state import initial_state
import uuid
from datetime import date

def test_causal_integration():
    print("--- CAUSAL INTEGRATION TEST ---")
    
    # 1. Pick a customer
    customers = db.select("customers")
    target = customers[0]
    print(f"Target Customer: {target['name']} ({target['id']})")
    
    # 2. Create an unmatched internal transaction for this customer
    tx_id = str(uuid.uuid4())
    db.insert("transactions", {
        "id": tx_id,
        "source": "internal",
        "amount": 5000.0,
        "transaction_date": date.today().isoformat(),
        "description": f"SYSTEMATIC DELAY: Payment for {target['name']} invoice AR-999",
        "counterparty": target['name'],
        "matched": False
    })
    print(f"Created anomalous transaction: {tx_id}")
    
    # 3. Run Reconciliation Node
    # We'll simulate the LLM finding a systematic pattern by injecting the keyword
    # Actually, the real LLM will run, so we used "SYSTEMATIC" in description.
    state = initial_state("daily_reconciliation", "causal-test")
    state["reconciliation"] = {"period": "2026-Q2"}
    
    print("Running Reconciliation Node...")
    recon_state = reconciliation_node(state)
    
    print(f"Recon Decision ID: {recon_state['reconciliation'].get('decision_id')}")
    print(f"Next Agent: {recon_state['next_agent']}")
    print(f"Anomalous IDs: {recon_state['reconciliation'].get('anomalous_customer_ids')}")
    
    if recon_state['next_agent'] == "credit":
        print("\nRunning Credit Node...")
        final_state = credit_node(recon_state)
        
        decision_id = final_state['credit'].get('decision_id')
        decision = db.select("agent_decisions", {"id": decision_id})[0]
        
        print(f"Credit Decision ID: {decision_id}")
        print(f"Technical: {decision['technical_explanation'][:200]}...")
        
        # Check for causal link
        links = db.select("causal_links", {"effect_decision_id": decision_id})
        if links:
            print(f"\nCAUSAL LINK FOUND!")
            print(f"Type: {links[0]['relationship_type']}")
            print(f"Explanation: {links[0]['explanation']}")
        else:
            print("\nNO CAUSAL LINK FOUND.")
    else:
        print("Failed to trigger credit agent escalation.")

if __name__ == "__main__":
    test_causal_integration()
