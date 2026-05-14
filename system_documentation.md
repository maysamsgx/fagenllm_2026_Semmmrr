# FAgentLLM V4: System Architecture & Implementation Documentation

## 1. System Overview

FAgentLLM is a unified multi-agent architecture designed to overcome the fragmented, high-performing silos inherent in modern enterprise finance. By employing Large Language Models as a cognitive orchestration layer, the system integrates unstructured semantic reasoning with deterministic financial logic across **six core domains**: invoice processing, budgeting, reconciliation, credit assessment, cash management, and governance.

The system relies on a **10/10 Causal Perfection Architecture**, emphasising **Explainable AI (XAI)**. Every action taken by any agent is logged as a "decision" and linked to other decisions via a causal graph. This allows the business to definitively trace the "why" behind any autonomous action, satisfying corporate audit and compliance requirements.

### Technology Stack
*   **Orchestration:** LangGraph (Python) with a `FinancialState` shared-context pattern
*   **Backend:** FastAPI (Python) — `uvicorn main:app`
*   **Database:** Supabase (PostgreSQL with Realtime triggers, `pgvector` for semantic matching, and PostgREST)
*   **LLMs:** Tiered Model Architecture via Groq:
    *   **Reasoning Tier:** Qwen3-32B (Best-in-class reasoning for Governance & Reflection)
    *   **Workhorse Tier:** Llama-3.1-8b-instant (High-speed, high-limit extraction)
    *   **Resilience:** Multi-key round-robin rotation (`gsk_...`) and auto-failover to OpenRouter (GPT-OSS-20B).
*   **Frontend:** React (Vite + TypeScript) — Recharts for Analytics, LangGraph-state-driven Trace Panel
*   **Resilience:** Auto-failover LLM routing and recursive Pydantic schema enforcement loops (`qwen_structured_with_reflection`)
*   **Security:** JWT-based authentication (`/token` endpoint); PII masking (`utils/security.mask_pii`) on all XAI trace logs


---

## 2. Core Components

### 2.1 Agent Orchestration (LangGraph)

The system uses LangGraph to manage deterministic flow between specialised agents. The central data structure is `FinancialState` (defined in `agents/state.py`), a shared typed dictionary that flows through all agents.

| Field | Purpose |
|---|---|
| `trigger` / `trigger_entity_id` | The event that kicked off this run |
| `invoice`, `budget`, `cash`, `reconciliation`, `credit`, `governance` | Agent-specific sub-contexts |
| `decision_ids` | Maps agent name → last logged decision UUID for causal linking |
| `pending_risk_assessments` | Multi-customer credit loop queue (V4) |
| `processed_risk_assessments` | Customers already checked in this run (V4) |
| `reasoning_trace` | Ordered list of XAI step entries for the UI Trace Panel |
| `error` / `error_agent` | Propagated error state for graceful degradation |

*   **Supervisor Agent:** Acts as the cognitive router. Based on the `trigger` field, it routes the state to the appropriate agent.
*   **Dynamic Handoffs:** Each agent returns a `next_agent` key, enabling non-linear, data-driven workflows (e.g. `reconciliation → credit → cash`).

---

### 2.2 Specialised Agents (Six-Agent Architecture)

#### Agent 1 — Invoice Agent (`agents/invoice_agent.py`)

**Workflow: 4-Stage Document Ingestion & Approval Pipeline**

1.  **OCR (3-Layer Pipeline):**
    *   Layer 1: Supabase Storage download + Baidu Qianfan-OCR-Fast via OpenRouter (primary; 99% confidence).
    *   Layer 2: Local Tesseract (fallback for offline/air-gapped processing; 80% confidence).
    *   Failure at this stage permanently rejects the invoice and logs an XAI decision.

2.  **Structured Extraction (Workhorse Tier):** Llama-3.1-8b-instant maps the OCR text to a structured schema (`vendor_name`, `invoice_number`, `invoice_date`, `total_amount`, `currency`, `department_id`). A **math validation** check (`subtotal + tax == total`) runs here; a mismatch reduces confidence by 15 points.

3.  **Fraud Prevention Layer (V4 — Thesis Improvement):** After extraction, the system calls `db.find_duplicate_invoice()` to check if the same vendor has already submitted an invoice with an identical number that is `approved`, `paid`, or `awaiting_approval`. On a hit:
    *   The invoice is immediately **rejected**.
    *   The fraud attempt is written to the `agent_memory` table as an episodic memory.
    *   An XAI decision of type `duplicate_detected` is logged with 100% confidence.

4.  **Vendor Risk Gate & Approval Routing:**
    *   Vendor risk score is loaded from `vendor_risk_scores`. New vendors receive a neutral baseline (50/100, `medium`).
    *   **Persistent Memory Check:** Past fraud memories for this vendor lower confidence by 20 pts and force human review regardless of risk score.
    *   **Risk Reasoning Enrichment (V4+):** The system now generates qualitative explanations for risk scores (e.g., citing long-term stability or identity verification needs) to aid human auditors.
    *   A **deterministic hard-stop gate** (budget utilisation ≥ 100%) runs before any LLM routing call.
    *   **Strategic Insights (V4+):** The approval prompt now requires the LLM to provide a forward-looking "Strategic Insight" in the business explanation, forecasting whether the department will stay under budget for the quarter based on current spend velocity.
    *   For all other cases, Qwen3 (`qwen_structured_with_reflection`) produces a `DecisionOutput` with `auto_approve`, `manager_review`, or `reject`. This **Reflection Pass** uses the Reasoning Tier (Qwen3) to audit the initial Workhorse Tier (Llama) decision.
    *   On auto-approval, a payment is immediately recorded via `db.record_payment()` (wire transfer).

**State Output:**  `next_agent → cash` (for liquidity checks during invoice flow).

---

#### Agent 2 — Budget Agent (`agents/budget_agent.py`)

The Budget Agent runs two distinct pipelines depending on the trigger, implemented via the `AgentPipeline` / `run_agent_pipeline` pattern from `utils/agent_modules.py` (Perception → Reasoning → Decision → Explanation → Execution → Communication).

**Pipeline A: `invoice_post_checks` (Deterministic, No LLM)**
*   Fetches the department's current `allocated`, `spent`, and `committed` budget.
*   Calculates projected utilisation: `(spent + committed + invoice_amount) / allocated × 100`.
*   Applies two thresholds (from `directives/policies.py BUDGET`):
    *   **Alert Threshold (95%):** Creates a `budget_alerts` row; escalates to senior manager.
    *   **Hard Stop Threshold (100%):** Mandatory rejection; bypasses all LLM reasoning.
*   Updates `budgets.committed` to reflect the newly pending invoice.

**Pipeline B: `budget_review` (LLM-Powered, Proactive)**
*   Scans **all** departments for the current period.
*   Identifies at-risk departments (utilisation ≥ `auto_approve_below`) and **surplus donors** (utilisation < 50%).
*   Reads episodic memory (past budget breaches per department) and injects historical context into the Qwen3 prompt.
*   Qwen3 produces: a narrative summary, per-department recommendations, a 30-day spend velocity forecast, and **reallocation suggestions** (from surplus → at-risk departments).
*   **Persistent Reallocation (V4):** All suggested reallocations are written to `budget_reallocations` table via `db.create_budget_reallocation()` for CFO review.
*   Budget breaches are persisted as `temporal` memories in `agent_memory`.

**State Output:** `next_agent → invoice` (pipeline A) or `END` (pipeline B).

---

#### Agent 3 — Cash Agent (`agents/cash_agent.py`)

**Three operating modes:**

1.  **`invoice_post_checks` — Liquidity Gate (Deterministic):**
    *   Implements the formula: `C_(t+1) = balance + projected_inflows - projected_outflows`.
    *   Projected inflows use a **Weighted Moving Average (WMA)** of the last 3 weeks' payment receipts (weights: 50/30/20%), blended with near-term receivables (0–7 days at full value, 8–30 days discounted by `CASH.far_discount`).
    *   If a budget breach is active in state, projected outflows are reduced by 20% (`spending_multiplier = 0.8`) to reflect tightened spending controls.
    *   Writes a 7-day cash flow forecast to `cash_flow_forecasts` (used by the dashboard chart).
    *   **State Output:** `next_agent → budget`.

2.  **`cash_position_refresh` — High-Risk Customer Refresh:**
    *   Triggered by the Credit Agent when a high-risk customer is identified.
    *   Refreshes the 7-day forecast and logs an XAI decision noting the conservative AR adjustment.

3.  **`ar_forecast_update` — Dynamic AR Discount (V4 — Thesis Improvement):**
    *   Triggered at the end of a full `Reconciliation → Credit → Cash` chain.
    *   Fetches the **system-wide risk score** from the latest `financial_state_snapshots` row.
    *   Applies a two-factor collection probability: `base_prob × (1 - system_risk/100)`.
    *   Base probs: `high → 40%`, `medium → 70%`, `low → 90%`.
    *   Updates open receivables' effective inflow forecast and logs the delta as an XAI decision.
    *   **Zero-value state guard:** If `total_at_risk == 0`, exits silently to prevent phantom risk propagation.
    *   Creates a causal link: `Credit decision → Cash AR adjustment`.

---

#### Agent 4 — Reconciliation Agent (`agents/reconciliation_agent.py`)

**4-Stage Forensic Matching Pipeline (V4+):**

1.  **Stage 0 — Semantic Memory Patterns (Episodic):** Before running algorithms, the agent scans `agent_memory` for known systematic mismatch rules (e.g. "Counterparty X always has a $2.00 bank fee"). This allows for zero-latency resolution of recurring discrepancies.
2.  **Stage 1 — TF-IDF Cosine Similarity:** Rapid matching of exact/near-exact text strings using `sklearn`. Threshold: ≥ 0.80.
3.  **Stage 2 — PGVector Semantic Search:** Items failing Stage 1 are re-scored using 384-dimensional MiniLM embeddings. The agent queries the entire bank history in Supabase using `pgvector` to find semantic matches (e.g. "AWS Cloud" vs "Amazon Web Svcs"). Threshold: ≥ 0.75.
4.  **Stage 3 — Multi-Currency Forensic Check:** For items with high semantic similarity but amount mismatches, the agent calculates the variance. If the discrepancy is ≤ 2% (controlled via `RECON.fx_tolerance`), it is automatically reconciled as an FX variance, satisfying multi-currency treasury requirements.

**LLM Anomaly Analysis:**
*   Qwen3 (`qwen_structured`) processes remaining anomalies to detect systematic patterns (e.g. ingestion failures).
*   If `is_systematic == True`, the agent stores a new `semantic` memory and escalates to the **Credit Agent**.

**Multi-Customer Credit Loop (V4):**
*   All affected customer IDs are placed in `pending_risk_assessments`.
*   The first customer is popped and set as `credit.customer_id`; remaining IDs stay in the queue.
*   `next_agent → credit` (or `END` if no anomalies).

---

#### Agent 5 — Credit Agent (`agents/credit_agent.py`)

**Deterministic Scoring Formula:**

```
R = clamp(0, 100, base_score − (delay_weight × f1) − (outstanding_weight × f2) − f3)
```

| Factor | Source |
|---|---|
| `f1` | `customers.payment_delay_avg` (real historical average from DB) |
| `f2` | `customers.total_outstanding / 1000` |
| `f3` | Dynamic reconciliation penalty (see below) |

**Dynamic Penalty (`calculate_dynamic_penalty`) — Thesis Improvement:**
*   Replaces legacy flat 20-point penalty.
*   Formula: `penalty = 15 + 5×(anomaly_count − 1) + min(10, 0.1×avg_variance)`, hard-capped at 50 pts.
*   Applied only when `customer_id ∈ recon_ctx.anomalous_customer_ids`.

**Persistent Memory:**
*   Reads the last 3 credit assessments for this customer from `agent_memory` and injects them into the Qwen3 prompt as `HISTORICAL CONTEXT`.
*   After assessment, stores the new result as an `episodic` memory entry.

**Autonomous Policy Enforcement:**
*   `risk_level == "high"` → Immediately slashes the customer's credit limit by 50%.
*   Advances `collection_stage` on all open receivables through the pipeline: `none → reminder → notice → escalated → legal`.

**Multi-Customer Loop (V4):**
*   If `credit.customer_id` is not set at entry, the agent pops the next ID from `pending_risk_assessments` and continues.
*   **State Output:** `next_agent → cash` (trigger: `ar_forecast_update`) if triggered by reconciliation, or `END`.

---

#### Agent 6 — Governance Auditor Agent (`agents/governance_agent.py`) — NEW in V4

**Role:** Final "Safety Gate" of every agentic run. Reviews the full `reasoning_trace` and cross-checks cross-agent consistency against fiscal policy (`directives/governance_policy.md`).

**Cross-Agent Conflict Detection:**
1.  **Budget vs. Invoice:** If `budget.hard_stop == True` but the invoice proceeded to approval logic → logs a `HIGH` severity `policy_breach` violation to `governance_violations`.
2.  **Credit vs. Invoice:** If a `high`-risk customer had an invoice > $5,000 auto-approved → logs a `MEDIUM` severity `risk_mismatch` violation.

**Output:** A `GovernanceOutput` Pydantic model containing:
*   `compliance_score` (0–100)
*   `decision`: `PASSED`, `FLAGGED`, or `BLOCKED`
*   `is_audit_safe` (boolean)
*   `findings` (list of plain-text conflict descriptions)

The Governance Agent is **always the last event** in the reasoning trace, providing a "seal of approval" linking all prior agent actions into a cohesive, auditable narrative.

---

### 2.3 Persistent Agent Memory (`agent_memory` table)

All agents can read and write structured memories to the `agent_memory` Supabase table via `db.store_memory()` and `db.get_recent_memories()`. Entity IDs must be valid UUIDs; department slugs are resolved via `db.get_department_uuid()` using a deterministic `uuid5` namespace that matches the seeder.

| Memory Type | Used By | Content |
|---|---|---|
| `episodic` | Invoice (fraud), Credit | Fraud event record; credit score + decision |
| `temporal` | Budget | Budget utilisation at breach time |
| `semantic` | Reconciliation | Anomaly count + summary per customer |

---

### 2.4 System Intelligence & XAI Tracing

*   **Tri-Layer Decision Logging:** Every agent logs a row to `agent_decisions` with three distinct explanation fields:
    *   `technical_explanation` — raw formula / model output
    *   `business_explanation` — plain-language business impact
    *   `causal_explanation` — what this decision unblocks or blocks downstream
*   **Causal Graph:** Decisions are linked via directed edges in `causal_links` (`cause → effect`, `relationship_type`, `strength`). The UI Trace Panel renders these edges as a full causal chain (e.g., `OCR → Extraction → Validation → Approval → Payment`).
*   **Macro-Financial Snapshots:** PostgreSQL triggers on key tables automatically snapshot the entire financial state (`financial_state_snapshots`) with `total_cash`, `total_ar`, and `system_risk_score`, ensuring historical consistency for trend analytics.
*   **PII Masking:** All XAI traces pass through `utils/security.mask_pii()` before being stored, preventing sensitive vendor/customer data from appearing in the audit log.

---

### 2.5 Resilience & Self-Correction

*   **Auto-Failover LLM Routing:** If the primary model (Qwen3-32B) encounters rate limits or downtime, the system automatically hot-swaps to a fallback model via OpenRouter.
*   **Recursive Pydantic Enforcement (`qwen_structured_with_reflection`):** All structured AI extractions are validated against Pydantic schemas. Invalid JSON is fed back into the prompt, forcing the LLM to self-correct before the LangGraph pipeline continues.
*   **Defensive State Refetch:** If an in-memory invoice amount is null (extraction edge-case), the Invoice Agent re-fetches the persisted row from Supabase before routing.
*   **Graceful Degradation:** `db.store_memory()` and `db.get_recent_memories()` catch all exceptions and log a warning rather than crashing the pipeline.
*   **Zero-Value State Guard (Cash Agent):** Prevents phantom risk calculations by silently exiting the AR forecast path when a customer has $0 in open receivables.

---

### 2.6 Directive Policy System (`directives/`)

Agents inject policy documents into their LLM prompts via `utils/directives.inject_directive()`. Thresholds and weights are centralised in `directives/policies.py` and never hardcoded in agent logic.

| Policy Object | Key Thresholds |
|---|---|
| `BUDGET` | `alert_threshold = 95%`, `hard_stop_threshold = 100%`, `auto_approve_below = 80%` |
| `CREDIT` | `base_score`, `delay_weight`, `outstanding_weight`, `high_risk_below`, `medium_risk_below` |
| `CASH` | `minimum_balance`, `near_window_days = 7`, `far_window_days = 30`, `far_discount`, `wma_weights`, `forecast_days` |
| `RECON` | `match_threshold`, `semantic_match_threshold`, `max_fetch` |

Narrative policy documents (`budget_policy.md`, `governance_policy.md`, etc.) are loaded on-demand and injected as system-prompt context.

---

## 3. API Layer (`routers/`)

The FastAPI backend exposes the following router namespaces:

| Router | Prefix | Description |
|---|---|---|
| `invoice.py` | `/api/invoice` | Upload & trigger invoice processing |
| `budget.py` | `/api/budget` | Budget status, alerts, and reallocation suggestions |
| `cash.py` | `/api/cash` | Cash balances, forecast, and liquidity checks |
| `reconciliation.py` | `/api/reconciliation` | Trigger reconciliation; fetch reports & items |
| `credit.py` | `/api/credit` | Customer credit scores & risk assessments |
| `payment.py` | `/api/payment` | Payment records |
| `departments.py` | `/api/departments` | Department list |
| `analytics.py` | `/api/analytics` | Research metrics, historical liquidity, and DSO |

**Authentication:** All protected endpoints require a Bearer JWT obtained from `POST /token` (admin credentials from `.env`).

**Bootstrap:** On startup, `utils/bootstrap.seed_if_empty()` seeds the database with synthetic ERP data if empty, and `ensure_initial_match_state()` prepares baseline reconciliation state.

---

## 4. Frontend Dashboard (`components/`)

The React frontend (Vite + TypeScript) provides the following views:

| Component | View |
|---|---|
| `OverviewView.tsx` | KPI cards (liquidity, match rate, DSO, invoice health) |
| `InvoiceView.tsx` | Invoice list, status badges, OCR confidence |
| `BudgetView.tsx` | Departmental utilisation bars, alerts, reallocation panel |
| `CashView.tsx` | 7-day liquidity forecast chart, shortfall indicators |
| `ReconciliationView.tsx` | Match rate analytics, anomaly list, reconciliation history |
| `CreditView.tsx` | Customer risk scores, collection stage pipeline |
| `AgingDashboard.tsx` | AR aging buckets |
| `GovernanceView.tsx` | Compliance score, violation log, audit findings |
| `TracePanel.tsx` | XAI causal graph — full decision chain for any run |
| `EvaluationView.tsx` | Thesis evaluation suite — quantitative metrics, sensitivity analysis, scenario testing |
| `DisputePortal.tsx` | Invoice dispute workflow |

---

## 5. Evaluation & Performance Analytics

### 5.1 XAI Causal Tracing (Built-in)
FAgentLLM uses its own native causal graph stored in Supabase (`agent_decisions` + `causal_links`) to provide full trace visibility across all LangGraph hops. The `analytics` router exposes `get_research_metrics()` which calculates:
*   Total liquidity (in millions, across all cash accounts)
*   Latest reconciliation match rate
*   AP health (paid vs. total invoices)
*   Total agent decisions and causal links logged
*   DSO (Days Sales Outstanding): `(total_open_AR / revenue_90d) × 90`

### 5.2 Thesis Evaluation Suite (`EvaluationView.tsx`)
The `EvaluationView` component provides a professional-grade, research-oriented reporting interface including:
*   Quantitative performance metrics against baseline benchmarks
*   Sensitivity analysis across key policy thresholds
*   Scenario-based testing results (invoice fraud, budget breach, credit escalation)
*   Academic-standard discussion of system limitations and theoretical implications

### 5.3 Visual Analytics Dashboard
The frontend incorporates Recharts-based analytics across all domain views:
*   Real-time reconciliation match rates and anomaly trends
*   Cash flow forecast charts (7-day + 13-week projections)
*   Budget utilisation heatmaps and reallocation advisor
*   Historical liquidity trend (from `financial_state_snapshots`)

---

## 6. Database Schema Highlights

Key tables (full schema in `schema.sql`):

| Table | Purpose |
|---|---|
| `agent_decisions` | XAI decision log (every agent action) |
| `causal_links` | Directed edges of the causal graph |
| `agent_memory` | Persistent episodic/temporal/semantic memory |
| `financial_state_snapshots` | Macro-financial snapshots (PostgreSQL trigger-driven) |
| `governance_violations` | Cross-agent policy breach log |
| `budget_reallocations` | Persistent CFO-reviewable reallocation suggestions |
| `transactions` | Internal + bank transactions with `match_score` and `embedding` (pgvector) |
| `reconciliation_reports` / `reconciliation_report_items` | Per-run reconciliation output |
| `cash_flow_forecasts` | Agent-generated 7-day rolling forecast |

---

## 7. Running the System

**Backend:**
```powershell
# From project root, with venv activated:
uvicorn main:app --reload --port 8000
```

**Frontend:**
```powershell
npm run dev
```

The backend bootstraps data automatically on first startup. The CORS policy allows origins on ports `5173–5177` (Vite default + hot-reload variants).

---

## 8. Future Work

1.  **Live API Integration:** Transitioning from the internal synthetic data seeder to live Open Banking and ERP API integrations.
2.  **Collection Automation:** External communication pathways (Email/SMS via Twilio/SendGrid) for the Credit Agent to actively execute its generated collection workflows.
3.  **PgVector Scaling:** Upgrading reconciliation from batch TF-IDF + MiniLM to a fully persistent vector-DB-first architecture, enabling semantic matching across the entire transaction history rather than just the current unmatched batch.
4.  **Multi-Tenant Architecture:** Extending `FinancialState` and the budget/credit policy objects to support multiple independent organisations within the same deployment.
