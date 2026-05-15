# Reconciliation Policy — FAgentLLM Directive

## Purpose
This directive defines how the Reconciliation Agent matches internal financial
records against bank transaction data, flags discrepancies, and routes anomalies
to downstream agents.

## What Reconciliation Does (Step by Step)
1. **Fetch** all unmatched transactions from both `internal` and `bank` sources
2. **Stage 0 — Pattern Memory**: Check against known systematic mismatch rules from episodic memory
3. **Stage 1 — TF-IDF**: Vectorise using TF-IDF on (amount, date, counterparty, description); match if cosine similarity ≥ 0.50
4. **Stage 2 — Semantic**: Re-score with MiniLM embeddings via PGVector; match if similarity ≥ 0.68
5. **Stage 3 — FX Variance**: If semantic similarity ≥ 0.60 but amounts differ by ≤ 2%, reconcile as FX variance
6. **Analyse** anomaly patterns with Qwen3 LLM
7. **Write** a reconciliation report with match rate and item-level traceability
8. **Route** to Credit Agent if systematic patterns are detected

## Matching Thresholds
- **TF-IDF match**: cosine similarity ≥ 0.50 (`RECON.match_threshold`)
- **Semantic match**: embedding similarity ≥ 0.68 (`RECON.semantic_match_threshold`)
- **Anomaly**: below both thresholds and not within FX tolerance
- Thresholds are defined in `directives/policies.py`

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
