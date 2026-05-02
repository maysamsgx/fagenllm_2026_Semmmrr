import React from 'react'

export function Card({ children, className = '', ...props }: { children: React.ReactNode; className?: string; [key: string]: any }) {
  return <div className={`card ${className}`} {...props}>{children}</div>
}

export function AgentAvatar({ agent, active }: { agent: string; active?: boolean }) {
  const src = getAgentAvatar(agent)
  return (
    <div className={`agent-avatar-wrapper ${active ? 'active' : ''}`}>
      <img src={src} className="agent-avatar-img" alt={`${agent} agent`} />
    </div>
  )
}

export function Badge({ label, color, bg, className = '' }: { label: string; color: string; bg: string; className?: string }) {
  return (
    <span
      className={`badge ${className}`.trim()}
      style={{
        background: bg,
        color,
        borderColor: color + '55',
      }}
    >
      {label}
    </span>
  )
}

export function Spinner() {
  return <div className="spinner" />
}

export function Empty({ msg }: { msg: string }) {
  return <div className="empty">{msg}</div>
}

export const RISK_COLOR: Record<string, string> = { low: '#34d399', medium: '#fbbf24', high: '#fb7185' }
export const RISK_BG: Record<string, string>    = { low: 'rgba(52, 211, 153, .12)', medium: 'rgba(251, 191, 36, .12)', high: 'rgba(251, 113, 133, .12)' }
export const STATUS_COLOR: Record<string, string> = {
  pending: '#94a3b8',
  extracting: '#67e8f9',
  validating: '#a78bfa',
  awaiting_approval: '#fbbf24',
  approved: '#34d399',
  rejected: '#fb7185',
  paid: '#22d3ee',
}
export const STATUS_BG: Record<string, string> = {
  pending: 'rgba(148, 163, 184, .14)',
  extracting: 'rgba(103, 232, 249, .14)',
  validating: 'rgba(167, 139, 250, .14)',
  awaiting_approval: 'rgba(251, 191, 36, .14)',
  approved: 'rgba(52, 211, 153, .14)',
  rejected: 'rgba(251, 113, 133, .14)',
  paid: 'rgba(34, 211, 238, .14)',
}
export const AGENT_COLOR: Record<string, string> = {
  invoice: '#67e8f9',
  cash: '#22d3ee',
  budget: '#a78bfa',
  reconciliation: '#fbbf24',
  credit: '#fb7185',
  supervisor: '#94a3b8',
}

export const BRAND_LOGO = '/assets/image-removebg-preview (21).png'
export const LEGACY_BRAND_LOGO = '/assets/logo_for_FAgentllm.png'

export const AGENT_AVATAR: Record<string, string> = {
  invoice: '/assets/agents/invoice.png',
  invoice_agent: '/assets/agents/invoice.png',
  cash: '/assets/agents/cash.png',
  cash_agent: '/assets/agents/cash.png',
  budget: '/assets/agents/budget.png',
  budget_agent: '/assets/agents/budget.png',
  reconciliation: '/assets/agents/reconciliation.png',
  reconciliation_agent: '/assets/agents/reconciliation.png',
  credit: '/assets/agents/credit.png',
  credit_agent: '/assets/agents/credit.png',
}

export const LEGACY_AGENT_AVATAR: Record<string, string> = {
  invoice: '/agents/invoice.png',
  invoice_agent: '/agents/invoice.png',
  cash: '/agents/cash.png',
  cash_agent: '/agents/cash.png',
  budget: '/agents/budget.png',
  budget_agent: '/agents/budget.png',
  reconciliation: '/agents/reconciliation.png',
  reconciliation_agent: '/agents/reconciliation.png',
  credit: '/agents/credit.png',
  credit_agent: '/agents/credit.png',
}

export function getAgentAvatar(agent: string) {
  const key = (agent || '').toLowerCase()
  if (AGENT_AVATAR[key]) return AGENT_AVATAR[key]
  if (key.includes('invoice')) return AGENT_AVATAR.invoice
  if (key.includes('cash')) return AGENT_AVATAR.cash
  if (key.includes('budget')) return AGENT_AVATAR.budget
  if (key.includes('reconciliation')) return AGENT_AVATAR.reconciliation
  if (key.includes('credit')) return AGENT_AVATAR.credit
  return BRAND_LOGO
}

export function getLegacyAgentAvatar(agent: string) {
  const key = (agent || '').toLowerCase()
  if (LEGACY_AGENT_AVATAR[key]) return LEGACY_AGENT_AVATAR[key]
  if (key.includes('invoice')) return LEGACY_AGENT_AVATAR.invoice
  if (key.includes('cash')) return LEGACY_AGENT_AVATAR.cash
  if (key.includes('budget')) return LEGACY_AGENT_AVATAR.budget
  if (key.includes('reconciliation')) return LEGACY_AGENT_AVATAR.reconciliation
  if (key.includes('credit')) return LEGACY_AGENT_AVATAR.credit
  return LEGACY_BRAND_LOGO
}

export function fmt(n: number | null, currency = 'USD') {
  if (n == null) return '—'
  if (Math.abs(n) >= 1_000_000) {
    const formatted = new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 1 }).format(n / 1_000_000)
    return `${formatted}M`
  }
  return new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 0 }).format(n)
}

export function pct(n: number) { return `${n.toFixed(1)}%` }
