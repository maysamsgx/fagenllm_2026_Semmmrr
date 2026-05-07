import React from 'react'

const AGENTS = [
  { id: 'invoice',        label: 'Invoice Agent',        desc: 'OCR extraction · 3-way matching · autonomous approval workflow', color: '#67e8f9', icon: '/assets/agents/invoice.png' },
  { id: 'cash',           label: 'Cash Flow Agent',       desc: 'Liquidity forecasting · anomaly gating · real-time alerts',      color: '#22d3ee', icon: '/assets/agents/cash.png' },
  { id: 'budget',         label: 'Budget Agent',          desc: 'Spend control · variance analysis · threshold enforcement',       color: '#a78bfa', icon: '/assets/agents/budget.png' },
  { id: 'reconciliation', label: 'Reconciliation Agent',  desc: 'TF-IDF matching · discrepancy detection · audit escalation',     color: '#fbbf24', icon: '/assets/agents/reconciliation.png' },
  { id: 'credit',         label: 'Credit Agent',          desc: 'Risk scoring · aging analysis · collection automation',          color: '#fb7185', icon: '/assets/agents/credit.png' },
]

export default function OverviewView() {
  return (
    <div className="view">
      <div className="view-header">
        <div>
          <h2>System Overview</h2>
          <p className="view-sub">FAgentLLM · Five Agents, One Vision · Status: Online</p>
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: '8px',
          background: 'rgba(52,211,153,.1)', border: '1px solid rgba(52,211,153,.25)',
          borderRadius: '999px', padding: '8px 16px',
          fontSize: '12px', color: '#34d399', fontWeight: 600
        }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#34d399', boxShadow: '0 0 8px #34d399', display: 'inline-block' }} />
          All Agents Operational
        </div>
      </div>

      {/* Hero Vision Statement */}
      <div style={{
        textAlign: 'center', padding: '48px 24px', marginBottom: '40px',
        background: 'linear-gradient(135deg, rgba(34,211,238,.04) 0%, rgba(167,139,250,.04) 100%)',
        border: '1px solid rgba(34,211,238,.12)', borderRadius: '20px',
        backdropFilter: 'blur(20px)',
        position: 'relative', overflow: 'hidden',
      }}>
        {/* Ambient glow */}
        <div style={{
          position: 'absolute', top: '-60px', left: '50%', transform: 'translateX(-50%)',
          width: '400px', height: '200px',
          background: 'radial-gradient(ellipse, rgba(34,211,238,.15) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
        <p style={{ fontSize: '12px', letterSpacing: '0.2em', color: 'var(--text-4)', textTransform: 'uppercase', fontFamily: "'Space Grotesk', sans-serif", marginBottom: '16px', fontWeight: 600 }}>
          Design Science Research Artifact · v1.0
        </p>
        <h1 style={{
          fontFamily: "'Instrument Serif', serif", fontSize: 'clamp(28px, 4vw, 52px)',
          fontWeight: 400, letterSpacing: '-0.03em', lineHeight: 1.15,
          background: 'linear-gradient(135deg, #f5f7ff 0%, #67e8f9 50%, #a78bfa 100%)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          backgroundClip: 'text', marginBottom: '20px',
        }}>
          FAgentLLM
        </h1>
        <p style={{
          fontFamily: "'Cormorant Garamond', serif", fontSize: 'clamp(16px, 2.5vw, 28px)',
          fontStyle: 'italic', color: 'var(--text-2)', letterSpacing: '0.01em',
          lineHeight: 1.4, maxWidth: '600px', margin: '0 auto 24px',
        }}>
          Five Agents, One Vision:<br />
          <span style={{ color: 'var(--cyan)' }}>Smarter Finance, Better Decisions.</span>
        </p>
        <p style={{ fontSize: '13.5px', color: 'var(--text-3)', maxWidth: '520px', margin: '0 auto', lineHeight: 1.7 }}>
          A unified multi-agent LLM architecture that overcomes fragmented enterprise finance operations through autonomous AI orchestration, causal reasoning, and explainable decision-making.
        </p>
      </div>

      {/* Five Agents Grid */}
      <div style={{ marginBottom: '16px' }}>
        <h3 style={{ marginBottom: '20px', color: 'var(--text-3)', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.14em', fontFamily: "'Space Grotesk', sans-serif" }}>
          The Five Agents
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '14px' }}>
          {AGENTS.map((agent, i) => (
            <div key={agent.id} className="card" style={{
              display: 'flex', alignItems: 'flex-start', gap: '16px',
              borderColor: `${agent.color}22`,
              transition: 'all .3s',
              animationDelay: `${i * 80}ms`,
            }}>
              <div style={{
                width: '44px', height: '44px', borderRadius: '12px', flexShrink: 0,
                background: `${agent.color}18`, border: `1px solid ${agent.color}33`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: `0 0 20px ${agent.color}22`,
              }}>
                <img src={agent.icon} alt={agent.label} style={{ width: '28px', height: '28px', objectFit: 'contain' }}
                  onError={(e) => { e.currentTarget.style.display = 'none' }} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: '13.5px', fontWeight: 600, color: agent.color, fontFamily: "'Space Grotesk', sans-serif", marginBottom: '5px' }}>
                  {agent.label}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-4)', lineHeight: 1.55 }}>
                  {agent.desc}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Tech Stack Footer */}
      <div style={{
        marginTop: '32px', display: 'flex', flexWrap: 'wrap', gap: '10px',
        padding: '20px 24px',
        background: 'rgba(255,255,255,.02)', border: '1px solid var(--border)',
        borderRadius: '14px',
      }}>
        {['LangGraph', 'Qwen3-32B', 'Supabase', 'FastAPI', 'Baidu OCR', 'TF-IDF Matching', 'XAI Causal Engine'].map(tech => (
          <span key={tech} style={{
            fontSize: '11px', padding: '4px 12px',
            background: 'rgba(34,211,238,.07)', border: '1px solid rgba(34,211,238,.18)',
            borderRadius: '999px', color: 'var(--cyan-soft)', fontWeight: 500,
            fontFamily: "'JetBrains Mono', monospace", letterSpacing: '0.01em',
          }}>
            {tech}
          </span>
        ))}
      </div>
    </div>
  )
}
