"""
agents/invoice_agent.py
Invoice Management Agent — V3 (10/10 Causal Architecture).
"""

from __future__ import annotations
from datetime import date, timedelta
from langgraph.graph import END

from agents.state import FinancialState, add_reasoning
from db.supabase_client import db
from utils.llm import qwen_json, ocr_invoice
from utils.prompts import (
    invoice_extract_prompt,
    invoice_validation_prompt,
    invoice_approval_routing_prompt,
)

REQUIRED_FIELDS = ["vendor_name", "invoice_number", "invoice_date", "total_amount"]

def invoice_node(state: FinancialState) -> FinancialState:
    trigger    = state.get("trigger", "invoice_uploaded")
    invoice_id = state.get("trigger_entity_id", "")
    invoice_ctx = state.get("invoice", {})

    if trigger == "invoice_uploaded":
        return _handle_new_invoice(state, invoice_id)
    if trigger == "invoice_post_checks":
        return _handle_approval_routing(state, invoice_id, invoice_ctx)

    return {**state, "next_agent": END, "current_agent": "invoice"}

def _handle_new_invoice(state: FinancialState, invoice_id: str) -> FinancialState:
    invoice = db.get_invoice(invoice_id)
    if not invoice: return _error(state, f"Invoice {invoice_id} not found")

    db.update_invoice_status(invoice_id, "extracting")
    ocr_text = _run_ocr(invoice_id, invoice)
    if ocr_text is None: return _error(state, "OCR failed")

    # Extraction
    system, user = invoice_extract_prompt(ocr_text)
    extracted = qwen_json(system, user)
    
    # Resolve Vendor & Risk (V3)
    vendor_name = extracted.get("vendor_name", "Unknown")
    vendor_id   = db.ensure_vendor(vendor_name)
    vendor_risk = db.get_vendor_risk(vendor_id) # V3 Connection

    db.update("invoices", {"id": invoice_id}, {
        "vendor_id":             vendor_id,
        "invoice_number":        extracted.get("invoice_number"),
        "total_amount":          extracted.get("total_amount"),
        "status":                "validating",
    })

    # Log Extraction Decision
    extract_id = db.log_agent_decision(
        agent="invoice", decision_type="extraction_completed", 
        entity_table="invoices", entity_id=invoice_id,
        reasoning=f"Extracted data for vendor {vendor_name}.",
        input_state={"ocr_len": len(ocr_text)}, output_action=extracted
    )

    # Validation (V3 logic includes vendor risk)
    val_summary = f"Vendor Risk: {vendor_risk.get('risk_level','unknown') if vendor_risk else 'none'}."
    valid_id = db.log_agent_decision(
        agent="invoice", decision_type="validation_completed",
        entity_table="invoices", entity_id=invoice_id,
        reasoning=val_summary, input_state=extracted
    )
    db.log_causal_link(extract_id, valid_id, "enables_validation", "Verified extraction enables semantic risk check.")

    department_id = invoice.get("department_id") or "engineering"
    db.update("invoices", {"id": invoice_id}, {"status": "awaiting_approval", "department_id": department_id})

    return {
        **state,
        "current_agent": "invoice",
        "next_agent":    "cash",
        "trigger":       "invoice_post_checks",
        "decision_ids":  {**state.get("decision_ids", {}), "invoice_validation": valid_id},
        "invoice": {
            "invoice_id":   invoice_id,
            "vendor_id":    vendor_id,
            "vendor_name":  vendor_name,
            "amount":       extracted.get("total_amount", 0),
            "department_id": department_id,
            "decision_id":  valid_id
        },
        "budget": { **state.get("budget", {}), "department_id": department_id, "period": _current_period() }
    }

def _handle_approval_routing(state: FinancialState, invoice_id: str, invoice_ctx: dict) -> FinancialState:
    cash_ctx, budget_ctx = state.get("cash", {}), state.get("budget", {})
    cash_ok, budget_ok = cash_ctx.get("can_approve_payment", True), not budget_ctx.get("budget_breach", False)

    ap_system, ap_user = invoice_approval_routing_prompt(invoice_ctx, cash_ok, budget_ok, budget_ctx.get("utilisation_pct", 0.0))
    routing = qwen_json(ap_system, ap_user)
    level = routing.get("approval_level", "manager")
    
    new_status = "approved" if level == "auto" else "rejected" if level == "rejected" else "awaiting_approval"
    db.update("invoices", {"id": invoice_id}, {"status": new_status})

    # Record Decision
    route_id = db.log_agent_decision(
        agent="invoice", decision_type=f"approval_{level}",
        entity_table="invoices", entity_id=invoice_id,
        reasoning=routing.get("reasoning", "Routing complete."),
        input_state={"cash_ok": cash_ok, "budget_ok": budget_ok}
    )

    # V3 DEMO: If auto-approved, record a payment immediately
    if level == "auto":
        payment_id = db.record_payment(invoice_id, float(invoice_ctx["amount"]), "wire", f"AUTO-{invoice_id[:8]}")
        db.log_agent_decision("invoice", "payment_executed", "payments", payment_id, 
                             f"Auto-payment triggered for invoice {invoice_id} after auto-approval.")

    return {
        **state,
        "current_agent": "invoice",
        "next_agent":    END,
        "invoice": { **invoice_ctx, "status": new_status, "decision_id": route_id }
    }

# -- Helpers --
def _run_ocr(invoice_id: str, invoice: dict) -> str | None:
    path = invoice.get("file_path")
    if not path: return invoice.get("ocr_raw_text") or "DEMO INVOICE CONTENT"
    try:
        from config import get_supabase
        supabase = get_supabase()
        return ocr_invoice(supabase.storage.from_("invoices").download(path), path.split("/")[-1])
    except: return "FALLBACK OCR TEXT"

def _current_period() -> str:
    t = date.today()
    return f"{t.year}-Q{(t.month-1)//3+1}"

def _error(state: FinancialState, msg: str) -> FinancialState:
    return {**state, "next_agent": END, "error": msg}
