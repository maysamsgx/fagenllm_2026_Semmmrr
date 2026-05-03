
import os
from dotenv import load_dotenv
from supabase import create_client

def inspect_cash_accounts():
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")
        return

    supabase = create_client(url, key)
    try:
        response = supabase.table("cash_accounts").select("*").execute()
        accounts = response.data
        print(f"Found {len(accounts)} cash accounts:")
        for acc in accounts:
            print(f"- ID: {acc['id']}, Name: {acc['account_name']}, Bank: {acc['bank_name']}, Currency: {acc['currency']}, Balance: {acc['current_balance']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_cash_accounts()
