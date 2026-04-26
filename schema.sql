-- =============================================================
-- FAgentLLM — Supabase Schema
-- Run this once in your Supabase project → SQL Editor
-- =============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- =============================================================
-- SHARED: Agent Events (XAI audit trail)
-- Every agent decision is logged here with its LLM reasoning.
-- =============================================================
CREATE TABLE IF NOT EXISTS agent_events (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent       TEXT NOT NULL,          -- 'invoice' | 'budget' | 'reconciliation' | 'credit' | 'cash'
    event_type  TEXT NOT NULL,          -- e.g. 'invoice_approved', 'budget_breach', 'risk_elevated'
    entity_id   TEXT NOT NULL,          -- ID of the invoice / customer / transaction affected
    details     JSONB NOT NULL DEFAULT '{}',
    reasoning   TEXT DEFAULT '',        -- Qwen3's natural language explanation (XAI)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_events_agent      ON agent_events(agent);
CREATE INDEX idx_agent_events_entity     ON agent_events(entity_id);
CREATE INDEX idx_agent_events_created_at ON agent_events(created_at DESC);


-- =============================================================
-- INVOICE AGENT
-- =============================================================
CREATE TABLE IF NOT EXISTS invoices (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Raw extraction from Baidu OCR + Qwen3
    vendor_name     TEXT,
    vendor_tax_id   TEXT,
    invoice_number  TEXT,
    invoice_date    DATE,
    due_date        DATE,
    total_amount    NUMERIC(14, 2),
    currency        TEXT DEFAULT 'USD',
    tax_amount      NUMERIC(14, 2),
    line_items      JSONB DEFAULT '[]',   -- [{description, quantity, unit_price, total}]

    -- Workflow
    status          TEXT NOT NULL DEFAULT 'pending',
    -- pending → extracting → validating → awaiting_approval → approved → rejected → paid
    department      TEXT,
    approver_id     TEXT,
    approved_at     TIMESTAMPTZ,
    rejection_reason TEXT,

    -- Source file
    file_path       TEXT,               -- Supabase Storage path
    ocr_raw_text    TEXT,               -- raw OCR output (kept for debugging)
    extraction_confidence NUMERIC(5,2), -- 0-100, from Qwen3

    -- Cross-agent flags (set by other agents)
    cash_check_passed   BOOLEAN,        -- set by Cash agent
    budget_check_passed BOOLEAN,        -- set by Budget agent

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_invoices_status     ON invoices(status);
CREATE INDEX idx_invoices_department ON invoices(department);
CREATE INDEX idx_invoices_due_date   ON invoices(due_date);


-- =============================================================
-- BUDGET AGENT
-- =============================================================
CREATE TABLE IF NOT EXISTS budgets (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    department  TEXT NOT NULL,
    period      TEXT NOT NULL,          -- e.g. '2025-Q2' or '2025-04'
    allocated   NUMERIC(14, 2) NOT NULL,
    spent       NUMERIC(14, 2) NOT NULL DEFAULT 0,
    committed   NUMERIC(14, 2) NOT NULL DEFAULT 0,  -- approved but not yet paid
    forecast    NUMERIC(14, 2),
    alert_threshold NUMERIC(5, 2) DEFAULT 90.0,     -- % utilisation that triggers alert
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(department, period)
);

CREATE TABLE IF NOT EXISTS budget_alerts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    budget_id       UUID REFERENCES budgets(id),
    department      TEXT NOT NULL,
    period          TEXT NOT NULL,
    utilisation_pct NUMERIC(5, 2),
    alert_type      TEXT,               -- 'threshold_breach' | 'forecast_overrun'
    message         TEXT,
    acknowledged    BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =============================================================
-- RECONCILIATION AGENT
-- =============================================================
CREATE TABLE IF NOT EXISTS transactions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source          TEXT NOT NULL,      -- 'internal' | 'bank' | 'supplier'
    reference       TEXT,
    amount          NUMERIC(14, 2) NOT NULL,
    currency        TEXT DEFAULT 'USD',
    transaction_date DATE NOT NULL,
    description     TEXT,
    counterparty    TEXT,
    matched         BOOLEAN DEFAULT FALSE,
    matched_to      UUID REFERENCES transactions(id),
    match_score     NUMERIC(5, 4),      -- cosine similarity score 0.0–1.0
    discrepancy_flag BOOLEAN DEFAULT FALSE,
    discrepancy_type TEXT,              -- 'amount_variance' | 'timing' | 'duplicate' | 'missing'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_transactions_matched      ON transactions(matched);
CREATE INDEX idx_transactions_source       ON transactions(source);
CREATE INDEX idx_transactions_date         ON transactions(transaction_date);

CREATE TABLE IF NOT EXISTS reconciliation_reports (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    period          TEXT NOT NULL,
    total_internal  INT,
    total_external  INT,
    matched_count   INT,
    unmatched_count INT,
    match_rate      NUMERIC(5, 2),
    discrepancies   JSONB DEFAULT '[]',
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =============================================================
-- CREDIT & COLLECTION AGENT
-- =============================================================
CREATE TABLE IF NOT EXISTS customers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL,
    email           TEXT,
    phone           TEXT,
    credit_limit    NUMERIC(14, 2) DEFAULT 0,
    credit_score    NUMERIC(5, 2) DEFAULT 50.0,   -- 0–100
    risk_level      TEXT DEFAULT 'medium',          -- 'low' | 'medium' | 'high'
    payment_terms   INT DEFAULT 30,                 -- days
    total_outstanding NUMERIC(14, 2) DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS receivables (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id     UUID REFERENCES customers(id),
    invoice_id      UUID REFERENCES invoices(id),
    amount          NUMERIC(14, 2) NOT NULL,
    due_date        DATE NOT NULL,
    days_overdue    INT GENERATED ALWAYS AS (
                        GREATEST(0, CURRENT_DATE - due_date)
                    ) STORED,
    status          TEXT DEFAULT 'open',            -- 'open' | 'partial' | 'paid' | 'written_off'
    collection_stage TEXT DEFAULT 'none',           -- 'none' | 'reminder' | 'notice' | 'escalated' | 'legal'
    last_reminder_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_receivables_customer  ON receivables(customer_id);
CREATE INDEX idx_receivables_due_date  ON receivables(due_date);
CREATE INDEX idx_receivables_status    ON receivables(status);


-- =============================================================
-- CASH MANAGEMENT AGENT
-- =============================================================
CREATE TABLE IF NOT EXISTS cash_accounts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_name    TEXT NOT NULL,
    bank_name       TEXT,
    currency        TEXT DEFAULT 'USD',
    current_balance NUMERIC(14, 2) NOT NULL DEFAULT 0,
    minimum_balance NUMERIC(14, 2) DEFAULT 0,       -- alert if below this
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cash_flow_forecasts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    forecast_date   DATE NOT NULL,
    projected_inflow  NUMERIC(14, 2) DEFAULT 0,
    projected_outflow NUMERIC(14, 2) DEFAULT 0,
    net_position    NUMERIC(14, 2) GENERATED ALWAYS AS (
                        projected_inflow - projected_outflow
                    ) STORED,
    actual_inflow   NUMERIC(14, 2),
    actual_outflow  NUMERIC(14, 2),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cash_forecasts_date ON cash_flow_forecasts(forecast_date);


-- =============================================================
-- Enable Supabase Realtime on key tables
-- (so React frontend gets live updates without polling)
-- =============================================================
ALTER PUBLICATION supabase_realtime ADD TABLE invoices;
ALTER PUBLICATION supabase_realtime ADD TABLE budget_alerts;
ALTER PUBLICATION supabase_realtime ADD TABLE agent_events;
ALTER PUBLICATION supabase_realtime ADD TABLE receivables;
ALTER PUBLICATION supabase_realtime ADD TABLE cash_flow_forecasts;
