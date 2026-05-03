from db.supabase_client import db
unmatched = db.get_unmatched_transactions()
print(f"Total unmatched: {len(unmatched)}")
for tx in unmatched[:5]:
    print(tx)
