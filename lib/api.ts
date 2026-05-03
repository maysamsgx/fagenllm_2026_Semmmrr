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
  technical_explanation: string | null
  business_explanation: string | null
  causal_explanation: string | null
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
  technical_explanation?: string | null
  business_explanation?: string | null
  causal_explanation?: string | null
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
        technical_explanation: d.technical_explanation,
        business_explanation: d.business_explanation,
        causal_explanation: d.causal_explanation,
        reasoning: d.technical_explanation || d.reasoning,
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

export interface CashScenarioResult {
  label: string
  amount: number
  current_balance: number
  projected_next: number
  balance_after: number
  minimum_balance: number
  headroom: number
  can_approve: boolean
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  analysis: Record<string, any>
}

export const cashApi = {
  position: () => req<{ total_balance: number; accounts: CashAccount[] }>('/cash/position'),
  forecast: (days = 7) => req<{ forecast: ForecastDay[] }>(`/cash/forecast?days=${days}`),
  run: () => req<{ message: string }>('/cash/run', { method: 'POST' }),
  scenario: (amount: number, label = 'Proposed payment') => {
    const qs = new URLSearchParams({ amount: String(amount), label })
    return req<CashScenarioResult>(`/cash/scenario?${qs.toString()}`, { method: 'POST' })
  },
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

export interface WhatIfResult {
  department_id: string
  period: string
  current_utilisation_pct: number
  hypothetical_utilisation_pct: number
  remaining_after: number
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  will_hard_stop: boolean
  analysis: Record<string, any>
}

export const budgetApi = {
  list: (period?: string) => req<Budget[]>(`/budget/${period ? `?period=${encodeURIComponent(period)}` : ''}`),
  periods: () => req<{ periods: string[]; current: string }>('/budget/periods'),
  alerts: () => req<BudgetAlert[]>('/budget/alerts/active'),
  ack: (id: string) => req(`/budget/alerts/${id}/acknowledge`, { method: 'POST' }),
  run: (period?: string, departmentId?: string) => {
    const qs = new URLSearchParams()
    if (period) qs.set('period', period)
    if (departmentId) qs.set('department_id', departmentId)
    const tail = qs.toString() ? `?${qs.toString()}` : ''
    return req<{ message: string }>(`/budget/run${tail}`, { method: 'POST' })
  },
  whatif: (departmentId: string, amount: number, period?: string) => {
    const qs = new URLSearchParams({ department_id: departmentId, amount: String(amount) })
    if (period) qs.set('period', period)
    return req<WhatIfResult>(`/budget/whatif?${qs.toString()}`, { method: 'POST' })
  },
  resetCommitted: (period: string) =>
    req<{ reset: boolean; period: string }>(`/budget/reset-committed?period=${encodeURIComponent(period)}`, { method: 'POST' }),
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

// ── Departments ──────────────────────────────────────────────────────────
export interface Department { id: string; name: string }

export const departmentsApi = {
  list: () => req<Department[]>('/departments'),
}

// ── System Intelligence ──────────────────────────────────────────────────
export const intelApi = {
  latestSnap: () => req<FinancialStateSnapshot>('/intel/snapshot/latest'),
  history: () => req<FinancialStateSnapshot[]>('/intel/snapshots?limit=50'),
  decisions: (entityTable: string, entityId: string) => 
    req<AgentDecision[]>(`/intel/decisions?entity_table=${entityTable}&entity_id=${entityId}`),
  causalGraph: () => req<{ nodes: AgentDecision[], edges: CausalLink[] }>('/intel/causal-graph'),
}

// ── Analytics (New) ───────────────────────────────────────────────────────
export const analyticsApi = {
  aging: () => req<any[]>('/analytics/aging'),
  performance: () => req<any>('/analytics/performance'),
  disputes: () => req<any[]>('/analytics/disputes'),
}

