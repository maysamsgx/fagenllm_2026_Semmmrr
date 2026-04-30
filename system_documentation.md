# FAgentLLM V3: System Architecture & Implementation Documentation

## 1. System Overview

FAgentLLM is a multi-agent LLM financial automation system designed to handle the lifecycle of financial operations, including invoice processing, budget monitoring, liquidity checks, reconciliation, and credit risk assessment.

The system relies on a **10/10 Causal Perfection Architecture**, which emphasizes **Explainable AI (XAI)**. Every action taken by any agent is logged as a "decision" and linked to other decisions via a causal graph, allowing the business to trace exactly *why* an action was taken (e.g., "Why was this invoice auto-approved?").

### Technology Stack
*   **Orchestration:** LangGraph (Python)
*   **Backend:** FastAPI (Python)
*   **Database:** Supabase (PostgreSQL with Realtime triggers)
*   **LLMs:** Qwen models via Baidu Qianfan API (for extraction, validation, and complex reasoning)
*   **Frontend:** React (Vite) + Tailwind CSS (assumed based on standard patterns)

## 2. Core Components

### 2.1 Agent Orchestration (LangGraph)
The system uses LangGraph to manage the flow of data between specialized agents. The core of this is the `FinancialState` (`agents/state.py`), a shared TypedDict that flows through all agents.
*   **Supervisor Agent:** Acts as the traffic cop (`agents/supervisor.py`). Based on the trigger event (e.g., `invoice_uploaded`, `cash_position_refresh`), it routes the state to the appropriate first agent.
*   **Conditional Edges:** After an agent completes its work, it specifies the `next_agent` in the state. The graph router follows this until `END` is reached.

### 2.2 Specialized Agents

1.  **Invoice Agent (`invoice_agent.py`):**
    *   **Triggers:** `invoice_uploaded`, `invoice_post_checks`
    *   **Workflow:** Runs OCR on uploaded documents, extracts structured data using Qwen LLM, validates vendor risk, and ultimately decides on approval routing (auto-approve, manual, reject) based on cash and budget constraints.
    *   **Action:** If auto-approved, it automatically records a wire payment.

2.  **Budget Agent (`budget_agent.py`):**
    *   **Triggers:** `budget_review`, `invoice_post_checks`
    *   **Workflow:** Checks department budgets against incoming invoices. Evaluates if the current invoice will cause a budget breach (e.g., > 95% utilization).
    *   **Action:** Triggers budget alerts if thresholds are breached and updates committed spend.

3.  **Cash Agent (`cash_agent.py`):**
    *   **Triggers:** `cash_position_refresh`, `invoice_post_checks`
    *   **Workflow:** Calculates short-term liquidity. It projects 7-day inflows (receivables + weighted moving average of historical collections) and outflows (approved invoices).
    *   **Action:** Determines if paying an invoice will drop the cash balance below the minimum threshold.

4.  **Reconciliation Agent (`reconciliation_agent.py`):**
    *   **Triggers:** `daily_reconciliation`, `manual_reconciliation`
    *   **Workflow:** Compares internal transactions with bank transactions. Uses TF-IDF vectorization and cosine similarity to match strings (amount, date, description) with an 80% threshold.
    *   **Action:** Logs matched and anomalous transactions. Uses Qwen LLM to analyze anomalies for systematic issues, potentially routing to the Credit agent if a specific customer pattern is detected.

5.  **Credit Agent (`credit_agent.py`):**
    *   **Triggers:** `customer_payment_check`, `daily_reconciliation`
    *   **Workflow:** Assesses customer credit risk based on payment delays and outstanding debt using a custom interpretable formula. Validates the mathematical assessment with LLM reasoning.
    *   **Action:** Flags customers as high/medium/low risk. High risk triggers a downstream cash position refresh.

### 2.3 System Intelligence & XAI Tracing
*   **Agent Decisions:** Every agent logs its reasoning (Technical, Business, and Causal explanations) to the `agent_decisions` table.
*   **Causal Links:** The system connects decisions (e.g., OCR Output -> Extraction -> Validation -> Approval) in the `causal_links` table, proving a traceable graph of *why* the AI did what it did.
*   **Financial State Snapshots:** PostgreSQL triggers automatically snapshot the entire financial state (cash, payables, receivables, risk) whenever key tables are updated.

## 3. Database Architecture (Supabase schema.sql)

The database schema is highly normalized and robust:
*   **Core Entities:** `departments`, `vendors`, `customers`.
*   **Transaction Entities:** `invoices`, `payments`, `budgets`, `receivables`, `transactions`, `cash_accounts`.
*   **Intelligence Entities:** `agent_decisions`, `causal_links`, `financial_state_snapshots`, `vendor_risk_scores`.
*   **Triggers:** `fn_snapshot_financial_state` acts as a massive audit trigger. Anytime financial data changes, it captures a macro snapshot.
*   **Realtime:** Most tables are added to the `supabase_realtime` publication, allowing the frontend to react to state changes instantly.

## 4. Important Implementation Steps (The Workflow)

Let's trace a standard invoice upload workflow:
1.  **Trigger:** User uploads an invoice. API calls Supabase to create an `invoices` row and triggers the LangGraph with `invoice_uploaded`.
2.  **Supervisor:** Routes to the **Invoice Agent**.
3.  **Extraction:** Invoice Agent runs OCR -> Qwen LLM extracts JSON -> Vendor Risk is checked -> State updated -> Routes back to Supervisor with `next_agent="cash"`.
4.  **Liquidity Check:** **Cash Agent** projects 7-day cash flow to ensure paying the invoice won't drain the accounts -> Updates state -> Routes to `budget`.
5.  **Budget Check:** **Budget Agent** checks department allocation. If safe, it updates committed funds -> Routes to `invoice`.
6.  **Final Approval:** **Invoice Agent** (triggered via `invoice_post_checks`) looks at the cash and budget context. It uses the LLM to make a final routing decision (Auto-Approve, Reject, or Await Manual).
7.  **Payment:** If Auto-Approved, the system inserts a `payments` record.
8.  **Audit:** Throughout this process, at least 6 separate `agent_decisions` and `causal_links` are saved to the database.

## 5. What is Working Well

*   **Explainable AI (XAI) Implementation:** The separation of `technical_explanation`, `business_explanation`, and `causal_explanation` is phenomenal. Building a causal graph in SQL (`causal_links`) provides unparalleled auditability for financial compliance.
*   **Event-Driven Database Triggers:** Using Postgres triggers (`fn_snapshot_financial_state`) to automatically snapshot the macro-financial state prevents the agents from having to manage complex global state updates manually. It guarantees data consistency.
*   **Stateful Orchestration:** LangGraph is used effectively. Sharing a single `FinancialState` dictionary that agents mutate ensures clean handoffs and prevents race conditions.
*   **Mathematical + LLM Hybrid Logic:** Agents (like Credit and Cash) use deterministic math (e.g., Weighted Moving Averages, cosine similarity) for the heavy lifting, and only use LLMs for summarization, anomaly detection, and final reasoning. This saves tokens, reduces latency, and prevents LLM hallucinations on basic arithmetic.

## 6. Areas for Further Improvement

1.  **OCR Fallback & Error Handling:**
    *   *Issue:* In `invoice_agent.py`, if OCR fails, the whole pipeline breaks and the invoice is rejected.
    *   *Fix:* Implement a robust retry mechanism or fallback to a simpler text-extraction method (e.g., PyMuPDF for digital PDFs) before failing entirely.

2.  **Reconciliation Scalability:**
    *   *Issue:* The Reconciliation Agent uses TF-IDF and cosine similarity in-memory over the `all_strings` array. For 100 transactions, this is fine. For 100,000, this will cause memory issues and massive latency.
    *   *Fix:* Move vector matching to the database using `pgvector`. Store embeddings on the `transactions` table when they are created, and do a vector similarity search in SQL.

3.  **LLM Call Caching & Resiliency:**
    *   *Issue:* The system relies heavily on synchronous Qwen API calls. If the LLM provider experiences downtime, the financial graph stalls.
    *   *Fix:* Implement asynchronous LLM calls (`async def`) and add caching for identical inputs (e.g., identical anomaly descriptions). Add circuit breakers for the LLM API.

4.  **Concurrency / Race Conditions:**
    *   *Issue:* The `Budget Agent` reads the `spent` and `committed` amounts, calculates new utilization, and then updates the database. If two invoices hit the budget agent simultaneously, one might overwrite the other's committed spend due to a read-modify-write race condition.
    *   *Fix:* Use atomic SQL updates (e.g., `UPDATE budgets SET committed = committed + amount WHERE id = X`) instead of calculating it in Python and writing the absolute value back.

5.  **Hardcoded Configurations:**
    *   *Issue:* Values like `min_balance = 10000.0` in the Cash Agent and `threshold = 0.8` in the Reconciliation Agent are hardcoded.
    *   *Fix:* Move these to a `system_settings` table in Supabase so administrators can tune the AI behavior via the frontend dashboard without deploying new code.
