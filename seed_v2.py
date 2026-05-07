"""
seed_v2.py — Research-Oriented Seed Script
==========================================
Engineered for comprehensive performance evaluation of FAgentLLM.

Key Research Scenarios:
1. [Matched Pairs] 50 transactions with perfect bank/internal alignment.
2. [Timing Anomalies] 10 delayed settlements for specific personas.
3. [Systematic Risk] Engineered discrepancies for Ecem, Misem, and Anas 
   to trigger Reconciliation -> Credit -> Cash causal chain.
4. [Budget & Cash] Large invoices triggering threshold breaches.

Metrics Supported:
- MAPE/MAE (via actual vs projected cash)
- Match Precision/Recall (via reconciliation items)
- Decision Latency (via agent_decisions timestamps)
"""

import os
import random
import uuid
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from faker import Faker

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

try:
    from supabase import create_client
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
    db_client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Error initializing Supabase client: {e}")
    exit(1)

fake = Faker()
Faker.seed(42)
random.seed(42)

TODAY = date(2026, 5, 6)
PERIOD_START = date(2025, 11, 1)
PERIOD_END   = date(2026, 7, 31) # Extended to July for research validation

# ---------------------------------------------------------------
# 1. PERSONAS & CUSTOMERS
# ---------------------------------------------------------------
RESEARCH_PERSONAS = [
    {"name": "ECEM ODUNCU", "risk": "low",    "limit": 100000},
    {"name": "MISEM SULEIMAN EMMHMED MOHAMED", "risk": "medium", "limit": 25000},
    {"name": "ANAS BRKJI", "risk": "high",   "limit": 5000},
    {"name": "ABDUL RAHMAN HACHEM", "risk": "medium", "limit": 15000},
]

def gen_research_customers():
    customers = []
    for p in RESEARCH_PERSONAS:
        customers.append({
            "id": str(uuid.uuid4()),
            "name": p["name"],
            "email": f"{p['name'].lower().replace(' ', '.')}@research.edu",
            "credit_limit": p["limit"],
            "risk_level": p["risk"],
            "payment_terms": 30 if p["risk"] != "high" else 15,
            "credit_score": 90 if p["risk"] == "low" else 60 if p["risk"] == "medium" else 30,
        })
    # Add 20 random ones
    for _ in range(20):
        customers.append({
            "id": str(uuid.uuid4()),
            "name": fake.unique.company()[:100],
            "email": fake.unique.company_email(),
            "credit_limit": random.choice([5000, 10000, 50000]),
            "risk_level": random.choice(["low", "medium", "high"]),
            "payment_terms": 30,
            "credit_score": round(random.uniform(30, 95), 2),
        })
    return customers

# ---------------------------------------------------------------
# 2. VENDORS & DEPARTMENTS
# ---------------------------------------------------------------
DEPARTMENTS_LIST = ["engineering", "marketing", "operations", "finance", "it"]

def gen_vendors():
    vendors = []
    for name in ["AWS", "Google Cloud", "Microsoft", "Slack", "Github"]:
        vendors.append({"id": str(uuid.uuid4()), "name": name, "tax_id": fake.unique.ein()})
    return vendors

# ---------------------------------------------------------------
# 3. SCENARIO GENERATORS
# ---------------------------------------------------------------

def safe_upsert(table, data):
    if isinstance(data, list):
        for item in data:
            try:
                db_client.table(table).upsert(item).execute()
            except Exception:
                pass
    else:
        try:
            db_client.table(table).upsert(data).execute()
        except Exception:
            pass

def seed_everything():
    print("--- Starting Research Seed v2 ---")
    
    # 1. Cleanup existing research data for a fresh run
    persona_names = [p["name"] for p in RESEARCH_PERSONAS]
    try:
        db_client.table("customers").delete().in_("name", persona_names).execute()
        print("  - Cleaned up existing research personas.")
    except Exception as e:
        print(f"  ! Cleanup skipped or failed: {e}")

    # 3. Customers
    customers = gen_research_customers()
    print(f"  + Seeding {len(customers)} customers...")
    safe_upsert("customers", customers)
    
    # 4. Vendors
    vendors = gen_vendors()
    print(f"  + Seeding vendors...")
    safe_upsert("vendors", vendors)
    
    # 5. Budgets
    budgets = []
    for d in DEPARTMENTS_LIST:
        budgets.append({
            "department_id": d,
            "period": "2026-Q2",
            "allocated": 500000 if d != "marketing" else 100000,
            "spent": 0,
            "committed": 0
        })
    safe_upsert("budgets", budgets)

    # 6. PERFECT STORM: RECONCILIATION
    transactions = []
    
    # A. 50 Perfect Matches
    for i in range(50):
        ref = f"MATCH-PERF-{i:03d}"
        amt = round(random.uniform(100, 5000), 2)
        dt  = (TODAY - timedelta(days=random.randint(5, 30))).isoformat()
        # Internal
        transactions.append({
            "source": "internal", "reference": ref, "amount": -amt, 
            "transaction_date": dt, "description": f"Office supplies {ref}", 
            "counterparty": "Vendor OfficeCo", "matched": False
        })
        # Bank
        transactions.append({
            "source": "bank", "reference": f"BANK-{ref}", "amount": -amt, 
            "transaction_date": dt, "description": f"OFFICE CO {ref}", 
            "counterparty": "OFFICE CO", "matched": False
        })

    # B. 10 Timing Anomalies (ECEM & MISEM)
    for i in range(5):
        for p in [customers[0], customers[1]]: # ECEM & MISEM
            ref = f"DELAY-{p['name'][:3].upper()}-{i}"
            amt = round(random.uniform(500, 2000), 2)
            dt_internal = (TODAY - timedelta(days=10)).isoformat()
            dt_bank     = (TODAY - timedelta(days=7)).isoformat() # 3 day delay
            
            transactions.append({
                "source": "internal", "reference": ref, "amount": amt, 
                "transaction_date": dt_internal, "description": f"Invoice {ref}", 
                "counterparty": p["name"], "matched": False
            })
            transactions.append({
                "source": "bank", "reference": f"BANK-{ref}", "amount": amt, 
                "transaction_date": dt_bank, "description": f"DEP {p['name']} {ref}", 
                "counterparty": p["name"], "matched": False
            })

    # C. 5 Systematic Issues (ANAS BRKJI & ABDUL RAHMAN HACHEM)
    # Scenario: pays $100 less than invoice amount every single time.
    for i in range(5):
        for p in [customers[2], customers[3]]: # ANAS & ABDUL RAHMAN
            ref = f"SYS-{p['name'][:4].upper()}-{i}"
            amt_inv = 1000.00
            amt_pay = 900.00
            dt = (TODAY - timedelta(days=5+i)).isoformat()
            
            transactions.append({
                "source": "internal", "reference": ref, "amount": amt_inv, 
                "transaction_date": dt, "description": f"{p['name']} Service {ref}", 
                "counterparty": p["name"], "matched": False
            })
            transactions.append({
                "source": "bank", "reference": f"BANK-{ref}", "amount": amt_pay, 
                "transaction_date": dt, "description": f"PAY {p['name']} {ref}", 
                "counterparty": p["name"], "matched": False
            })

    db_client.table("transactions").insert(transactions).execute()
    print(f"  + Seeded {len(transactions)} transactions for Perfect Storm scenario.")

    # 7. PERFECT STORM: INVOICE / BUDGET / CASH
    # Create a large invoice for ECEM that will breach budget
    # Get a valid vendor ID from the database
    try:
        res = db_client.table("vendors").select("id").limit(1).execute()
        if res.data:
            vendor_id = res.data[0]["id"]
            invoice = {
                "vendor_id": vendor_id,
                "customer_id": None,
                "department_id": "marketing",
                "invoice_number": f"BREACH-{random.randint(1000,9999)}",
                "invoice_date": TODAY.isoformat(),
                "total_amount": 95000.00, # Marketing budget is only 100k
                "status": "pending",
                "ocr_raw_text": "INVOICE BREACH-95K\nTotal: 95000.00\nDept: Marketing",
                "extraction_confidence": 0.98
            }
            db_client.table("invoices").insert(invoice).execute()
            print("  + Seeded 1 large budget-breach invoice for ECEM (Marketing).")
    except Exception as e:
        print(f"  ! Invoice seeding skipped: {e}")

    # 8. CASH FLOW FORECASTS (For MAE/MAPE Metrics)
    forecasts = []
    for i in range(7):
        d = (TODAY + timedelta(days=i)).isoformat()
        forecasts.append({
            "forecast_date": d,
            "projected_inflow": random.uniform(5000, 15000),
            "projected_outflow": random.uniform(2000, 8000),
            "actual_inflow": None, # Agents will fill this as days pass
            "actual_outflow": None
        })
    db_client.table("cash_flow_forecasts").insert(forecasts).execute()

    print("--- Research Seed v2 Complete ---")

if __name__ == "__main__":
    seed_everything()
