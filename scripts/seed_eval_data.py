import os
from execution.db.supabase_client import db

def seed_scientific_data():
    print("--- Seeding Scientific Evaluation Data V6 (Conflict-Resistant) ---")
    
    # 1. Departments
    depts = [
        {"id": "engineering", "name": "Engineering"},
        {"id": "marketing", "name": "Marketing"},
        {"id": "operations", "name": "Operations"}
    ]
    for d in depts:
        db.upsert("departments", d)
        print(f"  - Dept: {d['name']} ready.")

    # 2. Vendors (Use existing IDs if possible)
    vendor_names = ["Acme Supplies Ltd", "Marketing Pros", "HeavyMachinery Corp", "CloudSystems Inc"]
    for name in vendor_names:
        vendor_id = db.ensure_vendor(name)
        print(f"  - Vendor: {name} (ID: {vendor_id}) ready.")

    # 3. Budgets
    period = "2026-Q2"
    budgets = [
        {"department_id": "engineering", "period": period, "allocated": 100000, "spent": 15000},
        {"department_id": "marketing", "period": period, "allocated": 40000, "spent": 35000}, 
        {"department_id": "operations", "period": period, "allocated": 500000, "spent": 100000}
    ]
    for b in budgets:
        db._ensure_client().table("budgets").upsert(b, on_conflict="department_id,period").execute()
        print(f"  - Budget for {b['department_id']} ready.")

    # 4. Customers (Conflict-resistant Upsert)
    customers = [
        {"name": "Risky Business Corp", "credit_score": 35.0, "risk_level": "high"},
        {"name": "Middle Ground LLC", "credit_score": 70.0, "risk_level": "medium"}
    ]
    for c in customers:
        # Upsert by name to avoid unique constraint violations
        db._ensure_client().table("customers").upsert(c, on_conflict="name").execute()
        print(f"  - Customer: {c['name']} ready.")

    # 5. Cash Account
    db._ensure_client().table("cash_accounts").upsert({
        "id": "00000000-0000-0000-0000-000000000099",
        "account_name": "Operating Account",
        "current_balance": 50000, 
        "minimum_balance": 10000
    }).execute()
    print("  - Cash Account ready.")

    print("--- Seeding Complete ---")

if __name__ == "__main__":
    seed_scientific_data()
