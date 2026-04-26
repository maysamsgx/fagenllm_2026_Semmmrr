const BASE = '/api'

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json()
}

// ── Invoice ────────────────────────────────────────────────────────────────
export type InvoiceStatus =
  | 'pending' | 'extracting' | 'validating' | 'awaiting_approval'
  | 'approved' | 'rejected' | 'paid'

export interface Invoice {
  id: string
  vendor_name: string | null
  invoice_number: string | null
  invoice_date: string | null
  due_date: string | null
  total_amount: number | null
  currency: string
  status: InvoiceStatus
  department: string | null
  cash_check_passed: boolean | null
  budget_check_passed: boolean | null
  extraction_confidence: number | null
  created_at: string
}

export interface TraceEvent {
  agent: string
  event_type: string
  reasoning: string
  details: Record<string, unknown>
  timestamp: string
}

export const invoiceApi = {
  list: (status?: string) =>
    req<Invoice[]>(`/invoice/${status ? `?status=${status}` : ''}`),
  get: (id: string) => req<Invoice>(`/invoice/${id}`),
  trace: (id: string) => req<{ trace: TraceEvent[] }>(`/invoice/${id}/trace`),
  approve: (id: string, approver_id: string) =>
    req(`/invoice/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approver_id, notes: '' }),
    }),
  reject: (id: string, reason: string) =>
    req(`/invoice/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason, approver_id: 'dashboard-user' }),
    }),
  upload: async (file: File, department: string) => {
    const fd = new FormData()
    fd.append('file', file)
    const r = await fetch(`${BASE}/invoice/upload?department=${department}`, {
      method: 'POST',
      body: fd,
    })
    if (!r.ok) throw new Error(`Upload failed: ${r.statusText}`)
    return r.json() as Promise<{ invoice_id: string }>
  },
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
  position: () =>
    req<{ total_balance: number; accounts: CashAccount[] }>('/cash/position'),
  forecast: () => req<{ forecast: ForecastDay[] }>('/cash/forecast?days=7'),
}

// ── Budget ────────────────────────────────────────────────────────────────
export interface Budget {
  id: string
  department: string
  period: string
  allocated: number
  spent: number
  committed: number
  utilisation_pct: number
}

export interface BudgetAlert {
  id: string
  department: string
  utilisation_pct: number
  alert_type: string
  message: string
  acknowledged: boolean
  created_at: string
}

export const budgetApi = {
  list: () => req<Budget[]>('/budget/'),
  alerts: () => req<BudgetAlert[]>('/budget/alerts/active'),
  ack: (id: string) =>
    req(`/budget/alerts/${id}/acknowledge`, { method: 'POST' }),
}

// ── Reconciliation ────────────────────────────────────────────────────────
export interface ReconReport {
  period: string
  matched_count: number
  unmatched_count: number
  match_rate: number
  total_internal: number
  total_external: number
  generated_at: string
}

export interface ReconStats {
  total_transactions: number
  matched: number
  unmatched: number
  match_rate_pct: number
}

export const reconApi = {
  stats: () => req<ReconStats>('/reconciliation/stats'),
  report: () => req<ReconReport | { message: string }>('/reconciliation/report'),
  run: () => req('/reconciliation/run', { method: 'POST' }),
  unmatched: () => req<unknown[]>('/reconciliation/unmatched?limit=20'),
}

// ── Credit ────────────────────────────────────────────────────────────────
export interface Customer {
  id: string
  name: string
  email: string
  credit_score: number
  risk_level: 'low' | 'medium' | 'high'
  credit_limit: number
  total_outstanding: number
  payment_terms: number
  payment_delay_avg: number
  collection_stage?: string
}

export interface AgingBucket {
  buckets: Record<string, number>
  total_open: number
  currency: string
}

export const creditApi = {
  customers: (risk?: string) =>
    req<Customer[]>(`/credit/customers${risk ? `?risk_level=${risk}` : ''}`),
  aging: () => req<AgingBucket>('/credit/aging'),
  assess: (id: string) =>
    req(`/credit/assess/${id}`, { method: 'POST' }),
}
