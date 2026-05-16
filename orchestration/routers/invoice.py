"""
routers/invoice.py
Endpoints for managing invoice uploads and their reconciliation workflows.
This router triggers the LangGraph agent whenever a new invoice is uploaded.
"""

import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel

from execution.db.supabase_client import db
from orchestration.agents.graph import graph
from orchestration.agents.state import initial_state
from config import get_supabase

router = APIRouter()

class ApproveRequest(BaseModel):
    approver_id: str
    notes: str = ""

class RejectRequest(BaseModel):
    reason: str
    approver_id: str

@router.post("/upload")
async def upload_invoice(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    department_id: str = Query(default="engineering"),
):
    allowed = {"application/pdf", "image/jpeg", "image/png", "image/jpg"}
    if file.content_type not in allowed:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")

    invoice_id = str(uuid.uuid4())
    file_bytes = await file.read()

    file_path = f"{invoice_id}/{file.filename}"
    try:
        supabase = get_supabase()
        supabase.storage.from_("invoices").upload(path=file_path, file=file_bytes)
    except Exception as e:
        raise HTTPException(500, f"File upload failed: {e}")

    db.insert("invoices", {
        "id":            invoice_id,
        "file_path":     file_path,
        "department_id": department_id,
        "status":        "pending",
    })

    background_tasks.add_task(_run_invoice_graph, invoice_id)

    return {"invoice_id": invoice_id, "status": "pending"}

def _run_invoice_graph(invoice_id: str) -> None:
    try:
        # Initialize the graph state to begin processing the new invoice.
        state = initial_state(trigger="invoice_uploaded", entity_id=invoice_id)
        graph.invoke(state)
    except Exception as e:
        db.update_invoice_status(invoice_id, "pending", {"rejection_reason": f"System error: {str(e)}"})
        db.log_agent_decision("invoice", "graph_error", "invoices", invoice_id, f"Graph failed: {e}")

@router.get("/{invoice_id}")
def get_invoice(invoice_id: str):
    invoice = db.get_invoice(invoice_id)
    if not invoice: raise HTTPException(404, "Not found")
    
    # Map for UI
    invoice["vendor_name"] = invoice.get("vendors", {}).get("name") if invoice.get("vendors") else None
    invoice["department"] = invoice.get("department_id")
    return invoice

@router.get("/")
def list_invoices(status: str = None, department_id: str = None):
    supabase = get_supabase()
    # Thesis V4 Improvement: Limit result set to avoid PostgREST 'IN' clause URL length limits.
    query = supabase.table("invoices").select("*, vendors(name)").order("created_at", desc=True).limit(50)
    if status: query = query.eq("status", status)
    if department_id: query = query.eq("department_id", department_id)
    data = query.execute().data
    
    # Enrich with latest governance status
    invoice_ids = [i["id"] for i in data]
    if invoice_ids:
        # Fetch latest governance decisions for these invoices
        audit_decisions = (supabase.table("agent_decisions")
                          .select("entity_id, output_action")
                          .eq("agent", "governance")
                          .in_("entity_id", invoice_ids)
                          .order("created_at", desc=True)
                          .execute().data)
        
        # Create a mapping (Safe access to output_action)
        audit_map = {}
        audit_safe_map = {}
        for d in audit_decisions:
            eid = d.get("entity_id")
            oa = d.get("output_action")
            if eid and isinstance(oa, dict):
                # Only keep the latest decision per entity (query is ordered by created_at)
                if eid not in audit_map:
                    status = oa.get("status", "pending")
                    audit_map[eid] = status.lower() if isinstance(status, str) else "pending"
                    audit_safe_map[eid] = oa.get("is_audit_safe", False)
        
        for item in data:
            item["governance_status"] = audit_map.get(item["id"], "pending")
            item["is_audit_safe"] = audit_safe_map.get(item["id"], False)
            item["vendor_name"] = item.get("vendors", {}).get("name") if item.get("vendors") else None
            item["department"] = item.get("department_id")
    
    return data

@router.post("/{invoice_id}/approve")
def approve_invoice(invoice_id: str, body: ApproveRequest):
    invoice = db.get_invoice(invoice_id)
    if not invoice: raise HTTPException(404, "Not found")
    
    db.update("invoices", {"id": invoice_id}, {"status": "approved"})
    db.log_agent_decision("invoice", "manually_approved", "invoices", invoice_id, f"Approved by {body.approver_id}. {body.notes}")
    
    # Scenario 1, Step 7: Update cash flow forecast to reflect the newly committed liability
    try:
        from orchestration.agents.graph import graph
        from orchestration.agents.state import initial_state
        state = initial_state("cash_position_refresh", invoice_id)
        graph.invoke(state)
    except Exception:
        pass

    return {"status": "approved"}

@router.get("/{invoice_id}/causal-trace")
def get_causal_trace(invoice_id: str):
    """
    Full causal trail for an invoice: every decision row, every causal link,
    and the latest financial-state snapshot at the time of the last decision.
    The UI's TracePanel reads `trace`, which is the same decisions reshaped
    into the TraceEvent shape it renders.
    """
    supabase = get_supabase()

    # Pull every decision the invoice agent (or downstream agents) wrote
    # against this invoice OR against payments that came from it.
    decisions = db.select("agent_decisions", {"entity_id": invoice_id})
    payments = supabase.table("payments").select("id").eq("invoice_id", invoice_id).execute().data or []
    for p in payments:
        decisions.extend(db.select("agent_decisions", {"entity_id": p["id"]}))

    decisions = sorted(decisions, key=lambda d: d["created_at"])
    dec_ids = [d["id"] for d in decisions]

    links = []
    if dec_ids:
        in_list = ",".join(dec_ids)
        links = (supabase.table("causal_links")
                 .select("id, cause_decision_id, effect_decision_id, relationship_type, strength, explanation, created_at")
                 .or_(f"cause_decision_id.in.({in_list}),effect_decision_id.in.({in_list})")
                 .execute().data) or []

    snapshot = None
    if decisions:
        latest_dec = decisions[-1]
        if latest_dec.get("snapshot_id"):
            res = (supabase.table("financial_state_snapshots")
                   .select("*").eq("id", latest_dec["snapshot_id"]).execute().data)
            snapshot = res[0] if res else None

    trace = [
        {
            "agent": d.get("agent"),
            "event_type": d.get("decision_type"),
            "timestamp": d.get("created_at"),
            "reasoning": d.get("technical_explanation") or d.get("reasoning") or "",
            "technical_explanation": d.get("technical_explanation"),
            "business_explanation": d.get("business_explanation"),
            "causal_explanation": d.get("causal_explanation"),
            "details": {
                "input": d.get("input_state") or {},
                "output": d.get("output_action") or {},
                "confidence": d.get("confidence"),
            },
        }
        for d in decisions
    ]

    return {
        "decisions": decisions,
        "links": links,
        "snapshot": snapshot,
        "trace": trace,
    }
