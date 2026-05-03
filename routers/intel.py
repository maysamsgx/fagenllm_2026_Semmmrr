"""routers/intel.py — System Intelligence & Shared State endpoints (V2)."""

from fastapi import APIRouter, Query
from db.supabase_client import db
from config import get_supabase

router = APIRouter()


@router.get("")
@router.get("/")
def get_intel_summary():
    """Root endpoint: latest snapshot + decision/causal-link counts."""
    supabase = get_supabase()
    snapshot = db.get_latest_snapshot()
    decision_count = supabase.table("agent_decisions").select("id", count="exact").execute().count or 0
    causal_count = supabase.table("causal_links").select("id", count="exact").execute().count or 0
    return {
        "latest_snapshot": snapshot,
        "total_decisions": decision_count,
        "total_causal_links": causal_count,
    }


@router.get("/snapshot/latest")
def get_latest_snapshot():
    return db.get_latest_snapshot()

@router.get("/snapshots")
def list_snapshots(limit: int = Query(50, le=100)):
    supabase = get_supabase()
    return supabase.table("financial_state_snapshots") \
        .select("*").order("snapshot_time", desc=True).limit(limit).execute().data

@router.get("/decisions")
def get_decisions(entity_table: str = None, entity_id: str = None):
    filters = {}
    if entity_table: filters["entity_table"] = entity_table
    if entity_id: filters["entity_id"] = entity_id
    return db.select("agent_decisions", filters or None)

@router.get("/causal-graph")
def get_causal_graph(limit: int = 100):
    """Returns nodes and edges for the global causal relationship graph."""
    supabase = get_supabase()
    decisions = supabase.table("agent_decisions").select("*").order("created_at", desc=True).limit(limit).execute().data
    links = supabase.table("causal_links").select("*").limit(limit * 2).execute().data
    
    return {
        "nodes": decisions,
        "edges": links
    }
