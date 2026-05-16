# FAgentLLM — Enterprise Deployment & Setup Guide

This guide details the deployment process for FAgentLLM, a multi-agent financial automation architecture (v4). This setup validates the system for Design Science Research (DSR) methodology, encompassing the **10/10 Causal Perfection Architecture** with 6 autonomous agents, persistent pgvector memory, and real-time governance.

---

## Prerequisites

Ensure the following environments and accounts are provisioned:

- **Python 3.11+**
- **Node.js 18+**
- **Git**
- **Supabase Account** (Database & Realtime pub/sub with `pgvector` enabled)
- **Groq API Key** (Orchestration & Reasoning via Qwen3-32B)
- **OpenRouter API Key** ( OCR - Baidu Qianfan and fallback LLM for reasoing )

---

## 1. Repository & Environment Initialization

Clone the architecture repository:
```bash
git clone https://github.com/maysamsgx/fagenllm_2026_Semmmrr
cd fagenllm_2026_Semmmrr
```

Provision and **activate** an isolated Python environment:
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate
```

Install the required packages (ensure `venv` is active):
```bash
pip install -r requirements.txt
```

---

## 2. Environment Configuration

Copy the configuration template:
```bash
cp .env.example .env  # Use 'copy' on Windows
```

Populate the `.env` file with your specific credentials:

```env
# Database Infrastructure
SUPABASE_URL=https://[YOUR_PROJECT].supabase.co
SUPABASE_ANON_KEY=[YOUR_ANON_KEY]
SUPABASE_SERVICE_KEY=[YOUR_SERVICE_ROLE_KEY]
DATABASE_URL=postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres

# Frontend Client (Vite)
VITE_SUPABASE_URL=https://[YOUR_PROJECT].supabase.co
VITE_SUPABASE_ANON_KEY=[YOUR_ANON_KEY]

# Cognitive Orchestration (Rate Limit Resilience)
# Use GROQ_API_KEYS (plural) with commas to enable multi-key rotation
GROQ_API_KEYS=gsk_key1,gsk_key2
GROQ_BASE_URL=https://api.groq.com/openai/v1

# Tiered Model Strategy
QWEN_MODEL=qwen/qwen3-32b                   # Reasoning Tier
WORKHORSE_MODEL=llama-3.1-8b-instant       # Workhorse Tier (High-speed)

# Fallback & OCR
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_FALLBACK_MODEL=baidu/cobuddy:free
OCR_MODEL=baidu/qianfan-ocr-fast:free
```

---

## 3. Database Provisioning & Data Seeding

1. Navigate to the **SQL Editor** in your Supabase dashboard.
2. Execute the contents of `schema.sql`. This establishes the normalized financial entities, the `pgvector` memory tables, and the Explainable AI (XAI) causal graph tables (`agent_decisions`, `causal_links`).
3. Seed the database with synthetic financial data (~10k relational records):

```bash
# Verify constraints with a dry run
python erp_seed.py --dry-run

# Execute the active seed
python erp_seed.py
```

---

## 4. System Execution

### The Orchestration API (Backend)
Run the FastAPI server which hosts the LangGraph supervisor and the 6-agent system:
```bash
# Ensure venv is active
uvicorn main:app --reload --port 8000
```
*Health Check:* Navigate to `http://localhost:8000/health`. You should receive a `status: ok` confirming "FAgentLLM v4.2 (10/10 Architecture)" is online.

### 5. Essential: Vector Warming (First Run Only)
Before running the first reconciliation, backfill MiniLM embeddings for all existing transactions so Stage 2 semantic search has full coverage:
```bash
python -m scripts.warm_vectors
```

> **Why this matters:** `scripts/warm_vectors.py` imports `tx_to_string` directly from `agents/reconciliation_agent.py`. This guarantees that offline-warmed embeddings are encoded with the exact same text normalisation (absolute amount, noise-word removal) that the agent uses at query time. Divergent encodings produce cosine similarity ≈ 0, making Stage 2 effectively blind.

After this initial run, the reconciliation agent automatically computes and stores embeddings for any new bank transactions it encounters, so this script only needs to be re-run when seeding a fresh database.

### The Operations Dashboard (Frontend)
Initialize the Vite development server in a separate terminal:
```bash
npm install
npm run dev
```
*Access:* Navigate to `http://localhost:5173`. 
*Credentials:* Authenticate using `admin` / `admin123`.

---

## 5. System Evaluation & Testing

The system is designed for autonomous operation triggered by state changes across 8 integrated views.

### Interactive Testing via UI
1. **Invoice & Budget Loop:** Upload an invoice in the `Invoice` tab. Watch the **Budget Agent** and **Cash Agent** cooperate to validate the spend against departmental limits and real-time liquidity.
2. **Persistent Memory:** Observe the **Credit Agent** using `pgvector` memory to recall past payment delays and apply forensic risk penalties to customer scores.
3. **Governance Audit:** Navigate to the `Governance` tab to view real-time compliance monitoring and any detected policy violations across agent interactions.

### DSR Quantitative Evaluation
1. **Analytics Dashboard:** Navigate to `Reconciliation` → `Analytics` for performance metrics on transaction matching. The UI spinner stops automatically as soon as the new report is detected, rather than waiting a fixed 90 seconds.
2. **Evaluation Suite:** Use the `Evaluation` tab for research-grade reporting. The system uses an optimized **0.68 semantic threshold** for vector matching and a **0.50 TF-IDF threshold** for exact matching.

---

## 6. Architecture Overview
FAgentLLM utilizes a **Six-Agent Framework**:
- **Invoice Agent:** OCR & Extraction.
- **Budget Agent:** Spend control & Reallocation.
- **Cash Agent:** Liquidity forecasting.
- **Reconciliation Agent:** Vector-based transaction matching.
- **Credit Agent:** Risk scoring & Collections.
- **Governance Agent:** Conflict detection & Compliance audit.

