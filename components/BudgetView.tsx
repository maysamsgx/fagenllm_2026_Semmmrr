import { useState, useEffect } from 'react'
import { AlertTriangle, RefreshCw, ChevronDown, ChevronUp, FlaskConical } from 'lucide-react'
import { budgetApi, Budget, BudgetAlert, WhatIfResult } from '../lib/api'
import { Card, Badge, Spinner, fmt, pct, AgentAvatar } from './Shared'
import { useRealtime } from '../lib/useRealtime'

const RISK_COLOR: Record<string, string> = {
  low: '#34d399', medium: '#fbbf24', high: '#f97316', critical: '#fb7185',
}

export default function BudgetView() {
  const [budgets, setBudgets]     = useState<Budget[]>([])
  const [alerts, setAlerts]       = useState<BudgetAlert[]>([])
  const [periods, setPeriods]     = useState<string[]>([])
  const [period, setPeriod]       = useState<string>('')
  const [running, setRunning]     = useState(false)
  const [showWhatIf, setShowWhatIf] = useState(false)
  const [wiDept, setWiDept]       = useState('')
  const [wiAmount, setWiAmount]   = useState('')
  const [wiLoading, setWiLoading] = useState(false)
  const [wiResult, setWiResult]   = useState<WhatIfResult | null>(null)
  const [wiError, setWiError]     = useState('')

  useEffect(() => {
    budgetApi.periods().then(({ periods, current }) => {
      setPeriods(periods)
      const sel = periods.includes(current) ? current : periods[0] ?? ''
      setPeriod(sel)
    }).catch(() => {})
  }, [])

  const load = () => {
    if (!period) return
    budgetApi.list(period).then(setBudgets).catch(() => {})
    budgetApi.alerts().then(setAlerts).catch(() => {})
  }

  useEffect(() => { if (!period) return; load() }, [period])

  useRealtime('budgets', load)
  useRealtime('budget_alerts', load)

  const runWhatIf = async () => {
    const amt = parseFloat(wiAmount)
    if (!wiDept || isNaN(amt) || amt <= 0) { setWiError('Select a department and enter a valid amount.'); return }
    setWiError('')
    setWiLoading(true)
    setWiResult(null)
    try {
      const res = await budgetApi.whatif(wiDept, amt, period || undefined)
      setWiResult(res)
    } catch (e) {
      setWiError(`Error: ${e}`)
    } finally {
      setWiLoading(false)
    }
  }

  return (
    <div className="view">
      <div className="view-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <AgentAvatar agent="budget" active={running} />
          <div>
            <h2>Budget Management</h2>
            <p className="view-sub">Spend tracking · variance alerts · moving-average forecast</p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          {periods.length > 0 && (
            <select value={period} onChange={(e) => setPeriod(e.target.value)} className="period-select" aria-label="Budget period">
              {periods.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          )}
          <button
            className="btn-primary"
            disabled={running}
            onClick={async () => {
              setRunning(true)
              try { await budgetApi.run(period) } catch (e) { alert(`Run failed: ${e}`) }
              setTimeout(() => { load(); setRunning(false) }, 5000)
            }}
          >
            <RefreshCw size={14} className={running ? 'spin' : ''} strokeWidth={2.5} />
            {running ? 'Reviewing…' : 'Run Budget Review'}
          </button>
        </div>
      </div>

      {alerts.length > 0 && (
        <div style={{ marginBottom: 18 }}>
          {alerts.map((a: BudgetAlert) => (
            <div key={a.id} className="alert-banner">
              <AlertTriangle size={16} strokeWidth={2.5} />
              <span><strong style={{ textTransform: 'capitalize' }}>{a.department}</strong> · {a.alert_type.replace('_', ' ')} · {pct(a.utilisation_pct)} utilised</span>
              <span style={{ flex: 1, fontSize: 12, color: 'rgba(253, 230, 138, .7)' }}>{a.message?.slice(0, 80)}…</span>
              <button className="btn-sm" onClick={() => budgetApi.ack(a.id).then(load)}>Dismiss</button>
            </div>
          ))}
        </div>
      )}

      <div className="budget-grid">
        {budgets.map((b: Budget) => {
          const util  = b.utilisation_pct ?? ((b.spent + b.committed) / b.allocated * 100)
          const color = util >= 95 ? '#fb7185' : util >= 85 ? '#fbbf24' : '#34d399'
          const bg    = util >= 95 ? 'rgba(251,113,133,.14)' : util >= 85 ? 'rgba(251,191,36,.14)' : 'rgba(52,211,153,.14)'
          return (
            <Card key={b.id}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 14 }}>
                <div style={{ fontWeight: 600, textTransform: 'capitalize', fontSize: 14, color: 'var(--text)' }}>{b.department}</div>
                <Badge label={`${util.toFixed(0)}%`} color={color} bg={bg} />
              </div>
              <div style={{ height: 6, background: 'rgba(255,255,255,.05)', borderRadius: 999, marginBottom: 16, overflow: 'hidden' }}>
                <div style={{
                  width: `${Math.min(util, 100)}%`, height: '100%',
                  background: `linear-gradient(90deg, ${color}, ${color}cc)`, borderRadius: 999,
                  transition: 'width 0.8s cubic-bezier(.16, 1, .3, 1)', boxShadow: `0 0 12px ${color}80`,
                }} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, fontSize: 12 }}>
                {[['Allocated', fmt(b.allocated), 'var(--text-2)'], ['Spent', fmt(b.spent), 'var(--text-2)'], ['Committed', fmt(b.committed), 'var(--text-2)'], ['Remaining', fmt(b.allocated - b.spent - b.committed), color]].map(([label, val, c]) => (
                  <div key={label}>
                    <div style={{ color: 'var(--text-4)', fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '.06em' }}>{label}</div>
                    <div style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 500, color: c, marginTop: 2 }}>{val}</div>
                  </div>
                ))}
              </div>
            </Card>
          )
        })}
      </div>

      {/* What-If Scenario */}
      <div style={{ marginTop: 24, border: '1px solid rgba(255,255,255,.08)', borderRadius: 12, overflow: 'hidden' }}>
        <button
          onClick={() => setShowWhatIf(v => !v)}
          style={{
            width: '100%', display: 'flex', alignItems: 'center', gap: 10,
            padding: '14px 18px', background: 'rgba(255,255,255,.03)',
            border: 'none', cursor: 'pointer', color: 'var(--text)',
          }}
        >
          <FlaskConical size={15} color="#a78bfa" />
          <span style={{ fontWeight: 600, fontSize: 13, flex: 1, textAlign: 'left' }}>What-If Scenario</span>
          <span style={{ fontSize: 11, color: 'var(--text-4)', marginRight: 6 }}>
            Simulate budget impact before submitting an invoice
          </span>
          {showWhatIf ? <ChevronUp size={14} color="var(--text-3)" /> : <ChevronDown size={14} color="var(--text-3)" />}
        </button>

        {showWhatIf && (
          <div style={{ padding: '18px', background: 'rgba(0,0,0,.15)' }}>
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-4)', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '.06em' }}>Department</div>
                <select
                  value={wiDept}
                  onChange={e => { setWiDept(e.target.value); setWiResult(null) }}
                  style={{
                    background: 'rgba(255,255,255,.06)', border: '1px solid rgba(255,255,255,.12)',
                    borderRadius: 6, padding: '6px 10px', fontSize: 12, color: 'var(--text)', outline: 'none',
                  }}
                >
                  <option value="">Select…</option>
                  {budgets.map(b => <option key={b.id} value={b.department ?? b.id}>{b.department}</option>)}
                </select>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-4)', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '.06em' }}>Invoice Amount ($)</div>
                <input
                  type="number" min="1" step="100"
                  value={wiAmount}
                  onChange={e => { setWiAmount(e.target.value); setWiResult(null) }}
                  placeholder="e.g. 5000"
                  style={{
                    background: 'rgba(255,255,255,.06)', border: '1px solid rgba(255,255,255,.12)',
                    borderRadius: 6, padding: '6px 10px', fontSize: 12, color: 'var(--text)',
                    outline: 'none', width: 140,
                  }}
                />
              </div>
              <button
                className="btn-primary"
                disabled={wiLoading}
                onClick={runWhatIf}
                style={{ minWidth: 120 }}
              >
                {wiLoading ? <Spinner /> : <FlaskConical size={13} />}
                {wiLoading ? 'Analysing…' : 'Run Scenario'}
              </button>
            </div>

            {wiError && (
              <div style={{ marginTop: 12, color: '#fb7185', fontSize: 12 }}>{wiError}</div>
            )}

            {wiResult && (
              <div style={{ marginTop: 16 }}>
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 14 }}>
                  {[
                    ['Current utilisation', `${wiResult.current_utilisation_pct.toFixed(1)}%`, 'var(--text-2)'],
                    ['After approval', `${wiResult.hypothetical_utilisation_pct.toFixed(1)}%`, RISK_COLOR[wiResult.risk_level]],
                    ['Remaining budget', fmt(wiResult.remaining_after), wiResult.remaining_after <= 0 ? '#fb7185' : '#34d399'],
                  ].map(([label, val, color]) => (
                    <div key={label} style={{ padding: '10px 14px', background: 'rgba(255,255,255,.04)', borderRadius: 8, minWidth: 140 }}>
                      <div style={{ fontSize: 10.5, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 4 }}>{label}</div>
                      <div style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, fontSize: 16, color }}>{val}</div>
                    </div>
                  ))}
                  <div style={{ padding: '10px 14px', background: 'rgba(255,255,255,.04)', borderRadius: 8 }}>
                    <div style={{ fontSize: 10.5, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 4 }}>Risk level</div>
                    <Badge
                      label={wiResult.will_hard_stop ? 'Hard Stop' : wiResult.risk_level}
                      color={RISK_COLOR[wiResult.risk_level]}
                      bg={RISK_COLOR[wiResult.risk_level] + '22'}
                    />
                  </div>
                </div>

                {wiResult.analysis?.narrative && (
                  <div style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.7, padding: '12px 14px', background: 'rgba(167,139,250,.06)', borderLeft: '3px solid #a78bfa', borderRadius: '0 8px 8px 0', marginBottom: 12 }}>
                    {wiResult.analysis.narrative}
                  </div>
                )}

                {wiResult.analysis?.alternatives && Array.isArray(wiResult.analysis.alternatives) && (
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 6 }}>Alternatives</div>
                    <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: 'var(--text-2)', lineHeight: 1.8 }}>
                      {wiResult.analysis.alternatives.map((alt: string, i: number) => <li key={i}>{alt}</li>)}
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
