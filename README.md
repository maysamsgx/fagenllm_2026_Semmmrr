![FAgentLLM Banner](public/assets/image.png)

# 🌌 FAgentLLM
**Five Agents, One Vision: Smarter Finance, Better Decisions.**

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg?style=for-the-badge&logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://reactjs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-FF9900?style=for-the-badge&logo=langchain&logoColor=white)](https://www.langchain.com/langgraph)

*A unified multi-agent LLM architecture that overcomes fragmented enterprise finance operations through autonomous orchestration, causal reasoning, and explainable decision-making.*


---

## 📖 Project Overview

**FAgentLLM** is an advanced, multi-agent financial intelligence system designed to replicate and automate the complex, cross-domain decision-making processes of a corporate finance department. 

Instead of relying on rigid, rule-based ERP systems or isolated AI chat interfaces, FAgentLLM deploys **five specialized autonomous agents** (Invoice, Budget, Cash, Reconciliation, and Credit) that communicate, validate, and causally influence each other's decisions in real-time.

### ❓ Why this project exists (The Problem)
Enterprise finance teams suffer from massive operational silos. Accounts Payable doesn't dynamically talk to Treasury, and Credit Risk doesn't instantly react to Reconciliation anomalies. This fragmentation causes delayed reporting, missed liquidity risks, and manual data-entry bottlenecks. 

### 💡 The Solution
FAgentLLM solves this by acting as a **Cognitive Intelligence Layer** over traditional ERP data. When an anomaly occurs in reconciliation, the system autonomously traces the causal chain—instantly recalculating credit risk and adjusting near-term liquidity forecasts—with full Explainable AI (XAI) transparency.

---

## ✨ Key Features

- **🤖 5-Agent Ecosystem**: Specialized agents orchestrating Invoice, Budget, Cash, Reconciliation, and Credit operations.
- **📄 3-Layer Resilient OCR Pipeline**: Cascading document ingestion via PyMuPDF (Native) → Baidu Qianfan (Cloud) → Tesseract (Local fallback).
- **🔗 Causal Domain Reasoning**: The XAI engine dynamically links agent decisions. An anomaly in reconciliation autonomously triggers a credit risk reassessment and adjusts AR liquidity forecasts.
- **🛡️ Deterministic Financial Guardrails**: LLMs are used strictly for cognitive routing and qualitative analysis, while math, budgets, and similarities are enforced via hard deterministic formulas.
- **📊 Forensic Audit Tracing**: A beautiful React frontend that visualizes the exact technical, business, and causal reasoning behind every single autonomous decision.

---

## 🛠️ Tech Stack

### Backend / AI Orchestration
- **Python 3.11+**
- **FastAPI** (High-performance API routing)
- **LangGraph** (Stateful multi-agent orchestration)
- **Qwen3-32B** (Primary reasoning LLM via Groq)
- **Baidu Qianfan / Tesseract** (OCR pipeline)

### Frontend / UI
- **React 18 + Vite**
- **TypeScript**
- **Vanilla CSS** (Glassmorphism & modern design tokens)

### Database
- **Supabase (PostgreSQL)** (Real-time state and causal link storage)

---

## 🚀 Installation & Setup

### 1. Clone the repository
```bash
git https://github.com/maysamsgx/fagenllm_2026_Semmmrr
cd FAgentLLM
```

### 2. Set up the Python backend
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Set up environment variables
Create a `.env` file in the root directory (see `.env.example`):
```env
# Database
SUPABASE_URL="your_supabase_url"
SUPABASE_KEY="your_supabase_key"

# LLM Providers
GROQ_API_KEY="your_groq_key"
OPENROUTER_API_KEY="your_openrouter_key"
```

### 4. Run the Application
Start the FastAPI backend:
```bash
uvicorn main:app --reload --port 8000
```
Start the Vite frontend (in a new terminal):
```bash
npm install
npm run dev
```

---

## 🏗️ System Architecture

FAgentLLM is built on a **Supervisor-led Multi-Agent Orchestration** model using **LangGraph**. The architecture emphasizes modularity, shared state consistency, and causal explainability.

### 1. The Multi-Agent Cognitive Graph
The system operates as a **Stateful Agentic Hub**. Control is managed by the **Supervisor (Router)**, but communication is handled through the **Shared Financial State**. This prevents tight coupling and allows for asynchronous "Stigmergic" coordination.

```mermaid
graph LR
    %% Control Layer
    subgraph Control ["Cognitive Control Layer"]
        Supervisor{agent_supervisor}
    end

    %% State Layer (The Hub)
    subgraph State ["Shared Financial State (Memory Hub)"]
        FS((FinancialState))
    end

    %% Execution Layer (The Agents)
    subgraph Agents ["Domain Expert Agents"]
        Invoice[Invoice Agent]
        Budget[Budget Agent]
        Cash[Cash Agent]
        Recon[Reconciliation Agent]
        Credit[Credit Agent]
    end

    %% Routing Flow (Control)
    Supervisor -->|delegates| Invoice
    Supervisor -->|delegates| Budget
    Supervisor -->|delegates| Cash
    Supervisor -->|delegates| Recon
    Supervisor -->|delegates| Credit

    %% State Interaction (Data)
    Invoice <--> FS
    Budget <--> FS
    Cash <--> FS
    Recon <--> FS
    Credit <--> FS

    %% Persistence
    FS -.-> DB[(Supabase ERP Ledger)]
```

### 2. The FinancialState (Shared Memory)
The `FinancialState` is the single source of truth. Instead of agents passing messages to each other (which is brittle), they mutate the **Shared State Hub**. 
*   **The Workflow:** An agent reads the current state, performs its specialized logic (LLM reasoning + Deterministic Math), and writes its findings back to the Hub. 
*   **Causal Linkage:** When the state is updated, it triggers the next node in the LangGraph, creating a chain of autonomous reasoning.

### 3. Causal Reasoning Engine
The most innovative part of the architecture is the **Causal Linkage System**. When the Reconciliation Agent detects an anomaly, it doesn't just log it; it proactively creates a `causal_link` to the Credit Agent, forcing a risk-score reduction.

```mermaid
sequenceDiagram
    participant R as Reconciliation Agent
    participant C as Credit Agent
    participant S as Cash Agent
    
    R->>R: Detects Duplicate Transaction
    R->>C: PROACTIVE: Flag Risk Score reduction (-20 pts)
    C->>C: Lower Credit Limit
    C->>S: PROACTIVE: Apply Risk Discount to AR Forecast
    S->>S: Adjust 7-Day Liquidity Forecast
```

### 4. Deterministic Guardrails
To prevent "LLM Hallucinations" in financial contexts, the system employs a **Hybrid Execution Model**:
*   **LLM (Qwen3):** Handles qualitative reasoning, semantic interpretation, and complex decision-routing.
*   **Math Engine:** All budget subtractions, cash-flow totals, and risk score calculations are enforced via **Hard Python Logic**, ensuring 100% mathematical integrity.

---

## 🔮 Future Improvements / Roadmap

- [ ] **Asynchronous Event Bus**: Migrate from sequential LangGraph routing to an asynchronous pub/sub model (e.g., Kafka) for true parallel execution.
- [ ] **Vector Embeddings (RAG)**: Replace the current TF-IDF / textual matching with SBERT embeddings stored in `pgvector` for enhanced reconciliation accuracy.
- [ ] **External Integration**: Hook the Credit Agent's escalation logic into Twilio/SendGrid APIs for real automated collection notices.

---

<div align="center">
  <p>Built for the future of Autonomous Enterprise Finance.</p>
</div>
