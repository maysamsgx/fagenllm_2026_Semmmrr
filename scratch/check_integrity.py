
import os
from supabase import create_client
from dotenv import load_dotenv

def check_integrity():
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    supabase = create_client(url, key)
    
    # Invoices without line items
    res = supabase.table("invoices").select("id").execute()
    invoice_ids = {r['id'] for r in res.data}
    
    res = supabase.table("invoice_line_items").select("invoice_id").execute()
    li_invoice_ids = {r['invoice_id'] for r in res.data}
    
    missing_li = invoice_ids - li_invoice_ids
    print(f"Invoices without line items: {len(missing_li)}")
    
    # Transactions without internal/bank counterparts (reconciliation check)
    res = supabase.table("transactions").select("id, source, reference, matched").execute()
    txns = res.data
    internal = [t for t in txns if t['source'] == 'internal']
    bank = [t for t in txns if t['source'] == 'bank']
    
    print(f"Internal Transactions: {len(internal)}")
    print(f"Bank Transactions: {len(bank)}")
    
    unmatched_internal = [t for t in internal if not t['matched']]
    print(f"Unmatched Internal: {len(unmatched_internal)}")

if __name__ == "__main__":
    check_integrity()
