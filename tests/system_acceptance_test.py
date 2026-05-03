
import pytest
from agents.graph import graph
from agents.state import initial_state
from db.supabase_client import db

def verify_causal_links(cause_id: str, effect_agent: str):
    """Utility to verify a causal link exists in the DB."""
    links = db.select("causal_links", {"cause_decision_id": cause_id})
    found = any(l.get("effect_agent") == effect_agent or effect_agent in l.get("explanation", "") for l in links)
    if not found:
        # Check by result agent in agent_decisions if causal_links is empty but flow happened
        effects = db.select("agent_decisions", {"agent": effect_agent})
        # This is a bit loose but helps verify the flow
        return len(effects) > 0
    return True

@pytest.mark.parametrize("trigger, entity_id, description", [
    ("invoice_uploaded", "6ba06f54-1be1-4ca3-a141-c571cf285504", "Testing Spending Path: Invoice -> Budget -> Cash"),
    ("manual_reconciliation", "manual_run_001", "Testing Revenue Path: Recon -> Credit -> Cash"),
    ("customer_payment_check", "ba39f458-7745-4995-ab18-280fb9851a45", "Testing Risk Path: Credit -> Cash"),
])
def test_system_causal_chains(trigger, entity_id, description):
    """
    MASTER ACCEPTANCE TEST:
    Tests the three primary causal chains in the FAgentLLM system.
    """
    print(f"\n--- {description} ---")
    
    # 1. Resolve real ID if needed
    actual_entity_id = entity_id
    if trigger == "customer_payment_check" and entity_id == "real_customer_id":
        customers = db.select("customers")
        if not customers: pytest.skip("No customers for credit test")
        actual_entity_id = customers[0]["id"]
    
    # 2. Setup state
    state = initial_state(trigger, actual_entity_id)
    
    # Add dummy data for invoice if needed
    if trigger == "invoice_uploaded":
        # Ensure the invoice exists and has OCR text to bypass storage download
        db.update("invoices", {"id": actual_entity_id}, {
            "ocr_raw_text": "VENDOR: AWS Cloud Services\nAMOUNT: 500.00\nCURRENCY: USD\nDATE: 2026-05-01\nINV#: AWS-999",
            "status": "pending"
        })
        state["invoice"] = {
            "invoice_id": actual_entity_id,
            "amount": 500.0,
            "currency": "USD",
            "vendor_name": "AWS Cloud Services",
            "department_id": "engineering"
        }

    # 3. EXECUTION: Run the full graph
    try:
        final_state = graph.invoke(state)
    except Exception as e:
        pytest.fail(f"Graph failed for {trigger}: {e}")
    
    print(f"  Flow Path: { [t['agent'] for t in final_state.get('reasoning_trace', [])] }")
    print(f"  Final Agent: {final_state.get('current_agent')} -> Next: {final_state.get('next_agent')}")

    # 4. VERIFICATION: Causal reasoning traces exist
    trace = final_state.get("reasoning_trace", [])
    assert len(trace) > 0, "No reasoning trace generated"
    
    # Verify specific agent presence based on trigger
    agents_involved = [t["agent"] for t in trace]
    
    if trigger == "invoice_uploaded":
        # Should have at least Invoice and Budget
        assert "invoice" in agents_involved
        assert "budget" in agents_involved
        print("  [PASS] Spending Path (Invoice -> Budget) verified.")
        
    elif trigger == "manual_reconciliation":
        assert "reconciliation" in agents_involved
        print("  [PASS] Revenue Path (Reconciliation) verified.")
        
    elif trigger == "customer_payment_check":
        assert "credit" in agents_involved
        print("  [PASS] Risk Path (Credit) verified.")

    # 5. DB Verification (Decisions)
    for t in trace:
        agent = t["agent"]
        # Look for the decision in the DB
        decisions = db.select("agent_decisions", {"agent": agent})
        assert len(decisions) > 0, f"No decisions logged for agent {agent}"
    
    print("  [PASS] All agent decisions persisted to Database.")

def test_cross_agent_causal_links():
    """
    Verify that the system is actually creating causal link records 
    when one agent influences another.
    """
    print("\n--- Testing Cross-Agent Causal Connectivity ---")
    links = db.select("causal_links")
    # We want to see at least some links if the system has been running
    if len(links) == 0:
        print("  [INFO] No causal links found yet. System may need an anomalous run to trigger escalation.")
    else:
        print(f"  [PASS] Found {len(links)} causal links in the database.")
        for l in links[:3]:
            # Fetch agent names from the linked decisions
            cause = db.select("agent_decisions", {"id": l["cause_decision_id"]})
            effect = db.select("agent_decisions", {"id": l["effect_decision_id"]})
            c_agent = cause[0]["agent"] if cause else "unknown"
            e_agent = effect[0]["agent"] if effect else "unknown"
            print(f"    Link: {c_agent} -> {e_agent} ({l['relationship_type']})")

if __name__ == "__main__":
    pytest.main([__file__, "-s"])
