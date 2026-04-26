"""routers/payment.py — Payments Layer endpoints (V3)."""

from fastapi import APIRouter, Query
from db.supabase_client import db
from config import get_supabase

router = APIRouter()

@router.get("/")
def list_payments(status: str = Query(None)):
    supabase = get_supabase()
    query = supabase.table("payments").select("*, invoices(invoice_number, vendor_id, vendors(name))")
    if status: query = query.eq("status", status)
    return query.execute().data

@router.get("/{payment_id}")
def get_payment(payment_id: str):
    supabase = get_supabase()
    payment = supabase.table("payments").select("*, invoices(*)").eq("id", payment_id).single().execute().data
    # Also get related transactions
    txs = supabase.table("transactions").select("*").eq("payment_id", payment_id).execute().data
    return {**payment, "transactions": txs}
