import { useState, useEffect } from 'react'
import { RefreshCw, TrendingUp, TrendingDown } from 'lucide-react'
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'
import { cashApi, CashAccount, ForecastDay } from '../lib/api'
import { Card, Badge, Empty, fmt, AgentAvatar } from './Shared'
import { useRealtime } from '../lib/useRealtime'

export default function CashView() {
  const [pos, setPos]       = useState<{ total_balance: number; accounts: CashAccount[] } | null>(null)
  const [forecast, setFore] = useState<ForecastDay[]>([])
  const [running, setRunning] = useState(false)

  const load = () => {
    cashApi.position().then(setPos).catch(() => {})
    cashApi.forecast().then(r => setFore(r.forecast)).catch(() => {})
  }

  useEffect(() => { load() }, [])

  useRealtime('cash_accounts', load)
  useRealtime('transactions', load)
  useRealtime('cash_flow_forecasts', load)

  const fmtDay = (d: string) => new Date(d).toLocaleDateString('en', { weekday: 'short', day: 'numeric' })

  return (
    <div className="view">
      <div className="view-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <AgentAvatar agent="cash" active={running} />
          <div>
            <h2>Cash Management</h2>
            <p className="view-sub">C<sub>t+1</sub> = C<sub>t</sub> + I<sub>t</sub> − O<sub>t</sub> &nbsp;·&nbsp; 7-day liquidity forecast</p>
          </div>
        </div>
        <button
          className="btn-primary"
          disabled={running}
          onClick={async () => {
            setRunning(true)
            try { await cashApi.run() } catch (e) { alert(`Run failed: ${e}`) }
            setTimeout(() => { load(); setRunning(false) }, 4000)
          }}
        >
          <RefreshCw size={14} className={running ? 'spin' : ''} strokeWidth={2.5} />
          {running ? 'Refreshing…' : 'Refresh Position'}
        </button>
      </div>

      <div className="stats-row">
        <Card className="stat-featured">
          <div className="stat-label">Total balance</div>
          <div className="stat-value-lg" style={{ color: '#67e8f9', textShadow: '0 0 24px rgba(34, 211, 238, .35)' }}>
            {pos ? fmt(pos.total_balance) : '—'}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 6 }}>across all accounts</div>
        </Card>
        {pos?.accounts.map((a: CashAccount) => (
          <Card key={a.id}>
            <div className="stat-label">{a.account_name}</div>
            <div className="stat-value">
              {fmt(a.current_balance, a.currency)}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 6 }}>
              {a.bank_name} · min {fmt(a.minimum_balance, a.currency)}
            </div>
            {a.current_balance < a.minimum_balance * 1.2 && (
              <div style={{ marginTop: 8 }}>
                <Badge label="Low" color="#fb7185" bg="rgba(251, 113, 133, .14)" />
              </div>
            )}
          </Card>
        ))}
      </div>

      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
          <h3>7-Day Cash Flow Forecast</h3>
          <div style={{ display: 'flex', gap: 14, fontSize: 11, color: 'var(--text-3)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <TrendingUp size={12} color="#34d399" /> Inflows
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <TrendingDown size={12} color="#fb7185" /> Outflows
            </span>
          </div>
        </div>
        {forecast.length === 0 ? <Empty msg="No forecast data — run seed_data.py" /> : (
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={forecast.map((d: ForecastDay) => ({
              day: fmtDay(d.forecast_date),
              inflow: d.projected_inflow,
              outflow: d.projected_outflow,
              net: d.net_position,
            }))}>
              <defs>
                <linearGradient id="gi" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#34d399" stopOpacity={0.45} />
                  <stop offset="100%" stopColor="#34d399" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="go" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#fb7185" stopOpacity={0.45} />
                  <stop offset="100%" stopColor="#fb7185" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="2 4" stroke="rgba(255,255,255,.05)" />
              <XAxis dataKey="day" tick={{ fontSize: 11, fill: 'var(--text-3)' }} stroke="rgba(255,255,255,.08)" />
              <YAxis tick={{ fontSize: 11, fill: 'var(--text-3)' }} stroke="rgba(255,255,255,.08)" tickFormatter={v => `$${(v/1000).toFixed(0)}k`} />
              <Tooltip formatter={(v: number) => fmt(v)} />
              <Area type="monotone" dataKey="inflow"  stroke="#34d399" fill="url(#gi)" name="Inflows" strokeWidth={2} />
              <Area type="monotone" dataKey="outflow" stroke="#fb7185" fill="url(#go)" name="Outflows" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </Card>
    </div>
  )
}
