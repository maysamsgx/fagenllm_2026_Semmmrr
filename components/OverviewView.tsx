import React, { useState } from 'react'

const AGENTS = [
  { id: 'invoice',        label: 'Invoice Agent',        desc: 'Autonomously extracts data via 3-Layer OCR, enforces 3-way matching, and routes approvals globally.', color: '#67e8f9', icon: '/assets/agents/invoice.png' },
  { id: 'cash',           label: 'Cash Flow Agent',       desc: 'The ultimate liquidity defense. Projects 7-day cash flows and dynamically discounts AR based on real-time risk.',      color: '#22d3ee', icon: '/assets/agents/cash.png' },
  { id: 'budget',         label: 'Budget Agent',          desc: 'A real-time financial gatekeeper. Blocks excess spend and analyzes variance before cash leaves the system.',       color: '#a78bfa', icon: '/assets/agents/budget.png' },
  { id: 'reconciliation', label: 'Reconciliation Agent',  desc: 'Forensic anomaly detection. Maps transactional patterns to find root causes of cross-ledger discrepancies.',     color: '#fbbf24', icon: '/assets/agents/reconciliation.png' },
  { id: 'credit',         label: 'Credit Agent',          desc: 'Dynamic risk evaluation. Adjusts credit limits based on behavioral aging and cross-domain reconciliation penalties.',          color: '#fb7185', icon: '/assets/agents/credit.png' },
]

const UPDATES = [
  { tag: 'V3.2', title: 'Multi-Tiered OCR Pipeline', desc: 'Implemented cascading document ingestion. Defaults to PyMuPDF, escalating to Baidu Qianfan Cloud APIs, with a local Tesseract failover.' },
  { tag: 'CORE', title: 'LLM Failover Protocol', desc: 'Introduced automatic model routing. Inference shifts from primary Qwen3 nodes to GPT endpoints during rate limits. Includes recursive Pydantic schema-enforcement.' },
  { tag: 'XAI', title: 'Causal Graph Execution', desc: 'Reconciliation discrepancies now write directly to the causal event bus, automatically triggering deterministic credit reassessments and cash flow discount logic.' },
  { tag: 'UI', title: 'Forensic Tracing System', desc: 'Added granular inspection UI. Execution layers (Technical, Business, Causal) are now isolated, exposing raw JSON responses and latency metrics.' },
]

// 3D Tilt Card Component
function TiltCard({ agent, index, onNavigate }: { agent: typeof AGENTS[0], index: number, onNavigate?: (id: string) => void }) {
  const [rot, setRot] = useState({ x: 0, y: 0 })
  const [isHovered, setIsHovered] = useState(false)

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!e.currentTarget) return
    const rect = e.currentTarget.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    const centerX = rect.width / 2
    const centerY = rect.height / 2
    const rotateX = ((y - centerY) / centerY) * -10 // Max 10deg
    const rotateY = ((x - centerX) / centerX) * 10
    setRot({ x: rotateX, y: rotateY })
  }

  const handleMouseLeave = () => {
    setRot({ x: 0, y: 0 })
    setIsHovered(false)
  }

  const btnText = agent.id === 'invoice' ? 'Inspect Pipeline' : 
                  agent.id === 'cash' ? 'Analyze Liquidity' : 
                  agent.id === 'budget' ? 'Manage Caps' :
                  agent.id === 'reconciliation' ? 'Audit Ledgers' : 'Review Risk';

  return (
    <div
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={handleMouseLeave}
      style={{
        perspective: '1000px',
        animationDelay: `${index * 50}ms`,
        animation: 'fadeInUp 0.6s ease both',
        height: '100%',
        cursor: 'default',
        position: 'relative',
        zIndex: isHovered ? 10 : 1
      }}
    >
      <div
        className="card"
        style={{
          display: 'flex', flexDirection: 'column', gap: '20px',
          padding: '24px', height: '100%',
          background: 'rgba(10,10,10,0.8)',
          backdropFilter: 'blur(10px)',
          border: `1px solid rgba(255,255,255,0.1)`,
          borderRadius: '24px',
          transformStyle: 'preserve-3d',
          transition: isHovered ? 'none' : 'transform 0.5s cubic-bezier(0.25, 1, 0.5, 1), box-shadow 0.5s',
          transform: `rotateX(${rot.x}deg) rotateY(${rot.y}deg) ${isHovered ? 'scale3d(1.02, 1.02, 1.02)' : ''}`,
          boxShadow: isHovered ? `0 30px 60px -12px rgba(0,0,0,0.8), 0 0 30px ${agent.color}15` : `0 10px 30px -10px rgba(0,0,0,0.5)`,
        }}
      >
        {/* Header: Title, Description and Status */}
        <div style={{ transform: isHovered ? 'translateZ(30px)' : 'translateZ(0)', transition: 'transform 0.3s cubic-bezier(0.25, 1, 0.5, 1)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
            <div style={{ fontSize: '20px', fontWeight: 700, color: '#fff', fontFamily: "'Space Grotesk', sans-serif", letterSpacing: '-0.02em' }}>
              {agent.label}
            </div>
            <div style={{
              display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 10px', 
              borderRadius: '999px', background: `${agent.color}15`, border: `1px solid ${agent.color}33`, 
              color: agent.color, fontSize: '10px', fontWeight: 700, letterSpacing: '0.05em'
            }}>
              <span className="pulse-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: agent.color, boxShadow: `0 0 10px ${agent.color}` }} />
              ACTIVE
            </div>
          </div>
          <div style={{ fontSize: '13px', color: 'rgba(255,255,255,0.5)', lineHeight: 1.5, paddingRight: '20px' }}>
            {agent.desc}
          </div>
        </div>

        {/* Center Piece: Holographic Pod (Breakout Effect) */}
        <div style={{
          position: 'relative', width: '100%', height: '140px', borderRadius: '16px', flexShrink: 0,
          background: `rgba(20,20,20,0.4)`, 
          border: `1px solid rgba(255,255,255,0.05)`,
          display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
          boxShadow: `inset 0 0 40px rgba(0,0,0,0.5)`,
          transform: isHovered ? 'translateZ(50px)' : 'translateZ(0)',
          transition: 'transform 0.3s cubic-bezier(0.25, 1, 0.5, 1)',
          marginTop: '40px', // Space for the avatar's head to break out
        }}>
          {/* Inner container with hidden overflow for the grid/glow only */}
          <div style={{ position: 'absolute', inset: 0, borderRadius: '16px', overflow: 'hidden', zIndex: 0 }}>
            {/* Subtle Grid Background */}
            <div style={{ 
              position: 'absolute', inset: 0, 
              backgroundImage: `linear-gradient(to right, rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.03) 1px, transparent 1px)`, 
              backgroundSize: '14px 24px' 
            }} />
            
            {/* Glow Behind Mascot */}
            <div style={{ position: 'absolute', inset: 0, background: `radial-gradient(circle at center, ${agent.color}15 0%, transparent 70%)` }} />
          </div>

          <img src={agent.icon} alt={agent.label} style={{ 
            width: agent.id === 'invoice' ? '85%' : 'auto', 
            height: agent.id === 'invoice' ? 'auto' : '170px', 
            maxHeight: '170px',
            objectFit: 'contain', 
            filter: `drop-shadow(0 15px 25px ${agent.color}44)`, 
            position: 'relative', zIndex: 2,
            marginBottom: '-5px' // Anchors image to bottom, letting the top overflow
          }} onError={(e) => { e.currentTarget.style.display = 'none' }} />
        </div>

        {/* Footer Actions */}
        <div style={{
          display: 'flex', gap: '12px', marginTop: 'auto',
          transform: isHovered ? 'translateZ(20px)' : 'translateZ(0)', transition: 'transform 0.3s cubic-bezier(0.25, 1, 0.5, 1)'
        }}>
          <button onClick={() => onNavigate && onNavigate(agent.id)} style={{
            flex: 1, padding: '12px 0', background: `linear-gradient(135deg, ${agent.color}dd 0%, ${agent.color} 100%)`, border: 'none',
            color: '#000', borderRadius: '12px', fontSize: '13px', fontWeight: 700, cursor: 'pointer', fontFamily: "'Space Grotesk', sans-serif",
            display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '6px',
            boxShadow: `0 4px 15px ${agent.color}44`
          }}>
            {btnText} →
          </button>
        </div>
      </div>
    </div>
  )
}

export default function OverviewView({ onNavigate }: { onNavigate?: (id: string) => void }) {
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
        textAlign: 'center', padding: '56px 24px', marginBottom: '48px',
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

      <div style={{ display: 'flex', flexDirection: 'column', gap: '48px', marginBottom: '40px' }}>
        
        {/* Agent Roster */}
        <div>
          <h3 style={{ marginBottom: '24px', color: 'var(--text-3)', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.14em', fontFamily: "'Space Grotesk', sans-serif", borderBottom: '1px solid rgba(255,255,255,.05)', paddingBottom: '12px' }}>
            Agent Roster
          </h3>
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', 
            gap: '24px'
          }}>
            {AGENTS.map((agent, i) => (
              <TiltCard key={agent.id} agent={agent} index={i} onNavigate={onNavigate} />
            ))}
          </div>
        </div>

        {/* Latest Architecture Updates */}
        <div>
           <h3 style={{ marginBottom: '24px', color: 'var(--text-3)', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.14em', fontFamily: "'Space Grotesk', sans-serif", borderBottom: '1px solid rgba(255,255,255,.05)', paddingBottom: '12px' }}>
            Latest Architecture Updates
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px' }}>
            {UPDATES.map((update, i) => (
               <div key={i} style={{
                 padding: '24px', background: 'rgba(0,0,0,.2)', border: '1px solid rgba(255,255,255,.04)',
                 borderRadius: '20px', display: 'flex', flexDirection: 'column', gap: '12px',
                 boxShadow: '0 4px 10px rgba(0,0,0,0.2)'
               }}>
                 <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.1em', background: 'rgba(167,139,250,.15)', color: '#a78bfa', padding: '4px 10px', borderRadius: '6px' }}>
                      {update.tag}
                    </span>
                    <span style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-1)' }}>{update.title}</span>
                 </div>
                 <p style={{ fontSize: '14px', color: 'var(--text-4)', lineHeight: 1.6, margin: 0 }}>{update.desc}</p>
               </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tech Stack & System Capabilities */}
      <div style={{
        marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '24px',
        padding: '32px',
        background: 'rgba(0,0,0,.3)', border: '1px solid rgba(255,255,255,.05)',
        borderRadius: '24px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', borderBottom: '1px solid rgba(255,255,255,.05)', paddingBottom: '16px' }}>
          <h3 style={{ margin: 0, color: 'var(--text-3)', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.14em', fontFamily: "'Space Grotesk', sans-serif" }}>
            System Architecture & Tool Stack
          </h3>
        </div>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '32px' }}>
          <div>
            <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.4)', marginBottom: '12px', letterSpacing: '0.05em', fontFamily: "'JetBrains Mono', monospace" }}>ORCHESTRATION</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <span className="tech-badge">LangGraph Stateful DAG</span>
              <span className="tech-badge">FastAPI Async Backend</span>
              <span className="tech-badge">Pydantic Validation</span>
              <span className="tech-badge">XAI Causal Engine</span>
            </div>
          </div>
          <div>
            <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.4)', marginBottom: '12px', letterSpacing: '0.05em', fontFamily: "'JetBrains Mono', monospace" }}>COGNITIVE LAYER</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <span className="tech-badge">Qwen3-32B Inference</span>
              <span className="tech-badge">GPT OSS-20b Fallback</span>
              <span className="tech-badge">Recursive Self-Correction</span>
              <span className="tech-badge">Multi-Agent Routing</span>
            </div>
          </div>
          <div>
            <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.4)', marginBottom: '12px', letterSpacing: '0.05em', fontFamily: "'JetBrains Mono', monospace" }}>DATA INGESTION</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <span className="tech-badge">Baidu Qianfan Cloud OCR</span>
              <span className="tech-badge">PyMuPDF Document Parsing</span>
              <span className="tech-badge">Tesseract Engine</span>
              <span className="tech-badge">Deterministic Rule Engine</span>
            </div>
          </div>
          <div>
            <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.4)', marginBottom: '12px', letterSpacing: '0.05em', fontFamily: "'JetBrains Mono', monospace" }}>STORAGE & UI</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <span className="tech-badge">Supabase Cloud DB</span>
              <span className="tech-badge">PostgreSQL Realtime</span>
              <span className="tech-badge">React 18 + Vite</span>
              <span className="tech-badge">Glassmorphism UI</span>
            </div>
          </div>
        </div>
      </div>
      
      {/* Dynamic inline styles for the tech badges to avoid cluttering CSS */}
      <style>{`
        .tech-badge {
          font-size: 13px;
          color: var(--text-2);
          display: flex;
          align-items: center;
        }
        .tech-badge::before {
          content: '';
          display: inline-block;
          width: 4px;
          height: 4px;
          background: rgba(255,255,255,0.3);
          border-radius: 50%;
          margin-right: 8px;
        }
      `}</style>
    </div>
  )
}

