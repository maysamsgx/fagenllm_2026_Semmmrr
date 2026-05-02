# Budget Policy — FAgentLLM Directive

## Purpose
This directive defines how the Budget Agent evaluates department spend and routes invoice approvals.
It is injected into the LLM system prompt so the AI reasons within these boundaries.

## Approval Thresholds
| Utilisation | Action |
|---|---|
| < 90% | Eligible for auto-approval (subject to cash and vendor checks) |
| 90–94% | Manager review recommended |
| ≥ 95% | **Alert — escalate to senior manager** |
| ≥ 100% | **Hard stop — mandatory rejection, no manager override possible** |

## What to Do When a Department is Over 100%
1. The Budget Agent **automatically rejects** all new invoices for that department.
2. A `budget_alert` record is created and surfaced in the dashboard.
3. The finance manager must take one of the following actions before any invoice can proceed:
   - Raise a formal budget exception (requires senior manager sign-off)
   - Redistribute unspent budget from another department
   - Defer the invoice to the next budget period

## Committed vs Spent
- **Spent**: Invoices already paid (immutable, cannot be reversed)
- **Committed**: Invoices approved but not yet paid (can be uncommitted if rejected)
- Utilisation = (spent + committed + new_invoice_amount) / allocated × 100

## Period Definition
Budgets are managed quarterly: YYYY-Q1 through YYYY-Q4.
A new period resets committed to 0; spent accumulates from payments.

## What-If Scenario
Finance may submit a hypothetical check before uploading an invoice:
- Input: department_id + proposed amount
- Output: projected utilisation %, risk level, LLM narrative, and alternatives
- This does NOT create any actual commitment
