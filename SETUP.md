# FAgentLLM — Enterprise Deployment & Setup Guide

This guide details the deployment process for FAgentLLM, a multi-agent financial automation architecture. This setup validates the system for Design Science Research (DSR) evaluation, encompassing the orchestration backend, Supabase database, and React frontend.

---

## Prerequisites

Ensure the following environments and accounts are provisioned:

- **Python 3.11+**
- **Node.js 18+**
- **Git**
- **Supabase Account** (Database & Realtime pub/sub)
- **Groq API Key** (Orchestration & Reasoning via Qwen3)
- **OpenRouter API Key** (Legacy OCR via Baidu Qianfan)


---

## 1. Repository & Environment Initialization

Clone the architecture repository:
```bash
git clone https://github.com/maysamsgx/fagenllm_2026_Semmmrr
cd fagenllm_2026_Semmmrr
```

Provision an isolated Python environment to prevent dependency conflicts:
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Mac / Linux
source venv/bin/activate
```

Install the required packages, including FastAPI, LangGraph, and PyMuPDF:
```bash
pip install -r requirements.txt
```

---

## 2. Environment Configuration

Copy the configuration template:
```bash
cp .env.example .env  # Use 'copy' on Windows
```

Populate the `.env` file with your specific credentials.

```env
# Database Infrastructure
SUPABASE_URL=https://[YOUR_PROJECT].supabase.co
SUPABASE_SERVICE_KEY=[YOUR_SERVICE_ROLE_KEY]
DATABASE_URL=postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres

# Frontend Client
VITE_SUPABASE_URL=https://[YOUR_PROJECT].supabase.co
VITE_SUPABASE_ANON_KEY=[YOUR_ANON_KEY]

# Cognitive Orchestration (LLMs)
GROQ_API_KEY=gsk_...
GROQ_BASE_URL=https://api.groq.com/openai/v1
QWEN_MODEL=qwen/qwen3-32b

# OCR Fallback
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OCR_MODEL=baidu/qianfan-ocr-fast:free


# Application Security
APP_ENV=development
APP_SECRET=[SECURE_RANDOM_STRING]
```

---

## 3. Database Provisioning & Data Seeding

1. Navigate to the **SQL Editor** in your Supabase dashboard.
2. Execute the contents of `schema.sql`. This establishes the normalized financial entities and the Explainable AI (XAI) causal graph tables (`agent_decisions`, `causal_links`).
3. Seed the database with synthetic financial data to simulate an active enterprise environment:

```bash
# Verify constraints with a dry run
python seed.py --dry-run

# Execute the active seed (Generates ~10k relational records)
python seed.py
```

---

## 4. System Execution

### The Orchestration API (Backend)
Run the FastAPI server which hosts the LangGraph supervisor:
```bash
uvicorn main:app --reload --port 8000
```
*Health Check:* Navigate to `http://localhost:8000/health`. You should receive a `status: ok` confirming the 10/10 Architecture is online.

### The Operations Dashboard (Frontend)
Open a separate terminal instance and initialize the Vite development server:
```bash
npm install
npm run dev
```
*Access:* Navigate to `http://localhost:5173`. 
*Credentials:* Authenticate using `admin` / `admin123` (configurable in `.env`).

---

## 5. System Evaluation & Testing

The system is designed for autonomous operation triggered by state changes. 

### Interactive Testing via UI
1. **Invoice Workflow:** Navigate to the `Invoice` tab. Upload `test_system/safe_invoice.png`. Observe the state transition through the XAI Trace panel as the system extracts, validates, and auto-approves the document based on liquidity.
2. **Reconciliation Analytics:** Navigate to the `Reconciliation` tab. Click `Run Reconciliation`. Toggle the view from **Operations** to **Analytics** to view the professional Recharts dashboard visualizing the system's match-rate efficiency and anomaly detection workload.

### DSR Quantitative Evaluation
The system logs all agent decisions and causal links directly in Supabase. Use the Reconciliation Analytics dashboard in the UI to view real-time match rates, anomaly detection metrics, and performance trends.
