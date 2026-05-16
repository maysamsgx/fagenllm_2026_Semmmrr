"""
scripts/init_eval_db.py
Run once to verify (or create) the held-out evaluation tables.

If the tables are missing, this script prints the exact SQL to paste into
the Supabase SQL Editor — we cannot execute DDL directly via the REST API.
"""

from execution.db.supabase_client import db

# Full DDL for both tables. Also used as documentation of the schema.
EVAL_TABLES_SQL = """
-- Evaluation run summary (one row per evaluator.py invocation)
CREATE TABLE IF NOT EXISTS evaluation_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_name        TEXT    NOT NULL,
    run_type        TEXT    NOT NULL,          -- 'fagentllm' | 'baseline'
    total_cases     INTEGER NOT NULL,
    passed_cases    INTEGER NOT NULL DEFAULT 0,
    accuracy        FLOAT   NOT NULL DEFAULT 0,
    f1_score        FLOAT,
    precision_score FLOAT,
    recall_score    FLOAT,
    latency_avg     FLOAT,
    governance_pass_rate  FLOAT,
    causal_success_rate   FLOAT,
    hallucination_rate    FLOAT,
    metrics         JSONB,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Per-case result (one row per test case per run)
CREATE TABLE IF NOT EXISTS evaluation_results (
    id               UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id           UUID    REFERENCES evaluation_runs(id),
    test_case_id     TEXT    NOT NULL,
    scenario         TEXT    NOT NULL,
    category         TEXT,                     -- invoice | budget | reconciliation | adversarial …
    status           TEXT    NOT NULL,         -- 'pass' | 'fail'
    actual_path      TEXT[],
    expected_path    TEXT[],
    actual_verdict   TEXT,
    expected_verdict TEXT,
    -- Baseline comparison columns
    baseline_verdict       TEXT,
    baseline_passed        BOOLEAN,
    fagentllm_advantage    BOOLEAN,            -- TRUE when FAgentLLM passes but baseline fails
    -- Quality metrics
    reasoning_quality      INTEGER,            -- 0-100 qualitative score
    governance_passed      BOOLEAN,
    causal_links_present   BOOLEAN,
    latency                FLOAT,              -- seconds
    error_message          TEXT,
    trace_id               UUID,
    created_at             TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);
"""


def init_db():
    print("--- FAgentLLM: Evaluation DB Initialisation Check ---")

    tables = {
        "evaluation_runs":    "SELECT count(*) FROM evaluation_runs LIMIT 1",
        "evaluation_results": "SELECT count(*) FROM evaluation_results LIMIT 1",
    }

    all_ok = True
    for table, probe in tables.items():
        try:
            db._ensure_client().table(table).select("id", count="exact").limit(1).execute()
            print(f"  ✓  '{table}' table is present.")
        except Exception:
            print(f"  ✗  '{table}' table is MISSING.")
            all_ok = False

    if not all_ok:
        print("\n⚠  One or more tables are missing.")
        print("   Paste the following SQL into Supabase SQL Editor and re-run this script:\n")
        print(EVAL_TABLES_SQL)
    else:
        print("\n✓  All evaluation tables are ready.")


if __name__ == "__main__":
    init_db()
