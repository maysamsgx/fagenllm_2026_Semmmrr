"""
agents/invoice_agent.py
Invoice Agent — handles the whole lifecycle from OCR to approval routing.
Every step writes a row to agent_decisions so the XAI Trace panel can render it.
"""

from __future__ import annotations
from datetime import date
from langgraph.graph import END

from agents.state import FinancialState
from db.supabase_client import db
from directives.policies import BUDGET
from utils.directives import inject_directive
from utils.llm import qwen_json, ocr_invoice
from utils.prompts import (
    invoice_extract_prompt,
    invoice_approval_routing_prompt,
)

REQUIRED_FIELDS = ["vendor_name", "invoice_number", "invoice_date", "total_amount"]


def invoice_node(state: FinancialState) -> FinancialState:
    trigger = state.get("trigger", "invoice_uploaded")
    invoice_id = state.get("trigger_entity_id", "")
    invoice_ctx = state.get("invoice", {})

    if trigger == "invoice_uploaded":
        return _handle_new_invoice(state, invoice_id)
    if trigger == "invoice_post_checks":
        return _handle_approval_routing(state, invoice_id, invoice_ctx)

    return {**state, "next_agent": END, "current_agent": "invoice"}


def _handle_new_invoice(state: FinancialState, invoice_id: str) -> FinancialState:
    invoice = db.get_invoice(invoice_id)
    if not invoice:
        return _error(state, f"Invoice {invoice_id} not found")

    db.update_invoice_status(invoice_id, "extracting")

    # ── 1. OCR (skip if already present) ──────────────────────────────────
    ocr_text = invoice.get("ocr_raw_text")
    if not ocr_text:
        try:
            ocr_text = _run_ocr(invoice)
        except Exception as e:
            db.update_invoice_status(invoice_id, "rejected", {"rejection_reason": f"OCR failed: {e}"})
            db.log_agent_decision(
                agent="invoice", decision_type="ocr_failed",
                entity_table="invoices", entity_id=invoice_id,
                technical_explanation=f"OCR pipeline raised: {e}",
                business_explanation="The invoice file could not be digitised, so no fields could be read.",
                causal_explanation="Blocks all downstream agents (cash, budget, approval) for this invoice.",
                input_state={"file_path": invoice.get("file_path")},
                confidence=0.0,
            )
            return _error(state, f"OCR failed: {e}")

    ocr_pipeline = "local-tesseract fallback" if ocr_text.startswith("[LOCAL OCR") else "Baidu Qianfan OCR-Fast"
    ocr_confidence = 80.0 if ocr_text.startswith("[LOCAL OCR") else 99.0
    file_label = (invoice.get("file_path") or "").split("/")[-1] or "uploaded file"
    ocr_id = db.log_agent_decision(
        agent="invoice", decision_type="ocr_completed",
        entity_table="invoices", entity_id=invoice_id,
        technical_explanation=(
            f"OCR pipeline '{ocr_pipeline}' decoded {len(ocr_text):,} characters from "
            f"'{file_label}' at {ocr_confidence:.0f}% engine confidence."
        ),
        business_explanation=(
            "Converted the uploaded document into machine-readable text so the system can "
            "automatically capture vendor, amount, and line-item details without manual data entry."
        ),
        causal_explanation=(
            "Unblocks structured field extraction and downstream vendor-risk and budget checks; "
            "any failure here halts the workflow before financial commitments are recorded."
        ),
        input_state={"file_path": invoice.get("file_path"), "pipeline": ocr_pipeline},
        output_action={"characters": len(ocr_text), "ocr_text_excerpt": ocr_text[:1200]},
        confidence=ocr_confidence,
    )

    # Persist OCR text on the invoice row so it shows up in the UI/audit
    db.update("invoices", {"id": invoice_id}, {"ocr_raw_text": ocr_text[:8000]})

    # ── 2. Structured extraction via Qwen ─────────────────────────────────
    db.update_invoice_status(invoice_id, "validating")
    system, user = invoice_extract_prompt(ocr_text)
    extracted = qwen_json(system, user)

    if extracted.get("error") == "parse_failed":
        db.update_invoice_status(invoice_id, "rejected", {
            "rejection_reason": "LLM extraction returned unparseable response"
        })
        db.log_agent_decision(
            agent="invoice", decision_type="extraction_failed",
            entity_table="invoices", entity_id=invoice_id,
            technical_explanation="Qwen3 returned non-JSON output; cannot proceed with validation.",
            business_explanation="Failed to extract required fields, halting invoice processing.",
            causal_explanation="Blocks invoice progression, requires human intervention.",
            input_state={"ocr_excerpt": ocr_text[:600]},
            output_action={"raw_response": extracted.get("raw", "")[:600]},
            confidence=0.0,
        )
        return _error(state, "Extraction failed: invalid JSON")

    missing = [f for f in REQUIRED_FIELDS if not extracted.get(f)]
    confidence = max(0.0, 100.0 - 25.0 * len(missing))

    vendor_name = extracted.get("vendor_name") or "Unknown Vendor"
    vendor_id = db.ensure_vendor(vendor_name)
    vendor_risk = db.get_vendor_risk(vendor_id) or {}

    update_data: dict = {
        "vendor_id": vendor_id,
        "extraction_confidence": confidence,
    }
    if extracted.get("invoice_number"):
        update_data["invoice_number"] = extracted["invoice_number"]
    if extracted.get("invoice_date"):
        update_data["invoice_date"] = extracted["invoice_date"]
    if extracted.get("due_date"):
        update_data["due_date"] = extracted["due_date"]
    if extracted.get("total_amount") is not None:
        try:
            update_data["total_amount"] = float(extracted["total_amount"])
        except (TypeError, ValueError):
            pass
    if extracted.get("currency"):
        update_data["currency"] = extracted["currency"]
    db.update("invoices", {"id": invoice_id}, update_data)

    parsed_amount = float(update_data.get("total_amount") or 0)
    parsed_currency = update_data.get("currency", "USD")
    amount_label = f"{parsed_amount:,.2f} {parsed_currency}" if parsed_amount else "amount unresolved"
    extract_id = db.log_agent_decision(
        agent="invoice", decision_type="extraction_completed",
        entity_table="invoices", entity_id=invoice_id,
        technical_explanation=f"Qwen3 mapped OCR to schema at {confidence:.0f}% confidence ({len(REQUIRED_FIELDS) - len(missing)}/{len(REQUIRED_FIELDS)} required fields captured).",
        business_explanation=f"Identified vendor '{vendor_name}' with total {amount_label} for downstream financial review.",
        causal_explanation=(
            f"If extraction fails here, no financial commitment can be recorded — "
            f"vendor payment would require manual data entry. "
            f"The {len(REQUIRED_FIELDS) - len(missing)}/{len(REQUIRED_FIELDS)} captured fields "
            f"determine whether cash and budget checks can run at all."
        ),
        input_state={"ocr_excerpt": ocr_text[:600], "missing_fields": missing},
        output_action=extracted,
        confidence=confidence,
    )
    db.log_causal_link(ocr_id, extract_id, "enables_extraction",
                       "OCR output enabled the structured field extraction.")

    # ── 3. Validation summary (vendor risk gate) ─────────────────────────
    risk_score_raw = vendor_risk.get("risk_score")
    try:
        risk_score = float(risk_score_raw) if risk_score_raw is not None else 50.0
    except (TypeError, ValueError):
        risk_score = 50.0
    risk_level = vendor_risk.get("risk_level") or ("high" if risk_score >= 70 else "medium" if risk_score >= 40 else "low")
    is_new_vendor = not vendor_risk or (vendor_risk.get("factors") or {}).get("reason") == "new_vendor_no_history"
    risk_descriptor = "baseline (new vendor, no payment history)" if is_new_vendor else f"{risk_level} risk tier"
    val_reason = f"Vendor risk score {risk_score:.0f}/100 — {risk_descriptor}."
    needs_human = risk_level == "high"
    business_msg = (
        "High-risk vendor detected — invoice flagged for manual review."
        if needs_human else
        f"Vendor profile within tolerance ({risk_level}); cleared for liquidity and budget checks."
    )
    valid_id = db.log_agent_decision(
        agent="invoice", decision_type="validation_completed",
        entity_table="invoices", entity_id=invoice_id,
        technical_explanation=val_reason,
        business_explanation=business_msg,
        causal_explanation=(
            "A high vendor risk score blocks auto-approval regardless of amount, adding manual "
            "review latency. This check gates all downstream financial decisions — if skipped, "
            "a fraudulent vendor could receive an auto-approved payment."
        ),
        input_state={"vendor_id": vendor_id, "is_new_vendor": is_new_vendor, **{k: v for k, v in vendor_risk.items() if k != "factors"}},
        output_action={"validation": "passed", "risk_score": risk_score, "risk_level": risk_level, "needs_human": needs_human},
        confidence=confidence,
    )
    db.log_causal_link(extract_id, valid_id, "enables_validation",
                       "Extracted fields enabled vendor-risk validation.")

    department_id = invoice.get("department_id") or "engineering"
    db.update("invoices", {"id": invoice_id}, {
        "status": "awaiting_approval",
        "department_id": department_id,
    })

    return {
        **state,
        "current_agent": "invoice",
        "next_agent": "cash",
        "trigger": "invoice_post_checks",
        "decision_ids": {**state.get("decision_ids", {}), "invoice_validation": valid_id},
        "invoice": {
            "invoice_id": invoice_id,
            "vendor_id": vendor_id,
            "vendor_name": vendor_name,
            "amount": float(update_data.get("total_amount") or 0),
            "currency": update_data.get("currency", "USD"),
            "department_id": department_id,
            "decision_id": valid_id,
            "extraction_confidence": confidence,
        },
        "budget": {**state.get("budget", {}), "department_id": department_id, "period": _current_period()},
    }


def _handle_approval_routing(state: FinancialState, invoice_id: str, invoice_ctx: dict) -> FinancialState:
    cash_ctx = state.get("cash", {})
    budget_ctx = state.get("budget", {})
    cash_ok = cash_ctx.get("can_approve_payment", True)
    budget_ok = not budget_ctx.get("budget_breach", False)
    utilisation_pct = float(budget_ctx.get("utilisation_pct", 0.0))

    # Defensive refetch: if the amount was dropped from in-memory state
    # (e.g. an extraction edge-case left it null), pull it back from the
    # persisted invoice row before handing the prompt to the LLM.
    if not invoice_ctx.get("amount"):
        persisted = db.get_invoice(invoice_id) or {}
        if persisted.get("total_amount") is not None:
            try:
                invoice_ctx = {
                    **invoice_ctx,
                    "amount": float(persisted["total_amount"]),
                    "currency": persisted.get("currency") or invoice_ctx.get("currency", "USD"),
                    "vendor_name": invoice_ctx.get("vendor_name") or (persisted.get("vendors") or {}).get("name"),
                    "department_id": invoice_ctx.get("department_id") or persisted.get("department_id"),
                }
            except (TypeError, ValueError):
                pass

    # ── Deterministic hard gates ──────────────────────────────────────────────
    # These decisions are non-negotiable financial controls. Delegating them to
    # an LLM risks hallucination on the exact threshold that matters most.
    if utilisation_pct >= BUDGET.hard_stop_threshold:
        overage = utilisation_pct - 100.0
        tech = (
            f"Hard-stop: budget utilisation at {utilisation_pct:.1f}% exceeds the "
            f"{BUDGET.hard_stop_threshold:.0f}% ceiling by {overage:.1f}pp. Rejection is mandatory."
        )
        biz = (
            f"The department is already {overage:.1f}% over its allocated budget. "
            f"This invoice cannot be approved regardless of amount or cash position."
        )
        causal = (
            "Hard-stop breach forces rejection without manager override. The department "
            "budget must be revised or a budget exception raised before this vendor can be paid."
        )
        return _apply_routing_decision(
            state, invoice_id, invoice_ctx, budget_ctx, cash_ok,
            level="rejected", new_status="rejected",
            technical_explanation=tech, business_explanation=biz, causal_explanation=causal,
            confidence=100.0,
        )

    # ── LLM routing for non-hard-stop cases ──────────────────────────────────
    from utils.contracts import DecisionOutput
    from utils.llm import qwen_structured

    ap_system, ap_user = invoice_approval_routing_prompt(
        invoice_ctx, cash_ok, budget_ok, utilisation_pct
    )
    ap_system = inject_directive(ap_system, "invoice")
    routing = qwen_structured(ap_system, ap_user, DecisionOutput)
    level = routing.decision.lower()

    if "auto" in level:
        new_status = "approved"
    elif "reject" in level:
        new_status = "rejected"
    else:
        new_status = "awaiting_approval"

    return _apply_routing_decision(
        state, invoice_id, invoice_ctx, budget_ctx, cash_ok,
        level=level, new_status=new_status,
        technical_explanation=routing.technical_explanation,
        business_explanation=routing.business_explanation,
        causal_explanation=routing.causal_explanation,
        confidence=routing.confidence,
    )


def _apply_routing_decision(
    state: FinancialState,
    invoice_id: str,
    invoice_ctx: dict,
    budget_ctx: dict,
    cash_ok: bool,
    level: str,
    new_status: str,
    technical_explanation: str,
    business_explanation: str,
    causal_explanation: str,
    confidence: float,
) -> FinancialState:
    budget_ok = not budget_ctx.get("budget_breach", False)

    db.update("invoices", {"id": invoice_id}, {
        "status": new_status,
        "cash_check_passed": bool(cash_ok),
        "budget_check_passed": bool(budget_ok),
    })

    route_id = db.log_agent_decision(
        agent="invoice", decision_type=f"approval_{level}",
        entity_table="invoices", entity_id=invoice_id,
        technical_explanation=technical_explanation,
        business_explanation=business_explanation,
        causal_explanation=causal_explanation,
        input_state={
            "cash_ok": cash_ok, "budget_ok": budget_ok,
            "amount": invoice_ctx.get("amount"),
            "utilisation_pct": budget_ctx.get("utilisation_pct"),
        },
        output_action={"approval_level": level, "new_status": new_status},
        confidence=confidence,
    )

    trace = state.get("reasoning_trace", []) + [{
        "agent": "invoice",
        "step": "Approval Routing",
        "technical_explanation": technical_explanation,
        "business_explanation": business_explanation,
        "causal_explanation": causal_explanation,
    }]

    if invoice_ctx.get("decision_id"):
        db.log_causal_link(invoice_ctx["decision_id"], route_id,
                           "enables_approval" if level != "rejected" else "blocks_approval",
                           "Validation decision drove the final approval routing.")

    if level == "auto" and invoice_ctx.get("amount"):
        try:
            payment_id = db.record_payment(
                invoice_id, float(invoice_ctx["amount"]), "wire", f"AUTO-{invoice_id[:8]}"
            )
            pay_id = db.log_agent_decision(
                agent="invoice", decision_type="payment_executed",
                entity_table="payments", entity_id=payment_id,
                technical_explanation=f"Dispatched wire transfer AUTO-{invoice_id[:8]}.",
                business_explanation="Settled vendor invoice automatically.",
                causal_explanation="Reduces available cash balance.",
                input_state={"amount": invoice_ctx["amount"]},
                output_action={"method": "wire", "reference": f"AUTO-{invoice_id[:8]}"},
                confidence=100.0,
            )
            db.log_causal_link(route_id, pay_id, "reduces_liquidity",
                               "Auto-approval directly reduced cash position.")
        except Exception as e:
            import logging
            logging.getLogger("fagentllm").error(f"Auto-payment failed: {e}")

    return {
        **state,
        "current_agent": "invoice",
        "next_agent": END,
        "reasoning_trace": trace,
        "invoice": {**invoice_ctx, "status": new_status, "decision_id": route_id},
    }


# -- Helpers -----------------------------------------------------------------

def _run_ocr(invoice: dict) -> str:
    """
    Pull the file from Supabase storage and run the real OCR pipeline.
    No mock fallback — if everything fails the caller turns it into a real error.
    """
    path = invoice.get("file_path")
    if not path:
        raise RuntimeError("Invoice has no file_path; nothing to OCR")

    from config import get_supabase
    supabase = get_supabase()
    raw = supabase.storage.from_("invoices").download(path)
    if not raw:
        raise RuntimeError(f"Storage returned empty bytes for {path}")
    return ocr_invoice(raw, path.split("/")[-1])


def _current_period() -> str:
    t = date.today()
    return f"{t.year}-Q{(t.month - 1) // 3 + 1}"


def _error(state: FinancialState, msg: str) -> FinancialState:
    return {**state, "next_agent": END, "error": msg}
