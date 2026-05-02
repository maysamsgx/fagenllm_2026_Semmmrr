# Reconciliation Policy — FAgentLLM Directive

## Purpose
This directive defines how the Reconciliation Agent matches internal financial
records against bank transaction data, flags discrepancies, and routes anomalies
to downstream agents.

## What Reconciliation Does (Step by Step)
1. **Fetch** all unmatched transactions from both `internal` and `bank` sources
2. **Vectorise** each transaction using TF-IDF on (amount, date, counterparty, description)
3. **Compute** cosine similarity between every internal–bank pair
4. **Match** pairs with similarity ≥ 0.8 — mark `transactions.matched = true`
5. **Flag** everything below 0.8 as an anomaly
6. **Analyse** anomaly patterns with Qwen3 LLM
7. **Write** a reconciliation report with match rate and item-level traceability
8. **Route** to Credit Agent if systematic patterns are detected

## Matching Threshold
- **Match**: cosine similarity ≥ 0.80
- **Anomaly**: cosine similarity < 0.80
- Threshold is defined in `directives/policies.py` as `RECON.match_threshold`

## What Counts as Systematic?
An anomaly set is "systematic" if the LLM analysis contains any of:
`systematic`, `pattern`, `recurring`, `repeated`

When systematic, the agent attempts to identify the affected customer and
triggers the Credit Agent for risk reassessment.

## Discrepancy Types
| Type | Description |
|---|---|
| `amount_variance` | Amounts differ by more than rounding tolerance |
| `timing` | Transaction dates differ by > 2 business days |
| `duplicate` | Same transaction appears multiple times |
| `missing` | Internal record has no corresponding bank entry |

## Report Structure
Each reconciliation run produces:
- A `reconciliation_reports` row (period, match_rate, matched_count, unmatched_count)
- `reconciliation_report_items` rows for every matched and unmatched transaction
- An `agent_decisions` row with LLM narrative (accessible via Trace Panel)

## When to Run
- Automatically: daily via scheduled trigger
- Manually: via dashboard "Run Reconciliation" button
- After bulk payment processing
