from db.supabase_client import db
unmatched = db.get_unmatched_transactions(limit=1000)
ar_unmatched = [tx for tx in unmatched if tx.get('source') == 'internal' and tx.get('amount', 0) > 0]
print(f"Total AR unmatched: {len(ar_unmatched)}")
for tx in ar_unmatched[:5]:
    print(tx)
