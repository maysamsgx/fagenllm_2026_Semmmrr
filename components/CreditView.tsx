import { useState, useEffect, useRef } from 'react'
import { Shield, ChevronDown, Check } from 'lucide-react'
import { ResponsiveContainer, BarChart, Bar, Cell, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'
import { creditApi, Customer } from '../lib/api'
import { Card, Badge, Empty, Spinner, RISK_COLOR, RISK_BG, fmt, AgentAvatar } from './Shared'
import { useRealtime } from '../lib/useRealtime'
import { AgingMetricsRow, AgingChartCard, useAnalytics } from './AgingDashboard'
import DisputePortal from './DisputePortal'

const AGING_COLORS = ['#22d3ee', '#6366f1', '#a78bfa', '#e879f9', '#fb7185']


function AgingTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number; dataIndex?: number }[]; label?: string }) {
  if (!active || !payload?.length) return null
  const color = AGING_COLORS[payload[0].dataIndex ?? 0] ?? '#22d3ee'
  return (
    <div style={{
      background: 'rgba(13,18,38,.97)',
      border: `1px solid ${color}38`,
      borderRadius: 10,
      padding: '10px 14px',
      backdropFilter: 'blur(24px)',
      boxShadow: `0 16px 48px rgba(0,0,0,.65), 0 0 0 1px ${color}12`,
    }}>
      <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.1em', color: 'var(--text-4)', marginBottom: 6 }}>{label}</div>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 15, fontWeight: 600, color }}>{fmt(payload[0].value)}</div>
    </div>
  )
}

const RISK_OPTIONS = [
  { value: '',       label: 'All risk',  dot: null },
  { value: 'low',    label: 'Low',       dot: '#34d399' },
  { value: 'medium', label: 'Medium',    dot: '#fbbf24' },
  { value: 'high',   label: 'High',      dot: '#fb7185' },
]

function RiskDropdown({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const current = RISK_OPTIONS.find(o => o.value === value) ?? RISK_OPTIONS[0]

  return (
    <div ref={ref} style={{ position: 'relative', userSelect: 'none' }}>
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          background: open ? 'rgba(255,255,255,.1)' : 'rgba(255,255,255,.06)',
          border: `1px solid ${open ? 'rgba(34,211,238,.35)' : 'rgba(255,255,255,.12)'}`,
          borderRadius: 7, padding: '4px 10px', fontSize: 12,
          color: 'var(--text)', cursor: 'pointer', outline: 'none',
          transition: 'all .15s',
        }}
      >
        {current.dot && <span style={{ width: 7, height: 7, borderRadius: '50%', background: current.dot, flexShrink: 0 }} />}
        {current.label}
        <ChevronDown size={11} style={{ opacity: .55, transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .15s' }} />
      </button>

      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 6px)', right: 0,
          background: 'rgba(10,14,30,.97)', backdropFilter: 'blur(20px)',
          border: '1px solid rgba(255,255,255,.12)', borderRadius: 10,
          padding: '5px', minWidth: 130, zIndex: 100,
          boxShadow: '0 12px 40px rgba(0,0,0,.6), 0 0 0 1px rgba(34,211,238,.08)',
        }}>
          {RISK_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => { onChange(opt.value); setOpen(false) }}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, width: '100%',
                padding: '7px 10px', borderRadius: 7, border: 'none',
                background: value === opt.value ? 'rgba(34,211,238,.1)' : 'transparent',
                color: value === opt.value ? '#67e8f9' : 'var(--text-2)',
                fontSize: 12, cursor: 'pointer', textAlign: 'left',
                transition: 'background .1s',
              }}
              onMouseEnter={e => { if (value !== opt.value) (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,.06)' }}
              onMouseLeave={e => { if (value !== opt.value) (e.currentTarget as HTMLElement).style.background = 'transparent' }}
            >
              {opt.dot
                ? <span style={{ width: 7, height: 7, borderRadius: '50%', background: opt.dot, flexShrink: 0 }} />
                : <span style={{ width: 7 }} />}
              <span style={{ flex: 1 }}>{opt.label}</span>
              {value === opt.value && <Check size={10} />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
export default function CreditView() {
  const [customers, setCustomers]     = useState<Customer[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [riskFilter, setRiskFilter]   = useState('')
  const [assessingId, setAssessingId] = useState<string | null>(null)
  
  const { agingData, metrics, loading: analyticsLoading } = useAnalytics()

  const load = () => {
    creditApi.customers(riskFilter || undefined).then(rows => {
      const seen = new Set<string>()
      setCustomers(rows.filter(c => { if (seen.has(c.id)) return false; seen.add(c.id); return true }))
    }).catch(() => {})
  }
  useEffect(() => { load() }, [riskFilter])

  useRealtime('customers', load)
  useRealtime('receivables', load)

  const visibleCustomers = customers.filter(c =>
    !searchQuery || c.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const handleAssess = async (id: string) => {
    setAssessingId(id)
    try {
      await creditApi.assess(id)
      load()
    } finally {
      setAssessingId(null)
    }
  }

  return (
    <div className="view">
      <div className="view-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <AgentAvatar agent="credit" />
          <div>
            <h2>Credit & Collection</h2>
            <p className="view-sub">R = Σ(wᵢ × fᵢ) · automated collection stage escalation</p>
          </div>
        </div>
      </div>

      <AgingMetricsRow metrics={metrics} loading={analyticsLoading} />

      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 20, marginTop: 24, alignItems: 'start' }}>
        <Card style={{ minHeight: 600 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
            <h3 style={{ margin: 0, flex: 1, color: 'var(--cyan)' }}>Risk Monitoring</h3>

            <input
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search name…"
              style={{
                background: 'rgba(255,255,255,.06)', border: '1px solid rgba(255,255,255,.12)',
                borderRadius: 6, padding: '4px 10px', fontSize: 12, color: 'var(--text)',
                outline: 'none', width: 130,
              }}
            />
            <RiskDropdown value={riskFilter} onChange={setRiskFilter} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {visibleCustomers.length === 0
              ? <Empty msg="No customers match" />
              : visibleCustomers.map((c: Customer) => {
                  const sc = c.credit_score ?? 0
                  const scColor = sc > 70 ? '#34d399' : sc > 45 ? '#fbbf24' : '#fb7185'
                  const isAssessing = assessingId === c.id
                  return (
                    <div key={c.id} className="customer-row">
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 500, fontSize: 13, color: 'var(--text)' }}>{c.name}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-4)' }}>
                          {c.payment_terms}d terms · avg delay: {c.payment_delay_avg?.toFixed(1) ?? '?'}d
                        </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 13, color: 'var(--text)' }}>{fmt(c.total_outstanding)}</div>
                        <div style={{ marginTop: 3 }}>
                          <Badge label={c.risk_level} color={RISK_COLOR[c.risk_level]} bg={RISK_BG[c.risk_level]} />
                        </div>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 56 }}>
                        <div style={{
                          fontSize: 18, fontFamily: 'JetBrains Mono, monospace', fontWeight: 600,
                          color: scColor, textShadow: `0 0 12px ${scColor}66`,
                        }}>
                          {sc.toFixed(0)}
                        </div>
                        <div style={{ fontSize: 9.5, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '.08em', marginTop: 1 }}>R score</div>
                      </div>
                      <button
                        className="btn-sm"
                        disabled={isAssessing}
                        onClick={() => handleAssess(c.id)}
                        style={{ minWidth: 72, opacity: isAssessing ? 0.7 : 1 }}
                      >
                        {isAssessing ? <Spinner /> : <Shield size={11} />}
                        {isAssessing ? 'Running…' : 'Assess'}
                      </button>
                    </div>
                  )
                })}
          </div>
        </Card>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <AgingChartCard agingData={agingData} loading={analyticsLoading} />
          <DisputePortal />
        </div>
      </div>
    </div>
  )
}
