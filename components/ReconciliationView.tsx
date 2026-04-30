import { useState, useEffect } from 'react'
import { RefreshCw } from 'lucide-react'
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts'
import { reconApi, ReconStats } from '../lib/api'
import { Card, Empty, pct, AgentAvatar } from './Shared'
import { useRealtime } from '../lib/useRealtime'

export default function ReconciliationView() {
  const [stats, setStats]     = useState<ReconStats | null>(null)
  const [report, setReport]   = useState<Record<string, unknown> | null>(null)
  const [running, setRunning] = useState(false)

  const load = () => {
    reconApi.stats().then(setStats).catch(() => {})
    reconApi.report().then(r => {
      if (r && 'match_rate' in r) setReport(r as any)
    }).catch(() => {})
  }
  useEffect(() => { load() }, [])

  useRealtime('transactions', load)
  useRealtime('reconciliation_reports', load)

  async function runRecon() {
    setRunning(true)
    try { await reconApi.run() } catch (e) { alert(`Run failed: ${e}`) }
    setTimeout(() => { load(); setRunning(false) }, 8000)
  }

  const pieData = stats ? [
    { name: 'Matched',   value: stats.matched,   fill: '#34d399' },
    { name: 'Unmatched', value: stats.unmatched,  fill: '#fbbf24' },
  ] : []

  return (
    <div className="view">
      <div className="view-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <AgentAvatar agent="reconciliation" active={running} />
          <div>
            <h2>Reconciliation</h2>
            <p className="view-sub">TF-IDF cosine similarity · threshold ≥ 0.85 · Qwen3 anomaly analysis</p>
          </div>
        </div>
        <button className="btn-primary" onClick={runRecon} disabled={running}>
          <RefreshCw size={14} className={running ? 'spin' : ''} strokeWidth={2.5} />
          {running ? 'Running…' : 'Run Reconciliation'}
        </button>
      </div>

      <div className="stats-row">
        <Card>
          <div className="stat-label">Match rate</div>
          <div className="stat-value" style={{ color: (stats?.match_rate_pct ?? 0) >= 90 ? '#34d399' : '#fbbf24' }}>
            {stats ? pct(stats.match_rate_pct) : '—'}
          </div>
        </Card>
        <Card>
          <div className="stat-label">Matched pairs</div>
          <div className="stat-value">{stats?.matched ?? '—'}</div>
        </Card>
        <Card>
          <div className="stat-label">Unmatched</div>
          <div className="stat-value" style={{ color: (stats?.unmatched ?? 0) > 0 ? '#fbbf24' : '#34d399' }}>
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
          <h3 style={{ marginBottom: 14 }}>Match distribution</h3>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={88}
                  dataKey="value" stroke="rgba(0,0,0,.4)" strokeWidth={2}
                  label={({ name, value }: { name: string; value: number }) => `${name}: ${value}`} labelLine={false}>
                  {pieData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : <Empty msg="Run reconciliation to see results" />}
        </Card>

        <Card>
          <h3 style={{ marginBottom: 14 }}>Latest report</h3>
          {report ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {[
                ['Period', String(report.period)],
                ['Match rate', `${Number(report.match_rate).toFixed(1)}%`],
                ['Matched', String(report.matched_count)],
                ['Unmatched', String(report.unmatched_count)],
                ['Generated', new Date(String(report.generated_at)).toLocaleString()],
              ].map(([k, v]) => (
                <div key={k} className="kv-row">
                  <span className="kv-key">{k}</span>
                  <span className="kv-val">{v}</span>
                </div>
              ))}
            </div>
          ) : <Empty msg="No report yet" />}
        </Card>
      </div>
    </div>
  )
}
