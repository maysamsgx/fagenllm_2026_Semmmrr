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

const GOV_COLOR: Record<string, string> = {
  passed: '#34d399',
  flagged: '#fbbf24',
  blocked: '#fb7185',
  pending: '#94a3b8'
}

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
      {traceId && <TracePanel entityId={traceId} onClose={() => setTraceId(null)} />}

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
        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div className="stat-label">Audit Safety</div>
            <div style={{
              width: 28, height: 28, borderRadius: 8,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'rgba(52, 211, 153, 0.12)', color: '#34d399', border: '1px solid rgba(52, 211, 153, 0.3)',
            }}>
              <ShieldCheck size={14} strokeWidth={2.5} />
            </div>
          </div>
          <div className="stat-value" style={{ color: '#34d399', marginTop: 6 }}>
            {invoices.filter(i => i.governance_status === 'passed').length} / {invoices.length}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 4 }}>Compliance passed</div>
        </Card>
      </div>

      {loading ? <Spinner /> : invoices.length === 0 ? (
        <Empty msg="No invoices yet — upload a PDF to start" />
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: '30%' }}>Vendor / Dept</th>
                <th style={{ textAlign: 'right' }}>Amount</th>
                <th>Status</th>
                <th style={{ textAlign: 'center' }}>Health</th>
                <th>Auditor</th>
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
                          width: 32, height: 32, borderRadius: 8,
                          background: 'rgba(34, 211, 238, .08)',
                          border: '1px solid rgba(34, 211, 238, .15)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          color: '#67e8f9', flexShrink: 0,
                        }}>
                          <FileText size={14} />
                        </div>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontWeight: 600, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {inv.vendor_name || '—'}
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--text-4)', textTransform: 'capitalize', display: 'flex', alignItems: 'center', gap: 4 }}>
                            {inv.department || '—'}
                            <span style={{ opacity: 0.3 }}>•</span>
                            <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>#{inv.invoice_number || '—'}</span>
                          </div>
                        </div>
                      </div>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, color: 'var(--text)' }}>
                        {fmt(inv.total_amount, inv.currency)}
                      </div>
                      {conf != null && (
                        <div style={{ fontSize: 10, color: `var(--text-4)`, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 4, marginTop: 2 }}>
                          <div style={{ width: 4, height: 4, borderRadius: '50%', background: conf >= 80 ? '#34d399' : '#fbbf24' }} />
                          {Math.round(conf)}% conf
                        </div>
                      )}
                    </td>
                    <td>
                      <Badge label={inv.status.replace('_', ' ')}
                        color={STATUS_COLOR[statusKey]}
                        bg={STATUS_BG[statusKey] ?? STATUS_COLOR[statusKey] + '22'}
                        className="badge-status" />
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <div style={{ display: 'flex', gap: 12, justifyContent: 'center', alignItems: 'center' }}>
                        <div title="Cash Position" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                          {inv.cash_check_passed == null ? <div style={{ width: 14, height: 14, borderRadius: '50%', border: '1px dashed var(--border-3)' }} />
                            : inv.cash_check_passed
                              ? <CheckCircle size={15} color="#34d399" style={{ filter: 'drop-shadow(0 0 4px rgba(52,211,153,.3))' }} />
                              : <XCircle size={15} color="#fb7185" style={{ filter: 'drop-shadow(0 0 4px rgba(251,113,133,.3))' }} />}
                          <span style={{ fontSize: 8, textTransform: 'uppercase', color: 'var(--text-4)', fontWeight: 700 }}>Cash</span>
                        </div>
                        <div title="Budget Alignment" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                          {inv.budget_check_passed == null ? <div style={{ width: 14, height: 14, borderRadius: '50%', border: '1px dashed var(--border-3)' }} />
                            : inv.budget_check_passed
                              ? <CheckCircle size={15} color="#34d399" style={{ filter: 'drop-shadow(0 0 4px rgba(52,211,153,.3))' }} />
                              : <XCircle size={15} color="#fb7185" style={{ filter: 'drop-shadow(0 0 4px rgba(251,113,133,.3))' }} />}
                          <span style={{ fontSize: 8, textTransform: 'uppercase', color: 'var(--text-4)', fontWeight: 700 }}>Bgt</span>
                        </div>
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div style={{
                          width: 8, height: 8, borderRadius: '50%',
                          background: GOV_COLOR[inv.governance_status || 'pending'],
                          boxShadow: `0 0 8px ${GOV_COLOR[inv.governance_status || 'pending']}66`
                        }} />
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-2)', textTransform: 'capitalize', lineHeight: 1.2 }}>
                            {inv.governance_status || 'pending'}
                          </span>
                          <span style={{ fontSize: 9, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.02em' }}>Policy Audit</span>
                        </div>
                      </div>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                        <button className="btn-sm" onClick={() => setTraceId(inv.id)} title="View AI Decision Trace">
                          <Brain size={12} /> <span className="hide-mobile">Trace</span>
                        </button>
                        {inv.status === 'awaiting_approval' && (
                          <button className="btn-sm btn-green"
                            onClick={() => invoiceApi.approve(inv.id, 'dashboard').then(load)}>
                            <CheckCircle size={12} /> Approve
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
