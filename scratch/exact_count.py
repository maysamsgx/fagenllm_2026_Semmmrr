from config import get_supabase
client = get_supabase()
res = client.table("customers").select("id", count="exact").execute()
print(f"Exact count: {res.count}")
