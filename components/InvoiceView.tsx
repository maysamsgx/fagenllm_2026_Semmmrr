import { useState, useEffect, useCallback, useRef } from 'react'
import { Upload, CheckCircle, XCircle, Brain } from 'lucide-react'
import { invoiceApi, Invoice } from '../lib/api'
import { Card, Badge, Spinner, Empty, STATUS_COLOR, fmt } from './Shared'
import TracePanel from './TracePanel'

import { useRealtime } from '../lib/useRealtime'

export default function InvoiceView() {
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [loading, setLoading]   = useState(true)
  const [traceId, setTraceId]   = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [dept, setDept]         = useState('engineering')
  const fileRef                 = useRef<HTMLInputElement>(null)

  const load = useCallback(() => {
    invoiceApi.list().then(setInvoices).finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])
  useRealtime('invoices', load)

  async function upload(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]; if (!f) return
    setUploading(true)
    try {
      const { invoice_id } = await invoiceApi.upload(f, dept)
      setTraceId(invoice_id)
      load()
    } catch (err) { alert('Upload failed: ' + err) }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = '' }
  }

  return (
    <div className="view">
      {traceId && <TracePanel invoiceId={traceId} onClose={() => setTraceId(null)} />}

      <div className="view-header">
        <div>
          <h2>Invoice Management</h2>
          <p className="view-sub">OCR extraction → Qwen3 analysis → cross-agent approval</p>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <select value={dept} onChange={e => setDept(e.target.value)} className="select">
            {['engineering','marketing','operations','hr'].map((d: string) =>
              <option key={d} value={d}>{d}</option>)}
          </select>
          <label className="btn-primary" style={{ cursor: uploading ? 'wait' : 'pointer' }}>
            <Upload size={14} /> {uploading ? 'Processing…' : 'Upload Invoice'}
            <input ref={fileRef} type="file" accept=".pdf,.jpg,.jpeg,.png"
              onChange={upload} style={{ display: 'none' }} />
          </label>
        </div>
      </div>

      <div className="stats-row">
        {(['pending','awaiting_approval','approved','rejected'] as const).map((s: string) => {
          const count = invoices.filter(i => i.status === s).length
          return (
            <Card key={s}>
              <div className="stat-label">{s.replace('_', ' ')}</div>
              <div className="stat-value" style={{ color: STATUS_COLOR[s] }}>{count}</div>
            </Card>
          )
        })}
      </div>

      {loading ? <Spinner /> : invoices.length === 0 ? (
        <Empty msg="No invoices yet — upload a PDF to start" />
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Vendor</th><th>Amount</th><th>Department</th>
                <th>Status</th><th>Cash ✓</th><th>Budget ✓</th>
                <th>Confidence</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv: Invoice) => (
                <tr key={inv.id}>
                  <td><div style={{ fontWeight: 500 }}>{inv.vendor_name || '—'}</div>
                      <div style={{ fontSize: 11, color: '#64748b' }}>#{inv.invoice_number || '?'}</div></td>
                  <td style={{ fontFamily: 'DM Mono, monospace', fontWeight: 500 }}>
                    {fmt(inv.total_amount, inv.currency)}
                  </td>
                  <td>{inv.department || '—'}</td>
                  <td>
                    <Badge label={inv.status.replace('_', ' ')}
                      color={STATUS_COLOR[inv.status]}
                      bg={STATUS_COLOR[inv.status] + '22'} />
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    {inv.cash_check_passed == null ? '—'
                      : inv.cash_check_passed
                        ? <CheckCircle size={16} color="#22c55e" />
                        : <XCircle size={16} color="#ef4444" />}
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    {inv.budget_check_passed == null ? '—'
                      : inv.budget_check_passed
                        ? <CheckCircle size={16} color="#22c55e" />
                        : <XCircle size={16} color="#ef4444" />}
                  </td>
                  <td>
                    {inv.extraction_confidence != null && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <div style={{ flex: 1, height: 4, background: '#e2e8f0', borderRadius: 2 }}>
                          <div style={{ width: `${inv.extraction_confidence}%`, height: '100%',
                            background: inv.extraction_confidence > 70 ? '#22c55e' : '#f59e0b',
                            borderRadius: 2 }} />
                        </div>
                        <span style={{ fontSize: 11, fontFamily: 'DM Mono, monospace' }}>
                          {inv.extraction_confidence}%
                        </span>
                      </div>
                    )}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button className="btn-sm" onClick={() => setTraceId(inv.id)}>
                        <Brain size={12} /> Trace
                      </button>
                      {inv.status === 'awaiting_approval' && (
                        <button className="btn-sm btn-green"
                          onClick={() => invoiceApi.approve(inv.id, 'dashboard').then(load)}>
                          Approve
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
