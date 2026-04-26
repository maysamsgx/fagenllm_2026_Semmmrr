"""
scripts/seed_data.py
Seeds Supabase with realistic demo data for the jury presentation.

Run once:
    cd backend && python scripts/seed_data.py

Creates:
  - 3 cash accounts (USD, EUR, local)
  - Budget rows for 4 departments (Engineering, Marketing, Operations, HR)
  - 5 customers with varying credit profiles
  - 20 receivables (mix of on-time, overdue, paid)
  - 100 transactions (70 matched pairs + 30 discrepancies) for reconciliation
  - 7-day cash flow forecast
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import get_supabase
from datetime import date, timedelta
import random, uuid

supabase = get_supabase()
TODAY = date.today()

def seed_all():
    print("Seeding FAgentLLM demo data...")
    seed_cash_accounts()
    seed_budgets()
    seed_customers()
    seed_receivables()
    seed_transactions()
    seed_forecasts()
    print("\nDone. All demo data seeded successfully.")

def seed_cash_accounts():
    print("  Cash accounts...")
    accounts = [
        {"account_name": "Primary Operating Account", "bank_name": "Chase",
         "currency": "USD", "current_balance": 285_000.00, "minimum_balance": 50_000.00},
        {"account_name": "EUR Reserve Account", "bank_name": "Deutsche Bank",
         "currency": "EUR", "current_balance": 95_000.00, "minimum_balance": 20_000.00},
        {"account_name": "Payroll Account", "bank_name": "Chase",
         "currency": "USD", "current_balance": 120_000.00, "minimum_balance": 80_000.00},
    ]
    for a in accounts:
        supabase.table("cash_accounts").insert(a).execute()
    print(f"  → {len(accounts)} accounts created. Total: $500,000")

def seed_budgets():
    print("  Budgets...")
    period = f"{TODAY.year}-Q{(TODAY.month-1)//3+1}"
    budgets = [
        {"department": "engineering",  "period": period, "allocated": 300_000, "spent": 187_000, "committed": 45_000, "alert_threshold": 90.0},
        {"department": "marketing",    "period": period, "allocated": 150_000, "spent": 143_500, "committed": 8_000,  "alert_threshold": 90.0},  # near breach
        {"department": "operations",   "period": period, "allocated": 200_000, "spent": 98_000,  "committed": 22_000, "alert_threshold": 85.0},
        {"department": "hr",           "period": period, "allocated": 80_000,  "spent": 31_000,  "committed": 5_000,  "alert_threshold": 90.0},
    ]
    for b in budgets:
        supabase.table("budgets").insert(b).execute()
    print(f"  → {len(budgets)} budget rows. Marketing at {(143500+8000)/150000*100:.0f}% — ready for Scenario 3 demo")

def seed_customers():
    print("  Customers...")
    customers = [
        {"name": "Acme Corp",       "email": "ap@acmecorp.com",    "credit_limit": 200_000, "credit_score": 82.0, "risk_level": "low",    "payment_terms": 30, "total_outstanding": 45_000},
        {"name": "BuildRight Ltd",  "email": "billing@buildright.com", "credit_limit": 100_000, "credit_score": 51.0, "risk_level": "medium", "payment_terms": 30, "total_outstanding": 78_000},
        {"name": "TechStart Inc",   "email": "finance@techstart.io",   "credit_limit": 50_000,  "credit_score": 31.0, "risk_level": "high",   "payment_terms": 14, "total_outstanding": 48_500},
        {"name": "Global Trade GmbH","email": "ap@globaltrade.de",  "credit_limit": 500_000, "credit_score": 91.0, "risk_level": "low",    "payment_terms": 60, "total_outstanding": 120_000},
        {"name": "Metro Services",  "email": "accounts@metro.com",  "credit_limit": 75_000,  "credit_score": 63.0, "risk_level": "medium", "payment_terms": 30, "total_outstanding": 29_000},
    ]
    inserted = []
    for c in customers:
        r = supabase.table("customers").insert(c).execute()
        inserted.append(r.data[0]["id"])
    print(f"  → {len(customers)} customers. TechStart high-risk (score 31) — ready for Scenario 2 demo")
    return inserted

def seed_receivables():
    print("  Receivables...")
    # Get customer IDs
    customers = supabase.table("customers").select("id, name, risk_level").execute().data
    receivables = []
    for c in customers:
        # Each customer has 3-5 receivables
        for i in range(random.randint(3, 5)):
            days_offset = random.choice([-45, -30, -15, 0, 7, 14, 30])
            due = TODAY + timedelta(days=days_offset)
            overdue = days_offset < 0
            status = "open" if not overdue or random.random() > 0.3 else "partial"
            if c["risk_level"] == "high":
                status = "open"  # high-risk customers always have open overdue
            receivables.append({
                "customer_id": c["id"],
                "amount":      round(random.uniform(5_000, 40_000), 2),
                "due_date":    due.isoformat(),
                "status":      status,
                "collection_stage": "escalated" if overdue and c["risk_level"] == "high" else
                                    "reminder"  if overdue else "none",
            })
    for r in receivables:
        supabase.table("receivables").insert(r).execute()
    print(f"  → {len(receivables)} receivables seeded")

def seed_transactions():
    print("  Transactions (100 rows for reconciliation)...")
    vendors = ["Acme Corp", "BuildRight Ltd", "Office Depot", "AWS", "Google Cloud",
               "Salesforce", "Adobe", "WeWork", "DHL", "FedEx"]
    inserted = 0

    # 70 matched pairs: one internal + one bank record for same transaction
    for i in range(70):
        amount   = round(random.uniform(500, 25_000), 2)
        t_date   = (TODAY - timedelta(days=random.randint(1, 30))).isoformat()
        vendor   = random.choice(vendors)
        ref      = f"INV-{random.randint(10000,99999)}"

        # Internal record
        r1 = supabase.table("transactions").insert({
            "source": "internal", "reference": ref,
            "amount": amount, "transaction_date": t_date,
            "description": f"Payment to {vendor} - {ref}",
            "counterparty": vendor, "matched": False,
        }).execute().data[0]

        # Bank record (slight description variation — tests fuzzy matching)
        r2 = supabase.table("transactions").insert({
            "source": "bank", "reference": ref,
            "amount": amount, "transaction_date": t_date,
            "description": f"{vendor.upper()} {ref}",
            "counterparty": vendor, "matched": False,
        }).execute().data[0]

        # Mark both as matched to each other
        supabase.table("transactions").update(
            {"matched": True, "matched_to": r2["id"], "match_score": round(random.uniform(0.88, 1.0), 4)}
        ).eq("id", r1["id"]).execute()
        supabase.table("transactions").update(
            {"matched": True, "matched_to": r1["id"], "match_score": round(random.uniform(0.88, 1.0), 4)}
        ).eq("id", r2["id"]).execute()

        inserted += 2

    # 30 unmatched (discrepancies for demo)
    discrepancy_types = ["amount_variance", "timing", "duplicate", "missing"]
    for i in range(30):
        supabase.table("transactions").insert({
            "source":           random.choice(["internal", "bank"]),
            "reference":        f"DISC-{random.randint(10000,99999)}",
            "amount":           round(random.uniform(200, 15_000), 2),
            "transaction_date": (TODAY - timedelta(days=random.randint(1, 30))).isoformat(),
            "description":      f"Unmatched - {random.choice(vendors)}",
            "counterparty":     random.choice(vendors),
            "matched":          False,
            "discrepancy_flag": True,
            "discrepancy_type": random.choice(discrepancy_types),
        }).execute()
        inserted += 1

    print(f"  → {inserted} transactions (70 matched pairs + 30 discrepancies)")

def seed_forecasts():
    print("  7-day cash forecast...")
    for d in range(1, 8):
        forecast_date = TODAY + timedelta(days=d)
        inflow  = round(random.uniform(15_000, 45_000), 2)
        outflow = round(random.uniform(20_000, 55_000), 2)
        supabase.table("cash_flow_forecasts").insert({
            "forecast_date":    forecast_date.isoformat(),
            "projected_inflow": inflow,
            "projected_outflow": outflow,
        }).execute()
    print("  → 7 forecast rows seeded")


if __name__ == "__main__":
    seed_all()
