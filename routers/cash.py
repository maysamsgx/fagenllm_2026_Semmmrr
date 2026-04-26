"""routers/cash.py — Cash Management Agent endpoints."""

from fastapi import APIRouter, Query
from db.supabase_client import db
from config import get_supabase

router = APIRouter()

@router.get("/position")
def get_cash_position():
    accounts = db.get_cash_balances()
    total = sum(float(a.get("current_balance", 0) or 0) for a in accounts)
    return {"total_balance": round(total, 2), "accounts": accounts}

@router.get("/forecast")
def get_forecast(days: int = Query(7, le=30)):
    from datetime import date, timedelta
    supabase = get_supabase()
    start = date.today().isoformat()
    end   = (date.today() + timedelta(days=days)).isoformat()
    rows  = (supabase.table("cash_flow_forecasts").select("*")
             .gte("forecast_date", start).lte("forecast_date", end)
             .order("forecast_date").execute().data)
    return {"days": days, "forecast": rows}

@router.get("/accounts")
def list_accounts():
    return db.get_cash_balances()

@router.patch("/accounts/{account_id}/balance")
def update_balance(account_id: str, balance: float):
    from datetime import datetime, timezone
    return db.update("cash_accounts", {"id": account_id},
                     {"current_balance": balance,
                      "last_updated": datetime.now(timezone.utc).isoformat()})
