"""routers/budget.py — Budget Management Agent endpoints (V2)."""

from fastapi import APIRouter, Query, HTTPException
from db.supabase_client import db
from config import get_supabase

router = APIRouter()

@router.get("/")
def list_budgets(department_id: str = None):
    supabase = get_supabase()
    query = supabase.table("budgets").select("*, departments(name)")
    if department_id: query = query.eq("department_id", department_id)
    return query.execute().data

@router.get("/alerts/active")
def get_active_alerts():
    supabase = get_supabase()
    return (supabase.table("budget_alerts").select("*")
            .eq("acknowledged", False)
            .order("created_at", desc=True).execute().data)

@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str):
    return db.update("budget_alerts", {"id": alert_id}, {"acknowledged": True})
