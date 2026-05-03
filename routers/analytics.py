from fastapi import APIRouter
from db.supabase_client import db
from datetime import date, timedelta
from typing import List, Dict, Any

router = APIRouter()

@router.get("/aging")
def get_aging_analysis():
    """Calculate aging buckets for all open receivables."""
    receivables = db.select("receivables", {"status": "open"})
    today = date.today()
    
    buckets = {
        "current": 0.0,
        "31-60": 0.0,
        "61-90": 0.0,
        "90+": 0.0
    }
    
    for r in receivables:
        due_date = date.fromisoformat(r["due_date"])
        amount = float(r["amount"])
        
        if due_date >= today:
            buckets["current"] += amount
        else:
            days_overdue = (today - due_date).days
            if days_overdue <= 30:
                buckets["current"] += amount # 0-30 is usually considered 'current' or 'near current'
            elif days_overdue <= 60:
                buckets["31-60"] += amount
            elif days_overdue <= 90:
                buckets["61-90"] += amount
            else:
                buckets["90+"] += amount
                
    return [
        {"name": k, "value": round(v, 2)} for k, v in buckets.items()
    ]

@router.get("/performance")
def get_performance_metrics():
    """Calculate DSO and Recovery Rate."""
    # Simplified DSO calculation
    all_receivables = db.select("receivables")
    open_receivables = [r for r in all_receivables if r["status"] in ("open", "partial")]
    paid_receivables = [r for r in all_receivables if r["status"] == "paid"]
    
    total_open = sum(float(r["amount"]) for r in open_receivables)
    total_paid = sum(float(r["amount"]) for r in paid_receivables)
    total_sales = total_open + total_paid
    
    # DSO = (AR / Sales) * 365 (assuming annualised or total period)
    # Here we'll use a 90 day window for relevance
    dso = (total_open / max(1, total_sales)) * 90 
    
    # Recovery Rate = (Paid / Total Due) * 100
    recovery_rate = (total_paid / max(1, total_sales)) * 100
    
    return {
        "dso": round(dso, 1),
        "recovery_rate": round(recovery_rate, 1),
        "total_receivables": round(total_sales, 2),
        "collected_amount": round(total_paid, 2),
        "outstanding_amount": round(total_open, 2)
    }

@router.get("/disputes")
def get_disputes():
    """Stakeholder portal: list receivables in 'notice' or 'escalated' stage for dispute resolution."""
    # We'll treat receivables with specific collection stages as 'disputed' or needing resolution
    disputes = db.select("receivables")
    filtered = [d for d in disputes if d["collection_stage"] in ("notice", "escalated")]
    
    # Enrich with customer names
    customers = {c["id"]: c["name"] for c in db.select("customers")}
    for d in filtered:
        d["customer_name"] = customers.get(d["customer_id"], "Unknown")
        
    return filtered
