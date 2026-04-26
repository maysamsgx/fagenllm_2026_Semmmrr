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

// ── Invoice ────────────────────────────────────────────────────────────────
export type InvoiceStatus =
  | 'pending' | 'extracting' | 'validating' | 'awaiting_approval'
  | 'approved' | 'rejected' | 'paid'

export interface Invoice {
  id: string
  vendor_id: string | null
  vendor?: { name: string } | null
  customer_id: string | null
  customer?: { name: string } | null
  department_id: string | null
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
    snapshot: FinancialStateSnapshot | null
  }>(`/invoice/${id}/causal-trace`),
  upload: async (file: File, departmentId: string) => {
    const fd = new FormData()
    fd.append('file', file)
    const r = await fetch(`${BASE}/invoice/upload?department_id=${departmentId}`, { method: 'POST', body: fd })
    if (!r.ok) throw new Error(`Upload failed: ${r.statusText}`)
    return r.json() as Promise<{ invoice_id: string }>
  },
}

// ── Cash ──────────────────────────────────────────────────────────────────
export const cashApi = {
  position: () => req<{ total_balance: number; accounts: any[] }>('/cash/position'),
  forecast: () => req<{ forecast: any[] }>('/cash/forecast?days=7'),
}

// ── Budget ────────────────────────────────────────────────────────────────
export const budgetApi = {
  list: () => req<any[]>('/budget/'),
  alerts: () => req<any[]>('/budget/alerts/active'),
  ack: (id: string) => req(`/budget/alerts/${id}/acknowledge`, { method: 'POST' }),
}

// ── Reconciliation ────────────────────────────────────────────────────────
export interface ReconReport {
  id: string
  period: string
  match_rate: number
  unmatched_count: number
  generated_by_decision_id: string
  items?: any[]
}

export const reconApi = {
  stats: () => req<any>('/reconciliation/stats'),
  run: () => req('/reconciliation/run', { method: 'POST' }),
  unmatched: () => req<any[]>('/reconciliation/unmatched?limit=20'),
  reports: () => req<ReconReport[]>('/reconciliation/reports'),
}

// ── Credit ────────────────────────────────────────────────────────────────
export const creditApi = {
  customers: (risk?: string) => req<any[]>(`/credit/customers${risk ? `?risk_level=${risk}` : ''}`),
  aging: () => req<any>('/credit/aging'),
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
