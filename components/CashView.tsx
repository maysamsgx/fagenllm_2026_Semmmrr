import { useState, useEffect } from 'react'
import { RefreshCw, TrendingUp, TrendingDown, FlaskConical, ChevronDown, ChevronUp } from 'lucide-react'
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'
import { cashApi, CashAccount, ForecastDay, CashScenarioResult } from '../lib/api'
import { Card, Badge, Empty, fmt, AgentAvatar, Spinner } from './Shared'
import { useRealtime } from '../lib/useRealtime'

const RISK_COLOR: Record<string, string> = {
  low: '#34d399', medium: '#fbbf24', high: '#f97316', critical: '#fb7185',
}

export default function CashView() {
  const [pos, setPos]         = useState<{ total_balance: number; accounts: CashAccount[] } | null>(null)
  const [forecast, setFore]   = useState<ForecastDay[]>([])
  const [running, setRunning] = useState(false)

  // Scenario (what-if)
  const [showScenario, setShowScenario] = useState(false)
  const [scAmount, setScAmount]         = useState('')
  const [scLabel, setScLabel]           = useState('')
  const [scLoading, setScLoading]       = useState(false)
  const [scResult, setScResult]         = useState<CashScenarioResult | null>(null)
  const [scError, setScError]           = useState('')

  const load = () => {
    cashApi.position().then(setPos).catch(() => {})
    cashApi.forecast().then(r => setFore(r.forecast)).catch(() => {})
  }

  useEffect(() => { load() }, [])

  useRealtime('cash_accounts', load)
  useRealtime('transactions', load)
  useRealtime('cash_flow_forecasts', load)

  const fmtDay = (d: string) => new Date(d).toLocaleDateString('en', { weekday: 'short', day: 'numeric' })

  const runScenario = async () => {
    const amt = parseFloat(scAmount)
    if (isNaN(amt) || amt <= 0) { setScError('Enter a valid positive amount.'); return }
    setScError('')
    setScLoading(true)
    setScResult(null)
    try {
      const res = await cashApi.scenario(amt, scLabel || 'Proposed payment')
      setScResult(res)
    } catch (e) {
      setScError(`Error: ${e}`)
    } finally {
      setScLoading(false)
    }
  }

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
        {forecast.length === 0 ? <Empty msg="No forecast data — run Refresh Position" /> : (
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

      {/* What-If Scenario */}
      <div style={{ marginTop: 24, border: '1px solid rgba(255,255,255,.08)', borderRadius: 12, overflow: 'hidden' }}>
        <button
          onClick={() => setShowScenario(v => !v)}
          style={{
            width: '100%', display: 'flex', alignItems: 'center', gap: 10,
            padding: '14px 18px', background: 'rgba(255,255,255,.03)',
            border: 'none', cursor: 'pointer', color: 'var(--text)',
          }}
        >
          <FlaskConical size={15} color="#67e8f9" />
          <span style={{ fontWeight: 600, fontSize: 13, flex: 1, textAlign: 'left' }}>What-If Scenario</span>
          <span style={{ fontSize: 11, color: 'var(--text-4)', marginRight: 6 }}>
            Simulate liquidity impact before committing a payment
          </span>
          {showScenario ? <ChevronUp size={14} color="var(--text-3)" /> : <ChevronDown size={14} color="var(--text-3)" />}
        </button>

        {showScenario && (
          <div style={{ padding: '18px', background: 'rgba(0,0,0,.15)' }}>
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-4)', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '.06em' }}>Payment amount ($)</div>
                <input
                  type="number" min="1" step="100"
                  value={scAmount}
                  onChange={e => { setScAmount(e.target.value); setScResult(null) }}
                  placeholder="e.g. 25000"
                  style={{
                    background: 'rgba(255,255,255,.06)', border: '1px solid rgba(255,255,255,.12)',
                    borderRadius: 6, padding: '6px 10px', fontSize: 12, color: 'var(--text)',
                    outline: 'none', width: 150,
                  }}
                />
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-4)', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '.06em' }}>Label (optional)</div>
                <input
                  type="text"
                  value={scLabel}
                  onChange={e => { setScLabel(e.target.value); setScResult(null) }}
                  placeholder="e.g. Vendor invoice #42"
                  style={{
                    background: 'rgba(255,255,255,.06)', border: '1px solid rgba(255,255,255,.12)',
                    borderRadius: 6, padding: '6px 10px', fontSize: 12, color: 'var(--text)',
                    outline: 'none', width: 200,
                  }}
                />
              </div>
              <button
                className="btn-primary"
                disabled={scLoading}
                onClick={runScenario}
                style={{ minWidth: 130 }}
              >
                {scLoading ? <Spinner /> : <FlaskConical size={13} />}
                {scLoading ? 'Analysing…' : 'Run Scenario'}
              </button>
            </div>

            {scError && (
              <div style={{ marginTop: 12, color: '#fb7185', fontSize: 12 }}>{scError}</div>
            )}

            {scResult && (
              <div style={{ marginTop: 16 }}>
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 14 }}>
                  {[
                    ['Current balance', fmt(scResult.current_balance), 'var(--text-2)'],
                    ['After payment', fmt(scResult.balance_after), RISK_COLOR[scResult.risk_level]],
                    ['Headroom vs reserve', fmt(scResult.headroom), scResult.headroom >= 0 ? '#34d399' : '#fb7185'],
                  ].map(([label, val, color]) => (
                    <div key={label} style={{ padding: '10px 14px', background: 'rgba(255,255,255,.04)', borderRadius: 8, minWidth: 150 }}>
                      <div style={{ fontSize: 10.5, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 4 }}>{label}</div>
                      <div style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, fontSize: 15, color }}>{val}</div>
                    </div>
                  ))}
                  <div style={{ padding: '10px 14px', background: 'rgba(255,255,255,.04)', borderRadius: 8 }}>
                    <div style={{ fontSize: 10.5, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 4 }}>Decision</div>
                    <Badge
                      label={scResult.can_approve ? 'Approved' : 'Escalate'}
                      color={scResult.can_approve ? '#34d399' : '#fb7185'}
                      bg={scResult.can_approve ? 'rgba(52,211,153,.14)' : 'rgba(251,113,133,.14)'}
                    />
                  </div>
                </div>

                {scResult.analysis?.narrative && (
                  <div style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.7, padding: '12px 14px', background: 'rgba(103,232,249,.06)', borderLeft: '3px solid #67e8f9', borderRadius: '0 8px 8px 0', marginBottom: 12 }}>
                    {scResult.analysis.narrative}
                  </div>
                )}

                {scResult.analysis?.alternatives && Array.isArray(scResult.analysis.alternatives) && (
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 6 }}>Alternatives</div>
                    <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: 'var(--text-2)', lineHeight: 1.8 }}>
                      {scResult.analysis.alternatives.map((alt: string, i: number) => <li key={i}>{alt}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
