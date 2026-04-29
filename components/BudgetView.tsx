import { useState, useEffect } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { budgetApi, Budget, BudgetAlert } from '../lib/api'
import { Card, Badge, fmt, pct } from './Shared'
import { useRealtime } from '../lib/useRealtime'

export default function BudgetView() {
  const [budgets, setBudgets] = useState<Budget[]>([])
  const [alerts, setAlerts]   = useState<BudgetAlert[]>([])
  const [periods, setPeriods] = useState<string[]>([])
  const [period, setPeriod]   = useState<string>('')
  const [running, setRunning] = useState(false)

  useEffect(() => {
    budgetApi.periods().then(({ periods, current }) => {
      setPeriods(periods)
      setPeriod(periods.includes(current) ? current : periods[0] ?? '')
    }).catch(() => {})
  }, [])

  const load = () => {
    if (!period) return
    budgetApi.list(period).then(setBudgets).catch(() => {})
    budgetApi.alerts().then(setAlerts).catch(() => {})
  }

  useEffect(() => {
    if (!period) return
    load()
  }, [period])

  useRealtime('budgets', load)
  useRealtime('budget_alerts', load)

  return (
    <div className="view">
      <div className="view-header">
        <div>
          <h2>Budget Management</h2>
          <p className="view-sub">Spend tracking · variance alerts · moving-average forecast</p>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          {periods.length > 0 && (
            <select
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className="period-select"
              aria-label="Budget period"
            >
              {periods.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
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
          const util = b.utilisation_pct ?? ((b.spent + b.committed) / b.allocated * 100)
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
                  width: `${Math.min(util, 100)}%`,
                  height: '100%',
                  background: `linear-gradient(90deg, ${color}, ${color}cc)`,
                  borderRadius: 999,
                  transition: 'width 0.8s cubic-bezier(.16, 1, .3, 1)',
                  boxShadow: `0 0 12px ${color}80`,
                }} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, fontSize: 12 }}>
                <div>
                  <div style={{ color: 'var(--text-4)', fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '.06em' }}>Allocated</div>
                  <div style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 500, color: 'var(--text-2)', marginTop: 2 }}>{fmt(b.allocated)}</div>
                </div>
                <div>
                  <div style={{ color: 'var(--text-4)', fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '.06em' }}>Spent</div>
                  <div style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 500, color: 'var(--text-2)', marginTop: 2 }}>{fmt(b.spent)}</div>
                </div>
                <div>
                  <div style={{ color: 'var(--text-4)', fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '.06em' }}>Committed</div>
                  <div style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 500, color: 'var(--text-2)', marginTop: 2 }}>{fmt(b.committed)}</div>
                </div>
                <div>
                  <div style={{ color: 'var(--text-4)', fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '.06em' }}>Remaining</div>
                  <div style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 500, color, marginTop: 2 }}>{fmt(b.allocated - b.spent - b.committed)}</div>
                </div>
              </div>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
