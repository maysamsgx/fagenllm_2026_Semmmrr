# Governance & Compliance Policy — FAgentLLM Directive

## Purpose
This directive governs the **Auditor Agent** (Governance Agent), which acts as the final "Safety Gate" of the multi-agent system. It ensures that cross-agent coordination is consistent, policy-compliant, and audit-ready.

## Core Audit Standards

### 1. Liquidity Consistency (Scenario 1)
- **High-Value Threshold**: Any invoice > $100,000 is classified as "High-Value".
- **Audit Rule**: High-value invoices MUST be routed to a Senior Manager.
- **Liquidity Lock**: If the Cash Agent flags a `liquidity_shortfall`, the Auditor ensures the Invoice Agent explicitly highlighted this risk in the business explanation.
- **Commitment Rule**: Approvals must not be finalized until a "Cash Position Refresh" is triggered to update the 7-day forecast.

### 2. Forensic Integrity (Scenario 2)
- **Anomaly Propagation**: If the Reconciliation Agent identifies a `systematic_discrepancy`, the Auditor verifies that a causal link was established to the Credit Agent.
- **Risk Recalculation**: The Auditor ensures that "Payment Risk" was reassessed by the Credit Agent following a reconciliation failure.

### 3. Fiscal Control (Scenario 3)
- **Hard Stop Enforcement**: Budget utilisation ≥ 100% is a **Hard Stop**. The Auditor will block any approval that attempts to bypass this limit.
- **Threshold Alerts**: At 95% utilisation, the Auditor verifies that a `budget_threshold_breach` event was broadcast and the approval was escalated to Senior Management.
- **Forecast Realism**: Following a budget breach, the Auditor ensures the Cash Agent's outflow forecast reflects "tightened spending controls" (e.g., a conservative multiplier).

## The Auditor's Verdict
The Auditor Agent assigns a **Compliance Score** to every run based on these criteria:
- **PASSED**: All agents followed directives; logic is consistent; explanations are accurate.
- **FLAGGED**: Minor explanation mismatch or missing non-critical trace layer.
- **BLOCKED**: Violation of a Hard Stop (Budget ≥ 100%) or bypass of a mandatory escalation (Amount > $100k).

## Coordination Trace
The Auditor must be the **final event** in any reasoning trace, providing a "seal of approval" that links all agent actions into a cohesive business narrative.
