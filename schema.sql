-- =============================================================
-- FAgentLLM - Supabase Schema v2 (Causal-Reasoning-Ready)
-- =============================================================
-- Fixes vs v1:
--   1. Adds proper FKs between invoices <-> customers <-> receivables <-> transactions
--   2. Replaces weak agent_events with structured agent_decisions (XAI log)
--   3. Adds causal_links for cross-agent dependency graph
--   4. Adds financial_state_snapshots (the "shared financial state" your thesis requires)
--   5. Triggers auto-populate snapshots - no orphan tables
-- =============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================
-- LOOKUPS (used by FKs across agents)
-- =============================================================

CREATE TABLE IF NOT EXISTS departments (
    id          TEXT PRIMARY KEY,           -- e.g. 'engineering', 'marketing'
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vendors (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT NOT NULL,
    tax_id      TEXT UNIQUE,
    email       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- CUSTOMERS  (moved up so invoices can FK to it)
-- =============================================================
CREATE TABLE IF NOT EXISTS customers (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name              TEXT NOT NULL,
    email             TEXT,
    phone             TEXT,
    credit_limit      NUMERIC(14, 2) DEFAULT 0,
    credit_score      NUMERIC(5, 2)  DEFAULT 50.0,
    risk_level        TEXT DEFAULT 'medium' CHECK (risk_level IN ('low','medium','high')),
    payment_terms     INT DEFAULT 30,
    total_outstanding NUMERIC(14, 2) DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- INVOICE AGENT
-- =============================================================
CREATE TABLE IF NOT EXISTS invoices (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- FIX: real foreign keys instead of free-text
    vendor_id       UUID REFERENCES vendors(id),
    customer_id     UUID REFERENCES customers(id),       -- only for AR (sales) invoices
    department_id   TEXT REFERENCES departments(id),

    -- Extraction (Baidu OCR + Qwen3)
    invoice_number  TEXT,
    invoice_date    DATE,
    due_date        DATE,
    total_amount    NUMERIC(14, 2),
    currency        TEXT DEFAULT 'USD',
    tax_amount      NUMERIC(14, 2),

    -- Workflow
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','extracting','validating',
                                      'awaiting_approval','approved','rejected','paid')),
    approver_id     TEXT,
    approved_at     TIMESTAMPTZ,
    rejection_reason TEXT,

    -- Source
    file_path       TEXT,
    ocr_raw_text    TEXT,
    extraction_confidence NUMERIC(5,2),

    -- Cross-agent flags (set by other agents -> traceable via causal_links)
    cash_check_passed   BOOLEAN,
    budget_check_passed BOOLEAN,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_invoices_status     ON invoices(status);
CREATE INDEX idx_invoices_department ON invoices(department_id);
CREATE INDEX idx_invoices_due_date   ON invoices(due_date);
CREATE INDEX idx_invoices_vendor     ON invoices(vendor_id);
CREATE INDEX idx_invoices_customer   ON invoices(customer_id);

-- Line items as a real relational table (was JSONB - bad for joins)
CREATE TABLE IF NOT EXISTS invoice_line_items (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_id  UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description TEXT,
    quantity    NUMERIC(12,3),
    unit_price  NUMERIC(14,2),
    line_total  NUMERIC(14,2),
    line_no     INT
);
CREATE INDEX idx_line_items_invoice ON invoice_line_items(invoice_id);

-- =============================================================
-- BUDGET AGENT
-- =============================================================
CREATE TABLE IF NOT EXISTS budgets (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    department_id   TEXT NOT NULL REFERENCES departments(id),  -- FIX: was free-text
    period          TEXT NOT NULL,
    allocated       NUMERIC(14, 2) NOT NULL,
    spent           NUMERIC(14, 2) NOT NULL DEFAULT 0,
    committed       NUMERIC(14, 2) NOT NULL DEFAULT 0,
    forecast        NUMERIC(14, 2),
    alert_threshold NUMERIC(5, 2)  DEFAULT 90.0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(department_id, period)
);

CREATE TABLE IF NOT EXISTS budget_alerts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    budget_id       UUID NOT NULL REFERENCES budgets(id) ON DELETE CASCADE,
    triggered_by_invoice_id UUID REFERENCES invoices(id),  -- FIX: links cause to alert
    utilisation_pct NUMERIC(5, 2),
    alert_type      TEXT CHECK (alert_type IN ('threshold_breach','forecast_overrun')),
    message         TEXT,
    acknowledged    BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- RECONCILIATION AGENT
-- =============================================================
CREATE TABLE IF NOT EXISTS transactions (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source           TEXT NOT NULL CHECK (source IN ('internal','bank','supplier')),
    reference        TEXT,
    amount           NUMERIC(14, 2) NOT NULL,
    currency         TEXT DEFAULT 'USD',
    transaction_date DATE NOT NULL,
    description      TEXT,
    counterparty     TEXT,

    -- FIX: link transactions back to invoices (currently missing!)
    invoice_id       UUID REFERENCES invoices(id),
    cash_account_id  UUID,  -- FK added below after cash_accounts is created

    -- Matching
    matched          BOOLEAN DEFAULT FALSE,
    matched_to       UUID REFERENCES transactions(id),
    match_score      NUMERIC(5, 4),
    discrepancy_flag BOOLEAN DEFAULT FALSE,
    discrepancy_type TEXT CHECK (discrepancy_type IN
                     ('amount_variance','timing','duplicate','missing')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_transactions_matched  ON transactions(matched);
CREATE INDEX idx_transactions_source   ON transactions(source);
CREATE INDEX idx_transactions_date     ON transactions(transaction_date);
CREATE INDEX idx_transactions_invoice  ON transactions(invoice_id);

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
CREATE TABLE IF NOT EXISTS receivables (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id      UUID NOT NULL REFERENCES customers(id),
    invoice_id       UUID REFERENCES invoices(id),
    amount           NUMERIC(14, 2) NOT NULL,
    due_date         DATE NOT NULL,
    days_overdue     INT DEFAULT 0,
    status           TEXT DEFAULT 'open'
                     CHECK (status IN ('open','partial','paid','written_off')),
    collection_stage TEXT DEFAULT 'none'
                     CHECK (collection_stage IN ('none','reminder','notice','escalated','legal')),
    last_reminder_at TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_receivables_customer ON receivables(customer_id);
CREATE INDEX idx_receivables_due_date ON receivables(due_date);
CREATE INDEX idx_receivables_status   ON receivables(status);

-- =============================================================
-- CASH MANAGEMENT AGENT
-- =============================================================
CREATE TABLE IF NOT EXISTS cash_accounts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_name    TEXT NOT NULL,
    bank_name       TEXT,
    currency        TEXT DEFAULT 'USD',
    current_balance NUMERIC(14, 2) NOT NULL DEFAULT 0,
    minimum_balance NUMERIC(14, 2) DEFAULT 0,
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- now that cash_accounts exists, add the FK to transactions
ALTER TABLE transactions
    ADD CONSTRAINT fk_transactions_cash_account
    FOREIGN KEY (cash_account_id) REFERENCES cash_accounts(id);

CREATE TABLE IF NOT EXISTS cash_flow_forecasts (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    forecast_date     DATE NOT NULL,
    cash_account_id   UUID REFERENCES cash_accounts(id),  -- FIX: was disconnected!
    projected_inflow  NUMERIC(14, 2) DEFAULT 0,
    projected_outflow NUMERIC(14, 2) DEFAULT 0,
    net_position      NUMERIC(14, 2) GENERATED ALWAYS AS (
                          projected_inflow - projected_outflow
                      ) STORED,
    actual_inflow     NUMERIC(14, 2),
    actual_outflow    NUMERIC(14, 2),
    notes             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_cash_forecasts_date    ON cash_flow_forecasts(forecast_date);
CREATE INDEX idx_cash_forecasts_account ON cash_flow_forecasts(cash_account_id);

-- =============================================================
--  LAYER 2 - UNIFIED FINANCIAL STATE
-- The "shared financial state" your thesis requires.
-- One row per snapshot. Written by ALL agents whenever they
-- complete a meaningful action (invoice approved, payment posted,
-- budget breach, customer risk re-scored).
-- =============================================================
CREATE TABLE IF NOT EXISTS financial_state_snapshots (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    snapshot_time       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    triggered_by_agent  TEXT NOT NULL,        -- which agent caused the snapshot

    -- Liquidity
    total_cash          NUMERIC(14,2),
    projected_cash_7d   NUMERIC(14,2),

    -- Liabilities & receivables
    total_payables      NUMERIC(14,2),
    total_receivables   NUMERIC(14,2),
    overdue_receivables NUMERIC(14,2),

    -- Budget state across all departments
    budget_utilisation  JSONB DEFAULT '{}',   -- {'engineering': 78.2, 'marketing': 91.0, ...}

    -- Aggregate risk
    system_risk_score   NUMERIC(5,2),

    -- Why this snapshot exists (LLM-generated summary)
    causal_summary      TEXT,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_state_snap_time  ON financial_state_snapshots(snapshot_time DESC);
CREATE INDEX idx_state_snap_agent ON financial_state_snapshots(triggered_by_agent);

-- =============================================================
--  LAYER 3a - AGENT DECISIONS (XAI log)
-- Replaces the old agent_events. Every decision an agent makes
-- is recorded here with full input/output state and LLM trace.
-- =============================================================
CREATE TABLE IF NOT EXISTS agent_decisions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent               TEXT NOT NULL CHECK (agent IN
                        ('invoice','budget','reconciliation','credit','cash')),
    decision_type       TEXT NOT NULL,        -- 'invoice_approved', 'risk_elevated', etc.

    -- The entity affected - typed reference instead of free-text
    entity_table        TEXT NOT NULL,        -- 'invoices', 'customers', 'budgets', ...
    entity_id           UUID NOT NULL,

    -- Full reproducibility for XAI
    input_state         JSONB DEFAULT '{}',   -- snapshot of the inputs the agent saw
    output_action       JSONB DEFAULT '{}',   -- the action it took
    confidence          NUMERIC(5,2),

    -- LLM trace (the heart of XAI)
    llm_prompt          TEXT,
    llm_response        TEXT,
    reasoning           TEXT,                  -- natural-language summary

    -- Snapshot link - what the world looked like when the decision was made
    snapshot_id         UUID REFERENCES financial_state_snapshots(id),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_decisions_agent  ON agent_decisions(agent);
CREATE INDEX idx_decisions_entity ON agent_decisions(entity_table, entity_id);
CREATE INDEX idx_decisions_time   ON agent_decisions(created_at DESC);

-- =============================================================
--  LAYER 3b - CAUSAL LINKS (cross-agent dependency graph)
-- This is what makes your thesis "causal cross-domain reasoning"
-- demonstrable. Every time one agent's decision triggers another's,
-- you record the edge here. The result is a queryable DAG of causes.
-- =============================================================
CREATE TABLE IF NOT EXISTS causal_links (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- The two decisions in the cause -> effect relationship
    cause_decision_id   UUID NOT NULL REFERENCES agent_decisions(id) ON DELETE CASCADE,
    effect_decision_id  UUID NOT NULL REFERENCES agent_decisions(id) ON DELETE CASCADE,

    -- Semantic relationship - controlled vocabulary keeps it queryable
    relationship_type   TEXT NOT NULL CHECK (relationship_type IN (
                            'reduces_liquidity',
                            'increases_liquidity',
                            'breaches_budget',
                            'elevates_risk',
                            'lowers_risk',
                            'triggers_collection',
                            'blocks_approval',
                            'enables_approval'
                        )),
    strength            NUMERIC(3,2) CHECK (strength BETWEEN 0 AND 1),
    explanation         TEXT,                 -- LLM-generated natural language

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (cause_decision_id <> effect_decision_id)
);
CREATE INDEX idx_causal_cause  ON causal_links(cause_decision_id);
CREATE INDEX idx_causal_effect ON causal_links(effect_decision_id);
CREATE INDEX idx_causal_rel    ON causal_links(relationship_type);

-- =============================================================
-- TRIGGER - auto-snapshot on key state changes
-- (so financial_state_snapshots is never an orphan table)
-- =============================================================
CREATE OR REPLACE FUNCTION fn_snapshot_financial_state()
RETURNS TRIGGER AS $$
DECLARE
    v_total_cash       NUMERIC(14,2);
    v_total_payables   NUMERIC(14,2);
    v_total_receivable NUMERIC(14,2);
    v_overdue_recv     NUMERIC(14,2);
    v_budget_util      JSONB;
    v_agent            TEXT;
BEGIN
    -- Determine which agent triggered this
    v_agent := CASE TG_TABLE_NAME
                 WHEN 'invoices'    THEN 'invoice'
                 WHEN 'budgets'     THEN 'budget'
                 WHEN 'transactions'THEN 'reconciliation'
                 WHEN 'receivables' THEN 'credit'
                 WHEN 'cash_accounts' THEN 'cash'
                 ELSE 'system'
               END;

    SELECT COALESCE(SUM(current_balance),0) INTO v_total_cash
      FROM cash_accounts;

    SELECT COALESCE(SUM(total_amount),0) INTO v_total_payables
      FROM invoices WHERE status IN ('approved','awaiting_approval');

    SELECT COALESCE(SUM(amount),0) INTO v_total_receivable
      FROM receivables WHERE status = 'open';

    SELECT COALESCE(SUM(amount),0) INTO v_overdue_recv
      FROM receivables WHERE status = 'open' AND days_overdue > 0;

    SELECT COALESCE(jsonb_object_agg(department_id,
              ROUND((spent + committed) / NULLIF(allocated,0) * 100, 2)),
              '{}'::jsonb)
      INTO v_budget_util
      FROM budgets;

    INSERT INTO financial_state_snapshots(
        triggered_by_agent, total_cash, total_payables,
        total_receivables, overdue_receivables, budget_utilisation
    ) VALUES (
        v_agent, v_total_cash, v_total_payables,
        v_total_receivable, v_overdue_recv, v_budget_util
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_snap_invoices
  AFTER INSERT OR UPDATE OF status ON invoices
  FOR EACH ROW EXECUTE FUNCTION fn_snapshot_financial_state();

CREATE TRIGGER trg_snap_budgets
  AFTER INSERT OR UPDATE OF spent, committed ON budgets
  FOR EACH ROW EXECUTE FUNCTION fn_snapshot_financial_state();

CREATE TRIGGER trg_snap_receivables
  AFTER INSERT OR UPDATE OF status ON receivables
  FOR EACH ROW EXECUTE FUNCTION fn_snapshot_financial_state();

CREATE TRIGGER trg_snap_cash
  AFTER UPDATE OF current_balance ON cash_accounts
  FOR EACH ROW EXECUTE FUNCTION fn_snapshot_financial_state();

-- =============================================================
-- REALTIME publication
-- =============================================================
-- Note: You may need to drop existing publication if it conflicts
-- DROP PUBLICATION IF EXISTS supabase_realtime;
-- CREATE PUBLICATION supabase_realtime FOR TABLE invoices, budget_alerts, agent_decisions, causal_links, financial_state_snapshots, receivables, cash_flow_forecasts;
