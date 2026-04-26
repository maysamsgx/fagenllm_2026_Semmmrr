"""
seed_data_v2.py
Seeds Supabase with realistic demo data for the Causal-Reasoning schema v2.
"""

import sys, os
from datetime import date, timedelta
import random, uuid

# Ensure we can import from parent dir
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import get_supabase

supabase = get_supabase()
TODAY = date.today()

def seed_all():
    print("Seeding FAgentLLM v2 demo data...")
    
    # 1. Departments
    depts = seed_departments()
    
    # 2. Vendors
    vendors = seed_vendors()
    
    # 3. Customers
    customers = seed_customers()
    
    # 4. Cash Accounts
    accounts = seed_cash_accounts()
    
    # 5. Budgets
    seed_budgets(depts)
    
    # 6. Receivables
    seed_receivables(customers)
    
    # 7. Transactions
    seed_transactions(vendors, accounts)
    
    # 8. Forecasts
    seed_forecasts(accounts)
    
    print("\nDone. V2 demo data seeded successfully.")

def seed_departments():
    print("  Departments...")
    depts = [
        {"id": "engineering", "name": "Engineering & Product"},
        {"id": "marketing",   "name": "Marketing & Growth"},
        {"id": "operations",  "name": "Global Operations"},
        {"id": "hr",          "name": "Human Resources"},
    ]
    for d in depts:
        supabase.table("departments").insert(d).execute()
    return [d["id"] for d in depts]

def seed_vendors():
    print("  Vendors...")
    vendors = [
        {"name": "Amazon Web Services", "tax_id": "95-1234567", "email": "billing@aws.com"},
        {"name": "Google Cloud",        "tax_id": "94-7654321", "email": "ap@google.com"},
        {"name": "Office Depot",        "tax_id": "82-1112223", "email": "sales@officedepot.com"},
        {"name": "WeWork",              "tax_id": "13-9998887", "email": "billing@wework.com"},
        {"name": "Slack Technologies",  "tax_id": "46-5554443", "email": "finance@slack.com"},
    ]
    ids = []
    for v in vendors:
        r = supabase.table("vendors").insert(v).execute()
        ids.append(r.data[0]["id"])
    return ids

def seed_customers():
    print("  Customers...")
    customers = [
        {"name": "Acme Corp",       "email": "ap@acmecorp.com",    "credit_limit": 200_000, "credit_score": 82.0, "risk_level": "low",    "payment_terms": 30},
        {"name": "BuildRight Ltd",  "email": "billing@buildright.com", "credit_limit": 100_000, "credit_score": 51.0, "risk_level": "medium", "payment_terms": 30},
        {"name": "TechStart Inc",   "email": "finance@techstart.io",   "credit_limit": 50_000,  "credit_score": 31.0, "risk_level": "high",   "payment_terms": 14},
        {"name": "Global Trade GmbH","email": "ap@globaltrade.de",  "credit_limit": 500_000, "credit_score": 91.0, "risk_level": "low",    "payment_terms": 60},
    ]
    ids = []
    for c in customers:
        r = supabase.table("customers").insert(c).execute()
        ids.append(r.data[0]["id"])
    return ids

def seed_cash_accounts():
    print("  Cash accounts...")
    accounts = [
        {"account_name": "Primary Operating", "bank_name": "Chase", "currency": "USD", "current_balance": 285_000.00, "minimum_balance": 50_000.00},
        {"account_name": "EUR Reserve",       "bank_name": "HSBC",  "currency": "EUR", "current_balance": 95_000.00,  "minimum_balance": 20_000.00},
    ]
    ids = []
    for a in accounts:
        r = supabase.table("cash_accounts").insert(a).execute()
        ids.append(r.data[0]["id"])
    return ids

def seed_budgets(dept_ids):
    print("  Budgets...")
    period = f"{TODAY.year}-Q{(TODAY.month-1)//3+1}"
    for d in dept_ids:
        allocated = random.choice([50000, 100000, 200000, 300000])
        spent     = allocated * random.uniform(0.1, 0.8)
        supabase.table("budgets").insert({
            "department_id": d, "period": period,
            "allocated": allocated, "spent": round(spent, 2),
            "committed": round(spent * 0.1, 2)
        }).execute()

def seed_receivables(customer_ids):
    print("  Receivables...")
    for cid in customer_ids:
        for _ in range(random.randint(2, 4)):
            due = TODAY + timedelta(days=random.randint(-30, 30))
            amount = random.uniform(1000, 25000)
            status = "open" if due > TODAY or random.random() > 0.5 else "paid"
            supabase.table("receivables").insert({
                "customer_id": cid, "amount": round(amount, 2),
                "due_date": due.isoformat(), "status": status,
                "days_overdue": max(0, (TODAY - due).days) if status == "open" else 0
            }).execute()

def seed_transactions(vendor_ids, account_ids):
    print("  Transactions...")
    for _ in range(20):
        acc_id = random.choice(account_ids)
        amount = random.uniform(100, 10000)
        t_date = TODAY - timedelta(days=random.randint(1, 15))
        supabase.table("transactions").insert({
            "source": "bank", "amount": round(amount, 2),
            "transaction_date": t_date.isoformat(),
            "cash_account_id": acc_id,
            "description": f"Trans - {uuid.uuid4().hex[:6]}",
            "matched": False
        }).execute()

def seed_forecasts(account_ids):
    print("  Forecasts...")
    for acc_id in account_ids:
        for i in range(1, 8):
            f_date = TODAY + timedelta(days=i)
            supabase.table("cash_flow_forecasts").insert({
                "forecast_date": f_date.isoformat(),
                "cash_account_id": acc_id,
                "projected_inflow": round(random.uniform(5000, 20000), 2),
                "projected_outflow": round(random.uniform(2000, 15000), 2)
            }).execute()

if __name__ == "__main__":
    seed_all()
