<div align="center">

https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260403_050628_c4e32401-fab4-4a27-b7a8-6e9291cd5959.mp4

# 🌌 FAgentLLM
**Five Agents, One Vision: Smarter Finance, Better Decisions.**

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg?style=for-the-badge&logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://reactjs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-FF9900?style=for-the-badge&logo=langchain&logoColor=white)](https://www.langchain.com/langgraph)

*A unified multi-agent LLM architecture that overcomes fragmented enterprise finance operations through autonomous orchestration, causal reasoning, and explainable decision-making.*

</div>

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
- **📄 3-Layer Resilient OCR Pipeline**: Cascading document ingestion via PyMuPDF (Native) → Baidu Qianfan (Cloud) → Tesseract + LayoutLMv3 (Local fallback).
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

The core of FAgentLLM is built on **LangGraph**. The state is passed as a `FinancialState` dictionary through the nodes. 

1. **Input**: An event (e.g., invoice upload, reconciliation trigger) initiates the graph.
2. **Perception**: Agents pull relevant context from the Supabase ERP ledger.
3. **Reasoning**: Agents use the LLM to interpret complex/qualitative rules or deterministic models for hard math.
4. **Action**: Agents mutate the database (e.g., deducting budgets, flagging risk).
5. **Causal Linking**: If an agent's decision impacts another domain, it explicitly logs a `causal_link` to the database, forming a traversable BFS graph for the XAI trace UI.

---

## 🔮 Future Improvements / Roadmap

- [ ] **Asynchronous Event Bus**: Migrate from sequential LangGraph routing to an asynchronous pub/sub model (e.g., Kafka) for true parallel execution.
- [ ] **Vector Embeddings (RAG)**: Replace the current TF-IDF / textual matching with SBERT embeddings stored in `pgvector` for enhanced reconciliation accuracy.
- [ ] **External Integration**: Hook the Credit Agent's escalation logic into Twilio/SendGrid APIs for real automated collection notices.

---

<div align="center">
  <p>Built for the future of Autonomous Enterprise Finance.</p>
</div>
