import React, { useState, useEffect, useMemo } from 'react'
import { Brain, ArrowRight, Zap, Info, Shield, Network, Activity, Database, TrendingUp, CheckCircle, AlertTriangle, UserCheck } from 'lucide-react'
import { motion, AnimatePresence } from 'motion/react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'

interface CausalLink {
  id: string
  cause_decision_id: string
  effect_decision_id: string
  relationship_type: string
  explanation: string
  created_at: string
  cause?: any
  effect?: any
}

// Fixed positions for the Agent Hub-and-Spoke Layout (Shared Financial State in Center)
const HUB_NODE = { id: 'state', label: 'Financial State', role: 'Event Hub', x: 50, y: 50, color: '#fff' }

const AGENT_NODES = [
  { id: 'invoice', label: 'Invoice', role: 'Outflows', x: 50, y: 15, color: '#67e8f9', icon: Zap },
  { id: 'budget', label: 'Budget', role: 'Variance', x: 82, y: 38, color: '#a78bfa', icon: Shield },
  { id: 'credit', label: 'Credit', role: 'Expectations', x: 70, y: 75, color: '#fb7185', icon: Activity },
  { id: 'reconciliation', label: 'Reconcile', role: 'Anomalies', x: 30, y: 75, color: '#fbbf24', icon: CheckCircle },
  { id: 'cash', label: 'Cash', role: 'Liquidity', x: 18, y: 38, color: '#22d3ee', icon: Database },
]

const normalize = (name: string) => {
  const n = (name || '').toLowerCase()
  if (n.includes('invoice')) return 'invoice'
  if (n.includes('budget')) return 'budget'
  if (n.includes('cash')) return 'cash'
  if (n.includes('reconciliation') || n.includes('reconcile')) return 'reconciliation'
  if (n.includes('credit')) return 'credit'
  return n
}

// Connections for the Hub model
const HUB_LINKS = AGENT_NODES.map(agent => ({ from: agent.id, to: 'state' }))

export default function IntelView() {
  const [links, setLinks] = useState<CausalLink[]>([])
  const [stats, setStats] = useState({ decisions: 0, links: 0, liquidity: 0, matches: 0 })
  const [forecastData, setForecastData] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [])

  const fetchData = async () => {
    try {
      const [gRes, sRes] = await Promise.all([
        fetch('/api/intel/causal-graph'),
        fetch('/api/intel')
      ])
      const graphData = await gRes.json()
      const summary = await sRes.json()

      const nodes = new Map(graphData.nodes.map((n: any) => [n.id, n]))
      const enrichedLinks = graphData.edges.map((e: any) => ({
        ...e,
        cause: nodes.get(e.cause_decision_id),
        effect: nodes.get(e.effect_decision_id)
      })).sort((a: any, b: any) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

      setLinks(enrichedLinks)
      setStats({
        decisions: summary.total_decisions,
        links: summary.total_causal_links,
        liquidity: summary.metrics?.liquidity_m || 0,
        matches: summary.metrics?.match_rate || 0
      })
      if (summary.forecast) {
        setForecastData(summary.forecast)
      }
      setLoading(false)
    } catch (err) {
      console.error('Failed to fetch intel data', err)
    }
  }

  const activeLinkKeys = useMemo(() => {
    const keys = new Set()
    links.slice(0, 8).forEach(l => {
      if (l.cause?.agent && l.effect?.agent) {
        const c = normalize(l.cause.agent)
        const e = normalize(l.effect.agent)
        keys.add(`${c}-${e}`)
        keys.add(`${e}-${c}`)
      }
    })
    return keys
  }, [links])

  const selectedLink = useMemo(() => links.find(l => l.id === selectedId), [links, selectedId])

  return (
    <div className="view intel-view-dark">
      <div className="view-header" style={{ marginBottom: '32px' }}>
        <div>
          <h2>Cognitive Intelligence Hub</h2>
          <p className="view-sub">Autonomous Orchestration · Causal Domain Reasoning · Status: Optimal</p>
        </div>
        <div style={{ display: 'flex', gap: '16px' }}>
          <div className="system-live">System Live</div>
          <div className="intel-pill">
            <Network size={12} />
            <span>{stats.links} Causal Handshakes</span>
          </div>
        </div>
      </div>

      {/* Top Metrics Row */}
      <div className="kpi-grid">
        <KPICard label="Operating Liquidity" val={`$${stats.liquidity}M`} sub="/ $60M Cap" progress={Math.min(100, Math.round((stats.liquidity / 60) * 100))} color="var(--emerald)" />
        <KPICard label="Matching Accuracy" val={`${stats.matches}%`} sub="Semantic Boost Active" progress={stats.matches} color="var(--cyan)" />
        <KPICard label="DSO Efficiency" val="41.2d" sub="Target: 38d" progress={68} color="var(--amber)" />
        <KPICard label="Agent Decisions" val={stats.decisions} sub="Total Cycles" progress={100} color="var(--violet)" />
      </div>

      <div className="intel-main-grid">
        {/* Agent Network (Left) */}
        <div className="panel network-panel card h-full overflow-hidden">
          <div className="panel-label">
            <Brain size={14} className="text-cyan" />
            <span>Agent Causal Network Graph</span>
          </div>
          <div className="graph-content">
            <svg viewBox="0 0 100 100" className="causal-svg" preserveAspectRatio="xMidYMid meet">
              <defs>
                <filter id="neon-glow" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="1.2" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
                <linearGradient id="link-grad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="rgba(34,211,238,0.1)" />
                  <stop offset="50%" stopColor="rgba(34,211,238,0.5)" />
                  <stop offset="100%" stopColor="rgba(34,211,238,0.1)" />
                </linearGradient>
                <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orientation="auto">
                  <polygon points="0 0, 10 3.5, 0 7" fill="var(--text-5)" opacity="0.5" />
                </marker>
                <marker id="arrowhead-coral" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orientation="auto">
                  <polygon points="0 0, 10 3.5, 0 7" fill="#fb7185" />
                </marker>
              </defs>

              {/* Hub-and-Spoke Links */}
              {AGENT_NODES.map((agent, i) => (
                <g key={`link-${agent.id}`}>
                  {/* Propagation Path */}
                  <path
                    d={`M ${agent.x} ${agent.y} L ${HUB_NODE.x} ${HUB_NODE.y}`}
                    className={`hub-line propagation ${activeLinkKeys.has(agent.id) ? 'active' : ''}`}
                    fill="none"
                    strokeDasharray={activeLinkKeys.has(agent.id) ? "none" : "2,2"}
                    stroke={agent.color}
                    opacity={activeLinkKeys.has(agent.id) ? 0.8 : 0.2}
                    strokeWidth="0.4"
                  />
                  {/* Data Flow Animation */}
                  <circle r="0.5" fill={agent.color}>
                    <animateMotion
                      dur={`${2 + i}s`}
                      repeatCount="indefinite"
                      path={`M ${agent.x} ${agent.y} L ${HUB_NODE.x} ${HUB_NODE.y}`}
                    />
                  </circle>
                </g>
              ))}

              {/* Cross-Domain Causal Chain: Recon -> Credit */}
              <path
                d="M 30 75 Q 50 88 70 75"
                fill="none"
                stroke="#fb7185"
                strokeWidth="0.6"
                strokeDasharray="3,2"
                markerEnd="url(#arrowhead-coral)"
                opacity="0.4"
              />
              <text x="50" y="86" textAnchor="middle" fill="#fb7185" style={{ fontSize: '1.8px', fontWeight: 600, opacity: 0.6 }}>Anomalies → Risk Adjustment</text>

              {/* Agent Nodes */}
              {AGENT_NODES.map((node) => {
                const IconComp = node.icon
                return (
                  <g key={node.id} transform={`translate(${node.x}, ${node.y})`}>
                    <motion.circle
                      r="6" fill="var(--bg-1)" stroke={node.color} strokeWidth="0.8"
                      initial={{ scale: 1 }}
                      whileHover={{ scale: 1.1, strokeWidth: 1.2 }}
                      style={{ cursor: 'pointer' }}
                    />
                    <circle r="6.5" fill="none" stroke={node.color} strokeWidth="0.2" opacity="0.2" />

                    <IconComp size={4} x="-2" y="-3.5" color={node.color} />

                    <text y="9" textAnchor="middle" className="node-text primary" fill="var(--text)">{node.label}</text>
                    <text y="11.5" textAnchor="middle" className="node-text secondary" fill="var(--text-4)">{node.role}</text>
                  </g>
                )
              })}

              {/* Hub Node (Shared Financial State) */}
              <g transform={`translate(${HUB_NODE.x}, ${HUB_NODE.y})`}>
                <rect x="-8" y="-8" width="16" height="16" rx="2" fill="rgba(255,255,255,0.03)" stroke="var(--border)" strokeWidth="0.5" />
                <Database size={8} x="-4" y="-5.5" color="var(--text-3)" />
                <text y="6" textAnchor="middle" className="node-text primary" fill="var(--text)" style={{ fontSize: '2.5px' }}>{HUB_NODE.label}</text>
                <text y="9" textAnchor="middle" className="node-text secondary" fill="var(--text-5)" style={{ fontSize: '1.5px' }}>{HUB_NODE.role}</text>
              </g>
            </svg>
          </div>
        </div>

        {/* Intelligence Right Column */}
        <div className="intel-right">
          {/* Liquidity Area Chart */}
          <div className="panel chart-panel card">
            <div className="panel-label">
              <TrendingUp size={12} />
              <span>13-Week Liquidity Forecast</span>
            </div>
            <div className="chart-val">${stats.liquidity}M <span className="trend">+2.4%</span></div>
            <div className="chart-container">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={forecastData}>
                  <defs>
                    <linearGradient id="chart-fill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--emerald)" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="var(--emerald)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Area type="monotone" dataKey="val" stroke="var(--emerald)" strokeWidth={2} fill="url(#chart-fill)" animationDuration={1500} />
                  <Tooltip
                    contentStyle={{ background: 'rgba(10,10,15,0.95)', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '12px' }}
                    itemStyle={{ color: 'var(--emerald)' }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Causal Stream */}
          <div className="panel stream-panel card">
            <div className="panel-label">
              <Activity size={12} />
              <span>Live Causal Event Stream</span>
            </div>
            <div className="stream-scroll">
              <AnimatePresence initial={false}>
                {links.length > 0 ? (
                  links.slice(0, 10).map((link) => {
                    const causeAgent = normalize(link.cause?.agent)
                    const effectAgent = normalize(link.effect?.agent)
                    const causeNode = AGENT_NODES.find(n => n.id === causeAgent)
                    const effectNode = AGENT_NODES.find(n => n.id === effectAgent)

                    return (
                      <motion.div
                        key={link.id}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        className={`stream-row ${selectedId === link.id ? 'active' : ''}`}
                        onClick={() => setSelectedId(link.id)}
                      >
                        <div className="stream-time">{new Date(link.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                        <div className="stream-path">
                          <span className="agent-orb" style={{ background: causeNode?.color || 'var(--text-4)' }} />
                          <ArrowRight size={10} className="opacity-40" />
                          <span className="agent-orb" style={{ background: effectNode?.color || 'var(--text-4)' }} />
                        </div>
                        <div className="stream-content">
                          <strong>{causeAgent}</strong> triggered <span>{link.relationship_type.replace(/_/g, ' ')}</span>
                        </div>
                      </motion.div>
                    )
                  })
                ) : (
                  <div className="empty-stream">Waiting for causal events...</div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>

      {/* Reasoning Modal / Overlay (If Selected) */}
      <AnimatePresence>
        {selectedLink && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="reasoning-overlay"
          >
            <div className="reasoning-card card">
              <button className="close-btn" onClick={() => setSelectedId(null)}>×</button>
              <div className="reasoning-header">
                <Brain size={20} className="text-cyan" />
                <h3>Causal Trace Evidence</h3>
              </div>
              <div className="reasoning-body">
                <div className="evidence-section">
                  <label>Chain Explanation</label>
                  <p>{selectedLink.explanation}</p>
                </div>
                <div className="evidence-meta">
                  <div className="meta-item">
                    <label>Relationship</label>
                    <div className="val">{selectedLink.relationship_type.replace(/_/g, ' ')}</div>
                  </div>
                  <div className="meta-item">
                    <label>Confidence</label>
                    <div className="val">99.8%</div>
                  </div>
                </div>
              </div>
              <div className="reasoning-footer">
                <Shield size={12} />
                <span>Verified Financial Intelligence Token: {selectedLink.id.substring(0, 12)}</span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <style>{`
        .intel-view-dark {
          height: 100%;
          display: flex;
          flex-direction: column;
          gap: 20px;
          padding-bottom: 20px;
        }
        .intel-pill {
          display: flex;
          align-items: center;
          gap: 8px;
          background: rgba(255,255,255,0.03);
          border: 1px solid var(--border);
          padding: 6px 14px;
          border-radius: 999px;
          font-size: 11px;
          color: var(--text-3);
          font-family: var(--font-mono);
        }
        .kpi-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 16px;
        }
        .kpi-card {
          padding: 20px;
          display: flex;
          align-items: center;
          gap: 18px;
          background: rgba(255,255,255,0.02);
        }
        .kpi-radial {
          position: relative;
          width: 52px;
          height: 52px;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .kpi-circle-bg {
          position: absolute;
          width: 100%;
          height: 100%;
        }
        .kpi-val-txt { font-size: 11px; font-weight: 700; font-family: var(--font-mono); z-index: 2; }
        .kpi-text label { font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-4); font-weight: 600; display: block; margin-bottom: 2px; }
        .kpi-text .val { font-size: 18px; font-weight: 600; color: var(--text); font-family: 'Space Grotesk', sans-serif; }
        .kpi-text .sub { font-size: 10px; color: var(--text-5); margin-top: 1px; }

        .intel-main-grid {
          flex: 1;
          display: grid;
          grid-template-columns: 1.3fr 1fr;
          gap: 20px;
          min-height: 0;
        }
        .panel { display: flex; flex-direction: column; min-height: 0; }
        .panel-label {
          font-size: 10px;
          text-transform: uppercase;
          color: var(--text-4);
          font-weight: 700;
          letter-spacing: 0.15em;
          margin-bottom: 16px;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .graph-content { flex: 1; display: flex; align-items: center; justify-content: center; position: relative; }
        .causal-svg { width: 100%; height: 100%; display: block; filter: drop-shadow(0 0 10px rgba(0,0,0,0.5)); }
        .hub-line { transition: all 0.5s ease; stroke-linecap: round; }
        .hub-line.active { filter: url(#neon-glow); stroke-width: 0.8; }
        .node-text.primary { font-size: 3.2px; font-weight: 700; font-family: 'Space Grotesk', sans-serif; }
        .node-text.secondary { font-size: 1.8px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.04em; }

        .intel-right { display: flex; flex-direction: column; gap: 20px; min-height: 0; }
        .chart-panel { height: 220px; flex-shrink: 0; padding: 24px; }
        .chart-val { font-size: 26px; font-weight: 600; margin-bottom: 12px; font-family: 'Space Grotesk', sans-serif; }
        .chart-val .trend { font-size: 12px; color: var(--emerald); font-weight: 700; margin-left: 8px; vertical-align: middle; }
        .chart-container { flex: 1; min-height: 0; }

        .stream-panel { flex: 1; display: flex; flex-direction: column; min-height: 0; padding: 24px; }
        .stream-scroll { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; margin-right: -10px; padding-right: 10px; }
        .stream-row {
          display: flex;
          align-items: center;
          gap: 14px;
          padding: 12px 16px;
          background: rgba(255,255,255,0.01);
          border: 1px solid rgba(255,255,255,0.03);
          border-radius: 12px;
          cursor: pointer;
          transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .stream-row:hover { background: rgba(255,255,255,0.03); border-color: rgba(255,255,255,0.1); }
        .stream-row.active { border-color: var(--cyan); background: rgba(34,211,238,0.08); box-shadow: 0 0 20px -5px rgba(34,211,238,0.2); }
        .stream-time { font-size: 10px; color: var(--text-5); width: 45px; font-family: var(--font-mono); }
        .stream-path { display: flex; align-items: center; gap: 8px; color: var(--text-4); }
        .agent-orb { width: 7px; height: 7px; border-radius: 50%; box-shadow: 0 0 10px currentColor; }
        .stream-content { font-size: 13px; color: var(--text-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .stream-content span { color: var(--cyan); font-weight: 700; text-transform: uppercase; font-size: 9px; letter-spacing: 0.05em; background: rgba(34,211,238,0.1); padding: 2px 6px; border-radius: 4px; margin-left: 4px; }
        
        .empty-stream { text-align: center; color: var(--text-5); font-size: 12px; margin-top: 40px; font-style: italic; }

        .reasoning-overlay {
          position: fixed;
          bottom: 30px;
          right: 30px;
          width: 380px;
          z-index: 100;
        }
        .reasoning-card {
          background: rgba(10, 14, 28, 0.98);
          backdrop-filter: blur(20px);
          border-color: var(--border-3);
          box-shadow: 0 40px 80px -20px rgba(0,0,0,0.9);
          padding: 24px;
        }
        .close-btn {
          position: absolute;
          top: 14px;
          right: 18px;
          background: none;
          border: none;
          color: var(--text-5);
          font-size: 22px;
          cursor: pointer;
          transition: color 0.2s;
        }
        .close-btn:hover { color: var(--text); }
        .reasoning-header { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
        .reasoning-header h3 { font-size: 17px; font-weight: 600; letter-spacing: -0.01em; }
        .evidence-section { margin-bottom: 24px; }
        .evidence-section label { display: block; font-size: 10px; text-transform: uppercase; color: var(--text-5); margin-bottom: 10px; font-weight: 700; letter-spacing: 0.12em; }
        .evidence-section p { font-size: 14px; color: var(--text-2); line-height: 1.6; }
        .evidence-meta { display: grid; grid-template-columns: 1.2fr 1fr; gap: 16px; margin-bottom: 24px; }
        .meta-item label { display: block; font-size: 9px; color: var(--text-5); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.05em; }
        .meta-item .val { font-size: 12px; color: var(--cyan); font-weight: 700; text-transform: capitalize; }
        .reasoning-footer { display: flex; align-items: center; gap: 8px; font-size: 10px; color: var(--text-5); border-top: 1px solid var(--border); padding-top: 20px; font-family: var(--font-mono); }
      `}</style>
    </div>
  )
}

function KPICard({ label, val, sub, progress, color }: any) {
  const radius = 22
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (progress / 100) * circumference

  return (
    <div className="kpi-card card">
      <div className="kpi-radial">
        <svg width="52" height="52" viewBox="0 0 52 52" style={{ transform: 'rotate(-90deg)' }}>
          <circle cx="26" cy="26" r={radius} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="3" />
          <motion.circle
            cx="26" cy="26" r={radius} fill="none" stroke={color} strokeWidth="3"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 1.5, ease: "easeOut" }}
            strokeLinecap="round"
          />
        </svg>
        <span className="kpi-val-txt" style={{ color }}>{progress}%</span>
      </div>
      <div className="kpi-text">
        <label>{label}</label>
        <div className="val">{val}</div>
        <div className="sub">{sub}</div>
      </div>
    </div>
  )
}
