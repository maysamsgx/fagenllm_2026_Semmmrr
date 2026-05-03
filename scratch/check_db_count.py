from db.supabase_client import db
customers = db.select("customers")
print(f"Total customers in DB: {len(customers)}")
