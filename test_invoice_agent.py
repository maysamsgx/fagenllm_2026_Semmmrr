# test_invoice_agent.py
# Quick integration test for the Invoice Agent pipeline.

# Usage:
# 1. Start the server: venv\Scripts\uvicorn main:app --reload --port 8000
# 2. Run this script: venv\Scripts\python test_invoice_agent.py

import time
import sys
import requests

BASE = "http://localhost:8080"
INVOICE_FILE = "test_invoice.png"   
DEPARTMENT   = "engineering"

SEP = "-" * 60

def upload(filepath: str) -> str:
    print("\n" + "="*60)
    print(f"  STEP 1 - Uploading: {filepath}")
    print("="*60)
    with open(filepath, "rb") as f:
        resp = requests.post(
            f"{BASE}/invoice/upload",
            files={"file": (filepath, f, "image/png")},
            params={"department": DEPARTMENT},
        )
    resp.raise_for_status()
    data = resp.json()
    invoice_id = data["invoice_id"]
    print(f"  OK - Invoice created: {invoice_id}")
    print(f"  Status: {data['status']}")
    return invoice_id

def poll_status(invoice_id: str, timeout: int = 120) -> dict:
    print("\n" + "="*60)
    print(f"  STEP 2 - Polling status (up to {timeout}s)...")
    print("="*60)
    
    PROCESSING = {"pending", "extracting", "validating"}
    start = time.time()
    
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{BASE}/invoice/{invoice_id}")
            resp.raise_for_status()
            invoice = resp.json()
            status = invoice.get("status", "unknown")
            
            elapsed = int(time.time() - start)
            print(f"  [{elapsed:>3}s] status = {status:<25} confidence = {invoice.get('extraction_confidence', '-')}")
            
            if status not in PROCESSING:
                return invoice
        except Exception as e:
            print(f"  [error] {e}")
        
        time.sleep(4)
    
    return requests.get(f"{BASE}/invoice/{invoice_id}").json()

def print_invoice(invoice: dict):
    print("\n" + "="*60)
    print("  STEP 3 - Extracted Invoice Fields")
    print("="*60)
    
    fields = [
        ("Vendor",       invoice.get("vendor_name")),
        ("Invoice #",    invoice.get("invoice_number")),
        ("Amount",       invoice.get("total_amount")),
        ("Status",       invoice.get("status")),
        ("Confidence",   f"{invoice.get('extraction_confidence', '-')}%"),
    ]
    
    for label, value in fields:
        print(f"  [v] {label:<14} {value}")

def print_trace(invoice_id: str):
    print("\n" + "="*60)
    print("  STEP 4 - XAI Reasoning Trace")
    print("="*60)
    
    resp = requests.get(f"{BASE}/invoice/{invoice_id}/trace")
    resp.raise_for_status()
    data = resp.json()
    
    events = data.get("trace", [])
    for i, e in enumerate(events, 1):
        print(f"  [{i}] {e.get('agent')} - {e.get('event_type')}")
        print(f"       {e.get('reasoning')[:200]}")

if __name__ == "__main__":
    print("\nFAgentLLM - Invoice Agent Integration Test")
    
    invoice_file = sys.argv[1] if len(sys.argv) > 1 else INVOICE_FILE

    try:
        invoice_id = upload(invoice_file)
        invoice = poll_status(invoice_id)
        print_invoice(invoice)
        print_trace(invoice_id)
        print("\nTEST COMPLETE")
    except Exception as e:
        print(f"\nERROR: {e}")
