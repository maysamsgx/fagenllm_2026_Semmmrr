const BASE = '/api'

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json()
}

// ── Shared Intelligence ───────────────────────────────────────────────────

export interface FinancialStateSnapshot {
  id: string
  snapshot_time: string
  triggered_by_agent: string
  total_cash: number
  projected_cash_7d: number
  total_payables: number
  total_receivables: number
  overdue_receivables: number
  budget_utilisation: Record<string, number>
  system_risk_score: number
  system_vendor_risk_avg?: number // V3
  causal_summary: string | null
}

export interface AgentDecision {
  id: string
  agent: 'invoice' | 'budget' | 'reconciliation' | 'credit' | 'cash'
  decision_type: string
  entity_table: string
  entity_id: string
  confidence: number
  reasoning: string
  snapshot_id: string | null
  created_at: string
}

export interface CausalLink {
  id: string
  cause_decision_id: string
  effect_decision_id: string
  relationship_type: 
    | 'reduces_liquidity' | 'increases_liquidity' | 'breaches_budget'
    | 'elevates_risk' | 'lowers_risk' | 'triggers_collection'
    | 'blocks_approval' | 'enables_approval' | 'enables_validation'
  strength: number
  explanation: string
  created_at: string
}

export interface TraceEvent {
  agent: 'invoice' | 'budget' | 'reconciliation' | 'credit' | 'cash'
  event_type: string
  timestamp: string
  reasoning: string
  details: Record<string, any>
}

// ── Invoice ────────────────────────────────────────────────────────────────
export type InvoiceStatus =
  | 'pending' | 'extracting' | 'validating' | 'awaiting_approval'
  | 'approved' | 'rejected' | 'paid'

export interface Invoice {
  id: string
  vendor_id: string | null
  vendor?: { name: string } | null
  vendor_name?: string | null // UI expects this
  customer_id: string | null
  customer?: { name: string } | null
  department_id: string | null
  department?: string | null // UI expects this
  invoice_number: string | null
  invoice_date: string | null
  due_date: string | null
  total_amount: number | null
  currency: string
  status: InvoiceStatus
  cash_check_passed: boolean | null
  budget_check_passed: boolean | null
  extraction_confidence: number | null
  created_at: string
}

export const invoiceApi = {
  list: (status?: string) => req<Invoice[]>(`/invoice/${status ? `?status=${status}` : ''}`),
  get: (id: string) => req<Invoice>(`/invoice/${id}`),
  trace: (id: string) => req<{ 
    decisions: AgentDecision[], 
    links: CausalLink[],
    snapshot: FinancialStateSnapshot | null,
    trace: TraceEvent[] // TracePanel expects this
  }>(`/invoice/${id}/causal-trace`).then(r => {
    // If backend doesn't return 'trace' field yet, we map decisions to trace events
    if (!r.trace) {
      r.trace = r.decisions.map(d => ({
        agent: d.agent,
        event_type: d.decision_type,
        timestamp: d.created_at,
        reasoning: d.reasoning,
        details: {}
      }))
    }
    return r
  }),
  upload: async (file: File, departmentId: string) => {
    const fd = new FormData()
    fd.append('file', file)
    const r = await fetch(`${BASE}/invoice/upload?department_id=${departmentId}`, { method: 'POST', body: fd })
    if (!r.ok) {
      const body = await r.text().catch(() => '')
      let detail = body
      try { detail = JSON.parse(body).detail ?? body } catch { /* not JSON */ }
      throw new Error(`Upload failed (${r.status}): ${detail || r.statusText}`)
    }
    return r.json() as Promise<{ invoice_id: string }>
  },
  approve: (id: string, approverId: string) => req(`/invoice/${id}/approve`, { 
    method: 'POST', 
    body: JSON.stringify({ approver_id: approverId }) 
  }),
}

// ── Cash ──────────────────────────────────────────────────────────────────
export interface CashAccount {
  id: string
  account_name: string
  bank_name: string
  currency: string
  current_balance: number
  minimum_balance: number
}

export interface ForecastDay {
  forecast_date: string
  projected_inflow: number
  projected_outflow: number
  net_position: number
}

export const cashApi = {
  position: () => req<{ total_balance: number; accounts: CashAccount[] }>('/cash/position'),
  forecast: () => req<{ forecast: ForecastDay[] }>('/cash/forecast?days=7'),
}

// ── Budget ────────────────────────────────────────────────────────────────
export interface Budget {
  id: string
  department: string | null
  period: string
  allocated: number
  spent: number
  committed: number
  utilisation_pct?: number | null
}

export interface BudgetAlert {
  id: string
  department: string | null
  alert_type: string
  utilisation_pct: number
  message?: string | null
}

export const budgetApi = {
  list: (period?: string) => req<Budget[]>(`/budget/${period ? `?period=${encodeURIComponent(period)}` : ''}`),
  periods: () => req<{ periods: string[]; current: string }>('/budget/periods'),
  alerts: () => req<BudgetAlert[]>('/budget/alerts/active'),
  ack: (id: string) => req(`/budget/alerts/${id}/acknowledge`, { method: 'POST' }),
}

// ── Reconciliation ────────────────────────────────────────────────────────
export interface ReconReport {
  id: string
  period: string
  match_rate: number
  matched_count: number
  unmatched_count: number
  generated_at: string
  generated_by_decision_id: string
  items?: any[]
}

export interface ReconStats {
  total_transactions: number
  matched: number
  unmatched: number
  match_rate_pct: number
}

export const reconApi = {
  stats: () => req<ReconStats>('/reconciliation/stats'),
  run: () => req('/reconciliation/run', { method: 'POST' }),
  unmatched: () => req<any[]>('/reconciliation/unmatched?limit=20'),
  reports: () => req<ReconReport[]>('/reconciliation/reports'),
  report: () => req<ReconReport>('/reconciliation/report'),
}

// ── Credit ────────────────────────────────────────────────────────────────
export interface Customer {
  id: string
  name: string
  risk_level: 'low' | 'medium' | 'high'
  credit_score: number
  payment_terms: number
  payment_delay_avg?: number
  total_outstanding: number
}

export const creditApi = {
  customers: (risk?: string) => req<Customer[]>(`/credit/customers${risk ? `?risk_level=${risk}` : ''}`),
  aging: () => req<{ buckets: Record<string, number>, total_open: number }>('/credit/aging'),
  assess: (id: string) => req(`/credit/assess/${id}`, { method: 'POST' }),
}

// ── Payments Layer (V3) ──────────────────────────────────────────────────
export interface Payment {
  id: string
  invoice_id: string
  amount: number
  payment_date: string
  method: string
  status: string
  reference: string
  invoice?: Invoice
}

export const paymentApi = {
  list: (status?: string) => req<Payment[]>(`/payment/${status ? `?status=${status}` : ''}`),
  get: (id: string) => req<Payment>(`/payment/${id}`),
}

// ── System Intelligence ──────────────────────────────────────────────────
export const intelApi = {
  latestSnap: () => req<FinancialStateSnapshot>('/intel/snapshot/latest'),
  history: () => req<FinancialStateSnapshot[]>('/intel/snapshots?limit=50'),
  decisions: (entityTable: string, entityId: string) => 
    req<AgentDecision[]>(`/intel/decisions?entity_table=${entityTable}&entity_id=${entityId}`),
  causalGraph: () => req<{ nodes: AgentDecision[], edges: CausalLink[] }>('/intel/causal-graph'),
}

