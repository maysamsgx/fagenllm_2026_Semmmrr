"""routers/budget.py — Budget Management Agent endpoints (V2)."""

from datetime import date
from fastapi import APIRouter, Query, HTTPException
from db.supabase_client import db
from config import get_supabase

router = APIRouter()


def current_period() -> str:
    today = date.today()
    return f"{today.year}-Q{(today.month - 1) // 3 + 1}"


@router.get("/periods")
def list_periods():
    supabase = get_supabase()
    rows = supabase.table("budgets").select("period").execute().data
    periods = sorted({r["period"] for r in rows if r.get("period")}, reverse=True)
    return {"periods": periods, "current": current_period()}


@router.get("/")
def list_budgets(department_id: str = None, period: str = None):
    supabase = get_supabase()
    resolved_period = period or current_period()

    query = supabase.table("budgets").select("*, departments(name)").eq("period", resolved_period)
    if department_id:
        query = query.eq("department_id", department_id)
    data = query.execute().data

    if not data and not period:
        rows = supabase.table("budgets").select("period").execute().data
        if rows:
            resolved_period = max({r["period"] for r in rows if r.get("period")})
            query = supabase.table("budgets").select("*, departments(name)").eq("period", resolved_period)
            if department_id:
                query = query.eq("department_id", department_id)
            data = query.execute().data

    for item in data:
        item["department"] = item.get("department_id")
    return data

@router.get("/alerts/active")
def get_active_alerts():
    supabase = get_supabase()
    data = (supabase.table("budget_alerts").select("*")
            .eq("acknowledged", False)
            .order("created_at", desc=True).execute().data)
    for item in data:
        item["department"] = item.get("department_id")
    return data

@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str):
    return db.update("budget_alerts", {"id": alert_id}, {"acknowledged": True})
