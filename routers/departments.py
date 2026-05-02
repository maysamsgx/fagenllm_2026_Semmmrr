"""routers/departments.py — Departments lookup endpoint."""

from fastapi import APIRouter
from db.supabase_client import db

router = APIRouter()


@router.get("")
def list_departments():
    rows = db.select("departments", {})
    return [{"id": r["id"], "name": r.get("name") or r["id"]} for r in rows]
