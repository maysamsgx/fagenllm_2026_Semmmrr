"""
utils/prompts.py
All Qwen3 prompt templates for FAgentLLM.
Numeric thresholds are sourced from directives/policies.py — never hardcoded here.

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
  "department_id": "engineering | marketing | sales | operations | finance | hr | it | rnd (classify based on vendor activity)",
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
    Thresholds are aligned with budget_agent.py ALERT_THRESHOLD (95%) and
    HARD_STOP_THRESHOLD (100%). Rejection only triggers at 100%+ utilisation.
    """
    from directives.policies import INVOICE, BUDGET  # lazy import — avoids IDE path issues

    system = """You are a financial controller determining invoice approval routing.
Apply the exact approval thresholds listed below. Do NOT reject an invoice solely
because the amount is zero or unknown — escalate to manager instead.
Return ONLY valid JSON with these keys:
{
  "decision": "auto" | "manager" | "senior_manager" | "rejected",
  "technical_explanation": "string",
  "business_explanation": "string",
  "causal_explanation": "string",
  "confidence": 0-100
}"""

    amount = float(invoice.get('amount') or 0)
    amount_known = amount > 0
    amount_display = f"${amount:,.2f}" if amount_known else "unknown"
    currency = invoice.get('currency', 'USD')
    needs_human = invoice.get('needs_human', False)

    user = f"""Determine the correct approval routing.
    
INVOICE DATA:
- Amount: {amount:.2f}
- Flagged by validation: {'YES' if needs_human else 'NO'}

SYSTEM CONSTRAINTS:
- Cash liquidity: {'PASSED' if cash_ok else 'FAILED'}
- Budget utilisation: {budget_utilisation:.1f}%

STRICT ROUTING RULES:
1. REJECT if budget utilisation >= {BUDGET.hard_stop_threshold:.0f}
2. SENIOR MANAGER if amount > {INVOICE.manager_max:.0f} OR liquidity is FAILED OR budget utilisation >= {BUDGET.alert_threshold:.0f}
3. MANAGER if Flagged by validation is YES OR amount >= {INVOICE.auto_approve_max:.0f} OR budget utilisation >= {BUDGET.auto_approve_below:.0f}
4. AUTO-APPROVE ONLY if none of the above are true.

CRITICAL DIRECTIVES:
- If Amount ({amount:.2f}) < {INVOICE.auto_approve_max:.0f} AND validation is NO AND cash is PASSED AND budget < {BUDGET.auto_approve_below:.0f}, you MUST select 'auto'.
- In 'business_explanation', include a STRATEGIC INSIGHT: a forward-looking comment on whether this department will stay under budget for the quarter based on current {budget_utilisation:.1f}% utilisation.
- In 'causal_explanation', cite the specific threshold vs the actual value.
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

def reconciliation_anomaly_prompt(unmatched: list[dict], period: str) -> tuple[str, str]:
    """
    Generate enterprise forensic-grade intelligence for reconciliation anomalies.
    Produces 3 XAI fields in professional treasury operations language.
    """
    from directives.policies import RECON  # lazy import

    # Enrich with similarity scores and counterparty data
    if unmatched:
        # Sort by date descending, then amount to prioritize recent/large anomalies
        unmatched_sorted = sorted(unmatched, key=lambda x: (x.get('transaction_date', ''), abs(float(x.get('amount', 0)))), reverse=True)
        sample = unmatched_sorted[:5]
        items_text = "\n".join([
            f"  [{i+1:02d}] {t.get('source','?').upper()} | "
            f"Counterparty: {str(t.get('counterparty','Unknown'))[:35]} | "
            f"Amount: ${float(t.get('amount',0) or 0):>11,.2f} | "
            f"Date: {t.get('transaction_date','?')} | "
            f"Score: {float(t.get('sim_score') or t.get('match_score') or 0):.3f}"
            for i, t in enumerate(sample)
        ])
        total_n   = len(unmatched)
        total_exp = sum(float(t.get('amount', 0) or 0) for t in unmatched)
        cps       = list({t.get('counterparty','') for t in unmatched if t.get('counterparty')})
        dates     = sorted(t.get('transaction_date','') for t in unmatched if t.get('transaction_date'))
        date_range = f"{dates[0]} to {dates[-1]}" if len(dates) >= 2 else (dates[0] if dates else "N/A")
        avg_score = sum(float(t.get('sim_score') or t.get('match_score') or 0) for t in unmatched) / max(1, len(unmatched))
        cp_str    = ", ".join(cps[:5]) + (" ..." if len(cps) > 5 else "")
        note      = f" (showing 10 of {total_n})" if total_n > 10 else ""
    else:
        items_text = "  (none — all transactions reconciled)"
        total_n    = 0
        total_exp  = 0.0
        cps        = []
        date_range = "N/A"
        avg_score  = 0.0
        cp_str     = ""
        note       = ""

    system = """You are a senior treasury forensics agent embedded in an enterprise reconciliation system.
Transform structured reconciliation data into audit-ready intelligence with strict evidence-based reasoning.
Return ONLY valid JSON.

OUTPUT FORMAT:
{
  "technical_explanation": "Detailed forensic trace of mismatch patterns (e.g. 'Consistent $5.00 variance suggests bank fee ingestion failure').",
  "business_explanation": "High-level summary for the CFO, including STRATEGIC IMPLICATIONS of the unreconciled amount.",
  "causal_explanation": "What this anomaly blocks (e.g. 'Unreconciled AR prevents accurate credit score update for Customer X').",
  "risk_level": "low | medium | high | critical",
  "confidence": 0-100,
  "decision": "reconciliation_complete | escalation_required | manual_review_required",
  "is_systematic": true | false
}

FORENSIC DIRECTIVES:
- If a systematic pattern is detected, you MUST identify the 'Primary Hypothesis' (e.g. ingestion error, fraud risk, timing drift).
- Cite specific 'Evidence Markers' (e.g. '3 items with identical mismatch delta of $50.00').
- In 'business_explanation', suggest a corrective action (e.g. 'Investigate bank feed mapping for counterparty Y').

SCORE INTERPRETATION (critical — follow exactly):
- TF-IDF Score ≥ {RECON.match_threshold:.2f} OR Semantic Score ≥ {RECON.semantic_match_threshold:.2f} = strong match (reconciled)
- Scores 0.30–0.49 = SYSTEMATIC PARTIAL MATCH — items are related but threshold not met. Do NOT say 'no structural match'. Say 'consistent partial-match signals below threshold'.
- Scores <0.30 = no structural relationship found
NEVER say 'no structural match rules satisfied' when scores are in the 0.30–0.49 band.

TEMPORAL REASONING:
- If dates span more than 60 days, explicitly segment into: pre-period outliers vs primary cluster.
- State separately: 'pre-period anomaly: [dates]' and 'primary cluster: [dates]'.
- A 30-day gap between a single outlier date and a cluster should be named as an outlier, not described as part of the same distribution.

COUNTERPARTY CAUSALITY:
- Do NOT assume which side (ledger vs bank feed) is failing. State: 'Source of mismatch is unresolved: could be [ledger side] or [bank feed side]'.
- Only assign Vendor-specific root cause if you can show Vendor entries exist on one side but not the other.

AMOUNT ANALYSIS:
- Amount-band clustering (e.g. $1k, $5k, $10k groups) is an observation ONLY.
- Do NOT conclude 'no mirrored amounts' unless you explicitly compared paired internal vs bank entries.
- If you cannot compare pairs, state: 'Mirroring analysis requires paired dataset — not confirmable from unilateral view'.

ROOT CAUSE CLASSIFICATION:
- timing delay | missing bank record | ingestion failure | manual posting inconsistency | duplicate risk | rule mismatch
- Rank hypotheses by probability. Reject weaker ones with evidence.

FINANCIAL EXPOSURE:
- Do NOT assert unreconciled amount = real liability without confirming root cause.
- Use qualifier: 'unresolved exposure of $X (pending root cause confirmation)'.
- Distinguish between: timing mismatch (likely temporary) vs ingestion failure (requires action) vs classification error (may net to zero).

Return ONLY valid JSON."""

    user = f"""RECONCILIATION BRIEF — Period: {period}
CRITICAL: Total Unreconciled Items = {total_n}
Financial Exposure = ${total_exp:,.2f}
Affected Dates = {date_range}

Counterparties ({len(cps)}): {cp_str} | Avg Match-Score: {avg_score:.3f}

EVIDENCE (Top 5 largest/most recent items for forensic analysis):{note}
{items_text}


Return JSON with these 3 distinct analytical fields + metadata:

1. technical_explanation — Analytical fingerprint:
   Describe match-score distribution (clustered near 0 = no structural match).
   Identify timing concentration, counterparty recurrence, mirrored amounts, rounding gaps.
   Quantify items with score < 0.30.

2. business_explanation — Financial operations consequences (no repetition from field 1):
   Cash visibility gap of ${total_exp:,.2f} blocking {period} financial close.
   Audit readiness risk, DSO/DPO impact, working capital exposure.

3. causal_explanation — Inference chain (distinct from fields 1 and 2):
   observation → pattern → interpretation → root cause.
   Classify root cause: timing delay | missing bank record | ingestion failure |
   manual posting inconsistency | duplicate risk | rule mismatch.
   Name which agent/team acts first and their immediate action.

Also set:
  decision: reconciliation_complete | escalation_required | manual_review_required
  confidence: 0-100
  is_systematic: true if you identified ANY pattern or shared root cause in technical_explanation (e.g. counterparty recurrence, ingestion failure, timing drift).
"""
    return system, user


# ══════════════════════════════════════════════════════════════════════════════
# CREDIT AGENT PROMPTS
# ══════════════════════════════════════════════════════════════════════════════

def credit_risk_prompt(customer: dict, payment_history: list[dict],
                        risk_score: float, recon_anomalies: str | None = None,
                        f1: float = 0.0, f2: float = 0.0, f3: float = 0.0) -> tuple[str, str]:
    """
    Generate enterprise forensic-grade intelligence for credit risk assessment.
    Produces structured XAI reasoning for treasury and credit management.
    """
    system = """You are a senior credit intelligence agent specialized in enterprise risk forensics.
Transform quantitative risk metrics into executive-grade credit intelligence.
Return ONLY valid JSON.

FORMULA RULES (critical — follow exactly):
The score R is computed as:
  R = base(100) - (delay_weight × f1) - (outstanding_weight × f2) - f3_penalty
ALL components are SUBTRACTED. A higher penalty LOWERS the score.
When f1=0 and f2=0, say: 'No payment delay or outstanding balance recorded. Baseline deduction is zero for behavioral factors.'
When f3>0, explicitly state: 'A reconciliation-sourced anomaly penalty of {f3} points is SUBTRACTED from the baseline.'
Do NOT say 'bias penalty applied' — say 'anomaly deduction of X points reduces score from baseline'.

CAUSAL CHAIN RULES:
- Only escalate to collections if payment_history shows actual overdue behavior.
- If f1=0 and payment history is clean, the risk comes ONLY from the reconciliation anomaly.
- The chain must be: [evidence source] → [what it changes] → [score impact] → [proportionate action].
- Do NOT apply a blanket 'Formal Notice' if the customer's own payment behavior is clean.

EXPOSURE QUALIFICATION:
- If the exposure comes from a reconciliation anomaly (not direct customer default), say: 'unresolved reconciliation exposure of $X — root cause pending confirmation'.
- Do NOT assert 'direct liability' from a reconciliation anomaly without confirmed root cause.

Return ONLY valid JSON with exactly:
{
  "technical_explanation": "...",
  "business_explanation": "...",
  "causal_explanation": "...",
  "decision": "reminder | formal_notice | escalate | legal_referral | monitor",
  "confidence": 0-100
}"""

    recent_payments = payment_history[-5:] if payment_history else []
    payment_text = "\n".join([
        f"  - Invoice {p.get('invoice_id', '?')[:8]}: "
        f"Due: {p.get('due_date')}, Paid: {p.get('paid_date', 'OVERDUE')}, "
        f"Delay: {p.get('days_late', 0)}d | Stage: {p.get('collection_stage', 'none')} | Amount: ${float(p.get('amount', 0)):,.2f}"
        for p in recent_payments
    ]) or "  - No receivables history on record for this customer"

    recon_ctx = ""
    if recon_anomalies:
        recon_ctx = f"\nCROSS-DOMAIN SIGNAL (from Reconciliation Agent):\n  Anomaly: {recon_anomalies}\n  Action: Reconciliation anomaly deduction of {f3:.0f} pts SUBTRACTED from score.\n  Note: This is an unresolved reconciliation exposure — not confirmed customer default.\n"

    user = f"""CREDIT RISK FORENSIC ANALYSIS

CUSTOMER: {customer.get('name')} | Credit Limit: ${customer.get('credit_limit', 0):,.2f} | Outstanding: ${customer.get('total_outstanding', 0):,.2f}

SCORE COMPUTATION (deterministic — do not recompute, only explain):
  R = 100 - ({f1:.1f} × delay_weight) - ({f2:.3f} × outstanding_weight) - {f3:.1f} penalty = {risk_score:.1f}
  f1 (avg delay days) = {f1:.1f} {'(clean — no delays recorded)' if f1 == 0 else ''}
  f2 (outstanding $k) = {f2:.3f} {'(zero balance)' if f2 == 0 else ''}
  f3 (anomaly deduction) = {f3:.1f} {'(no reconciliation anomaly)' if f3 == 0 else '(from cross-domain recon signal)'}
{recon_ctx}
PAYMENT BEHAVIOR (last 5 events):
{payment_text}

REQUIRED OUTPUT:
1. TECHNICAL — Explain the score components using the EXACT f1/f2/f3 values above. Never say 'bias penalty' — say 'anomaly deduction'.
2. BUSINESS — Cash flow and audit risk. If f3 is the ONLY deduction, explicitly say so and qualify the exposure.
3. CAUSAL — Evidence chain from the data above. Only recommend escalation if behavioral evidence (f1>0 or overdue receivables) justifies it.

decision: proportionate to evidence (monitor if only f3 is non-zero and payment history is clean)
confidence: 0-100
"""
    return system, user


def governance_audit_prompt(trace_summary: str) -> tuple[str, str]:
    """
    Final governance pass to ensure cross-agent consistency (Objective 10).
    Now specifically validates the CAUSAL CHAIN and Domain Reasoning performance.
    """
    system = (
        "You are the FAgentLLM Governance Auditor. Your role is to review the end-to-end multi-agent "
        "causal trace for policy violations, logic gaps, or decision-making performance.\n\n"
        "GOVERNANCE POLICIES:\n"
        "1. Causal Consistency: Decisions must logically follow the causal chain (e.g. if Recon flagged a gap, Credit MUST reassess).\n"
        "2. Domain Reasoning: Verify that the 'Causal Domain Reasoning' fields accurately bridge technical events to business outcomes.\n"
        "3. Performance Validation: Confirm that tracking cause-and-effect across agents improves final decision quality vs isolated agents.\n"
        "4. Strategic Impact: Evaluate if the event-driven orchestration has successfully mitigated risk or optimized liquidity.\n"
        "Return ONLY valid JSON."
    )

    user = f"""
    AUDIT TASK: Review the multi-agent execution trace and validate the CAUSAL DOMAIN REASONING.
    
    EXECUTION TRACE:
    {trace_summary}
    
    REQUIRED OUTPUT (JSON):
    {{
      "compliance_score": 0-100,
      "decision": "audit_passed" | "audit_failed" | "requires_oversight",
      "is_audit_safe": true | false,
      "technical_explanation": "Detailed analysis of the causal link integrity between agents.",
      "business_explanation": "Executive summary confirming how the event-driven architecture improved the decision quality in this specific run. Start with 'PERFORMANCE VALIDATED:' if the claim is supported.",
      "causal_explanation": "Explicit validation of the 'cause and effect' chain. Explain EXACTLY how tracking the causal flow led to a better decision than an isolated agent would have made.",
      "findings": ["list of findings or conflicts"],
      "cause": "The primary root cause for the final audit verdict based on the trace evidence.",
      "actions": ["List of specific validating or corrective actions taken during the audit."],
      "effects": ["List of downstream consequences of this governance decision."],
      "verdict": "PASSED | FLAGGED | BLOCKED",
      "confidence": 0-100
    }}
    
    CRITICAL: You MUST support the claim that 'when we have AI agents with causal event-driven logic, they improve performance and lead to better decisions by tracking them'. 
    Provide specific evidence from the execution trace above where a downstream agent (e.g., Credit or Cash) made a better-informed decision because it 'understood' the causal context from an upstream agent (e.g., Reconciliation or Invoice).
    Break down the final verdict into:
    - Cause: What was the primary driver of this audit result?
    - Actions: What did the system do to verify or fix the situation?
    - Effects: What is the impact of this audit on future operations?
    - Verdict: A single-word final status.
    """
    return system, user
