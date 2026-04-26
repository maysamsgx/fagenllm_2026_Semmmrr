"""routers/credit.py — Credit & Collection Agent endpoints."""

from fastapi import APIRouter, Query, BackgroundTasks, HTTPException
from db.supabase_client import db
from config import get_supabase

router = APIRouter()


@router.get("/customers")
def list_customers(risk_level: str | None = Query(None)):
    """List customers, optionally filtered by risk level."""
    filters = {"risk_level": risk_level} if risk_level else None
    return db.select("customers", filters)


@router.get("/customers/{customer_id}")
def get_customer(customer_id: str):
    c = db.get_customer(customer_id)
    if not c:
        raise HTTPException(404, f"Customer {customer_id} not found")
    receivables = db.select("receivables", {"customer_id": customer_id})
    return {**c, "receivables": receivables}


@router.post("/assess/{customer_id}")
def assess_customer(customer_id: str, background_tasks: BackgroundTasks):
    """Trigger credit risk assessment for a specific customer."""
    if not db.get_customer(customer_id):
        raise HTTPException(404, f"Customer {customer_id} not found")

    def _run():
        from agents.graph import graph
        from agents.state import initial_state
        state = initial_state("customer_payment_check", customer_id)
        state["credit"] = {"customer_id": customer_id}
        graph.invoke(state)

    background_tasks.add_task(_run)
    return {"message": f"Credit assessment started for {customer_id}"}


@router.get("/receivables")
def list_receivables(status: str | None = Query(None),
                      overdue_only: bool = Query(False)):
    """List all receivables with optional filters."""
    supabase = get_supabase()
    from datetime import date
    query = supabase.table("receivables").select(
        "*, customers(name, risk_level)"
    ).order("due_date")
    if status:
        query = query.eq("status", status)
    if overdue_only:
        query = query.lt("due_date", date.today().isoformat())
    return query.execute().data


@router.get("/aging")
def get_aging_buckets():
    """
    Accounts receivable aging report.
    Buckets: current, 1-30, 31-60, 61-90, 90+ days overdue.
    """
    from datetime import date
    today    = date.today()
    supabase = get_supabase()
    rows     = (supabase.table("receivables").select("amount, due_date, status")
                .eq("status", "open").execute().data)

    buckets = {"current": 0, "1_30": 0, "31_60": 0, "61_90": 0, "over_90": 0}
    for r in rows:
        try:
            due     = date.fromisoformat(str(r["due_date"]))
            overdue = (today - due).days
            amount  = float(r.get("amount", 0) or 0)
            if overdue <= 0:
                buckets["current"] += amount
            elif overdue <= 30:
                buckets["1_30"]    += amount
            elif overdue <= 60:
                buckets["31_60"]   += amount
            elif overdue <= 90:
                buckets["61_90"]   += amount
            else:
                buckets["over_90"] += amount
        except Exception:
            pass

    total = sum(buckets.values())
    return {
        "buckets":     {k: round(v, 2) for k, v in buckets.items()},
        "total_open":  round(total, 2),
        "currency":    "USD",
    }


@router.get("/events/{customer_id}")
def get_credit_events(customer_id: str):
    """Get reasoning trace for a customer — XAI audit log."""
    events = db.select("agent_events", {"entity_id": customer_id})
    events = [e for e in events if e.get("agent") == "credit"]
    events.sort(key=lambda e: e.get("created_at", ""))
    return {"customer_id": customer_id, "events": events}
