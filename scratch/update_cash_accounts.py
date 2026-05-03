
import os
import sys
from dotenv import load_dotenv
from supabase import create_client

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

CASH_ACCOUNTS_UPDATES = [
    ("Operating Account",  "İş Bankası",      "TRY", 25_000_000),
    ("Reserve Account",    "Garanti BBVA",    "USD", 1_200_000),
    ("Payroll Account",    "Akbank",          "TRY", 15_000_000),
    ("FX Account",         "Yapı Kredi",      "EUR", 200_000),
]

def update_cash_accounts():
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")
        return

    supabase = create_client(url, key)
    
    # 1. Fetch current accounts
    response = supabase.table("cash_accounts").select("id", "account_name").execute()
    current_accounts = {acc['account_name']: acc['id'] for acc in response.data}
    
    print(f"Syncing {len(CASH_ACCOUNTS_UPDATES)} accounts...")
    
    for name, bank, curr, bal in CASH_ACCOUNTS_UPDATES:
        if name in current_accounts:
            acc_id = current_accounts[name]
            print(f"Updating '{name}' (ID: {acc_id}) -> {bank} ({curr})")
            supabase.table("cash_accounts").update({
                "bank_name": bank,
                "currency": curr,
                "current_balance": bal,
                "last_updated": "now()"
            }).eq("id", acc_id).execute()
        else:
            print(f"Account '{name}' not found. Skipping.")

    print("\nUpdate complete.")

if __name__ == "__main__":
    update_cash_accounts()
