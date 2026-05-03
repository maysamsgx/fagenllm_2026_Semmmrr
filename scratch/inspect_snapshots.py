
import os
from supabase import create_client
from dotenv import load_dotenv

def inspect_snapshots():
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    supabase = create_client(url, key)
    
    res = supabase.table("financial_state_snapshots").select("*").order("snapshot_time", desc=True).limit(5).execute()
    for row in res.data:
        print(f"Time: {row['snapshot_time']} | Agent: {row['triggered_by_agent']} | Cash: {row['total_cash']} | Payables: {row['total_payables']}")

if __name__ == "__main__":
    inspect_snapshots()
