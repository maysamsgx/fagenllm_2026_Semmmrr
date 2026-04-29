-- =============================================================
-- FAgentLLM — Supabase Schema v3 (10/10 Causal Perfection)
-- =============================================================
-- Improvements vs v2:
--   1. Added 'payments' table to bridge invoices and transactions.
--   2. Added 'reconciliation_report_items' for item-level match traceability.
--   3. Added 'vendor_risk_scores' for pro-active AP risk assessment.
--   4. Enhanced triggers to include system-wide risk and payment impacts.
-- =============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================
-- LOOKUPS
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

-- V3: Vendor Risk Layer
CREATE TABLE IF NOT EXISTS vendor_risk_scores (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor_id       UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    risk_score      NUMERIC(5, 2) DEFAULT 100.0,
    risk_level      TEXT CHECK (risk_level IN ('low','medium','high')),
    last_assessed   TIMESTAMPTZ DEFAULT NOW(),
    factors         JSONB,                  -- {'late_deliveries': 2, 'price_volatility': 'high'}
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

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
-- INVOICE & PAYMENTS LAYER
-- =============================================================

CREATE TABLE IF NOT EXISTS invoices (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor_id       UUID REFERENCES vendors(id),
    customer_id     UUID REFERENCES customers(id),
    department_id   TEXT REFERENCES departments(id),

    invoice_number  TEXT,
    invoice_date    DATE,
    due_date        DATE,
    total_amount    NUMERIC(14, 2),
    currency        TEXT DEFAULT 'USD',
    tax_amount      NUMERIC(14, 2),

    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','extracting','validating',
                                      'awaiting_approval','approved','rejected','paid')),
    approver_id     TEXT,
    approved_at     TIMESTAMPTZ,
    rejection_reason TEXT,

    file_path       TEXT,
    ocr_raw_text    TEXT,
    extraction_confidence NUMERIC(5,2),

    cash_check_passed   BOOLEAN,
    budget_check_passed BOOLEAN,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS invoice_line_items (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_id  UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description TEXT,
    quantity    NUMERIC(12,3),
    unit_price  NUMERIC(14,2),
    line_total  NUMERIC(14,2),
    line_no     INT
);

-- V3: Payments bridge (was missing in V2)
CREATE TABLE IF NOT EXISTS payments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_id      UUID REFERENCES invoices(id),
    amount          NUMERIC(14, 2) NOT NULL,
    payment_date    DATE DEFAULT CURRENT_DATE,
    method          TEXT,
    status          TEXT DEFAULT 'completed',
    reference       TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================
-- BUDGET AGENT
-- =============================================================

CREATE TABLE IF NOT EXISTS budgets (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    department_id   TEXT NOT NULL REFERENCES departments(id),
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
    triggered_by_invoice_id UUID REFERENCES invoices(id),
    utilisation_pct NUMERIC(5, 2),
    alert_type      TEXT CHECK (alert_type IN ('threshold_breach','forecast_overrun')),
    message         TEXT,
    acknowledged    BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- RECONCILIATION AGENT
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

CREATE TABLE IF NOT EXISTS transactions (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source           TEXT NOT NULL CHECK (source IN ('internal','bank','supplier')),
    reference        TEXT,
    amount           NUMERIC(14, 2) NOT NULL,
    currency         TEXT DEFAULT 'USD',
    transaction_date DATE NOT NULL,
    description      TEXT,
    counterparty     TEXT,
    invoice_id       UUID REFERENCES invoices(id),
    payment_id       UUID REFERENCES payments(id),    -- V3 Link
    cash_account_id  UUID REFERENCES cash_accounts(id),
    matched          BOOLEAN DEFAULT FALSE,
    matched_to       UUID REFERENCES transactions(id),
    match_score      NUMERIC(5, 4),
    discrepancy_flag BOOLEAN DEFAULT FALSE,
    discrepancy_type TEXT CHECK (discrepancy_type IN
                      ('amount_variance','timing','duplicate','missing')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reconciliation_reports (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    period          TEXT NOT NULL,
    total_internal  INT,
    total_external  INT,
    matched_count   INT,
    unmatched_count INT,
    match_rate      NUMERIC(5, 2),
    discrepancies   JSONB DEFAULT '[]',
    generated_by_decision_id UUID, -- Links to agent_decisions
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- V3: Item-level match traceability
CREATE TABLE IF NOT EXISTS reconciliation_report_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_id       UUID NOT NULL REFERENCES reconciliation_reports(id) ON DELETE CASCADE,
    transaction_id  UUID NOT NULL REFERENCES transactions(id),
    item_type       TEXT CHECK (item_type IN ('matched','unmatched','discrepancy')),
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
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

CREATE TABLE IF NOT EXISTS cash_flow_forecasts (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    forecast_date     DATE NOT NULL,
    cash_account_id   UUID REFERENCES cash_accounts(id),
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

-- =============================================================
-- SYSTEM INTELLIGENCE (LAYER 2 & 3)
-- =============================================================

CREATE TABLE IF NOT EXISTS financial_state_snapshots (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    snapshot_time       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    triggered_by_agent  TEXT NOT NULL,
    total_cash          NUMERIC(14,2),
    projected_cash_7d   NUMERIC(14,2),
    total_payables      NUMERIC(14,2),
    total_receivables   NUMERIC(14,2),
    overdue_receivables NUMERIC(14,2),
    budget_utilisation  JSONB DEFAULT '{}',
    system_risk_score   NUMERIC(5,2),
    system_vendor_risk_avg NUMERIC(5,2),        -- V3 metric
    causal_summary      TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_decisions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent               TEXT NOT NULL,
    decision_type       TEXT NOT NULL,
    entity_table        TEXT NOT NULL,
    entity_id           UUID NOT NULL,
    input_state         JSONB DEFAULT '{}',
    output_action       JSONB DEFAULT '{}',
    confidence          NUMERIC(5,2),
    llm_prompt          TEXT,
    llm_response        TEXT,
    technical_explanation TEXT,
    business_explanation  TEXT,
    causal_explanation    TEXT,
    snapshot_id         UUID REFERENCES financial_state_snapshots(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS causal_links (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cause_decision_id   UUID NOT NULL REFERENCES agent_decisions(id) ON DELETE CASCADE,
    effect_decision_id  UUID NOT NULL REFERENCES agent_decisions(id) ON DELETE CASCADE,
    relationship_type   TEXT NOT NULL,
    strength            NUMERIC(3,2) CHECK (strength BETWEEN 0 AND 1),
    explanation         TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- TRIGGER - auto-snapshot on key state changes
-- =============================================================

CREATE OR REPLACE FUNCTION fn_snapshot_financial_state()
RETURNS TRIGGER AS $$
DECLARE
    v_total_cash       NUMERIC(14,2);
    v_total_payables   NUMERIC(14,2);
    v_total_receivable NUMERIC(14,2);
    v_overdue_recv     NUMERIC(14,2);
    v_vendor_risk_avg  NUMERIC(5,2);
    v_budget_util      JSONB;
    v_agent            TEXT;
BEGIN
    v_agent := CASE TG_TABLE_NAME
                 WHEN 'invoices'    THEN 'invoice'
                 WHEN 'budgets'     THEN 'budget'
                 WHEN 'transactions'THEN 'reconciliation'
                 WHEN 'receivables' THEN 'credit'
                 WHEN 'cash_accounts' THEN 'cash'
                 WHEN 'payments'    THEN 'invoice'
                 ELSE 'system'
               END;

    SELECT COALESCE(SUM(current_balance),0) INTO v_total_cash FROM cash_accounts;
    SELECT COALESCE(SUM(total_amount),0) INTO v_total_payables FROM invoices WHERE status IN ('approved','awaiting_approval');
    SELECT COALESCE(SUM(amount),0) INTO v_total_receivable FROM receivables WHERE status = 'open';
    SELECT COALESCE(SUM(amount),0) INTO v_overdue_recv FROM receivables WHERE status = 'open' AND days_overdue > 0;
    SELECT COALESCE(AVG(risk_score),100) INTO v_vendor_risk_avg FROM vendor_risk_scores;
    
    SELECT COALESCE(jsonb_object_agg(department_id, ROUND((spent + committed) / NULLIF(allocated,0) * 100, 2)), '{}'::jsonb)
      INTO v_budget_util FROM budgets;

    INSERT INTO financial_state_snapshots(
        triggered_by_agent, total_cash, total_payables,
        total_receivables, overdue_receivables, budget_utilisation, system_vendor_risk_avg
    ) VALUES (
        v_agent, v_total_cash, v_total_payables,
        v_total_receivable, v_overdue_recv, v_budget_util, v_vendor_risk_avg
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================
-- Bind fn_snapshot_financial_state() to the tables that should snapshot
-- =============================================================
DROP TRIGGER IF EXISTS trg_snap_invoices      ON invoices;
DROP TRIGGER IF EXISTS trg_snap_budgets       ON budgets;
DROP TRIGGER IF EXISTS trg_snap_transactions  ON transactions;
DROP TRIGGER IF EXISTS trg_snap_receivables   ON receivables;
DROP TRIGGER IF EXISTS trg_snap_cash_accounts ON cash_accounts;
DROP TRIGGER IF EXISTS trg_snap_payments      ON payments;

CREATE TRIGGER trg_snap_invoices
  AFTER INSERT OR UPDATE OF status, total_amount ON invoices
  FOR EACH ROW EXECUTE FUNCTION fn_snapshot_financial_state();

CREATE TRIGGER trg_snap_budgets
  AFTER INSERT OR UPDATE OF spent, committed, allocated ON budgets
  FOR EACH ROW EXECUTE FUNCTION fn_snapshot_financial_state();

CREATE TRIGGER trg_snap_transactions
  AFTER INSERT OR UPDATE OF matched, amount ON transactions
  FOR EACH ROW EXECUTE FUNCTION fn_snapshot_financial_state();

CREATE TRIGGER trg_snap_receivables
  AFTER INSERT OR UPDATE OF status, amount, days_overdue ON receivables
  FOR EACH ROW EXECUTE FUNCTION fn_snapshot_financial_state();

CREATE TRIGGER trg_snap_cash_accounts
  AFTER INSERT OR UPDATE OF current_balance ON cash_accounts
  FOR EACH ROW EXECUTE FUNCTION fn_snapshot_financial_state();

CREATE TRIGGER trg_snap_payments
  AFTER INSERT OR UPDATE OF amount, status ON payments
  FOR EACH ROW EXECUTE FUNCTION fn_snapshot_financial_state();

-- =============================================================
-- Realtime: full row replication and publication membership
-- =============================================================
ALTER TABLE invoices                  REPLICA IDENTITY FULL;
ALTER TABLE budgets                   REPLICA IDENTITY FULL;
ALTER TABLE budget_alerts             REPLICA IDENTITY FULL;
ALTER TABLE transactions              REPLICA IDENTITY FULL;
ALTER TABLE receivables               REPLICA IDENTITY FULL;
ALTER TABLE cash_accounts             REPLICA IDENTITY FULL;
ALTER TABLE cash_flow_forecasts       REPLICA IDENTITY FULL;
ALTER TABLE customers                 REPLICA IDENTITY FULL;
ALTER TABLE payments                  REPLICA IDENTITY FULL;
ALTER TABLE reconciliation_reports    REPLICA IDENTITY FULL;
ALTER TABLE financial_state_snapshots REPLICA IDENTITY FULL;
ALTER TABLE agent_decisions           REPLICA IDENTITY FULL;
ALTER TABLE causal_links              REPLICA IDENTITY FULL;
ALTER TABLE vendor_risk_scores        REPLICA IDENTITY FULL;

DO $pub$
DECLARE
  t TEXT;
  tables TEXT[] := ARRAY[
    'invoices','budgets','budget_alerts','transactions','receivables',
    'cash_accounts','cash_flow_forecasts','customers','payments',
    'reconciliation_reports','financial_state_snapshots','agent_decisions',
    'causal_links','vendor_risk_scores'
  ];
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
    CREATE PUBLICATION supabase_realtime FOR TABLE
      invoices, budgets, budget_alerts, transactions, receivables,
      cash_accounts, cash_flow_forecasts, customers, payments,
      reconciliation_reports, financial_state_snapshots, agent_decisions,
      causal_links, vendor_risk_scores;
  ELSE
    FOREACH t IN ARRAY tables LOOP
      BEGIN
        EXECUTE format('ALTER PUBLICATION supabase_realtime ADD TABLE %I', t);
      EXCEPTION WHEN duplicate_object THEN
        -- table already in publication, skip
        NULL;
      END;
    END LOOP;
  END IF;
END
$pub$;
