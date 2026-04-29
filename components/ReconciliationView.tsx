import { useState, useEffect } from 'react'
import { RefreshCw } from 'lucide-react'
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts'
import { reconApi, ReconStats } from '../lib/api'
import { Card, Empty, pct } from './Shared'
import { useRealtime } from '../lib/useRealtime'

export default function ReconciliationView() {
  const [stats, setStats]     = useState<ReconStats | null>(null)
  const [report, setReport]   = useState<Record<string, unknown> | null>(null)
  const [running, setRunning] = useState(false)

  const load = () => {
    reconApi.stats().then(setStats)
    reconApi.report().then(r => {
      if (r && 'match_rate' in r) setReport(r as any)
    })
  }
  useEffect(() => { load() }, [])

  useRealtime('transactions', load)
  useRealtime('reconciliation_reports', load)

  async function runRecon() {
    setRunning(true)
    await reconApi.run()
    setTimeout(() => { load(); setRunning(false) }, 8000)
  }

  const pieData = stats ? [
    { name: 'Matched',   value: stats.matched,   fill: '#22c55e' },
    { name: 'Unmatched', value: stats.unmatched,  fill: '#f59e0b' },
  ] : []

  return (
    <div className="view">
      <div className="view-header">
        <div>
          <h2>Reconciliation</h2>
          <p className="view-sub">TF-IDF cosine similarity · threshold ≥ 0.85 · Qwen3 anomaly analysis</p>
        </div>
        <button className="btn-primary" onClick={runRecon} disabled={running}>
          <RefreshCw size={14} className={running ? 'spin' : ''} />
          {running ? 'Running…' : 'Run Reconciliation'}
        </button>
      </div>

      <div className="stats-row">
        <Card>
          <div className="stat-label">Match rate</div>
          <div className="stat-value" style={{ color: (stats?.match_rate_pct ?? 0) >= 90 ? '#22c55e' : '#f59e0b' }}>
            {stats ? pct(stats.match_rate_pct) : '—'}
          </div>
        </Card>
        <Card>
          <div className="stat-label">Matched pairs</div>
          <div className="stat-value">{stats?.matched ?? '—'}</div>
        </Card>
        <Card>
          <div className="stat-label">Unmatched</div>
          <div className="stat-value" style={{ color: (stats?.unmatched ?? 0) > 0 ? '#f59e0b' : '#22c55e' }}>
            {stats?.unmatched ?? '—'}
          </div>
        </Card>
        <Card>
          <div className="stat-label">Total transactions</div>
          <div className="stat-value">{stats?.total_transactions ?? '—'}</div>
        </Card>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Card>
          <h3 style={{ marginBottom: 12 }}>Match distribution</h3>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={55} outerRadius={80}
                  dataKey="value" label={({ name, value }: { name: string; value: number }) => `${name}: ${value}`} labelLine={false}>
                  {pieData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : <Empty msg="Run reconciliation to see results" />}
        </Card>

        <Card>
          <h3 style={{ marginBottom: 12 }}>Latest report</h3>
          {report ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[
                ['Period', String(report.period)],
                ['Match rate', `${Number(report.match_rate).toFixed(1)}%`],
                ['Matched', String(report.matched_count)],
                ['Unmatched', String(report.unmatched_count)],
                ['Generated', new Date(String(report.generated_at)).toLocaleString()],
              ].map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, borderBottom: '1px solid #f1f5f9', paddingBottom: 4 }}>
                  <span style={{ color: '#64748b' }}>{k}</span>
                  <span style={{ fontFamily: 'DM Mono, monospace', fontWeight: 500 }}>{v}</span>
                </div>
              ))}
            </div>
          ) : <Empty msg="No report yet" />}
        </Card>
      </div>
    </div>
  )
}
