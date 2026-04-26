"""routers/credit.py — Credit & Collection Agent endpoints (V2)."""

from fastapi import APIRouter, Query, BackgroundTasks, HTTPException
from db.supabase_client import db
from config import get_supabase

router = APIRouter()

@router.get("/customers")
def list_customers(risk_level: str = Query(None)):
    supabase = get_supabase()
    query = supabase.table("customers").select("*")
    if risk_level: query = query.eq("risk_level", risk_level)
    return query.execute().data

@router.get("/aging")
def get_aging_buckets():
    from datetime import date
    today = date.today()
    supabase = get_supabase()
    rows = supabase.table("receivables").select("amount, due_date, status").eq("status", "open").execute().data

    buckets = {"current": 0, "1_30": 0, "31_60": 0, "61_90": 0, "over_90": 0}
    for r in rows:
        try:
            due = date.fromisoformat(str(r["due_date"]))
            overdue = (today - due).days
            amount = float(r.get("amount", 0) or 0)
            if overdue <= 0: buckets["current"] += amount
            elif overdue <= 30: buckets["1_30"] += amount
            elif overdue <= 60: buckets["31_60"] += amount
            elif overdue <= 90: buckets["61_90"] += amount
            else: buckets["over_90"] += amount
        except: pass

    return {
        "buckets": {k: round(v, 2) for k, v in buckets.items()},
        "total_open": round(sum(buckets.values()), 2),
        "currency": "USD"
    }

@router.get("/events/{customer_id}")
def get_credit_events(customer_id: str):
    """V2: Get reasoning trace for a customer from agent_decisions."""
    decisions = db.select("agent_decisions", {"entity_id": customer_id, "agent": "credit"})
    return {"customer_id": customer_id, "decisions": sorted(decisions, key=lambda d: d["created_at"])}

@router.post("/assess/{customer_id}")
def assess_customer(customer_id: str, background_tasks: BackgroundTasks):
    def _run():
        from agents.graph import graph
        from agents.state import initial_state
        state = initial_state("customer_payment_check", customer_id)
        graph.invoke(state)
    background_tasks.add_task(_run)
    return {"message": "Assessment started"}
