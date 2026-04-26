"""routers/budget.py — Budget Management Agent endpoints."""

from fastapi import APIRouter, Query
from db.supabase_client import db
from config import get_supabase

router = APIRouter()

@router.get("/")
def list_budgets(department: str | None = Query(None)):
    filters = {"department": department} if department else {}
    return db.select("budgets", filters or None)

@router.get("/{department}/{period}")
def get_budget(department: str, period: str):
    b = db.get_budget(department, period)
    if not b:
        from fastapi import HTTPException
        raise HTTPException(404, f"No budget for {department}/{period}")
    utilisation = (b["spent"] + b["committed"]) / b["allocated"] * 100 if b["allocated"] else 0
    return {**b, "utilisation_pct": round(utilisation, 2)}

@router.get("/alerts/active")
def get_active_alerts():
    supabase = get_supabase()
    return (supabase.table("budget_alerts").select("*")
            .eq("acknowledged", False)
            .order("created_at", desc=True).execute().data)

@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str):
    return db.update("budget_alerts", {"id": alert_id}, {"acknowledged": True})

@router.post("/seed")
def seed_budgets(body: dict):
    """Seed budget rows for demo. Body: [{department, period, allocated, alert_threshold}]"""
    created = []
    for row in body.get("budgets", []):
        created.append(db.insert("budgets", {
            "department":       row["department"],
            "period":           row["period"],
            "allocated":        row["allocated"],
            "spent":            row.get("spent", 0),
            "committed":        row.get("committed", 0),
            "alert_threshold":  row.get("alert_threshold", 90.0),
        }))
    return {"created": len(created), "budgets": created}
