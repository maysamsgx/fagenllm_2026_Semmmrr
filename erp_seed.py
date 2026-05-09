"""
FAgentLLM - Enterprise Synthetic Data Seeder
==================================
Seeds the v2 schema with ~10K rows of realistic financial data for
the period Nov 2025 -> Apr 2026 (6 months).

What it does NOT seed (by design - our agents must generate these):
  - agent_decisions
  - causal_links
  - financial_state_snapshots (auto-populated by trigger)
  - budget_alerts
  - reconciliation_reports

Engineered scenarios (so you have testable cases):
  S1: Clean approvals (~60% of AP invoices)
  S2: Budget-breach invoices (~15%) - push departments past 90% threshold
  S3: Cash-tight large invoices (~5%)
  S4: Late-paying customers (~15% of AR receivables)
  S5: Reconciliation discrepancies (~10% of bank transactions)
  S6: One "perfect storm" invoice that triggers all 5 agents

Usage:
    pip install faker supabase python-dotenv
    # create .env with SUPABASE_URL and SUPABASE_KEY (use service_role key)
    python erp_seed.py

Or test the data generation without DB writes:
    python erp_seed.py --dry-run
"""

import argparse
import csv
import os
import random
import sys
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from faker import Faker

try:
    from supabase import create_client
    from dotenv import load_dotenv
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# Reproducible randomness
SEED = 42
random.seed(SEED)
fake = Faker()
Faker.seed(SEED)

# ---------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------
TODAY        = date.today()
PERIOD_END   = TODAY
PERIOD_START = TODAY - timedelta(days=180) # 6 months of historical data

PERFECT_STORM_VENDOR_ID = str(uuid.uuid4())
PERFECT_STORM_CUSTOMER_ID = str(uuid.uuid4())
PERFECT_STORM_INV_ID = str(uuid.uuid4())

CLIENTS_CSV = Path(__file__).parent / "clients.csv"

# Volume targets
N_VENDORS         = 50
N_AP_INVOICES     = 800        # vendor bills
N_AR_INVOICES     = 1200       # customer invoices
N_CASH_ACCOUNTS   = 4
FORECAST_DAYS     = 90

# Scenario distribution (AP invoices)
PCT_BUDGET_BREACH = 0.15
PCT_CASH_TIGHT    = 0.05

# Scenario distribution (AR / receivables)
PCT_LATE_PAYERS   = 0.15

# Reconciliation noise
PCT_TIMING_DIFF   = 0.05
PCT_AMOUNT_DIFF   = 0.02
PCT_MISSING_BANK  = 0.02
PCT_DUPLICATE     = 0.01


# ---------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------
DEPARTMENTS = [
    # (id, name, base quarterly budget)
    # Sized realistically to absorb ~100 AP invoices/dept/quarter
    ("engineering",  "Engineering",            1_800_000),
    ("marketing",    "Marketing",                900_000),
    ("sales",        "Sales",                    600_000),
    ("operations",   "Operations",             1_200_000),
    ("finance",      "Finance",                  500_000),
    ("hr",           "Human Resources",          350_000),
    ("it",           "IT",                       800_000),
    ("rnd",          "Research & Development", 1_500_000),
]

VENDOR_CATEGORIES = [
    ("AWS Cloud Services",       "engineering", "high_freq"),  # name pattern, default dept, frequency
    ("Google Cloud Platform",    "engineering", "high_freq"),
    ("Microsoft Azure",          "it",          "high_freq"),
    ("GitHub Enterprise",        "engineering", "monthly"),
    ("Slack",                    "operations",  "monthly"),
    ("Atlassian",                "engineering", "monthly"),
    ("DataDog",                  "it",          "monthly"),
    ("Salesforce",               "sales",       "monthly"),
    ("HubSpot",                  "marketing",   "monthly"),
    ("LinkedIn Marketing",       "marketing",   "occasional"),
    ("Facebook Ads",             "marketing",   "high_freq"),
    ("Google Ads",               "marketing",   "high_freq"),
    ("Office Supplies Co",       "operations",  "occasional"),
    ("WeWork",                   "operations",  "monthly"),
    ("Legal Counsel LLP",        "finance",     "occasional"),
    ("Deloitte Audit",           "finance",     "quarterly"),
    ("Recruiting Partners Inc",  "hr",          "occasional"),
    ("Coursera Business",        "hr",          "monthly"),
    ("Lab Equipment Supplier",   "rnd",         "occasional"),
    ("Research Materials Co",    "rnd",         "occasional"),
]

CASH_ACCOUNTS_DATA = [
    ("Operating Account",  "İş Bankası",      "USD", 833_333.33),   # 25M TRY / 30
    ("Reserve Account",    "Garanti BBVA",    "USD", 1_200_000.00), # 1.2M USD
    ("Payroll Account",    "Akbank",          "USD", 500_000.00),   # 15M TRY / 30
    ("FX Account",         "Yapı Kredi",      "USD", 220_000.00),   # 200K EUR * 1.1
]

# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------
def random_date_in_period(start=PERIOD_START, end=PERIOD_END):
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))

def lognormal_amount(median=2000, sigma=1.0, min_v=50, max_v=200_000):
    """Realistic invoice amounts - many small, few huge."""
    import math
    val = math.exp(random.normalvariate(math.log(median), sigma))
    return round(max(min_v, min(max_v, val)), 2)

# ── Deterministic UUIDs ──────────────────────────────────────────────────────
# Using uuid5 ensure that if we run the seeder multiple times, it 'upserts' 
# the same records instead of creating duplicates.
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, 'fagent-llm.enterprise.seed')

def gen_uuid(name: str) -> str:
    """Generate a stable UUID derived from a unique name/key."""
    return str(uuid.uuid5(NAMESPACE, name))


# ---------------------------------------------------------------
# Generators
# ---------------------------------------------------------------
def gen_departments():
    return [
        {"id": d_id, "name": name}
        for d_id, name, _ in DEPARTMENTS
    ]


def gen_vendors():
    """Generate ~50 vendors. First 20 are 'known' high-frequency vendors, rest are random."""
    vendors = []
    # Known vendors (will get 80% of invoice volume)
    for name, default_dept, freq in VENDOR_CATEGORIES:
        vendors.append({
            "id": gen_uuid(f"vendor-{name}"),
            "name": name,
            "tax_id": f"TAX-{name[:3].upper()}-{random.randint(100,999)}",
            "email": f"billing@{name.lower().replace(' ', '').replace('&', 'and')}.com"[:50],
            "_default_dept": default_dept,
            "_frequency": freq,
        })
    # Long-tail random vendors
    for i in range(N_VENDORS - len(VENDOR_CATEGORIES)):
        name = fake.company()
        vendors.append({
            "id": gen_uuid(f"vendor-tail-{i}"),
            "name": name,
            "tax_id": f"TAX-LT-{i:03d}",
            "email": fake.company_email(),
            "_default_dept": random.choice([d[0] for d in DEPARTMENTS]),
            "_frequency": "occasional",
        })
        
    # Inject "Perfect Storm" vendor
    vendors.append({
        "id": PERFECT_STORM_VENDOR_ID,
        "name": "Global Synergy Dynamics (PERFECT STORM)",
        "tax_id": "STORM-001",
        "email": "billing@globalsynergy.test",
        "_default_dept": "marketing",
        "_frequency": "occasional"
    })
    return vendors


def normalize_name_to_email(name, existing_emails):
    import re
    import unicodedata
    normalized = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('utf-8').lower()
    base = re.sub(r'[^a-z0-9]+', '.', normalized).strip('.')
    domain = "example.com"
    email = f"{base}@{domain}"
    if email not in existing_emails:
        return email
    counter = 1
    while True:
        email = f"{base}.{counter}@{domain}"
        if email not in existing_emails:
            return email
        counter += 1

def gen_customers():
    """Use real client names from clients.csv. Assign realistic credit profiles."""
    customers = []
    if not CLIENTS_CSV.exists():
        print(f"WARNING: {CLIENTS_CSV} not found, using Faker names instead")
        names = [fake.company() for _ in range(400)]
    else:
        with open(CLIENTS_CSV, encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            names = list(set([row[0].strip() for row in reader if row and row[0].strip()]))

    existing_emails = set()
    for name in names:
        r = random.random()
        if r < 0.60:
            risk, score = "low", random.uniform(75, 95)
            credit_limit = random.choice([10_000, 25_000, 50_000, 100_000])
            terms = random.choice([30, 30, 30, 45])
        elif r < 0.90:
            risk, score = "medium", random.uniform(50, 74)
            credit_limit = random.choice([5_000, 10_000, 25_000])
            terms = random.choice([30, 30, 60])
        else:
            risk, score = "high", random.uniform(20, 49)
            credit_limit = random.choice([2_000, 5_000])
            terms = random.choice([15, 30])

        email = normalize_name_to_email(name, existing_emails)
        existing_emails.add(email)

        customers.append({
            "id": gen_uuid(f"customer-{name}"),
            "name": name[:120],
            "email": email,
            "phone": fake.phone_number()[:30],
            "credit_limit": credit_limit,
            "credit_score": round(score, 2),
            "risk_level": risk,
            "payment_terms": terms,
            "total_outstanding": 0,
        })
        
    # Inject "Perfect Storm" customer
    email = normalize_name_to_email("Acme Corp (PERFECT STORM)", existing_emails)
    customers.append({
        "id": PERFECT_STORM_CUSTOMER_ID,
        "name": "Acme Corp (PERFECT STORM)",
        "email": email,
        "phone": "555-0199",
        "credit_limit": 100000,
        "credit_score": 60.0,
        "risk_level": "medium",
        "payment_terms": 30,
        "total_outstanding": 0,
    })
    return customers


def gen_cash_accounts():
    return [
        {
            "id": gen_uuid(f"acc-{name}"),
            "account_name": name,
            "bank_name": bank,
            "currency": curr,
            "current_balance": balance,
            "minimum_balance": round(balance * 0.15, 2),
        }
        for name, bank, curr, balance in CASH_ACCOUNTS_DATA
    ]


def gen_budgets(departments):
    """8 departments x 2 quarters covered (2025-Q4, 2026-Q1, plus partial 2026-Q2)."""
    budgets = []
    quarters = ["2025-Q4", "2026-Q1", "2026-Q2"]
    for d_id, _, base in DEPARTMENTS:
        for q in quarters:
            multiplier = 1.0 if q != "2026-Q2" else 0.5
            allocated = round(base * multiplier * random.uniform(0.95, 1.10), 2)
            budgets.append({
                "id": gen_uuid(f"budget-{d_id}-{q}"),
                "department_id": d_id,
                "period": q,
                "allocated": allocated,
                "spent": 0,
                "committed": 0,
                "forecast": None,
                "alert_threshold": 90.0,
            })
    return budgets


def gen_vendor_risk_scores(vendors):
    """Generate V3 risk scores for every vendor."""
    scores = []
    for v in vendors:
        if v["id"] == PERFECT_STORM_VENDOR_ID:
            scores.append({
                "id": gen_uuid(f"risk-{v['id']}"),
                "vendor_id": v["id"],
                "risk_score": 25.0,
                "risk_level": "high",
                "last_assessed": TODAY.isoformat(),
                "factors": {"payment_reliability": "low", "years_active": 1, "data_quality": "marginal"}
            })
            continue

        r = random.random()
        if r < 0.60:
            risk, score = "low", random.uniform(85, 100)
        elif r < 0.90:
            risk, score = "medium", random.uniform(50, 84)
        else:
            risk, score = "high", random.uniform(10, 49)

        scores.append({
            "id": gen_uuid(f"risk-{v['id']}"),
            "vendor_id": v["id"],
            "risk_score": round(score, 2),
            "risk_level": risk,
            "last_assessed": TODAY.isoformat(),
            "factors": {
                "payment_reliability": "high" if risk == "low" else "low",
                "years_active": random.randint(1, 15),
                "data_quality": "excellent" if r < 0.8 else "marginal"
            },
        })
    return scores


def period_for_date(d: date) -> str:
    q = (d.month - 1) // 3 + 1
    return f"{d.year}-Q{q}"


def gen_ap_invoices(vendors, departments_ids):
    """
    Vendor bills (Accounts Payable). These drive budget consumption and cash outflows.
    """
    invoices = []
    weighted_vendors = (
        [v for v in vendors[:20] for _ in range(8)]
        + vendors[20:]
    )

    # ── Budget Tracking ──────────────────────────────────────────────────────────
    # We track consumption during generation to ensure we don't accidentally
    # blow the budget in the "clean" scenario.
    budget_map = {} # (dept, period) -> current_committed
    breach_dept = random.choice([d for d in departments_ids if d != "hr"])

    for i in range(N_AP_INVOICES):
        v = random.choice(weighted_vendors)
        if v["id"] == PERFECT_STORM_VENDOR_ID:
            v = vendors[0]

        dept = v.get("_default_dept", random.choice(departments_ids))
        inv_date = random_date_in_period()
        period = period_for_date(inv_date)
        due_date = inv_date + timedelta(days=random.choice([15, 30, 30, 30, 45, 60]))

        scenario = "clean"
        r = random.random()
        if r < PCT_BUDGET_BREACH and dept == breach_dept:
            amount = round(random.uniform(15_000, 40_000), 2)
            scenario = "budget_breach"
        elif r < PCT_BUDGET_BREACH + PCT_CASH_TIGHT:
            amount = round(random.uniform(25_000, 60_000), 2)
            inv_date = random_date_in_period(date(2026, 3, 15), PERIOD_END)
            period = period_for_date(inv_date)
            due_date = inv_date + timedelta(days=random.choice([15, 30]))
            scenario = "cash_tight"
        else:
            amount = lognormal_amount()

        # Deterministic status based on age
        days_old = (TODAY - inv_date).days
        if days_old < 3:
            status = random.choices(["pending", "extracting", "validating", "awaiting_approval"], weights=[3, 2, 2, 3])[0]
        elif days_old < 14:
            status = random.choices(["awaiting_approval", "approved", "rejected"], weights=[3, 6, 1])[0]
        else:
            status = random.choices(["approved", "paid", "rejected"], weights=[2, 7, 1])[0]

        # ── Budget Enforcement in Seeder ──
        # If this is a 'clean' scenario, ensure we don't exceed budget.
        # If we would exceed, we flip it to 'awaiting_approval' or 'pending' 
        # to demonstrate the hard-stop gate in the live system.
        if scenario == "clean" and status in ("approved", "paid"):
            key = (dept, period)
            consumed = budget_map.get(key, 0)
            # Find the budget for this dept/period
            # (Note: we haven't generated budgets yet in the generate_all() flow, 
            # but we know they average around $400k-$1M based on gen_budgets logic).
            # We'll assume a conservative limit for safety.
            if consumed + amount > 300_000: 
                status = "awaiting_approval"
            else:
                budget_map[key] = consumed + amount

        approved_at = None
        rejection_reason = None
        if status in ("approved", "paid"):
            approved_at = (datetime.combine(inv_date, datetime.min.time()) + timedelta(days=random.randint(1, 5))).isoformat()
        if status == "rejected":
            rejection_reason = random.choice(["Duplicate invoice", "Incorrect line items", "Vendor not in approved list", "Amount exceeds PO"])

        tax_amount = round(amount * 0.18, 2) if random.random() > 0.3 else None

        invoices.append({
            "id": gen_uuid(f"inv-ap-{i}"),
            "vendor_id": v["id"],
            "customer_id": None,
            "department_id": dept,
            "invoice_number": f"AP-{i+10000:06d}",
            "invoice_date": inv_date.isoformat(),
            "due_date": due_date.isoformat(),
            "total_amount": amount,
            "currency": "USD",
            "tax_amount": tax_amount,
            "status": status,
            "approver_id": f"user_{random.randint(1,8):02d}" if approved_at else None,
            "approved_at": approved_at,
            "rejection_reason": rejection_reason,
            "file_path": f"invoices/ap/{i+10000:06d}.pdf",
            "ocr_raw_text": f"{v['name']}\nAmount: {amount}\nDate: {inv_date}",
            "extraction_confidence": round(random.uniform(78, 99), 2),
            "cash_check_passed": True if status in ("approved", "paid") else None,
            "budget_check_passed": True if status in ("approved", "paid") else None,
            "_scenario": scenario,
        })

    # S6: THE PERFECT STORM INVOICE (AP Path: Invoice -> Budget -> Cash)
    invoices.append({
        "id": PERFECT_STORM_INV_ID,
        "vendor_id": PERFECT_STORM_VENDOR_ID,
        "customer_id": None,
        "department_id": breach_dept, # Ensures a massive budget breach
        "invoice_number": "AP-STORM-9999",
        "invoice_date": TODAY.isoformat(),
        "due_date": (TODAY + timedelta(days=5)).isoformat(), # Very tight cash window
        "total_amount": 450000.00, # Massive amount to breach cash
        "currency": "USD",
        "tax_amount": 81000.00,
        "status": "pending",
        "approver_id": None,
        "approved_at": None,
        "rejection_reason": None,
        "file_path": f"invoices/ap/STORM-9999.pdf",
        "ocr_raw_text": "Global Synergy Dynamics\nAmount: 450000.00\nURGENT PAYMENT REQUIRED",
        "extraction_confidence": 0.99,
        "cash_check_passed": None,
        "budget_check_passed": None,
        "_scenario": "perfect_storm",
    })

    return invoices


def gen_ar_invoices(customers):
    """
    Customer invoices (Accounts Receivable). Drive receivables and inflows.
    """
    invoices = []
    for i in range(N_AR_INVOICES):
        c = random.choice(customers)
        if c["id"] == PERFECT_STORM_CUSTOMER_ID:
            c = customers[0]

        inv_date = random_date_in_period()
        due_date = inv_date + timedelta(days=c["payment_terms"])
        amount = lognormal_amount(median=3500, sigma=0.9)

        if c["risk_level"] == "high": paid_prob = 0.40
        elif c["risk_level"] == "medium": paid_prob = 0.75
        else: paid_prob = 0.93

        days_old = (TODAY - inv_date).days
        if days_old < 15: paid_prob *= 0.4

        is_paid = random.random() < paid_prob
        status = "paid" if is_paid else "approved"

        invoices.append({
            "id": gen_uuid(f"inv-ar-{i}"),
            "vendor_id": None,
            "customer_id": c["id"],
            "department_id": "sales",
            "invoice_number": f"AR-{i+50000:06d}",
            "invoice_date": inv_date.isoformat(),
            "due_date": due_date.isoformat(),
            "total_amount": amount,
            "currency": "USD",
            "tax_amount": round(amount * 0.18, 2),
            "status": status,
            "approver_id": f"user_{random.randint(1,8):02d}",
            "approved_at": (datetime.combine(inv_date, datetime.min.time()) + timedelta(days=1)).isoformat(),
            "rejection_reason": None,
            "file_path": f"invoices/ar/{i+50000:06d}.pdf",
            "ocr_raw_text": None,
            "extraction_confidence": None,
            "cash_check_passed": None,
            "budget_check_passed": None,
            "_scenario": "ar_paid" if is_paid else "ar_open",
        })
    return invoices


def gen_line_items(invoices):
    """2-4 line items per invoice."""
    line_items = []
    descriptions = [
        "Software subscription", "Cloud compute", "Professional services",
        "Hardware purchase", "Consulting hours", "Marketing campaign"
    ]
    for inv in invoices:
        n_lines = random.choices([1, 2, 3, 4], weights=[2, 5, 4, 2])[0]
        amount_remaining = float(inv["total_amount"])
        for line_no in range(1, n_lines + 1):
            if line_no == n_lines:
                line_total = round(amount_remaining, 2)
            else:
                line_total = round(amount_remaining * random.uniform(0.2, 0.5), 2)
                amount_remaining -= line_total
            qty = random.choice([1, 1, 1, 2, 5, 10])
            line_items.append({
                "id": gen_uuid(f"line-{inv['id']}-{line_no}"),
                "invoice_id": inv["id"],
                "description": random.choice(descriptions),
                "quantity": qty,
                "unit_price": round(line_total / qty, 2),
                "line_total": line_total,
                "line_no": line_no,
            })
    return line_items


def gen_receivables(ar_invoices, customers):
    """One receivable per unpaid AR invoice. Plant overdue cases."""
    receivables = []
    cust_map = {c["id"]: c for c in customers}

    for inv in ar_invoices:
        if inv["status"] == "paid":
            receivables.append({
                "id": gen_uuid(f"recv-{inv['id']}"), "customer_id": inv["customer_id"], "invoice_id": inv["id"],
                "amount": inv["total_amount"], "due_date": inv["due_date"],
                "status": "paid", "collection_stage": "none", "last_reminder_at": None,
            })
            continue

        c = cust_map[inv["customer_id"]]
        due = date.fromisoformat(inv["due_date"])
        days_overdue = max(0, (TODAY - due).days)

        if days_overdue == 0:
            stage = "none"
            last_reminder = None
        elif days_overdue < 15:
            stage = "reminder" if c["risk_level"] != "low" else "none"
            last_reminder = (TODAY - timedelta(days=random.randint(1, 5))).isoformat() if stage != "none" else None
        elif days_overdue < 45:
            stage = "notice"
            last_reminder = (TODAY - timedelta(days=random.randint(1, 10))).isoformat()
        elif days_overdue < 90:
            stage = "escalated"
            last_reminder = (TODAY - timedelta(days=random.randint(1, 7))).isoformat()
        else:
            stage = "legal" if c["risk_level"] == "high" else "escalated"
            last_reminder = (TODAY - timedelta(days=random.randint(1, 14))).isoformat()

        if days_overdue > 30 and random.random() < 0.2: status = "partial"
        else: status = "open"

        receivables.append({
            "id": gen_uuid(f"recv-{inv['id']}"), "customer_id": inv["customer_id"], "invoice_id": inv["id"],
            "amount": inv["total_amount"], "due_date": inv["due_date"],
            "status": status, "collection_stage": stage, "last_reminder_at": last_reminder,
        })
    return receivables


def gen_payments(ap_invoices):
    payments = []
    for inv in ap_invoices:
        if inv["status"] == "paid":
            inv_date = date.fromisoformat(inv["invoice_date"])
            pay_date = inv_date + timedelta(days=random.randint(5, 25))
            if pay_date > TODAY: continue
            payments.append({
                "id": gen_uuid(f"pay-{inv['id']}"), "invoice_id": inv["id"], "amount": inv["total_amount"],
                "payment_date": pay_date.isoformat(), "method": "wire", "status": "completed",
                "reference": f"PAY-{inv['invoice_number']}",
            })
    return payments


def gen_transactions(ap_invoices, ar_invoices, cash_accounts, payments):
    transactions = []
    operating = next(a for a in cash_accounts if a["account_name"] == "Operating Account")
    payroll   = next(a for a in cash_accounts if a["account_name"] == "Payroll Account")

    pay_map = {p["invoice_id"]: p["id"] for p in payments}

    for inv in ap_invoices:
        if inv["status"] != "paid": continue
        inv_date = date.fromisoformat(inv["invoice_date"])
        pay_date = inv_date + timedelta(days=random.randint(5, 25))
        if pay_date > TODAY: continue

        internal_id = gen_uuid(f"tx-{inv['id']}-internal")
        transactions.append({
            "id": internal_id, "source": "internal", "reference": inv["invoice_number"],
            "amount": -float(inv["total_amount"]), "currency": "USD", "transaction_date": pay_date.isoformat(),
            "description": f"Payment for {inv['invoice_number']}", "counterparty": "Vendor",
            "invoice_id": inv["id"], "payment_id": pay_map.get(inv["id"]), "cash_account_id": operating["id"],
            "matched": False, "matched_to": None, "match_score": None, "discrepancy_flag": False, "discrepancy_type": None,
        })

        r = random.random()
        if r < PCT_MISSING_BANK: continue

        if r < PCT_MISSING_BANK + PCT_TIMING_DIFF:
            bank_date = pay_date + timedelta(days=random.randint(1, 3))
        else:
            bank_date = pay_date

        bank_amount = -float(inv["total_amount"])
        if PCT_MISSING_BANK + PCT_TIMING_DIFF <= r < PCT_MISSING_BANK + PCT_TIMING_DIFF + PCT_AMOUNT_DIFF:
            bank_amount += round(random.uniform(-3, 3), 2)

        bank_id = gen_uuid(f"tx-{inv['id']}-bank")
        transactions.append({
            "id": bank_id, "source": "bank", "reference": f"WIRE-{random.randint(100000, 999999)}",
            "amount": round(bank_amount, 2), "currency": "USD", "transaction_date": bank_date.isoformat(),
            "description": f"WIRE OUT {inv['invoice_number']}", "counterparty": "Beneficiary",
            "invoice_id": inv["id"], "cash_account_id": operating["id"], "matched": False, "matched_to": None,
            "match_score": None, "discrepancy_flag": False, "discrepancy_type": None,
        })

    for inv in ar_invoices:
        if inv["status"] != "paid": continue
        inv_date = date.fromisoformat(inv["invoice_date"])
        recv_date = inv_date + timedelta(days=random.randint(15, 45))
        if recv_date > TODAY: continue

        transactions.append({
            "id": gen_uuid(f"tx-{inv['id']}-internal"), "source": "internal", "reference": inv["invoice_number"],
            "amount": float(inv["total_amount"]), "currency": "USD", "transaction_date": recv_date.isoformat(),
            "description": f"Customer payment {inv['invoice_number']}", "counterparty": "Customer",
            "invoice_id": inv["id"], "cash_account_id": operating["id"], "matched": False, "matched_to": None,
            "match_score": None, "discrepancy_flag": False, "discrepancy_type": None,
        })

        if random.random() > PCT_MISSING_BANK:
            transactions.append({
                "id": gen_uuid(f"tx-{inv['id']}-bank"), "source": "bank", "reference": f"ACH-{random.randint(100000, 999999)}",
                "amount": float(inv["total_amount"]), "currency": "USD", "transaction_date": recv_date.isoformat(),
                "description": f"ACH IN {inv['invoice_number']}", "counterparty": "Customer",
                "invoice_id": inv["id"], "cash_account_id": operating["id"], "matched": False, "matched_to": None,
                "match_score": None, "discrepancy_flag": False, "discrepancy_type": None,
            })
            
    # S6: THE PERFECT STORM RECONCILIATION ANOMALY (AR Path: Recon -> Credit -> Cash)
    # We engineer Acme Corp explicitly underpaying systematically
    for i in range(1, 6):
        expected_amt = 5000.00
        received_amt = 4850.00 # Missing exactly $150 each time (systematic)
        dt = (TODAY - timedelta(days=i*3)).isoformat()
        ref = f"AR-STORM-00{i}"
        
        transactions.append({
            "id": gen_uuid(f"tx-storm-{i}-internal"), "source": "internal", "reference": ref, "amount": expected_amt,
            "currency": "USD", "transaction_date": dt, "description": f"Expected {ref}",
            "counterparty": "Acme Corp (PERFECT STORM)", "invoice_id": None, "cash_account_id": operating["id"],
            "matched": False, "matched_to": None, "match_score": None, "discrepancy_flag": False, "discrepancy_type": None,
        })
        transactions.append({
            "id": gen_uuid(f"tx-storm-{i}-bank"), "source": "bank", "reference": f"ACH-ACME-{i}", "amount": received_amt,
            "currency": "USD", "transaction_date": dt, "description": f"ACH IN ACME",
            "counterparty": "ACME", "invoice_id": None, "cash_account_id": operating["id"],
            "matched": False, "matched_to": None, "match_score": None, "discrepancy_flag": False, "discrepancy_type": None,
        })

    return transactions


def gen_cash_flow_forecasts(cash_accounts, ap_invoices, ar_invoices):
    forecasts = []
    operating = next(a for a in cash_accounts if a["account_name"] == "Operating Account")

    outflows = {}
    inflows = {}
    for inv in ap_invoices:
        if inv["status"] in ("approved", "awaiting_approval"):
            d = date.fromisoformat(inv["due_date"])
            if d > TODAY: outflows[d] = outflows.get(d, 0) + float(inv["total_amount"])
    for inv in ar_invoices:
        if inv["status"] != "paid":
            d = date.fromisoformat(inv["due_date"])
            if d > TODAY: inflows[d] = inflows.get(d, 0) + float(inv["total_amount"]) * 0.7

    for i in range(FORECAST_DAYS):
        d = TODAY + timedelta(days=i)
        forecasts.append({
            "id": gen_uuid(f"fc-{operating['id']}-{d.isoformat()}"), "forecast_date": d.isoformat(), "cash_account_id": operating["id"],
            "projected_inflow":  round(inflows.get(d, 0), 2), "projected_outflow": round(outflows.get(d, 0), 2),
            "actual_inflow": None, "actual_outflow": None, "notes": None,
        })
    return forecasts


def update_budgets_from_invoices(budgets, ap_invoices):
    by_dept_period = {(b["department_id"], b["period"]): b for b in budgets}
    for inv in ap_invoices:
        if inv["vendor_id"] is None: continue
        period = period_for_date(date.fromisoformat(inv["invoice_date"]))
        key = (inv["department_id"], period)
        if key not in by_dept_period: continue
        b = by_dept_period[key]
        if inv["status"] == "paid": b["spent"] = float(b["spent"]) + float(inv["total_amount"])
        elif inv["status"] in ("approved", "awaiting_approval"): b["committed"] = float(b["committed"]) + float(inv["total_amount"])
    
    for b in budgets:
        b["spent"] = round(b["spent"], 2)
        b["committed"] = round(b["committed"], 2)
        b["forecast"] = round(b["spent"] + b["committed"] * 1.05, 2)
    return budgets


def update_customer_outstanding(customers, receivables):
    by_cust = {}
    for r in receivables:
        if r["status"] in ("open", "partial"):
            by_cust[r["customer_id"]] = by_cust.get(r["customer_id"], 0) + float(r["amount"])
    for c in customers:
        c["total_outstanding"] = round(by_cust.get(c["id"], 0), 2)
    return customers

def clean(rows):
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]

def clear_db(client):
    print("\n" + "=" * 60)
    print("CLEARING OLD DATA FROM SUPABASE")
    print("=" * 60)
    tables = [
        "causal_links",
        "agent_decisions",
        "financial_state_snapshots",
        "reconciliation_report_items",
        "reconciliation_reports",
        "transactions",
        "receivables",
        "payments",
        "invoice_line_items",
        "budget_alerts",
        "invoices",
        "budgets",
        "vendor_risk_scores",
        "vendors",
        "customers",
        "departments",
        "cash_accounts",
        "cash_flow_forecasts",
    ]
    for t in tables:
        try:
            client.table(t).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            print(f"  Cleared table: {t}")
        except Exception as e:
            print(f"  Could not clear {t}: {e}")

def insert_to_supabase(data):
    if not SUPABASE_AVAILABLE:
        print("ERROR: supabase-py not installed. Run: pip install supabase python-dotenv")
        sys.exit(1)

    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env ")
        sys.exit(1)

    client = create_client(url, key)
    
    # 1. Clear DB first!
    clear_db(client)
    
    print("\n" + "=" * 60)
    print("INSERTING INTO SUPABASE")
    print("=" * 60)

    INSERT_ORDER = [
        "departments", "vendors", "vendor_risk_scores", "customers",
        "cash_accounts", "budgets", "invoices", "invoice_line_items",
        "payments", "receivables", "transactions", "cash_flow_forecasts",
    ]
    BATCH_SIZES = {"default": 500, "invoice_line_items": 500, "transactions": 500}

    for table in INSERT_ORDER:
        rows = clean(data[table])
        batch_size = BATCH_SIZES.get(table, BATCH_SIZES["default"])
        total = len(rows)
        inserted = 0

        for start in range(0, total, batch_size):
            batch = rows[start:start + batch_size]
            try:
                client.table(table).upsert(batch).execute()
                inserted += len(batch)
                print(f"  {table:25s} {inserted:>6d} / {total} rows", end="\r")
            except Exception as e:
                print(f"\n  [X] {table} batch failed: {e}")
                sys.exit(1)
        print(f"  * {table:25s} {total:>6d} rows inserted   ")

    print("\nDone. The ERP is now seeded with 10k rows including the S6 Perfect Storm scenarios!")

def generate_all():
    print("Generating reference data...")
    departments = gen_departments()
    vendors = gen_vendors()
    customers = gen_customers()
    cash_accounts = gen_cash_accounts()

    budgets = gen_budgets(departments)

    dept_ids = [d["id"] for d in departments]
    ap_invoices = gen_ap_invoices(vendors, dept_ids)
    ar_invoices = gen_ar_invoices(customers)

    line_items = gen_line_items(ap_invoices + ar_invoices)
    vendor_risk_scores = gen_vendor_risk_scores(vendors)
    payments = gen_payments(ap_invoices)

    receivables = gen_receivables(ar_invoices, customers)
    transactions = gen_transactions(ap_invoices, ar_invoices, cash_accounts, payments)
    forecasts = gen_cash_flow_forecasts(cash_accounts, ap_invoices, ar_invoices)

    update_budgets_from_invoices(budgets, ap_invoices)
    update_customer_outstanding(customers, receivables)

    return {
        "departments": departments, "vendors": vendors, "vendor_risk_scores": vendor_risk_scores,
        "customers": customers, "cash_accounts": cash_accounts, "budgets": budgets,
        "invoices": ap_invoices + ar_invoices, "invoice_line_items": line_items,
        "payments": payments, "receivables": receivables, "transactions": transactions,
        "cash_flow_forecasts": forecasts,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    data = generate_all()
    if not args.dry_run:
        insert_to_supabase(data)

if __name__ == "__main__":
    main()
