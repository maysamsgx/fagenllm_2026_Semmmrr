import { useState, useEffect } from 'react'
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from 'recharts'
import { cashApi, CashAccount, ForecastDay } from '../lib/api'
import { Card, Badge, Empty, fmt } from './Shared'

export default function CashView() {
  const [pos, setPos]       = useState<{ total_balance: number; accounts: CashAccount[] } | null>(null)
  const [forecast, setFore] = useState<ForecastDay[]>([])

  useEffect(() => {
    cashApi.position().then(setPos)
    cashApi.forecast().then(r => setFore(r.forecast))
    const t = setInterval(() => {
      cashApi.position().then(setPos)
      cashApi.forecast().then(r => setFore(r.forecast))
    }, 10000)
    return () => clearInterval(t)
  }, [])

  const fmtDay = (d: string) => new Date(d).toLocaleDateString('en', { weekday: 'short', day: 'numeric' })

  return (
    <div className="view">
      <div className="view-header">
        <div>
          <h2>Cash Management</h2>
          <p className="view-sub">C<sub>t+1</sub> = C<sub>t</sub> + I<sub>t</sub> − O<sub>t</sub> &nbsp;·&nbsp; 7-day liquidity forecast</p>
        </div>
      </div>

      <div className="stats-row">
        <Card className="stat-featured">
          <div className="stat-label">Total balance</div>
          <div className="stat-value-lg">{pos ? fmt(pos.total_balance) : '—'}</div>
          <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>across all accounts</div>
        </Card>
        {pos?.accounts.map((a: CashAccount) => (
          <Card key={a.id}>
            <div className="stat-label">{a.account_name}</div>
            <div className="stat-value" style={{ fontFamily: 'DM Mono, monospace' }}>
              {fmt(a.current_balance, a.currency)}
            </div>
            <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
              {a.bank_name} · min {fmt(a.minimum_balance, a.currency)}
            </div>
            {a.current_balance < a.minimum_balance * 1.2 && (
              <div style={{ marginTop: 6 }}>
                <Badge label="Low" color="#ef4444" bg="#fee2e2" />
              </div>
            )}
          </Card>
        ))}
      </div>

      <Card>
        <h3 style={{ marginBottom: 16 }}>7-Day Cash Flow Forecast</h3>
        {forecast.length === 0 ? <Empty msg="No forecast data — run seed_data.py" /> : (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={forecast.map((d: ForecastDay) => ({
              day: fmtDay(d.forecast_date),
              inflow: d.projected_inflow,
              outflow: d.projected_outflow,
              net: d.net_position,
            }))}>
              <defs>
                <linearGradient id="gi" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="go" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `$${(v/1000).toFixed(0)}k`} />
              <Tooltip formatter={(v: number) => fmt(v)} />
              <Area type="monotone" dataKey="inflow"  stroke="#22c55e" fill="url(#gi)" name="Inflows" strokeWidth={2} />
              <Area type="monotone" dataKey="outflow" stroke="#ef4444" fill="url(#go)" name="Outflows" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </Card>
    </div>
  )
}
