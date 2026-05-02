# Invoice Policy — FAgentLLM Directive

## Purpose
This directive defines the full invoice lifecycle: from upload through OCR, extraction,
vendor validation, and final approval routing. It governs what the Invoice Agent does
at each stage and what conditions trigger escalation or rejection.

## Stage 1 — OCR
- Primary OCR engine: Baidu Qianfan-OCR-Fast via OpenRouter
- Fallback OCR engine: Tesseract (local)
- If both fail: invoice is rejected with status `ocr_failed`; human intervention required

## Stage 2 — Structured Extraction
- LLM (Qwen3) extracts: vendor_name, invoice_number, invoice_date, due_date,
  total_amount, currency, tax_amount, line_items, payment_terms
- **Required fields**: vendor_name, invoice_number, invoice_date, total_amount
- Confidence = 100 - (25 × missing_required_fields)
- If extraction fails entirely: invoice is rejected

## Stage 3 — Vendor Validation
- New vendor (no history): baseline risk score 50/100
- Risk level: score ≥ 70 → low; 40–69 → medium; < 40 → high
- High-risk vendor: flagged for manual review (does NOT auto-reject; escalates)

## Stage 4 — Approval Routing
Apply rules in order; first match wins:

| Rule | Condition | Action |
|---|---|---|
| 1. Hard stop | Budget utilisation ≥ 100% | **REJECT** — mandatory, no override |
| 2. Senior manager | Amount > $50,000 OR cash FAILED OR utilisation ≥ 95% | Escalate |
| 3. Manager | Amount $5,000–$50,000 OR utilisation ≥ 90% OR amount unknown | Manager review |
| 4. Auto-approve | Amount < $5,000 AND cash PASSED AND utilisation < 90% | Approve automatically |

## Causal Chain
OCR → Extraction → Vendor Validation → Cash Check → Budget Check → Approval Routing

Each stage writes a decision to the audit log. A failure at any stage halts the chain
and records why. This chain is visualised in the Trace Panel.
