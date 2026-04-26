"""
routers/invoice.py
FastAPI router for the Invoice Management Agent.

Endpoints:
  POST /invoice/upload          — upload file, create DB record, trigger graph
  GET  /invoice/{id}            — get invoice status + extracted fields
  GET  /invoice/                — list invoices with optional status filter
  POST /invoice/{id}/approve    — manually approve (manager action)
  POST /invoice/{id}/reject     — reject with reason
  GET  /invoice/{id}/trace      — get reasoning trace (XAI audit log)
"""

import uuid
from typing import Literal
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel

from db.supabase_client import db
from agents.graph import graph
from agents.state import initial_state
from config import get_supabase

router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────────────

class ApproveRequest(BaseModel):
    approver_id: str
    notes: str = ""

class RejectRequest(BaseModel):
    reason: str
    approver_id: str


# ── Upload endpoint ───────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_invoice(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    department: str = Query(default="general"),
):
    """
    Upload an invoice file (PDF or image).
    1. Saves file to Supabase Storage bucket 'invoices'
    2. Creates a DB record in invoices table
    3. Fires the LangGraph in the background (non-blocking)
    Returns immediately with invoice_id so frontend can poll status.
    """
    # Validate file type
    allowed = {"application/pdf", "image/jpeg", "image/png", "image/jpg"}
    if file.content_type not in allowed:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}. "
                                  f"Allowed: PDF, JPEG, PNG")

    invoice_id = str(uuid.uuid4())
    file_bytes = await file.read()

    # Upload to Supabase Storage
    file_path = f"{invoice_id}/{file.filename}"
    try:
        supabase = get_supabase()
        supabase.storage.from_("invoices").upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": file.content_type},
        )
    except Exception as e:
        raise HTTPException(500, f"File upload failed: {e}")

    # Create invoice record in DB
    db.create_invoice({
        "id":         invoice_id,
        "file_path":  file_path,
        "department": department,
        "status":     "pending",
    })

    # Run graph in background so the HTTP response returns immediately
    background_tasks.add_task(_run_invoice_graph, invoice_id)

    return {
        "invoice_id": invoice_id,
        "status":     "pending",
        "message":    "Invoice received. Processing started. Poll /invoice/{id} for status.",
    }


def _run_invoice_graph(invoice_id: str) -> None:
    """Background task: runs the LangGraph for this invoice."""
    try:
        state = initial_state(trigger="invoice_uploaded", entity_id=invoice_id)
        graph.invoke(state)
    except Exception as e:
        db.update_invoice_status(invoice_id, "pending", {
            "rejection_reason": f"Processing error: {str(e)}"
        })
        db.log_agent_event("invoice", "graph_error", invoice_id, {"error": str(e)},
                           reasoning=f"LangGraph execution failed: {e}")


# ── Status / detail endpoint ──────────────────────────────────────────────────

@router.get("/{invoice_id}")
def get_invoice(invoice_id: str):
    """Get full invoice record including extracted fields and current status."""
    invoice = db.get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(404, f"Invoice {invoice_id} not found")
    return invoice


@router.get("/")
def list_invoices(
    status: str | None = Query(None),
    department: str | None = Query(None),
    limit: int = Query(50, le=200),
):
    """List invoices, optionally filtered by status or department."""
    filters = {}
    if status:
        filters["status"] = status
    if department:
        filters["department"] = department

    supabase = get_supabase()
    query = supabase.table("invoices").select("*").order("created_at", desc=True).limit(limit)
    for k, v in filters.items():
        query = query.eq(k, v)
    return query.execute().data


# ── Approval actions ──────────────────────────────────────────────────────────

@router.post("/{invoice_id}/approve")
def approve_invoice(invoice_id: str, body: ApproveRequest):
    """
    Manually approve an invoice (called by a manager via the UI).
    Updates status, logs approval event with approver ID.
    """
    invoice = db.get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(404, f"Invoice {invoice_id} not found")
    if invoice["status"] not in ("awaiting_approval", "pending"):
        raise HTTPException(400, f"Cannot approve invoice with status '{invoice['status']}'")

    from datetime import datetime, timezone
    db.update("invoices", {"id": invoice_id}, {
        "status":      "approved",
        "approver_id": body.approver_id,
        "approved_at": datetime.now(timezone.utc).isoformat(),
    })

    reasoning = f"Manually approved by {body.approver_id}. Notes: {body.notes or 'none'}"
    db.log_agent_event("invoice", "manually_approved", invoice_id,
                       {"approver_id": body.approver_id, "notes": body.notes},
                       reasoning=reasoning)

    return {"invoice_id": invoice_id, "status": "approved", "reasoning": reasoning}


@router.post("/{invoice_id}/reject")
def reject_invoice(invoice_id: str, body: RejectRequest):
    """Reject an invoice with a reason."""
    invoice = db.get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(404, f"Invoice {invoice_id} not found")

    db.update("invoices", {"id": invoice_id}, {
        "status":           "rejected",
        "rejection_reason": body.reason,
        "approver_id":      body.approver_id,
    })

    db.log_agent_event("invoice", "manually_rejected", invoice_id,
                       {"reason": body.reason, "approver_id": body.approver_id},
                       reasoning=f"Rejected by {body.approver_id}: {body.reason}")

    return {"invoice_id": invoice_id, "status": "rejected"}


# ── XAI trace endpoint ────────────────────────────────────────────────────────

@router.get("/{invoice_id}/trace")
def get_reasoning_trace(invoice_id: str):
    """
    Return the full reasoning trace for an invoice.
    This is the XAI audit trail shown in the demo UI.
    Each entry has: agent, event_type, reasoning, created_at
    """
    events = db.select("agent_events", {"entity_id": invoice_id})
    if not events:
        return {"invoice_id": invoice_id, "trace": [], "message": "No events yet"}

    # Sort chronologically
    events.sort(key=lambda e: e.get("created_at", ""))
    return {
        "invoice_id": invoice_id,
        "event_count": len(events),
        "trace": [
            {
                "agent":      e["agent"],
                "event_type": e["event_type"],
                "reasoning":  e["reasoning"],
                "details":    e["details"],
                "timestamp":  e["created_at"],
            }
            for e in events
        ],
    }
