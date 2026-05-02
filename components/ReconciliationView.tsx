import { useState, useEffect } from 'react'
import { RefreshCw, ChevronDown, ChevronUp, Info } from 'lucide-react'
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts'
import { reconApi, ReconStats, ReconReport } from '../lib/api'
import { Card, Empty, pct, AgentAvatar } from './Shared'
import { useRealtime } from '../lib/useRealtime'

export default function ReconciliationView() {
  const [stats, setStats]         = useState<ReconStats | null>(null)
  const [report, setReport]       = useState<ReconReport | null>(null)
  const [unmatched, setUnmatched] = useState<any[]>([])
  const [running, setRunning]     = useState(false)
  const [showInfo, setShowInfo]   = useState(false)

  const load = () => {
    reconApi.stats().then(setStats).catch(() => {})
    reconApi.report().then(r => { if (r && 'match_rate' in r) setReport(r) }).catch(() => {})
    reconApi.unmatched().then(setUnmatched).catch(() => {})
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
    { name: 'Matched',   value: stats.matched,  fill: '#34d399' },
    { name: 'Unmatched', value: stats.unmatched, fill: '#fbbf24' },
  ] : []

  const anomalyNarrative = (report as any)?.anomaly_summary || (report as any)?.causal_summary || null

  return (
    <div className="view">
      <div className="view-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <AgentAvatar agent="reconciliation" active={running} />
          <div>
            <h2>Reconciliation</h2>
            <p className="view-sub">TF-IDF cosine similarity · threshold ≥ 0.80 · Qwen3 anomaly analysis</p>
          </div>
        </div>
        <button className="btn-primary" onClick={runRecon} disabled={running}>
          <RefreshCw size={14} className={running ? 'spin' : ''} strokeWidth={2.5} />
          {running ? 'Running…' : 'Run Reconciliation'}
        </button>
      </div>

      {/* How it works info panel */}
      <div style={{ marginBottom: 18, border: '1px solid rgba(103,232,249,.15)', borderRadius: 10, overflow: 'hidden' }}>
        <button
          onClick={() => setShowInfo(v => !v)}
          style={{
            width: '100%', display: 'flex', alignItems: 'center', gap: 8,
            padding: '10px 16px', background: 'rgba(103,232,249,.05)',
            border: 'none', cursor: 'pointer', color: 'var(--text)',
          }}
        >
          <Info size={13} color="#67e8f9" />
          <span style={{ fontSize: 12, fontWeight: 600, flex: 1, textAlign: 'left', color: '#67e8f9' }}>How reconciliation works</span>
          {showInfo ? <ChevronUp size={13} color="var(--text-3)" /> : <ChevronDown size={13} color="var(--text-3)" />}
        </button>
        {showInfo && (
          <div style={{ padding: '14px 16px', fontSize: 12, color: 'var(--text-2)', lineHeight: 1.8, background: 'rgba(0,0,0,.15)' }}>
            <ol style={{ margin: 0, paddingLeft: 18 }}>
              <li>Fetches all <strong>unmatched transactions</strong> from both internal records and bank statements.</li>
              <li>Each transaction is converted to a text string: <em>amount + date + counterparty + description</em>.</li>
              <li>A <strong>TF-IDF vectorizer</strong> encodes all strings into numerical feature vectors.</li>
              <li>The agent computes a <strong>cosine similarity matrix</strong> (internal × bank). Pairs with similarity ≥ 0.80 are marked as <em>matched</em>.</li>
              <li>Transactions below the threshold become <strong>anomalies</strong> and are flagged for Qwen3 analysis.</li>
              <li>Qwen3 reads the anomaly list and produces a narrative explaining <em>whether a systematic pattern exists</em> (e.g. timing drift, duplicate entries, missing bank postings).</li>
              <li>If a systematic issue is found, the workflow escalates to the <strong>Credit Agent</strong> to check the relevant customer's payment behaviour.</li>
            </ol>
          </div>
        )}
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

      {/* Anomaly narrative — shown prominently after a run */}
      {anomalyNarrative && (
        <div style={{
          padding: '14px 18px', background: 'rgba(251,191,36,.06)',
          border: '1px solid rgba(251,191,36,.2)', borderRadius: 10, marginBottom: 16,
        }}>
          <div style={{ fontSize: 11, color: '#fbbf24', textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 6, fontWeight: 600 }}>
            Qwen3 Anomaly Analysis
          </div>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--text-2)', lineHeight: 1.7 }}>{anomalyNarrative}</p>
        </div>
      )}

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

      {/* Unmatched transactions table */}
      {unmatched.length > 0 && (
        <Card style={{ marginTop: 16 }}>
          <h3 style={{ marginBottom: 14 }}>Unmatched Transactions ({unmatched.length})</h3>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Date</th>
                  <th>Counterparty</th>
                  <th>Description</th>
                  <th style={{ textAlign: 'right' }}>Amount</th>
                  <th style={{ textAlign: 'right' }}>Similarity</th>
                </tr>
              </thead>
              <tbody>
                {unmatched.map((tx: any) => (
                  <tr key={tx.id}>
                    <td>
                      <span style={{
                        fontSize: 10, padding: '2px 7px', borderRadius: 4, fontWeight: 600,
                        background: tx.source === 'bank' ? 'rgba(167,139,250,.15)' : 'rgba(34,211,238,.12)',
                        color: tx.source === 'bank' ? '#a78bfa' : '#67e8f9',
                        textTransform: 'uppercase', letterSpacing: '.06em',
                      }}>
                        {tx.source ?? '—'}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}>{tx.date ?? '—'}</td>
                    <td style={{ fontSize: 12 }}>{tx.counterparty ?? tx.counterparty_id ?? '—'}</td>
                    <td style={{ fontSize: 12, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{tx.description ?? '—'}</td>
                    <td style={{ textAlign: 'right', fontFamily: 'JetBrains Mono, monospace', fontWeight: 500 }}>
                      ${Number(tx.amount ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td style={{ textAlign: 'right', fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}>
                      {tx.sim_score != null ? (
                        <span style={{ color: Number(tx.sim_score) >= 0.6 ? '#fbbf24' : '#fb7185' }}>
                          {(Number(tx.sim_score) * 100).toFixed(0)}%
                        </span>
                      ) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
