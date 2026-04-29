"""
utils/prompts.py
All Qwen3 prompt templates for FAgentLLM.

Each prompt is a function that takes runtime values and returns
(system_prompt, user_prompt) ready to pass to qwen_json() or qwen_explain().

Keeping prompts here means:
  - Agents stay clean (no big strings inline)
  - Easy to iterate / version prompts without touching logic
  - Thesis appendix: copy these directly as "Prompt Engineering Framework"
"""

# ══════════════════════════════════════════════════════════════════════════════
# INVOICE AGENT PROMPTS
# ══════════════════════════════════════════════════════════════════════════════

INVOICE_EXTRACT_SYSTEM = """You are a financial document processing specialist with expertise in invoice analysis.
Your task is to extract structured information from invoice text with high precision.
Return ONLY valid JSON. No explanation, no markdown fences, no commentary."""


def invoice_extract_prompt(ocr_text: str) -> tuple[str, str]:
    """
    Extract structured fields from raw OCR text of an invoice.
    Returns (system, user) tuple.
    Target: ≥85% field-level F1 (thesis metric).
    """
    user = f"""Extract all available fields from this invoice text.

Invoice text:
\"\"\"
{ocr_text}
\"\"\"

Return a JSON object with exactly these fields (use null if not found):
{{
  "vendor_name": "string",
  "vendor_tax_id": "string",
  "invoice_number": "string",
  "invoice_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "total_amount": number_or_null,
  "currency": "USD or detected currency code",
  "tax_amount": number_or_null,
  "subtotal": number_or_null,
  "line_items": [
    {{
      "description": "string",
      "quantity": number_or_null,
      "unit_price": number_or_null,
      "total": number_or_null
    }}
  ],
  "payment_terms": "string or null",
  "notes": "string or null",
  "confidence": 0-100
}}

Rules:
- All monetary values must be numeric (no currency symbols)
- Dates must be YYYY-MM-DD format
- confidence = your estimate of overall extraction quality (0-100)
- If invoice_date found but due_date not stated, estimate due_date as invoice_date + 30 days"""

    return INVOICE_EXTRACT_SYSTEM, user


def invoice_validation_prompt(extracted: dict, vendor_history: dict | None) -> tuple[str, str]:
    """
    Validate extracted invoice fields and check for anomalies.
    vendor_history: previous invoices from same vendor (avg amount, frequency)
    """
    system = """You are a financial compliance specialist reviewing invoice data for anomalies.
Analyse the extracted invoice and flag any issues. Return ONLY valid JSON."""

    vendor_ctx = ""
    if vendor_history:
        vendor_ctx = f"""
Vendor history:
- Average invoice amount: {vendor_history.get('avg_amount', 'unknown')}
- Invoices in last 90 days: {vendor_history.get('recent_count', 0)}
- Last invoice date: {vendor_history.get('last_date', 'unknown')}"""

    user = f"""Review this extracted invoice data and identify any validation issues.

Extracted data:
{extracted}
{vendor_ctx}

Return JSON:
{{
  "is_valid": true/false,
  "issues": ["list of specific issues found, empty if none"],
  "anomalies": ["list of anomalies vs vendor history, empty if none"],
  "requires_manual_review": true/false,
  "review_reason": "string explaining why manual review needed, or null"
}}"""

    return system, user


def invoice_approval_routing_prompt(invoice: dict, cash_ok: bool, budget_ok: bool,
                                     budget_utilisation: float) -> tuple[str, str]:
    """
    Determine approval routing: auto-approve, manager, or senior manager.
    This is the XAI reasoning trace the jury will see.
    """
    system = """You are a financial controller determining invoice approval routing.
Apply approval thresholds and contextual constraints. Return ONLY valid JSON."""

    user = f"""Determine the correct approval routing for this invoice.

Invoice details:
- Amount: {invoice.get('total_amount')} {invoice.get('currency', 'USD')}
- Vendor: {invoice.get('vendor_name')}
- Department: {invoice.get('department', 'unknown')}

System constraints:
- Cash liquidity check: {'PASSED' if cash_ok else 'FAILED - projected shortfall'}
- Budget check: {'PASSED' if budget_ok else f'FAILED - department at {budget_utilisation:.1f}% utilisation'}

Approval thresholds:
- Auto-approve: amount < 5,000 AND cash_ok AND budget_ok
- Manager approval: amount 5,000-50,000 OR cash warning OR budget > 90%
- Senior manager: amount > 50,000 OR cash FAILED OR budget > 95%
- Reject: budget FAILED AND amount > 10,000

Your response must provide:
1. Technical Explanation: Logic behind the routing decision.
2. Business Explanation: Financial implications of this routing.
3. Causal Explanation: Downstream impacts on cash and budget.
4. Decision: One of "auto", "manager", "senior_manager", "rejected".
"""

    return system, user


# ══════════════════════════════════════════════════════════════════════════════
# CASH AGENT PROMPTS
# ══════════════════════════════════════════════════════════════════════════════

def cash_liquidity_prompt(current_balance: float, projected_inflows: float,
                           projected_outflows: float, invoice_amount: float,
                           minimum_balance: float) -> tuple[str, str]:
    """
    Assess whether a proposed payment can be approved given liquidity.
    Implements C_{t+1} = C_t + I_t - O_t from thesis Section 2.7.3.
    """
    system = """You are a treasury analyst assessing cash liquidity.
Use the projected cash balance formula to evaluate payment feasibility. Return ONLY valid JSON."""

    projected_next = current_balance + projected_inflows - projected_outflows

    user = f"""Assess liquidity for a proposed invoice payment.

Current cash position:
- Balance now (C_t): ${current_balance:,.2f}
- Projected inflows (I_t, next 7 days): ${projected_inflows:,.2f}
- Projected outflows (O_t, next 7 days): ${projected_outflows:,.2f}
- Projected balance C_{{t+1}} = C_t + I_t - O_t = ${projected_next:,.2f}
- Minimum operating balance: ${minimum_balance:,.2f}

Proposed payment: ${invoice_amount:,.2f}

Balance after payment: ${projected_next - invoice_amount:,.2f}

Return JSON:
{{
  "can_approve": true/false,
  "projected_balance_after": {projected_next - invoice_amount:.2f},
  "shortfall": {max(0, minimum_balance - (projected_next - invoice_amount)):.2f},
  "risk_level": "low" | "medium" | "high",
  "reasoning": "1-2 sentence explanation citing the specific numbers"
}}"""

    return system, user


# ══════════════════════════════════════════════════════════════════════════════
# RECONCILIATION AGENT PROMPTS
# ══════════════════════════════════════════════════════════════════════════════

def reconciliation_anomaly_prompt(unmatched: list[dict],
                                   period: str) -> tuple[str, str]:
    """
    Generate natural language explanation for unmatched / anomalous transactions.
    XAI output stored in agent_events.reasoning.
    """
    system = """You are a reconciliation specialist analysing unmatched financial transactions.
Identify patterns and provide actionable explanations. Return ONLY valid JSON."""

    items_text = "\n".join([
        f"- {t.get('source')} | {t.get('description', 'no desc')} | "
        f"${t.get('amount', 0):,.2f} | {t.get('transaction_date')}"
        for t in unmatched[:20]
    ])

    user = f"""Analyse these unmatched transactions for the period {period}.

Unmatched transactions:
{items_text}

Identify:
1. Any systematic patterns (same vendor, recurring amounts, consistent timing gaps)
2. Likely root causes (timing differences, data entry errors, missing records)
3. Recommended actions

Your response must provide:
1. Technical Explanation: Data patterns and discrepancies found.
2. Business Explanation: Probable root causes and business impact.
3. Causal Explanation: Recommended actions and downstream triggers.
4. Decision: Status of the reconciliation.
"""

    return system, user


# ══════════════════════════════════════════════════════════════════════════════
# CREDIT AGENT PROMPTS
# ══════════════════════════════════════════════════════════════════════════════

def credit_risk_prompt(customer: dict, payment_history: list[dict],
                        risk_score: float) -> tuple[str, str]:
    """
    Generate XAI explanation for credit risk assessment.
    Implements weighted R = Σ(w_i × f_i) from thesis Section 2.7.2.
    risk_score already computed deterministically — LLM adds the explanation.
    """
    system = """You are a credit risk analyst providing explainable risk assessments.
Your explanation must be clear enough for a non-technical finance manager. Return ONLY valid JSON."""

    recent_payments = payment_history[-5:] if payment_history else []
    payment_text = "\n".join([
        f"- Invoice {p.get('invoice_id', '?')}: "
        f"due {p.get('due_date')}, paid {p.get('paid_date', 'UNPAID')}, "
        f"delay: {p.get('days_late', 0)} days"
        for p in recent_payments
    ]) or "No payment history available"

    user = f"""Explain this credit risk assessment for a finance manager.

Customer: {customer.get('name')}
Credit limit: ${customer.get('credit_limit', 0):,.2f}
Outstanding balance: ${customer.get('total_outstanding', 0):,.2f}
Computed risk score R: {risk_score:.1f} / 100
(Higher = higher risk. Formula: R = Σ(w_i × f_i) over payment delay, outstanding ratio, dispute frequency)

Recent payment history (last 5):
{payment_text}

Your response must provide:
1. Technical Explanation: Interpretation of the risk score R.
2. Business Explanation: What this means for the company's credit exposure.
3. Causal Explanation: How this affects payment terms or future transactions.
4. Decision: One of "reminder", "formal_notice", "escalate", "legal_referral", "monitor".
"""

    return system, user
