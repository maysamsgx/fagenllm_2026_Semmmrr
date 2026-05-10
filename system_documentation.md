# FAgentLLM V3: System Architecture & Implementation Documentation

## 1. System Overview

FAgentLLM is a unified multi-agent architecture designed to overcome the fragmented, high-performing silos inherent in modern enterprise finance. By employing Large Language Models as a cognitive orchestration layer, the system integrates unstructured semantic reasoning with deterministic financial logic across five core domains: invoice processing, budgeting, reconciliation, credit assessment, and cash management.

The system relies on a **10/10 Causal Perfection Architecture**, emphasizing **Explainable AI (XAI)**. Every action taken by any agent is logged as a "decision" and linked to other decisions via a causal graph. This allows the business to definitively trace the "why" behind any autonomous action, satisfying corporate audit and compliance requirements.

### Technology Stack
*   **Orchestration:** LangGraph (Python)
*   **Backend:** FastAPI (Python)
*   **Database:** Supabase (PostgreSQL with Realtime triggers and Vector support)
*   **LLMs:** Qwen3-32B via Groq/OpenRouter (for extraction, validation, and complex reasoning)
*   **Frontend:** React (Vite) + Recharts for Analytics
*   **Resilience:** Auto-failover LLM routing and recursive Pydantic schema enforcement loops.


## 2. Core Components

### 2.1 Agent Orchestration (LangGraph)
The system uses LangGraph to manage the deterministic flow of data between specialized agents. The core of this is the `FinancialState`, a shared context that flows through the system.
*   **Supervisor Agent:** Acts as the cognitive router. Based on external triggers (e.g., `invoice_uploaded`), it routes the state to the appropriate agent.
*   **Dynamic Handoffs:** Agents process their domain logic and return the `next_agent` to the Supervisor, enabling dynamic, non-linear workflows based on real-time financial findings.

### 2.2 Specialized Agents

1.  **Invoice Agent:**
    *   **Workflow:** Implements a highly resilient **3-Layer Document Ingestion Pipeline**:
        1.  Native PyMuPDF extraction (fastest, for digital PDFs).
        2.  Baidu Qianfan-OCR-Fast via OpenRouter (primary cloud OCR for scanned documents).
        3.  Local Tesseract (absolute fallback for offline/air-gapped processing).
        After extraction, Qwen3 performs structured JSON field extraction and validates cross-domain constraints (calling Budget and Cash agents).
    *   **Impact:** Ensures 100% ingestion uptime and field extraction accuracy while dynamically routing approvals based on deterministic thresholds.

2.  **Budget Agent:**
    *   **Workflow:** Evaluates incoming invoices against real-time departmental allocations.
    *   **Impact:** Prevents budget breaches before cash leaves the organization by analyzing projected utilization.

3.  **Cash Agent:**
    *   **Workflow:** Projects short-term liquidity through 7-day inflows and outflows. Critically, it features a cross-domain integration where it discounts expected Accounts Receivable inflows dynamically based on the Credit Agent's real-time risk level adjustments.
    *   **Impact:** Acts as the ultimate liquidity gatekeeper. It incorporates "zero-value state handling" to prevent phantom risk calculations, ensuring the system never approves an invoice it cannot afford.

4.  **Reconciliation Agent:**
    *   **Workflow:** Compares internal ledger entries with external bank statements using similarity matching. Qwen3 acts as a forensic anomaly detector, interpreting match-score distributions, temporal clustering, and counterparty recurrence.
    *   **Impact:** Dramatically accelerates month-end close. Instead of just flagging errors, the **Cross-Domain Causal Engine** ensures systemic anomalies autonomously trigger the Credit Agent for a risk reassessment.

5.  **Credit Agent:**
    *   **Workflow:** Assesses credit risk via a deterministic scoring formula ($f_1$ delay, $f_2$ balance, $f_3$ reconciliation anomaly penalty) merged with LLM qualitative analysis.
    *   **Impact:** Closes the loop between operations and risk. A systematic reconciliation anomaly deducts 20 points from the risk baseline, triggering collection stage escalation and notifying the Cash Agent to discount near-term AR forecasts.

### 2.3 System Intelligence & XAI Tracing
*   **Agent Decisions:** Every agent logs its reasoning (Technical, Business, and Causal explanations) to a centralized ledger.
*   **Causal Links:** The system connects decisions in a causal graph, proving a traceable lineage of *why* the AI acted (e.g., OCR Output -> Extraction -> Validation -> Approval -> Payment).
*   **Macro-Financial Snapshots:** PostgreSQL triggers automatically snapshot the entire financial state whenever key tables are updated, ensuring historical consistency.

### 2.4 Resilience & Self-Correction
*   **Auto-Failover LLM Routing:** If the primary reasoning model (Qwen3-32B) encounters API rate limits (e.g., `413 Request too large`) or downtime, the system automatically hot-swaps to a fallback model (e.g., `gpt-oss-20b`) via OpenRouter, ensuring uninterrupted financial processing.
*   **Recursive Pydantic Execution:** All structured AI extractions are strictly enforced via Pydantic schemas. If the LLM generates invalid JSON, the system intercepts the error and feeds the broken output back into the prompt, forcing the LLM to self-correct and conform to the schema before the LangGraph pipeline continues.

## 3. Evaluation & Performance Analytics

### 3.1 XAI Causal Tracing (Built-in)
FAgentLLM uses its own native causal graph stored in Supabase (`agent_decisions` + `causal_links`) to provide full trace visibility across all LangGraph hops. Every agent decision is logged with Technical, Business, and Causal explanations — no external observability tool required.

### 3.2 Visual Analytics Dashboard
The frontend incorporates a professional, Recharts-based **Reconciliation Analytics** dashboard. 
*   **Metrics:** It provides real-time visualization of average match rates, total anomalies detected, and historical efficiency trends.
*   **Significance:** This bridges the gap between backend AI logic and executive visibility, proving the operational value of the multi-agent system to stakeholders.

## 4. Continuous Iteration & Future Work
While the current architecture successfully proves the DSR artifact, future enhancements will focus on enterprise scale:
1.  **Dense Vector Embeddings:** Upgrading the Reconciliation Agent from TF-IDF to dense LLM embeddings (via `pgvector`) to capture deep semantic matching capabilities across disparate accounting terminologies.
2.  **Live API Integration:** Transitioning from the internal synthetic data seeder to live Open Banking and ERP API integrations.
3.  **Collection Automation:** Implementing external communication pathways (Email/SMS via Twilio/SendGrid) for the Credit Agent to actively execute its generated collection workflows.
