import { useState, useEffect } from 'react'
import { Shield } from 'lucide-react'
import { ResponsiveContainer, BarChart, Bar, Cell, XAxis, YAxis, Tooltip } from 'recharts'
import { creditApi, Customer } from '../lib/api'
import { Card, Badge, Empty, RISK_COLOR, RISK_BG, fmt } from './Shared'

export default function CreditView() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [aging, setAging]         = useState<Record<string, number>>({})
  const [totalOpen, setTotalOpen] = useState(0)

  const load = () => {
    creditApi.customers().then(setCustomers)
    creditApi.aging().then(r => { setAging(r.buckets); setTotalOpen(r.total_open) })
  }
  useEffect(() => { load(); const t = setInterval(load, 10000); return () => clearInterval(t) }, [])

  const agingData = Object.entries(aging).map(([k, v]) => ({
    bucket: k.replace('_', '–').replace('1', '1'), amount: v,
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
          <div className="stat-value" style={{ fontFamily: 'DM Mono' }}>{fmt(totalOpen)}</div>
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
          <h3 style={{ marginBottom: 12 }}>Customers</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {customers.slice(0, 8).map((c: Customer) => (
              <div key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 12,
                padding: '8px 0', borderBottom: '1px solid #f1f5f9' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 500, fontSize: 13 }}>{c.name}</div>
                  <div style={{ fontSize: 11, color: '#64748b' }}>
                    {c.payment_terms}d terms · avg delay: {c.payment_delay_avg?.toFixed(1) ?? '?'}d
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontFamily: 'DM Mono', fontSize: 13 }}>{fmt(c.total_outstanding)}</div>
                  <Badge label={c.risk_level} color={RISK_COLOR[c.risk_level]} bg={RISK_BG[c.risk_level]} />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 48 }}>
                  <div style={{ fontSize: 18, fontFamily: 'DM Mono', fontWeight: 600,
                    color: c.credit_score > 70 ? '#22c55e' : c.credit_score > 45 ? '#f59e0b' : '#ef4444' }}>
                    {c.credit_score?.toFixed(0) ?? '?'}
                  </div>
                  <div style={{ fontSize: 10, color: '#94a3b8' }}>R score</div>
                </div>
                <button className="btn-sm" onClick={() => creditApi.assess(c.id).then(load)}>
                  <Shield size={11} /> Assess
                </button>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <h3 style={{ marginBottom: 12 }}>AR Aging</h3>
          {agingData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={agingData} layout="vertical">
                <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v: number) => `$${(v/1000).toFixed(0)}k`} />
                <YAxis dataKey="bucket" type="category" tick={{ fontSize: 11 }} width={60} />
                <Tooltip formatter={(v: number) => fmt(v)} />
                <Bar dataKey="amount" radius={[0, 4, 4, 0]}>
                  {agingData.map((d: any, i: number) => (
                    <Cell key={i} fill={['#22c55e','#84cc16','#f59e0b','#f97316','#ef4444'][i] ?? '#64748b'} />
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
