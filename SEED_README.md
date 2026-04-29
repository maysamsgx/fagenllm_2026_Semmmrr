# FAgentLLM Synthetic Data Seeder

~10K rows of realistic financial data covering **Nov 2025 → Apr 2026**.

## What gets seeded (and what doesn't)

| Table | Rows | Source |
|---|---|---|
| `departments` | 8 | Hardcoded |
| `vendors` | 50 | 20 known SaaS vendors + 30 long-tail (Faker) |
| `customers` | 432 | **Real names from `clients.csv`** |
| `cash_accounts` | 4 | Operating, Reserve, Payroll, FX |
| `budgets` | 24 | 8 depts × 3 quarters |
| `invoices` | 2,000 | 800 AP + 1,200 AR |
| `invoice_line_items` | ~4,900 | 1–4 lines per invoice |
| `receivables` | 1,200 | One per AR invoice |
| `transactions` | ~2,500 | Internal + bank, with engineered noise |
| `cash_flow_forecasts` | 90 | Forward 90 days |

**Not seeded** — your agents must produce these at runtime:
- `agent_decisions` — the XAI log is what your agents write to
- `causal_links` — your causal graph is what your agents prove they can build
- `financial_state_snapshots` — auto-populated by the schema's trigger
- `budget_alerts` — the Budget Agent should generate these from the seeded data
- `reconciliation_reports` — the Reconciliation Agent generates on demand

## Engineered scenarios

The seeder deliberately plants these so your agents have testable cases:

- **S1** Clean approvals (~60%) — baseline
- **S2** ~17 budget-breach AP invoices, ~$500K total — pushes one department over 90%
- **S3** ~150 cash-tight large invoices in late March/April — drives liquidity reasoning
- **S4** ~176 overdue receivables, ~$1.1M outstanding, 23 escalated to legal stage
- **S5** ~24 reconciliation discrepancies (timing, amount variance, missing, duplicate)
- **S6** "Perfect storm" emerges naturally from S2+S3+S4 overlapping in the finance dept

The seeder prints a scenario summary at the end so you know exactly what your agents will encounter.

## Usage

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up `.env`

```bash
cp .env.example .env
# edit .env and add your SUPABASE_URL + SUPABASE_KEY (service_role)
```

⚠️ **Use the `service_role` key, not `anon`.** The anon key is rate-limited and respects RLS — bulk inserts will silently fail or take forever.

### 3. Make sure schema v2 is deployed

Run `schema_v2_fixed.sql` in Supabase SQL Editor first.

### 4. Test without writing to DB (recommended first)

```bash
python seed.py --dry-run
```

This generates everything in memory and prints the scenario summary. **Look at the budget utilization output** — you should see most departments at 30–70% and one or two at 90%+. If they're all at 200%+, the budget allocations need scaling.

### 5. Seed for real

```bash
python seed.py
```

Takes ~30 seconds. The script inserts in dependency order and shows progress per table.

### 6. Verify in Supabase

```sql
SELECT 'invoices' AS t, COUNT(*) FROM invoices
UNION ALL SELECT 'customers', COUNT(*) FROM customers
UNION ALL SELECT 'transactions', COUNT(*) FROM transactions
UNION ALL SELECT 'financial_state_snapshots', COUNT(*) FROM financial_state_snapshots;
```

The snapshot count should be > 0 — it means your trigger fired correctly during the inserts.

## Reproducibility

The script uses `SEED = 42` for both `random` and `Faker`. Same seed = same data every time. Change it at the top of `seed.py` if you want different scenarios.

## Troubleshooting

**"duplicate key violates unique constraint"** — you already seeded once. Truncate first:
```sql
TRUNCATE TABLE causal_links, agent_decisions, financial_state_snapshots,
  cash_flow_forecasts, transactions, receivables,
  invoice_line_items, invoices, budget_alerts, budgets,
  cash_accounts, customers, vendors, departments
CASCADE;
```

**"violates foreign key constraint"** — usually means your schema isn't fully deployed. Re-run `schema_v2_fixed.sql`.

**Inserts hang or time out** — you're using the anon key. Switch to `service_role`.

**Budget utilization shows >200%** — the AP invoice volume exceeds the budgets in `DEPARTMENTS`. Either scale up the dept budgets or scale down `N_AP_INVOICES`.
