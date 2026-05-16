# Cash Policy — FAgentLLM Directive

## Purpose
This directive governs how the Cash Agent projects liquidity and decides whether
a proposed payment can be approved without breaching the operating reserve.

## Operating Reserve
- **Minimum balance**: $10,000 at all times across all accounts
- If the post-payment balance falls below this threshold, the invoice is escalated
  to senior manager regardless of amount or budget status

## Liquidity Formula
```
C_{t+1} = C_t + I_t - O_t
```
- `C_t` = current total cash across all accounts
- `I_t` = projected inflows over the next 7 days (see below)
- `O_t` = projected outflows over the next 7 days (approved invoices due)
- Post-payment balance = C_{t+1} - new_invoice_amount

## Inflow Projection Method
Inflows are a weighted blend of two components:

### Near-term receivables (0–7 days)
Receivables with `due_date` within 7 days, counted at 100% face value.

### WMA of historical collections
Weighted Moving Average over the last 3 weeks of actual payment receipts:
- Most recent week: weight 0.50
- Week -2:          weight 0.30
- Week -3:          weight 0.20

### 8–30 day receivables (probabilistic)
Receivables due in 8–30 days, discounted at 70% probability of collection.
This improves forecast realism without overstating expected cash.

### Blend
`I_t = (near_receivables × 0.4) + (WMA × 0.6) + (far_receivables × 0.7 × weight)`

## Outflow Projection
Sum of all `approved` invoices with `due_date` within the next 7 days,
excluding the invoice currently being evaluated.

## Routing Rules
| Outcome | Next agent |
|---|---|
| Balance after payment > minimum | Continue to Budget Agent |
| Balance after payment ≤ minimum | Escalate to senior manager (Cash FAILED flag) |
