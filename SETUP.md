# FAgentLLM — Local Setup Guide

This is a plain walkthrough for getting the full system running on your machine. Covers the backend, database, and frontend. No prior experience assumed — just go step by step.

---

## What You Need First

Make sure you have these installed before starting:

- **Python 3.11+** → [python.org](https://python.org)
- **Node.js 18+** → [nodejs.org](https://nodejs.org)
- **Git** → [git-scm.com](https://git-scm.com)

You also need accounts on:

- **Supabase** → [supabase.com](https://supabase.com) — free tier is fine
- **Groq** → [console.groq.com](https://console.groq.com) — for the Qwen LLM (free tier available)
- **OpenRouter** → [openrouter.ai](https://openrouter.ai) — for Baidu OCR (free model available)

> If you're on Windows, run all commands in **PowerShell** or **Windows Terminal**.

---

## Step 1 — Get the Code

```bash
git clone https://github.com/maysamsgx/fagenllm_2026_Semmmrr
cd fagenllm_2026_Semmmrr
```

If you already cloned it, just `cd` into the folder.

---

## Step 2 — Set Up the Python Environment

Create a virtual environment so packages don't get installed globally:

```bash
python -m venv venv
```

Activate it:

```bash
# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate
```

You should see `(venv)` at the start of your terminal line. Now install the dependencies:

```bash
pip install -r requirements.txt
```

This installs FastAPI, LangGraph, Supabase client, PDF/OCR tools, and more. Takes a couple of minutes.

---

## Step 3 — Create Your `.env` File

Copy the example:

```bash
# Mac / Linux
cp .env.example .env

# Windows
copy .env.example .env
```

Open `.env` and fill in your actual values. Here's what each section needs:

```env
# Supabase
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key

# Frontend (Vite)
VITE_SUPABASE_URL=https://your-project-id.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key

# Qwen3-32B via Groq
GROQ_API_KEY=gsk_...
GROQ_BASE_URL=https://api.groq.com/openai/v1
QWEN_MODEL=qwen/qwen3-32b

# Baidu OCR via OpenRouter
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OCR_MODEL=baidu/qianfan-ocr-fast:free

# App
APP_ENV=development
APP_SECRET=pick-any-long-random-string
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_ID.supabase.co:5432/postgres
```

**Where to find each key:**

| Key | Where to get it |
|---|---|
| `SUPABASE_URL` + keys | Supabase dashboard → Settings → API |
| `GROQ_API_KEY` | [console.groq.com/keys](https://console.groq.com/keys) |
| `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) |
| `DATABASE_URL` | Supabase dashboard → Settings → Database → Connection string |

> **Important:** For seeding the database use the `service_role` key, not the `anon` key. The anon key respects row-level security and bulk inserts will silently fail.

---

## Step 4 — Set Up the Database Schema

1. Open your Supabase project dashboard
2. Click **SQL Editor** in the left sidebar
3. Open `schema.sql` from this repo
4. Paste the full contents into the editor
5. Click **Run**

This creates all the tables — invoices, budgets, agent decisions, causal links, etc.

---

## Step 5 — Seed the Database

The project includes a seeder that generates ~10,000 rows of realistic financial data (vendors, customers, invoices, transactions, budgets) so you have real scenarios to test with.

First do a dry run to make sure things look right:

```bash
python seed.py --dry-run
```

This runs in memory only — nothing is written to the database. Check that budget utilisation numbers are in the 30–90% range (not 200%+).

If it looks good, run for real:

```bash
python seed.py
```

Takes about 30 seconds. You'll see progress per table. When done, verify in the Supabase SQL Editor:

```sql
SELECT 'invoices' AS t, COUNT(*) FROM invoices
UNION ALL SELECT 'customers', COUNT(*) FROM customers
UNION ALL SELECT 'transactions', COUNT(*) FROM transactions;
```

You should see 2,000+ invoices, 432+ customers, 2,500+ transactions.

> If you get a "duplicate key" error, you already seeded once. See the reset instructions at the bottom.

---

## Step 6 — Start the Backend

```bash
uvicorn main:app --reload --port 8000
```

Once it's running, open:

```
http://localhost:8000/health
```

You should see:

```json
{"status": "ok", "system": "FAgentLLM v3 (10/10 Architecture)"}
```

The full interactive API docs are at `http://localhost:8000/docs` — FastAPI generates this automatically. You can trigger agents directly from there.

---

## Step 7 — Start the Frontend

Open a **second terminal** (keep the backend running in the first). From the same project folder:

```bash
npm install
npm run dev
```

You'll see:

```
  VITE v5.x  ready in 300ms
  ➜  Local:   http://localhost:5173/
```

Open `http://localhost:5173` in your browser. The FAgentLLM dashboard should load.

---

## Step 8 — Log In

Default credentials:

- **Username:** `admin`
- **Password:** `admin123`

These are controlled by `ADMIN_USER` and `ADMIN_PASS` in your `.env`.

---

## Quick Sanity Check

| Service | URL |
|---|---|
| Backend API | `http://localhost:8000` |
| API docs (interactive) | `http://localhost:8000/docs` |
| Frontend dashboard | `http://localhost:5173` |
| Database | Your Supabase project dashboard |

---

## Testing the Agents

The agents don't run on a schedule — they run when triggered via API. The easiest way is through the interactive docs at `http://localhost:8000/docs`.

### Upload an Invoice

There are two test images in `test_system/`:
- `safe_invoice.png` — should get auto-approved
- `risky_invoice.png` — should get flagged or escalated

In the API docs, use:

```
POST /api/invoice/upload
```

Upload the image, set `department_id` to `engineering`, hit Execute. You'll get back an `invoice_id`. The agents run in the background, so wait 5–10 seconds then check:

```
GET /api/invoice/{invoice_id}
```

The `status` will update from `pending` → `extracting` → `validating` → `approved` or `awaiting_approval`. You can also watch the `invoices` table update live in Supabase.

### Run a Budget Review

```
POST /api/budget/run
```

Then check for alerts:

```
GET /api/budget/alerts/active
```

The seeder puts a couple of departments near the 95% threshold, so you should see at least one alert.

### Run Reconciliation

```
POST /api/reconciliation/run
```

Wait 10–15 seconds, then get the report:

```
GET /api/reconciliation/report
```

The seeder planted ~24 deliberate discrepancies, so the agent should surface some anomalies.

### Credit Risk Check

```
GET /api/credit/{customer_id}
```

Pick any customer ID from the Supabase `customers` table.

---

## Reading the XAI Trace

Every decision any agent makes is logged with three explanations: what it did technically, what it means for the business, and what it causes downstream. After an invoice finishes processing, call:

```
GET /api/invoice/{invoice_id}/causal-trace
```

The frontend's XAI Trace Panel renders this visually.

---

## All Trigger Endpoints

| What to test | Endpoint |
|---|---|
| Upload invoice | `POST /api/invoice/upload` |
| Invoice status | `GET /api/invoice/{id}` |
| XAI trace | `GET /api/invoice/{id}/causal-trace` |
| Budget review | `POST /api/budget/run` |
| Budget alerts | `GET /api/budget/alerts/active` |
| Reconciliation | `POST /api/reconciliation/run` |
| Recon report | `GET /api/reconciliation/report` |
| Credit check | `GET /api/credit/{customer_id}` |
| Cash position | `GET /api/cash/position` |
| Agent decisions log | `GET /api/intel/decisions` |

---

## Resetting the Database

**Wipe only agent-generated data** (keeps seeded vendors, invoices, customers):

```sql
TRUNCATE TABLE causal_links, agent_decisions,
               reconciliation_reports, budget_alerts CASCADE;
```

**Full reset** (wipes everything, then re-seed):

```sql
TRUNCATE TABLE causal_links, agent_decisions, financial_state_snapshots,
  cash_flow_forecasts, transactions, receivables,
  invoice_line_items, invoices, budget_alerts, budgets,
  cash_accounts, customers, vendors, departments
CASCADE;
```

Then run `python seed.py` again.

---

## Common Problems

**`ModuleNotFoundError`** — virtual environment isn't active. Run `venv\Scripts\activate`.

**`Connection refused` on port 8000** — backend isn't running. Check the uvicorn terminal for errors.

**Dashboard loads but no data** — double-check `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` in `.env`.

**Seed script hangs** — you're using the anon key. Switch to `SUPABASE_SERVICE_KEY`.

**OCR returns empty or fails** — check your `OPENROUTER_API_KEY` is valid and the `baidu/qianfan-ocr-fast:free` model is available on your account.

**LLM calls fail with auth error** — check your `GROQ_API_KEY` is correct and you have Groq credits/free tier active.

**`invalid signature` on login** — `APP_SECRET` is missing in `.env`. Set it to anything and restart the backend.
