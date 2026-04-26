import React from 'react'

export function Card({ children, className = '', ...props }: { children: React.ReactNode; className?: string; [key: string]: any }) {
  return <div className={`card ${className}`} {...props}>{children}</div>
}

export function Badge({ label, color, bg }: { label: string; color: string; bg: string }) {
  return (
    <span style={{ background: bg, color, fontSize: 11, fontWeight: 600,
      padding: '2px 8px', borderRadius: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
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

export const RISK_COLOR: Record<string, string> = { low: '#22c55e', medium: '#f59e0b', high: '#ef4444' }
export const RISK_BG: Record<string, string>    = { low: '#dcfce7', medium: '#fef3c7', high: '#fee2e2' }
export const STATUS_COLOR: Record<string, string> = {
  pending: '#94a3b8', extracting: '#6366f1', validating: '#8b5cf6',
  awaiting_approval: '#f59e0b', approved: '#22c55e', rejected: '#ef4444', paid: '#0ea5e9',
}
export const AGENT_COLOR: Record<string, string> = {
  invoice: '#6366f1', cash: '#0ea5e9', budget: '#8b5cf6',
  reconciliation: '#f59e0b', credit: '#ef4444', supervisor: '#64748b',
}

export function fmt(n: number | null, currency = 'USD') {
  if (n == null) return '—'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 0 }).format(n)
}

export function pct(n: number) { return `${n.toFixed(1)}%` }
