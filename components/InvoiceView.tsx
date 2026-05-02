import { useState, useEffect, useCallback, useRef } from 'react'
import { Upload, CheckCircle, XCircle, Brain, Clock, FileText, ShieldCheck, AlertTriangle } from 'lucide-react'
import { invoiceApi, Invoice, departmentsApi, Department } from '../lib/api'
import { Card, Badge, Spinner, Empty, STATUS_COLOR, STATUS_BG, fmt, AgentAvatar } from './Shared'
import TracePanel from './TracePanel'

import { useRealtime } from '../lib/useRealtime'

const STAT_DEFS: { key: 'pending' | 'awaiting_approval' | 'approved' | 'rejected'; label: string; icon: any; tint: string }[] = [
  { key: 'pending',           label: 'Pending',           icon: Clock,       tint: '#94a3b8' },
  { key: 'awaiting_approval', label: 'Awaiting approval', icon: AlertTriangle, tint: '#fbbf24' },
  { key: 'approved',          label: 'Approved',          icon: ShieldCheck, tint: '#34d399' },
  { key: 'rejected',          label: 'Rejected',          icon: XCircle,     tint: '#fb7185' },
]

export default function InvoiceView() {
  const [invoices, setInvoices]     = useState<Invoice[]>([])
  const [loading, setLoading]       = useState(true)
  const [traceId, setTraceId]       = useState<string | null>(null)
  const [uploading, setUploading]   = useState(false)
  const [dept, setDept]             = useState('engineering')
  const [departments, setDepartments] = useState<Department[]>([])
  const fileRef                     = useRef<HTMLInputElement>(null)

  const load = useCallback(() => {
    invoiceApi.list().then(setInvoices).finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    departmentsApi.list().then(rows => {
      setDepartments(rows)
      if (rows.length > 0 && !rows.find(d => d.id === dept)) setDept(rows[0].id)
    }).catch(() => {})
  }, [])
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <AgentAvatar agent="invoice" active={uploading} />
          <div>
            <h2>Invoice Management</h2>
            <p className="view-sub">OCR extraction → Qwen3 analysis → cross-agent approval</p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <select value={dept} onChange={e => setDept(e.target.value)} className="select">
            {departments.map((d: Department) =>
              <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          <label className="btn-primary" style={{ cursor: uploading ? 'wait' : 'pointer' }}>
            <Upload size={14} strokeWidth={2.5} /> {uploading ? 'Processing…' : 'Upload Invoice'}
            <input ref={fileRef} type="file" accept=".pdf,.jpg,.jpeg,.png"
              onChange={upload} className="sr-only" />
          </label>
        </div>
      </div>

      <div className="stats-row">
        {STAT_DEFS.map(({ key, label, icon: Icon, tint }) => {
          const count = invoices.filter(i => i.status === key).length
          return (
            <Card key={key}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div className="stat-label">{label}</div>
                <div style={{
                  width: 28, height: 28, borderRadius: 8,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: tint + '18', color: tint, border: `1px solid ${tint}33`,
                }}>
                  <Icon size={14} strokeWidth={2.5} />
                </div>
              </div>
              <div className="stat-value" style={{ color: tint, marginTop: 6 }}>{count}</div>
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
                <th>Vendor</th>
                <th>Amount</th>
                <th>Department</th>
                <th>Status</th>
                <th style={{ textAlign: 'center' }}>Cash</th>
                <th style={{ textAlign: 'center' }}>Budget</th>
                <th>Confidence</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv: Invoice) => {
                const conf = inv.extraction_confidence ?? null
                const confClass = conf == null ? '' : conf >= 80 ? 'good' : conf >= 50 ? 'warn' : 'bad'
                const statusKey = inv.status as keyof typeof STATUS_COLOR
                return (
                  <tr key={inv.id}>
                    <td>
                      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                        <div style={{
                          width: 30, height: 30, borderRadius: 8,
                          background: 'rgba(34, 211, 238, .1)',
                          border: '1px solid rgba(34, 211, 238, .25)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          color: '#67e8f9',
                        }}>
                          <FileText size={13} />
                        </div>
                        <div>
                          <div style={{ fontWeight: 500, color: 'var(--text)' }}>{inv.vendor_name || '—'}</div>
                          <div style={{ fontSize: 11, color: 'var(--text-4)', fontFamily: 'JetBrains Mono, monospace' }}>
                            #{inv.invoice_number || '—'}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 500, fontVariantNumeric: 'tabular-nums', color: 'var(--text)' }}>
                      {fmt(inv.total_amount, inv.currency)}
                    </td>
                    <td style={{ textTransform: 'capitalize' }}>{inv.department || '—'}</td>
                    <td>
                      <Badge label={inv.status.replace('_', ' ')}
                        color={STATUS_COLOR[statusKey]}
                        bg={STATUS_BG[statusKey] ?? STATUS_COLOR[statusKey] + '22'}
                        className="badge-status" />
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      {inv.cash_check_passed == null ? <span style={{ color: 'var(--text-4)' }}>—</span>
                        : inv.cash_check_passed
                          ? <CheckCircle size={15} color="#34d399" style={{ filter: 'drop-shadow(0 0 4px rgba(52,211,153,.5))' }} />
                          : <XCircle size={15} color="#fb7185" style={{ filter: 'drop-shadow(0 0 4px rgba(251,113,133,.5))' }} />}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      {inv.budget_check_passed == null ? <span style={{ color: 'var(--text-4)' }}>—</span>
                        : inv.budget_check_passed
                          ? <CheckCircle size={15} color="#34d399" style={{ filter: 'drop-shadow(0 0 4px rgba(52,211,153,.5))' }} />
                          : <XCircle size={15} color="#fb7185" style={{ filter: 'drop-shadow(0 0 4px rgba(251,113,133,.5))' }} />}
                    </td>
                    <td>
                      {conf != null ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 110 }}>
                          <div className={`conf-bar ${confClass}`}>
                            <span style={{ width: `${conf}%` }} />
                          </div>
                          <span style={{ fontSize: 11, fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-2)', minWidth: 32, textAlign: 'right' }}>
                            {Math.round(conf)}%
                          </span>
                        </div>
                      ) : <span style={{ color: 'var(--text-4)' }}>—</span>}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                        <button className="btn-sm" onClick={() => setTraceId(inv.id)}>
                          <Brain size={11} /> Trace
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
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
