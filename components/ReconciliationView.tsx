import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, ChevronDown, ChevronUp, Info, Brain } from 'lucide-react'
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend } from 'recharts'
import { reconApi, analyticsApi, ReconStats, ReconReport } from '../lib/api'
import { Card, Empty, pct, AgentAvatar } from './Shared'
import { useRealtime } from '../lib/useRealtime'
import TracePanel from './TracePanel'

export default function ReconciliationView() {
  const [stats, setStats]         = useState<ReconStats | null>(null)
  const [report, setReport]       = useState<ReconReport | null>(null)
  const [unmatched, setUnmatched] = useState<any[]>([])
  const [running, setRunning]     = useState(false)
  const [showInfo, setShowInfo]   = useState(false)
  const [viewMode, setViewMode]   = useState<'operations' | 'dashboard'>('operations')
  const [dashboardData, setDashboardData] = useState<any[]>([])
  const [traceId, setTraceId]             = useState<string | null>(null)
  const [selectedTx, setSelectedTx]       = useState<any | null>(null)

  const load = useCallback(() => {
    reconApi.stats().then(setStats).catch(console.error)
    reconApi.report().then(r => { 
      if (r && typeof r === 'object' && 'match_rate' in r) setReport(r as ReconReport) 
    }).catch(console.error)
    reconApi.unmatched().then(setUnmatched).catch(console.error)
    analyticsApi.reconciliation().then(setDashboardData).catch(console.error)
  }, [])

  useEffect(() => { load() }, [load])

  useRealtime('transactions', load)
  useRealtime('reconciliation_reports', load)

  async function runRecon() {
    setRunning(true)
    try { 
      await reconApi.run() 
      // Polling fallback (v3.1): Increase duration to 60s to handle cold-starts/large batches
      let attempts = 0
      const poll = setInterval(() => {
        load()
        attempts++
        if (attempts >= 30) {
          clearInterval(poll)
          setRunning(false)
        }
      }, 2000)
      
      // Safety release
      setTimeout(() => {
        clearInterval(poll)
        setRunning(false)
        load()
      }, 65000)
    } catch (e) { 
      alert(`Run failed: ${e}`) 
      setRunning(false)
    }
  }

  async function handleResolve(action: 'match' | 'escalate') {
    if (!selectedTx) return
    try {
      await reconApi.resolve(selectedTx.id, action)
      setSelectedTx(null)
      load()
    } catch (e) {
      alert(`Resolution failed: ${e}`)
    }
  }

  const pieData = stats ? [
    { name: 'Matched',   value: stats.matched,  fill: '#34d399' },
    { name: 'Unmatched', value: stats.unmatched, fill: '#fbbf24' },
  ] : []

  const anomalyNarrative = (report as any)?.anomaly_summary || (report as any)?.causal_summary || null

  return (
    <div className="view">
      {traceId && <TracePanel entityId={traceId} entityType="reconciliation" onClose={() => setTraceId(null)} />}
      <div className="view-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <AgentAvatar agent="reconciliation" active={running} />
          <div>
            <h2>Reconciliation</h2>
            <p className="view-sub">TF-IDF (≥0.80) + Semantic MiniLM (≥0.75) · Qwen3 anomaly analysis</p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <div className="toggle-group" style={{ display: 'flex', background: 'rgba(0,0,0,0.2)', padding: '4px', borderRadius: '8px' }}>
            <button
              style={{ padding: '6px 14px', borderRadius: '6px', border: 'none', background: viewMode === 'operations' ? 'rgba(103,232,249,0.15)' : 'transparent', color: viewMode === 'operations' ? '#67e8f9' : 'var(--text-3)', cursor: 'pointer', fontSize: '13px', fontWeight: 600, transition: 'all 0.2s' }}
              onClick={() => setViewMode('operations')}
            >Operations</button>
            <button
              style={{ padding: '6px 14px', borderRadius: '6px', border: 'none', background: viewMode === 'dashboard' ? 'rgba(103,232,249,0.15)' : 'transparent', color: viewMode === 'dashboard' ? '#67e8f9' : 'var(--text-3)', cursor: 'pointer', fontSize: '13px', fontWeight: 600, transition: 'all 0.2s' }}
              onClick={() => setViewMode('dashboard')}
            >Analytics</button>
          </div>
          <button className="btn-primary" onClick={runRecon} disabled={running}>
            <RefreshCw size={14} className={running ? 'spin' : ''} strokeWidth={2.5} />
            {running ? 'Running…' : 'Run Reconciliation'}
          </button>
        </div>
      </div>

      {viewMode === 'operations' ? (
        <>
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
                  <li>Pairs below the TF-IDF threshold are re-scored via <strong>Semantic Matching</strong> — MiniLM sentence embeddings (<em>all-MiniLM-L6-v2</em>) produce a second similarity score. The best of TF-IDF or semantic wins; pairs reaching ≥ 0.75 semantically are promoted to <em>matched</em>.</li>
                  <li>Transactions below <em>both</em> thresholds become <strong>anomalies</strong> and are flagged for Qwen3 analysis.</li>
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
              <div style={{ fontSize: 10, color: 'var(--text-4)', marginTop: -4 }}>System Accuracy</div>
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
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
                <h3 style={{ margin: 0 }}>Latest report</h3>
                {report && (
                  <button className="btn-sm" onClick={() => setTraceId(report.id)}>
                    <Brain size={11} /> Trace
                  </button>
                )}
              </div>
              {report ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {[
                    ['Period', String(report.period)],
                    ['System rate', `${Number(report.match_rate).toFixed(1)}%`],
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
                <table className="table" style={{ borderCollapse: 'separate', borderSpacing: '0 8px', marginTop: -8 }}>
                  <thead>
                    <tr>
                      <th style={{ background: 'transparent', border: 'none' }}>Source</th>
                      <th style={{ background: 'transparent', border: 'none' }}>Date</th>
                      <th style={{ background: 'transparent', border: 'none' }}>Counterparty</th>
                      <th style={{ background: 'transparent', border: 'none' }}>Description</th>
                      <th style={{ background: 'transparent', border: 'none', textAlign: 'right' }}>Amount</th>
                      <th style={{ background: 'transparent', border: 'none', textAlign: 'right' }}>Similarity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {unmatched.map((tx: any) => (
                      <tr key={tx.id} className="table-row-hover" style={{ background: 'rgba(255,255,255,0.02)', borderRadius: 8 }}>
                        <td style={{ padding: '12px 18px', borderTopLeftRadius: 8, borderBottomLeftRadius: 8 }}>
                          <span style={{
                            fontSize: 10, padding: '3px 8px', borderRadius: 6, fontWeight: 700,
                            background: tx.source === 'bank' ? 'rgba(167,139,250,.15)' : 'rgba(34,211,238,.12)',
                            color: tx.source === 'bank' ? '#a78bfa' : '#67e8f9',
                            textTransform: 'uppercase', letterSpacing: '.06em',
                            border: `1px solid ${tx.source === 'bank' ? 'rgba(167,139,250,.2)' : 'rgba(34,211,238,.2)'}`
                          }}>
                            {tx.source ?? '—'}
                          </span>
                        </td>
                        <td style={{ padding: '12px 18px', fontFamily: 'JetBrains Mono, monospace', fontSize: 12, color: 'var(--text-2)' }}>{tx.transaction_date ?? tx.date ?? '—'}</td>
                        <td style={{ padding: '12px 18px', fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>{tx.counterparty ?? tx.counterparty_id ?? '—'}</td>
                        <td style={{ padding: '12px 18px', fontSize: 12, color: 'var(--text-3)', maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {tx.description ?? '—'}
                        </td>
                        <td style={{ padding: '12px 18px', textAlign: 'right', fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, color: 'var(--text)' }}>
                          ${Number(tx.amount ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </td>
                        <td style={{ padding: '12px 18px', textAlign: 'right', borderTopRightRadius: 8, borderBottomRightRadius: 8 }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 12 }}>
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
                              <span style={{
                                fontFamily: 'JetBrains Mono, monospace',
                                fontSize: 12,
                                fontWeight: 700,
                                color: (tx.match_score || tx.sim_score) != null && Number(tx.match_score || tx.sim_score) >= 0.6 ? '#fbbf24' : '#fb7185'
                              }}>
                                {(Number(tx.match_score || tx.sim_score || 0) * 100).toFixed(0)}%
                              </span>
                              <div style={{ width: 60, height: 3, background: 'rgba(255,255,255,0.05)', borderRadius: 2, overflow: 'hidden' }}>
                                <div style={{
                                  width: `${Math.min(100, Number(tx.match_score || tx.sim_score || 0) * 100)}%`,
                                  height: '100%',
                                  background: (tx.match_score || tx.sim_score) != null && Number(tx.match_score || tx.sim_score) >= 0.6 ? '#fbbf24' : '#fb7185',
                                  boxShadow: `0 0 8px ${(tx.match_score || tx.sim_score) != null && Number(tx.match_score || tx.sim_score) >= 0.6 ? 'rgba(251,191,36,0.4)' : 'rgba(251,113,133,0.4)'}`
                                }} />
                              </div>
                            </div>
                            <button 
                              className="btn-sm" 
                              style={{ background: 'rgba(103,232,249,0.1)', color: '#67e8f9', padding: '4px 8px' }}
                              onClick={() => setSelectedTx(tx)}
                            >
                              Resolve
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Executive Analytics Row */}
          <div className="stats-row">
            <Card style={{ background: 'linear-gradient(135deg, rgba(52, 211, 153, 0.05) 0%, transparent 100%)' }}>
              <div className="stat-label">System Match Accuracy</div>
              <div className="stat-value" style={{ color: '#34d399', display: 'flex', alignItems: 'baseline', gap: 6 }}>
                {dashboardData.length > 0 ? pct(dashboardData[dashboardData.length - 1].match_rate) : '—'}
                <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-4)' }}>Current</span>
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-4)', marginTop: 4 }}>
                Avg: {dashboardData.length > 0 ? (dashboardData.reduce((acc, curr) => acc + curr.match_rate, 0) / dashboardData.length).toFixed(1) : 0}%
              </div>
            </Card>
            <Card style={{ background: 'linear-gradient(135deg, rgba(251, 113, 133, 0.05) 0%, transparent 100%)' }}>
              <div className="stat-label">Exposure Under Review</div>
              <div className="stat-value" style={{ color: '#fb7185' }}>
                {dashboardData.length > 0 ? dashboardData[dashboardData.length - 1].unmatched_count : 0}
                <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-4)', marginLeft: 6 }}>Anomalies</span>
              </div>
            </Card>
            <Card>
              <div className="stat-label">Autonomous Throughput</div>
              <div className="stat-value" style={{ color: '#67e8f9' }}>
                {dashboardData.reduce((acc, curr) => acc + curr.matched_count, 0)}
                <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-4)', marginLeft: 6 }}>Total Matches</span>
              </div>
            </Card>
            <Card>
              <div className="stat-label">Cognitive Audit Depth</div>
              <div className="stat-value" style={{ fontSize: 20 }}>Forensic</div>
            </Card>
          </div>

          <div className="diagnostic-grid">
            <Card className="diagnostic-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                <h3 style={{ margin: 0, fontSize: 14 }}>Accuracy Progression</h3>
                <span style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>TF-IDF + Semantic</span>
              </div>
              {dashboardData.length > 0 ? (
                <div style={{ height: 320 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={dashboardData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                      <XAxis 
                        dataKey="generated_at" 
                        stroke="var(--text-4)" 
                        fontSize={9} 
                        tickLine={false} 
                        axisLine={false}
                        tickFormatter={(str) => {
                          const d = new Date(str);
                          return `${d.getMonth()+1}/${d.getDate()} ${d.getHours()}:${d.getMinutes().toString().padStart(2, '0')}`;
                        }}
                      />
                      <YAxis stroke="var(--text-4)" fontSize={10} tickLine={false} axisLine={false} domain={[0, 100]} />
                      <Tooltip 
                        contentStyle={{ background: 'rgba(13, 18, 38, 0.95)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 11 }}
                        itemStyle={{ color: '#34d399' }}
                      />
                      <Line 
                        type="monotone" 
                        dataKey="match_rate" 
                        stroke="#34d399" 
                        strokeWidth={3} 
                        dot={{ r: 4, fill: '#34d399', strokeWidth: 2, stroke: '#0d1226' }}
                        activeDot={{ r: 6, strokeWidth: 0 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : <Empty msg="Insufficient data for trend analysis" />}
            </Card>

            <Card className="diagnostic-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                <h3 style={{ margin: 0, fontSize: 14 }}>Anomaly Density</h3>
                <span style={{ fontSize: 10, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Unmatched Counts</span>
              </div>
              {dashboardData.length > 0 ? (
                <div style={{ height: 320 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={dashboardData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                      <XAxis 
                        dataKey="generated_at" 
                        stroke="var(--text-4)" 
                        fontSize={9} 
                        tickLine={false} 
                        axisLine={false}
                        tickFormatter={(str) => {
                          const d = new Date(str);
                          return `${d.getMonth()+1}/${d.getDate()} ${d.getHours()}:${d.getMinutes().toString().padStart(2, '0')}`;
                        }}
                      />
                      <YAxis stroke="var(--text-4)" fontSize={10} tickLine={false} axisLine={false} />
                      <Tooltip 
                        contentStyle={{ background: 'rgba(13, 18, 38, 0.95)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 11 }}
                        cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                      />
                      <Bar dataKey="unmatched_count" fill="rgba(251, 191, 36, 0.4)" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : <Empty msg="Insufficient data for density analysis" />}
            </Card>
          </div>

          {/* Forensic Intelligence Panel */}
          {dashboardData.length > 0 && dashboardData[dashboardData.length - 1].narrative && (
            <div className="forensic-narrative">
              <div className="forensic-title">
                <Brain size={14} /> AI Forensic Intelligence — {dashboardData[dashboardData.length - 1].period} Report
              </div>
              <div className="forensic-text">
                {dashboardData[dashboardData.length - 1].narrative}
              </div>
              <div style={{ marginTop: 14, display: 'flex', gap: 12 }}>
                <button 
                  className="btn-sm" 
                  onClick={() => setTraceId(dashboardData[dashboardData.length - 1].id)}
                  style={{ background: 'rgba(103, 232, 249, 0.1)', color: '#67e8f9', border: '1px solid rgba(103, 232, 249, 0.2)' }}
                >
                  View Full Reasoning Trace
                </button>
              </div>
            </div>
          )}
        </div>
      )}
      {selectedTx && (
        <div className="modal-overlay">
          <Card className="modal-content" style={{ maxWidth: 500 }}>
            <h3 style={{ marginBottom: 16 }}>Dispute Resolution</h3>
            <p style={{ fontSize: 13, color: 'var(--text-3)', marginBottom: 20 }}>
              Transaction ID: <code style={{ color: '#67e8f9' }}>{selectedTx.id}</code><br/>
              Counterparty: <strong>{selectedTx.counterparty}</strong><br/>
              Amount: <strong>${selectedTx.amount?.toLocaleString()}</strong>
            </p>
            
            <div style={{ background: 'rgba(0,0,0,0.2)', padding: 12, borderRadius: 8, marginBottom: 20 }}>
              <div style={{ fontSize: 11, color: 'var(--text-4)', textTransform: 'uppercase', marginBottom: 6 }}>AI Reasoning</div>
              <p style={{ margin: 0, fontSize: 12, color: 'var(--text-2)' }}>
                Similarity score of <strong>{(selectedTx.match_score || selectedTx.sim_score || 0 * 100).toFixed(0)}%</strong> via {selectedTx.match_type || 'TF-IDF'}. 
                Manual stakeholder intervention required due to policy threshold (0.80).
              </p>
            </div>

            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
              <button className="btn-secondary" onClick={() => setSelectedTx(null)}>Cancel</button>
              <button className="btn-secondary" style={{ color: '#fb7185' }} onClick={() => handleResolve('escalate')}>Escalate to Audit</button>
              <button className="btn-primary" onClick={() => handleResolve('match')}>Force Match</button>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
