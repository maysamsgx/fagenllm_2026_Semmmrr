from db.supabase_client import db
all_unmatched = db.select("transactions", {"matched": False})
ar_unmatched = [tx for tx in all_unmatched if tx.get('source') == 'internal' and tx.get('amount', 0) > 0]
print(f"Total AR unmatched in DB: {len(ar_unmatched)}")
for tx in ar_unmatched[:5]:
    print(f"ID: {tx['id']}, Desc: {tx['description']}, Counterparty: {tx['counterparty']}")
