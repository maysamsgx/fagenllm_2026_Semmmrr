"""
agents/invoice_agent.py
Invoice Management Agent — the primary demo agent.

Pipeline per run:
  1. EXTRACT  — Baidu OCR → Qwen3 JSON extraction → save to Supabase
  2. VALIDATE — field validation + duplicate check + vendor anomaly detection
  3. CHECK    — query Cash agent for liquidity, query Budget agent for headroom
  4. ROUTE    — Qwen3 approval routing decision (auto / manager / senior / reject)
  5. LOG      — reasoning trace written to agent_events (XAI audit trail)

Cross-agent coordination (Scenario 1 from thesis Appendix A):
  invoice_uploaded → invoice_node → cash_node → budget_node → invoice_node (routing) → END
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
MIN_CONFIDENCE  = 60


def invoice_node(state: FinancialState) -> FinancialState:
    trigger    = state.get("trigger", "invoice_uploaded")
    invoice_id = state.get("trigger_entity_id", "")
    invoice_ctx = state.get("invoice", {})

    if trigger == "invoice_uploaded":
        return _handle_new_invoice(state, invoice_id)
    if trigger == "invoice_post_checks":
        return _handle_approval_routing(state, invoice_id, invoice_ctx)

    return {**state, "next_agent": END, "current_agent": "invoice",
            "error": f"invoice_node: unknown trigger '{trigger}'"}


def _handle_new_invoice(state: FinancialState, invoice_id: str) -> FinancialState:
    invoice = db.get_invoice(invoice_id)
    if not invoice:
        return _error(state, f"Invoice {invoice_id} not found")

    db.update_invoice_status(invoice_id, "extracting")

    # Step 1 — OCR
    ocr_text = _run_ocr(invoice_id, invoice)
    if ocr_text is None:
        return _error(state, f"OCR failed for invoice {invoice_id}")

    # Step 2 — Qwen3 extraction
    system, user = invoice_extract_prompt(ocr_text)
    extracted = qwen_json(system, user)

    if "error" in extracted:
        db.update_invoice_status(invoice_id, "pending", {"ocr_raw_text": ocr_text})
        return _error(state, f"Extraction failed: {extracted.get('raw','')[:200]}")

    db.update("invoices", {"id": invoice_id}, {
        "vendor_name":           extracted.get("vendor_name"),
        "vendor_tax_id":         extracted.get("vendor_tax_id"),
        "invoice_number":        extracted.get("invoice_number"),
        "invoice_date":          extracted.get("invoice_date"),
        "due_date":              extracted.get("due_date") or _estimate_due_date(extracted.get("invoice_date")),
        "total_amount":          extracted.get("total_amount"),
        "currency":              extracted.get("currency", "USD"),
        "tax_amount":            extracted.get("tax_amount"),
        "line_items":            extracted.get("line_items", []),
        "extraction_confidence": extracted.get("confidence", 0),
        "ocr_raw_text":          ocr_text,
        "status":                "validating",
    })

    # Step 3 — Validation
    missing = [f for f in REQUIRED_FIELDS if not extracted.get(f)]
    if missing:
        reason = f"Missing required fields: {', '.join(missing)}"
        db.update_invoice_status(invoice_id, "pending", {"rejection_reason": reason})
        db.log_agent_event("invoice", "validation_failed", invoice_id,
                           {"missing_fields": missing}, reasoning=reason)
        return _error(state, reason)

    if _is_duplicate(extracted, invoice_id):
        reason = f"Duplicate invoice number {extracted.get('invoice_number')}"
        db.update_invoice_status(invoice_id, "rejected", {"rejection_reason": reason})
        db.log_agent_event("invoice", "rejected_duplicate", invoice_id, {}, reasoning=reason)
        return {**state, "current_agent": "invoice", "next_agent": END,
                "invoice": {**state.get("invoice", {}), "invoice_id": invoice_id, "status": "rejected"}}

    confidence = extracted.get("confidence", 0)
    vendor_history = _get_vendor_history(extracted.get("vendor_name", ""))
    val_system, val_user = invoice_validation_prompt(extracted, vendor_history)
    validation = qwen_json(val_system, val_user)

    val_summary = validation.get("review_reason") or "No anomalies detected"
    state = add_reasoning(state, "invoice", "validation",
                          f"Invoice {invoice_id} validated. Confidence: {confidence}%. "
                          f"Issues: {validation.get('issues', [])}. {val_summary}")

    db.log_agent_event("invoice", "validated", invoice_id, {
        "confidence": confidence,
        "issues": validation.get("issues", []),
        "anomalies": validation.get("anomalies", []),
    }, reasoning=val_summary)

    # Step 4 — Trigger cross-agent checks
    amount     = extracted.get("total_amount", 0) or 0
    department = invoice.get("department") or "general"

    db.update("invoices", {"id": invoice_id}, {
        "status":     "awaiting_approval",
        "department": department,
    })

    return {
        **state,
        "current_agent": "invoice",
        "next_agent":    "cash",
        "trigger":       "invoice_post_checks",
        "invoice": {
            "invoice_id":   invoice_id,
            "vendor_name":  extracted.get("vendor_name"),
            "amount":       amount,
            "currency":     extracted.get("currency", "USD"),
            "department":   department,
            "due_date":     extracted.get("due_date"),
            "status":       "awaiting_approval",
            "extraction_confidence": confidence,
            "requires_approval": True,
        },
        "budget": {
            **state.get("budget", {}),
            "department": department,
            "period":     _current_period(),
        },
    }


def _handle_approval_routing(state: FinancialState,
                               invoice_id: str,
                               invoice_ctx: dict) -> FinancialState:
    cash_ctx    = state.get("cash", {})
    budget_ctx  = state.get("budget", {})
    cash_ok     = cash_ctx.get("can_approve_payment", True)
    budget_ok   = not budget_ctx.get("budget_breach", False)
    utilisation = budget_ctx.get("utilisation_pct", 0.0)

    invoice = db.get_invoice(invoice_id) or {}
    merged  = {**invoice, **invoice_ctx}

    ap_system, ap_user = invoice_approval_routing_prompt(merged, cash_ok, budget_ok, utilisation)
    routing = qwen_json(ap_system, ap_user)

    approval_level = routing.get("approval_level", "manager")
    reasoning      = routing.get("reasoning", "Routing determined by system policy.")
    flags          = routing.get("flags", [])

    status_map = {"auto": "approved", "manager": "awaiting_approval",
                  "senior_manager": "awaiting_approval", "rejected": "rejected"}
    new_status = status_map.get(approval_level, "awaiting_approval")

    db.update("invoices", {"id": invoice_id}, {
        "status":              new_status,
        "cash_check_passed":   cash_ok,
        "budget_check_passed": budget_ok,
        "approved_at":         _now_iso() if new_status == "approved" else None,
    })

    db.log_agent_event(
        agent="invoice",
        event_type=f"approval_{approval_level}",
        entity_id=invoice_id,
        details={
            "approval_level":  approval_level,
            "cash_ok":         cash_ok,
            "budget_ok":       budget_ok,
            "utilisation_pct": round(utilisation, 1),
            "amount":          invoice_ctx.get("amount"),
            "flags":           flags,
        },
        reasoning=reasoning,
    )

    state = add_reasoning(state, "invoice", "approval_routing",
                          f"Invoice {invoice_id} → {approval_level.upper()}. {reasoning}")

    return {
        **state,
        "current_agent": "invoice",
        "next_agent":    "cash" if new_status == "approved" else END,
        "trigger":       "cash_position_refresh" if new_status == "approved" else "done",
        "invoice": {
            **invoice_ctx,
            "status":           new_status,
            "approval_reason":  reasoning,
            "requires_approval": approval_level in ("manager", "senior_manager"),
        },
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _run_ocr(invoice_id: str, invoice: dict) -> str | None:
    file_path = invoice.get("file_path")
    if not file_path:
        return invoice.get("ocr_raw_text") or None
    try:
        from config import get_supabase
        supabase = get_supabase()
        file_bytes = supabase.storage.from_("invoices").download(file_path)
        filename   = file_path.split("/")[-1]
        return ocr_invoice(file_bytes, filename)
    except Exception as e:
        db.log_agent_event("invoice", "ocr_error", invoice_id,
                           {"error": str(e)}, reasoning=f"OCR failed: {e}")
        return None


def _is_duplicate(extracted: dict, current_id: str) -> bool:
    inv_num = extracted.get("invoice_number")
    if not inv_num:
        return False
    existing = db.select("invoices", {"invoice_number": inv_num})
    return any(r["id"] != current_id for r in existing)


def _get_vendor_history(vendor_name: str) -> dict | None:
    if not vendor_name:
        return None
    rows = db.select("invoices", {"vendor_name": vendor_name})
    if not rows:
        return None
    amounts = [r["total_amount"] for r in rows if r.get("total_amount")]
    return {
        "avg_amount":  sum(amounts) / len(amounts) if amounts else 0,
        "recent_count": len(rows),
        "last_date":   max((r.get("invoice_date", "") for r in rows), default=""),
    }


def _estimate_due_date(invoice_date_str: str | None) -> str | None:
    if not invoice_date_str:
        return None
    try:
        d = date.fromisoformat(invoice_date_str)
        return (d + timedelta(days=30)).isoformat()
    except ValueError:
        return None


def _current_period() -> str:
    today   = date.today()
    quarter = (today.month - 1) // 3 + 1
    return f"{today.year}-Q{quarter}"


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _error(state: FinancialState, message: str) -> FinancialState:
    return {**state, "current_agent": "invoice", "next_agent": END,
            "error": message, "error_agent": "invoice"}
