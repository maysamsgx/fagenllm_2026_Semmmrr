
import os
from supabase import create_client
from dotenv import load_dotenv
from collections import Counter

def check_db():
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not url or not key:
        print("Error: SUPABASE_URL or SUPABASE_SERVICE_KEY not found in .env")
        return

    supabase = create_client(url, key)
    
    tables = [
        "departments", "vendors", "vendor_risk_scores", "customers", 
        "cash_accounts", "budgets", "invoices", "invoice_line_items", 
        "payments", "receivables", "transactions", "cash_flow_forecasts",
        "financial_state_snapshots", "agent_decisions", "causal_links"
    ]
    
    print("--- Database Row Counts ---")
    for table in tables:
        try:
            res = supabase.table(table).select("*", count="exact").execute()
            count = res.count
            print(f"{table:25s}: {count}")
        except Exception as e:
            print(f"{table:25s}: [ERROR] {e}")

    print("\n--- Checking for Duplicates ---")
    
    # Check Invoices
    try:
        res = supabase.table("invoices").select("invoice_number").execute()
        numbers = [r['invoice_number'] for r in res.data]
        counts = Counter(numbers)
        dupes = {num: count for num, count in counts.items() if count > 1}
        if dupes:
            print(f"Invoices: Found {len(dupes)} duplicate invoice numbers.")
            # Show first 5
            for i, (num, count) in enumerate(dupes.items()):
                if i >= 5: break
                print(f"  - {num}: {count} occurrences")
        else:
            print("Invoices: No duplicate invoice numbers found.")
    except Exception as e:
        print(f"Invoices: [ERROR] {e}")

    # Check Transactions
    try:
        res = supabase.table("transactions").select("reference, source").execute()
        refs = [f"{r['source']}:{r['reference']}" for r in res.data if r['reference']]
        counts = Counter(refs)
        dupes = {ref: count for ref, count in counts.items() if count > 1}
        if dupes:
            print(f"Transactions: Found {len(dupes)} duplicate references.")
            for i, (ref, count) in enumerate(dupes.items()):
                if i >= 5: break
                print(f"  - {ref}: {count} occurrences")
        else:
            print("Transactions: No duplicate references found.")
    except Exception as e:
        print(f"Transactions: [ERROR] {e}")

if __name__ == "__main__":
    check_db()
