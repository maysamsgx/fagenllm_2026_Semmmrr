import { useState, useEffect } from 'react'
import { Brain } from 'lucide-react'
import { invoiceApi, TraceEvent } from '../lib/api'
import { Spinner, Empty, AGENT_COLOR } from './Shared'

export default function TracePanel({ invoiceId, onClose }: { invoiceId: string; onClose: () => void }) {
  const [trace, setTrace] = useState<TraceEvent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    invoiceApi.trace(invoiceId)
      .then(r => setTrace(r.trace))
      .finally(() => setLoading(false))
    const t = setInterval(() =>
      invoiceApi.trace(invoiceId).then(r => setTrace(r.trace)), 4000)
    return () => clearInterval(t)
  }, [invoiceId])

  return (
    <div className="trace-overlay">
      <div className="trace-panel">
        <div className="trace-header">
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Brain size={16} color="#6366f1" /> XAI Reasoning Trace
          </span>
          <button onClick={onClose} className="btn-ghost">✕</button>
        </div>
        <div style={{ fontSize: 11, color: '#64748b', padding: '4px 16px 12px' }}>
          Invoice {invoiceId.slice(0, 8)}…
        </div>
        {loading ? <Spinner /> : trace.length === 0 ? <Empty msg="No events yet — processing…" /> : (
          <div className="trace-list">
            {trace.map((e: TraceEvent, i: number) => (
              <div key={i} className="trace-event">
                <div className="trace-event-header">
                  <span className="trace-agent" style={{ background: AGENT_COLOR[e.agent] + '22', color: AGENT_COLOR[e.agent] }}>
                    {e.agent}
                  </span>
                  <span className="trace-type">{e.event_type.replace(/_/g, ' ')}</span>
                  <span className="trace-time">
                    {new Date(e.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <p className="trace-reasoning">{e.reasoning}</p>
                {Object.keys(e.details).length > 0 && (
                  <details className="trace-details">
                    <summary>Details</summary>
                    <pre>{JSON.stringify(e.details, null, 2)}</pre>
                  </details>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
