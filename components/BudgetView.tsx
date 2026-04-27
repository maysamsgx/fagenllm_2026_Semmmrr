import { useState, useEffect } from 'react'
import { AlertTriangle } from 'lucide-react'
import { budgetApi, Budget, BudgetAlert } from '../lib/api'
import { Card, Badge, fmt, pct } from './Shared'

export default function BudgetView() {
  const [budgets, setBudgets] = useState<Budget[]>([])
  const [alerts, setAlerts]   = useState<BudgetAlert[]>([])
  const [periods, setPeriods] = useState<string[]>([])
  const [period, setPeriod]   = useState<string>('')

  useEffect(() => {
    budgetApi.periods().then(({ periods, current }) => {
      setPeriods(periods)
      setPeriod(periods.includes(current) ? current : periods[0] ?? '')
    })
  }, [])

  const load = () => {
    if (!period) return
    budgetApi.list(period).then(setBudgets)
    budgetApi.alerts().then(setAlerts)
  }

  useEffect(() => {
    if (!period) return
    load()
    const t = setInterval(load, 8000)
    return () => clearInterval(t)
  }, [period])

  return (
    <div className="view">
      <div className="view-header">
        <div>
          <h2>Budget Management</h2>
          <p className="view-sub">Spend tracking · variance alerts · moving-average forecast</p>
        </div>
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
      </div>

      {alerts.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          {alerts.map((a: BudgetAlert) => (
            <div key={a.id} className="alert-banner">
              <AlertTriangle size={16} />
              <span><strong>{a.department}</strong> · {a.alert_type.replace('_', ' ')} · {pct(a.utilisation_pct)} utilised</span>
              <span style={{ flex: 1, fontSize: 12, color: '#92400e' }}>{a.message?.slice(0, 80)}…</span>
              <button className="btn-sm" onClick={() => budgetApi.ack(a.id).then(load)}>Dismiss</button>
            </div>
          ))}
        </div>
      )}

      <div className="budget-grid">
        {budgets.map((b: Budget) => {
          const util = b.utilisation_pct ?? ((b.spent + b.committed) / b.allocated * 100)
          const color = util >= 95 ? '#ef4444' : util >= 85 ? '#f59e0b' : '#22c55e'
          return (
            <Card key={b.id}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                <div style={{ fontWeight: 600, textTransform: 'capitalize' }}>{b.department}</div>
                <Badge label={`${util.toFixed(0)}%`} color={color} bg={color + '22'} />
              </div>
              <div style={{ height: 8, background: '#e2e8f0', borderRadius: 4, marginBottom: 12 }}>
                <div style={{ width: `${Math.min(util, 100)}%`, height: '100%',
                  background: color, borderRadius: 4, transition: 'width 0.5s' }} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 12 }}>
                <div><div style={{ color: '#64748b' }}>Allocated</div>
                     <div style={{ fontFamily: 'DM Mono', fontWeight: 500 }}>{fmt(b.allocated)}</div></div>
                <div><div style={{ color: '#64748b' }}>Spent</div>
                     <div style={{ fontFamily: 'DM Mono', fontWeight: 500 }}>{fmt(b.spent)}</div></div>
                <div><div style={{ color: '#64748b' }}>Committed</div>
                     <div style={{ fontFamily: 'DM Mono', fontWeight: 500 }}>{fmt(b.committed)}</div></div>
                <div><div style={{ color: '#64748b' }}>Remaining</div>
                     <div style={{ fontFamily: 'DM Mono', fontWeight: 500, color: color }}>
                       {fmt(b.allocated - b.spent - b.committed)}</div></div>
              </div>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
