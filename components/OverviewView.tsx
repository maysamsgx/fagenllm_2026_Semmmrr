import React from 'react'

const AGENTS = [
  { id: 'invoice',        label: 'Invoice Agent',        desc: '3-Layer OCR Pipeline · 3-way matching · Autonomous approval routing', color: '#67e8f9', icon: '/assets/agents/invoice.png' },
  { id: 'cash',           label: 'Cash Flow Agent',       desc: 'Liquidity defense · AR forecasting · Zero-value state handling',      color: '#22d3ee', icon: '/assets/agents/cash.png' },
  { id: 'budget',         label: 'Budget Agent',          desc: 'Real-time spend control · Variance analysis · Threshold enforcement',       color: '#a78bfa', icon: '/assets/agents/budget.png' },
  { id: 'reconciliation', label: 'Reconciliation Agent',  desc: 'Temporal pattern recognition · Discrepancy detection · Root cause analysis',     color: '#fbbf24', icon: '/assets/agents/reconciliation.png' },
  { id: 'credit',         label: 'Credit Agent',          desc: 'Dynamic risk scoring · Aging analysis · Collection automation',          color: '#fb7185', icon: '/assets/agents/credit.png' },
]

const UPDATES = [
  { tag: 'NEW', title: '3-Layer Resilient OCR', desc: 'Cascading document ingestion via PyMuPDF, Baidu Qianfan Cloud, and local Tesseract fallback.' },
  { tag: 'RESILIENCE', title: 'Auto-Failover LLM & Self-Correction', desc: 'Automatic model fallbacks (Qwen3 → GPT) on API limits, and Pydantic recursive JSON self-correction loops.' },
  { tag: 'CORE', title: 'Cross-Domain Causal Engine', desc: 'Reconciliation anomalies autonomously trigger Credit risk reassessments and Cash flow discounts.' },
  { tag: 'UI', title: 'Forensic Trace Architecture', desc: 'Distinct layers for Technical, Business, and Causal reasoning with extracted liquidity metrics.' },
]

export default function OverviewView() {
  return (
    <div className="view">
      <div className="view-header" style={{ marginBottom: '32px' }}>
        <div>
          <h2>Cognitive Intelligence Hub</h2>
          <p className="view-sub">FAgentLLM · Real-time Multi-Agent Orchestration</p>
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: '8px',
          background: 'rgba(52,211,153,.1)', border: '1px solid rgba(52,211,153,.25)',
          borderRadius: '999px', padding: '8px 16px',
          fontSize: '12px', color: '#34d399', fontWeight: 600,
          boxShadow: '0 0 20px rgba(52,211,153,.1)'
        }}>
          <span className="pulse-dot" style={{ width: 8, height: 8, borderRadius: '50%', background: '#34d399', boxShadow: '0 0 10px #34d399', display: 'inline-block' }} />
          All Agents Operational
        </div>
      </div>

      {/* Hero Vision Statement */}
      <div style={{
        textAlign: 'center', padding: '56px 24px', marginBottom: '40px',
        background: 'linear-gradient(135deg, rgba(34,211,238,.05) 0%, rgba(167,139,250,.05) 100%)',
        border: '1px solid rgba(255,255,255,.05)', borderRadius: '24px',
        backdropFilter: 'blur(20px)',
        position: 'relative', overflow: 'hidden',
        boxShadow: '0 20px 40px rgba(0,0,0,.2) inset, 0 1px 0 rgba(255,255,255,.1) inset',
      }}>
        {/* Ambient glow */}
        <div style={{
          position: 'absolute', top: '-100px', left: '50%', transform: 'translateX(-50%)',
          width: '600px', height: '300px',
          background: 'radial-gradient(ellipse, rgba(34,211,238,.15) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
        
        <p style={{ fontSize: '11px', letterSpacing: '0.25em', color: 'var(--text-4)', textTransform: 'uppercase', fontFamily: "'Space Grotesk', sans-serif", marginBottom: '20px', fontWeight: 700 }}>
          Design Science Research Artifact · v1.2
        </p>
        <h1 style={{
          fontFamily: "'Instrument Serif', serif", fontSize: 'clamp(36px, 5vw, 64px)',
          fontWeight: 400, letterSpacing: '-0.03em', lineHeight: 1.1,
          background: 'linear-gradient(135deg, #ffffff 0%, #67e8f9 50%, #a78bfa 100%)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          backgroundClip: 'text', marginBottom: '24px',
        }}>
          FAgentLLM
        </h1>
        <p style={{
          fontFamily: "'Cormorant Garamond', serif", fontSize: 'clamp(18px, 2.5vw, 32px)',
          fontStyle: 'italic', color: 'var(--text-2)', letterSpacing: '0.01em',
          lineHeight: 1.4, maxWidth: '650px', margin: '0 auto 28px',
        }}>
          Five Agents, One Vision:<br />
          <span style={{ color: '#67e8f9', textShadow: '0 0 20px rgba(103,232,249,.3)' }}>Smarter Finance, Better Decisions.</span>
        </p>
        <p style={{ fontSize: '14px', color: 'var(--text-3)', maxWidth: '580px', margin: '0 auto', lineHeight: 1.8, fontWeight: 400 }}>
          A unified multi-agent architecture overcoming fragmented enterprise finance operations through autonomous orchestration, cross-domain causal reasoning, and explainable decision-making.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '32px', marginBottom: '40px' }}>
        {/* Five Agents Grid */}
        <div style={{ flex: 2 }}>
          <h3 style={{ marginBottom: '20px', color: 'var(--text-3)', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.14em', fontFamily: "'Space Grotesk', sans-serif", borderBottom: '1px solid rgba(255,255,255,.05)', paddingBottom: '12px' }}>
            Agent Roster
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
            {AGENTS.map((agent, i) => (
              <div key={agent.id} className="card" style={{
                display: 'flex', alignItems: 'flex-start', gap: '16px',
                background: 'rgba(255,255,255,.02)',
                border: `1px solid ${agent.color}22`,
                transition: 'all .3s ease',
                animationDelay: `${i * 50}ms`,
              }}>
                <div style={{
                  width: '48px', height: '48px', borderRadius: '14px', flexShrink: 0,
                  background: `linear-gradient(135deg, ${agent.color}22 0%, transparent 100%)`, 
                  border: `1px solid ${agent.color}33`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  boxShadow: `inset 0 1px 0 rgba(255,255,255,.1)`,
                }}>
                  <img src={agent.icon} alt={agent.label} style={{ width: '28px', height: '28px', objectFit: 'contain', filter: 'drop-shadow(0 2px 4px rgba(0,0,0,.5))' }}
                    onError={(e) => { e.currentTarget.style.display = 'none' }} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: '#fff', fontFamily: "'Space Grotesk', sans-serif", marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {agent.label}
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: agent.color, opacity: 0.8 }} />
                  </div>
                  <div style={{ fontSize: '12.5px', color: 'var(--text-4)', lineHeight: 1.5 }}>
                    {agent.desc}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Latest Architecture Updates */}
        <div style={{ flex: 1, minWidth: '300px' }}>
           <h3 style={{ marginBottom: '20px', color: 'var(--text-3)', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.14em', fontFamily: "'Space Grotesk', sans-serif", borderBottom: '1px solid rgba(255,255,255,.05)', paddingBottom: '12px' }}>
            Latest Architecture Updates
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {UPDATES.map((update, i) => (
               <div key={i} style={{
                 padding: '16px', background: 'rgba(0,0,0,.2)', border: '1px solid rgba(255,255,255,.04)',
                 borderRadius: '16px', display: 'flex', flexDirection: 'column', gap: '8px'
               }}>
                 <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '0.1em', background: 'rgba(167,139,250,.15)', color: '#a78bfa', padding: '2px 8px', borderRadius: '4px' }}>
                      {update.tag}
                    </span>
                    <span style={{ fontSize: '13.5px', fontWeight: 600, color: 'var(--text-1)' }}>{update.title}</span>
                 </div>
                 <p style={{ fontSize: '12.5px', color: 'var(--text-4)', lineHeight: 1.5, margin: 0 }}>{update.desc}</p>
               </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tech Stack Footer */}
      <div style={{
        marginTop: '20px', display: 'flex', flexWrap: 'wrap', gap: '12px', justifyContent: 'center',
        padding: '24px',
        background: 'rgba(0,0,0,.15)', border: '1px solid rgba(255,255,255,.03)',
        borderRadius: '20px',
      }}>
        {['LangGraph', 'Qwen3-32B', 'Supabase Vector', 'FastAPI', 'Baidu OCR', 'Tesseract', 'PyMuPDF', 'React 18', 'XAI Causal Engine'].map(tech => (
          <span key={tech} style={{
            fontSize: '11px', padding: '6px 16px',
            background: 'rgba(255,255,255,.03)', border: '1px solid rgba(255,255,255,.08)',
            borderRadius: '999px', color: 'var(--text-3)', fontWeight: 500,
            fontFamily: "'JetBrains Mono', monospace", letterSpacing: '0.02em',
            boxShadow: 'inset 0 1px 0 rgba(255,255,255,.05)'
          }}>
            {tech}
          </span>
        ))}
      </div>
    </div>
  )
}
