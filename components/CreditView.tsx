import { useState, useEffect } from 'react'
import { Shield } from 'lucide-react'
import { ResponsiveContainer, BarChart, Bar, Cell, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'
import { creditApi, Customer } from '../lib/api'
import { Card, Badge, Empty, RISK_COLOR, RISK_BG, fmt } from './Shared'
import { useRealtime } from '../lib/useRealtime'

export default function CreditView() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [aging, setAging]         = useState<Record<string, number>>({})
  const [totalOpen, setTotalOpen] = useState(0)

  const load = () => {
    creditApi.customers().then(setCustomers).catch(() => {})
    creditApi.aging().then(r => { setAging(r.buckets); setTotalOpen(r.total_open) }).catch(() => {})
  }
  useEffect(() => { load() }, [])

  useRealtime('customers', load)
  useRealtime('receivables', load)

  const agingData = Object.entries(aging).map(([k, v]) => ({
    bucket: k.replace('_', '–'), amount: v,
  }))

  return (
    <div className="view">
      <div className="view-header">
        <div>
          <h2>Credit & Collection</h2>
          <p className="view-sub">R = Σ(wᵢ × fᵢ) · automated collection stage escalation</p>
        </div>
      </div>

      <div className="stats-row">
        <Card>
          <div className="stat-label">Total AR open</div>
          <div className="stat-value" style={{ color: '#67e8f9' }}>{fmt(totalOpen)}</div>
        </Card>
        {(['low','medium','high'] as const).map((r: 'low' | 'medium' | 'high') => (
          <Card key={r}>
            <div className="stat-label">{r} risk</div>
            <div className="stat-value" style={{ color: RISK_COLOR[r] }}>
              {customers.filter((c: Customer) => c.risk_level === r).length}
            </div>
          </Card>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 16 }}>
        <Card>
          <h3 style={{ marginBottom: 14 }}>Customers</h3>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {customers.slice(0, 8).map((c: Customer) => {
              const sc = c.credit_score ?? 0
              const scColor = sc > 70 ? '#34d399' : sc > 45 ? '#fbbf24' : '#fb7185'
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
                  <button className="btn-sm" onClick={() => creditApi.assess(c.id).then(load)}>
                    <Shield size={11} /> Assess
                  </button>
                </div>
              )
            })}
          </div>
        </Card>

        <Card>
          <h3 style={{ marginBottom: 14 }}>AR Aging</h3>
          {agingData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={agingData} layout="vertical">
                <CartesianGrid strokeDasharray="2 4" stroke="rgba(255,255,255,.05)" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: 'var(--text-3)' }} stroke="rgba(255,255,255,.08)" tickFormatter={(v: number) => `$${(v/1000).toFixed(0)}k`} />
                <YAxis dataKey="bucket" type="category" tick={{ fontSize: 11, fill: 'var(--text-3)' }} stroke="rgba(255,255,255,.08)" width={64} />
                <Tooltip formatter={(v: number) => fmt(v)} cursor={{ fill: 'rgba(34, 211, 238, .08)' }} />
                <Bar dataKey="amount" radius={[0, 6, 6, 0]}>
                  {agingData.map((_, i: number) => (
                    <Cell key={i} fill={['#34d399','#84cc16','#fbbf24','#f97316','#fb7185'][i] ?? '#67e8f9'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty msg="No receivables data" />}
        </Card>
      </div>
    </div>
  )
}
