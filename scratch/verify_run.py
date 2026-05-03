from db.supabase_client import db
import json
from datetime import datetime, timezone

def diagnostic():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"--- DECISIONS FOR {today} ---")
    decisions = db.select("agent_decisions")
    # Sort by created_at desc
    sorted_decisions = sorted(decisions, key=lambda x: x.get("created_at", ""), reverse=True)
    found = 0
    for d in sorted_decisions:
        if today in d['created_at']:
            found += 1
            print(f"[{d['created_at']}] Agent: {d['agent']}, Type: {d['decision_type']}, Entity: {d['entity_table']}/{d['entity_id']}")
            print(f"  Technical: {d['technical_explanation'][:100]}...")
            print(f"  Business:  {d['business_explanation'][:100]}...")
            print(f"  Output:    {json.dumps(d['output_action'])}")
            print("-" * 40)
    if found == 0:
        print("No decisions found for today yet.")

    print(f"\n--- CAUSAL LINKS FOR {today} ---")
    links = db.select("causal_links")
    sorted_links = sorted(links, key=lambda x: x.get("created_at", ""), reverse=True)
    found_links = 0
    for l in sorted_links:
        if today in l['created_at']:
            found_links += 1
            print(f"[{l['created_at']}] {l['cause_decision_id']} -> {l['effect_decision_id']} ({l['relationship_type']})")
            print(f"  Explanation: {l['explanation']}")
            print("-" * 40)
    if found_links == 0:
        print("No links found for today yet.")

if __name__ == "__main__":
    diagnostic()
