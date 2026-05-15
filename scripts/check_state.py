import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db.supabase_client import db

client = db._ensure_client()

total = client.table("transactions").select("id", count="exact").execute().count
matched = client.table("transactions").select("id", count="exact").eq("matched", True).execute().count
no_emb = client.table("transactions").select("id", count="exact").is_("embedding", "null").execute().count

print(f"Total transactions: {total}")
print(f"Matched: {matched}")
print(f"Unmatched: {total - matched}")
print(f"Missing embeddings: {no_emb}")

reports = client.table("reconciliation_reports").select("*").order("generated_at", desc=True).limit(3).execute().data
print(f"\nLatest reconciliation reports ({len(reports)} found):")
for r in reports:
    period = r["period"]
    rate = r["match_rate"]
    gen = r["generated_at"][:19]
    dec_id = r.get("generated_by_decision_id")
    print(f"  - Period: {period}, Match rate: {rate}%, Generated: {gen}")
    print(f"    Decision ID: {dec_id}")

links = client.table("causal_links").select("id", count="exact").execute().count
decisions = client.table("agent_decisions").select("id", count="exact").execute().count
print(f"\nTotal agent decisions: {decisions}")
print(f"Total causal links: {links}")

# Check agent decisions by type
dec_rows = client.table("agent_decisions").select("agent,decision_type").order("created_at", desc=True).limit(20).execute().data
print(f"\nLast 20 decisions:")
for d in dec_rows:
    print(f"  [{d['agent']}] {d['decision_type']}")
