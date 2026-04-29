import { useState, useEffect } from 'react'
import { Brain, X } from 'lucide-react'
import { invoiceApi, TraceEvent } from '../lib/api'
import { Spinner, Empty, AGENT_COLOR, getAgentAvatar, getLegacyAgentAvatar } from './Shared'

export default function TracePanel({ invoiceId, onClose }: { invoiceId: string; onClose: () => void }) {
  const [trace, setTrace] = useState<TraceEvent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    invoiceApi.trace(invoiceId)
      .then(r => { if (alive) setTrace(r.trace) })
      .finally(() => { if (alive) setLoading(false) })
    const t = setInterval(() => {
      invoiceApi.trace(invoiceId).then(r => { if (alive) setTrace(r.trace) }).catch(() => {})
    }, 4000)
    return () => { alive = false; clearInterval(t) }
  }, [invoiceId])

  return (
    <div className="trace-overlay" onClick={onClose}>
      <div className="trace-panel" onClick={e => e.stopPropagation()} role="dialog" aria-label="XAI Reasoning Trace">
        <div className="trace-header">
          <span className="trace-header-title">
            <Brain size={17} /> XAI Reasoning Trace
          </span>
          <button onClick={onClose} className="btn-ghost" aria-label="Close">
            <X size={15} />
          </button>
        </div>

        <div className="trace-subtitle">
          INVOICE <span className="badge-id">{invoiceId.slice(0, 8)}…</span>
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
              return (
                <div key={i} className="trace-event" style={{ animationDelay: `${i * 60}ms` }}>
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
                    <span className="trace-time">
                      {e.timestamp ? new Date(e.timestamp).toLocaleTimeString([], { hour12: false }) : ''}
                    </span>
                  </div>

                  {e.reasoning && <p className="trace-reasoning">{e.reasoning}</p>}

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
                        <div className="trace-xai-item trace-xai-causal">
                          <span className="trace-xai-label">Causal</span>
                          <span className="trace-xai-content">{e.causal_explanation}</span>
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
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
