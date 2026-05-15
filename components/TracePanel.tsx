import { useState, useEffect } from 'react'
import { Brain, X } from 'lucide-react'
import { reconApi, invoiceApi, creditApi, TraceEvent } from '../lib/api'
import { Spinner, Empty, AGENT_COLOR, getAgentAvatar, getLegacyAgentAvatar } from './Shared'

export default function TracePanel({ entityId, entityType = 'invoice', onClose }: { entityId: string; entityType?: 'invoice' | 'reconciliation' | 'credit'; onClose: () => void }) {
  const [trace, setTrace] = useState<TraceEvent[]>([])
  const [entityName, setEntityName] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    const fetchTrace = () => {
      if (entityType === 'credit') return creditApi.trace(entityId)
      const api = entityType === 'reconciliation' ? reconApi : invoiceApi
      return api.trace(entityId)
    }

    fetchTrace()
      .then(r => { 
        if (alive) {
          setTrace(r.trace)
          if ((r as any).name) setEntityName((r as any).name)
        }
      })
      .finally(() => { if (alive) setLoading(false) })
      
    const t = setInterval(() => {
      fetchTrace().then(r => { 
        if (alive) {
          setTrace(r.trace)
          if ((r as any).name) setEntityName((r as any).name)
        }
      }).catch(() => {})
    }, 4000)
    return () => { alive = false; clearInterval(t) }
  }, [entityId, entityType])

  return (
    <div className="trace-overlay" onClick={onClose}>
      <div className="trace-panel" onClick={e => e.stopPropagation()} role="dialog" aria-label="XAI Reasoning Trace">
        <div className="trace-header">
          <span className="trace-header-title">
            <Brain size={17} /> {entityName || 'XAI Reasoning Trace'}
          </span>
          <button onClick={onClose} className="btn-ghost" aria-label="Close">
            <X size={15} />
          </button>
        </div>

        <div className="trace-subtitle">
          {entityType.toUpperCase()} IDENTITY <span className="badge-id">{entityId}</span>
          {trace.length > 0 && <span style={{ marginLeft: 10, color: 'var(--text-3)' }}>· {trace.length} events</span>}
        </div>

        {loading ? (
          <Spinner />
        ) : trace.length === 0 ? (
          <Empty msg="Awaiting agent signals — processing…" />
        ) : (
          <div className="trace-list">
            {trace.map((e: TraceEvent, i: number) => {
              const color = AGENT_COLOR[e.agent] || '#67e8f9'
              const prevAgent = i > 0 ? trace[i-1].agent : null
              const isCrossAgent = prevAgent && prevAgent !== e.agent
              return (
                <div key={i}>
                  {isCrossAgent && (
                    <div className="trace-causal-bridge">
                      <span className="trace-causal-bridge-line" />
                      <span className="trace-causal-bridge-label">CAUSAL ECHO ↓</span>
                      <span className="trace-causal-bridge-line" />
                    </div>
                  )}
                  <div className="trace-event" style={{ animationDelay: `${i * 60}ms` }}>
                  <div className="trace-event-header">
                    <span className="trace-agent" style={{ color, borderColor: color + '55', background: color + '15' }}>
                      <img
                        className="trace-agent-avatar"
                        src={getAgentAvatar(e.agent)}
                        alt={`${e.agent} avatar`}
                        onError={(ev) => { ev.currentTarget.src = getLegacyAgentAvatar(e.agent) }}
                      />
                      {e.agent}
                    </span>
                    <span className="trace-type">{e.event_type.replace(/_/g, ' ')}</span>
                    {e.details?.confidence !== undefined && (
                      <span style={{ fontSize: 10, fontWeight: 700, color: e.details.confidence >= 80 ? '#34d399' : e.details.confidence >= 60 ? '#fbbf24' : '#fb7185', marginLeft: 'auto', marginRight: 8 }}>
                        {e.details.confidence}% confidence
                      </span>
                    )}
                    <span className="trace-time">
                      {e.timestamp ? new Date(e.timestamp).toLocaleTimeString([], { hour12: false }) : ''}
                    </span>
                  </div>

                  {e.reasoning && !e.technical_explanation && <p className="trace-reasoning">{e.reasoning}</p>}

                  {/* Forensic Metrics */}
                  {(e.details?.score !== undefined || e.details?.confidence !== undefined || e.details?.risk_level || e.details?.liquidity_exposure !== undefined) && (
                    <div className="trace-metrics">
                      {e.details.score !== undefined && (
                        <div className="trace-metric">
                          <span className="trace-metric-label">Score</span>
                          <span className="trace-metric-value">{e.details.score.toFixed(1)}</span>
                        </div>
                      )}
                      {e.details.confidence !== undefined && (
                        <div className="trace-metric">
                          <span className="trace-metric-label">Confidence</span>
                          <span className="trace-metric-value">{e.details.confidence}%</span>
                        </div>
                      )}
                      {e.details.risk_level && (
                        <div className="trace-metric">
                          <span className="trace-metric-label">Risk</span>
                          <span className="trace-metric-value" style={{ textTransform: 'uppercase' }}>{e.details.risk_level}</span>
                        </div>
                      )}
                      {e.details.liquidity_exposure !== undefined && (
                        <div className="trace-metric trace-metric-exposure">
                          <span className="trace-metric-label">Liquidity Exposure</span>
                          <span className="trace-metric-value" style={{ color: '#fb7185' }}>
                            ${e.details.liquidity_exposure.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {(e.technical_explanation || e.business_explanation || e.causal_explanation) && (
                    <div className="trace-xai">
                      {e.technical_explanation && (
                        <div className="trace-xai-item trace-xai-technical">
                          <span className="trace-xai-label">Technical</span>
                          <span className="trace-xai-content">{e.technical_explanation}</span>
                        </div>
                      )}
                      {e.business_explanation && (
                        <div className="trace-xai-item trace-xai-business">
                          <span className="trace-xai-label">Business</span>
                          <span className="trace-xai-content">{e.business_explanation}</span>
                        </div>
                      )}
                      {e.causal_explanation && (
                        <div className={`trace-causal ${e.agent === 'governance' ? 'trace-causal-governance' : ''}`}>
                          <span className="trace-causal-label">
                            {e.agent === 'governance' ? 'Final Performance Validation' : 'Causal Domain Reasoning'}
                          </span>
                          <div className="trace-causal-content">
                            {e.agent === 'governance' && e.business_explanation?.includes('PERFORMANCE VALIDATED') && (
                              <div style={{ color: '#34d399', fontWeight: 700, fontSize: '10px', marginBottom: '4px', textTransform: 'uppercase' }}>
                                ✓ Performance Claim Verified
                              </div>
                            )}
                            {e.causal_explanation}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {e.details && Object.keys(e.details).length > 0 && (
                    <details className="trace-details">
                      <summary>Inspect payload</summary>
                      <pre>{JSON.stringify(e.details, null, 2)}</pre>
                    </details>
                  )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
