import { useState, useEffect } from 'react'
import { ShieldCheck, ShieldAlert, ShieldOff, Activity, ClipboardList, CheckCircle2, AlertTriangle, ExternalLink } from 'lucide-react'
import { Card, Badge, Spinner, Empty, AgentAvatar } from './Shared'
import { supabase } from '../lib/supabase'

interface AuditDecision {
  id: string
  entity_id: string
  entity_table: string
  decision_type: string
  confidence: number
  business_explanation: string
  technical_explanation: string
  causal_explanation: string
  output_action: {
    status: 'passed' | 'flagged' | 'blocked'
    compliance_score: number
    is_audit_safe: boolean
    findings?: string[]
  }
  created_at: string
}

export default function GovernanceView() {
  const [audits, setAudits] = useState<AuditDecision[]>([])
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState({ total: 0, passed: 0, flagged: 0, blocked: 0 })

  const load = async () => {
    setLoading(true)
    try {
      const { data, error } = await supabase
        .from('agent_decisions')
        .select('*')
        .eq('agent', 'governance')
        .order('created_at', { ascending: false })
        .limit(50)

      if (error) throw error

      const items = (data || []) as AuditDecision[]
      setAudits(items)

      const s = { total: items.length, passed: 0, flagged: 0, blocked: 0 }
      items.forEach(a => {
        const st = a.output_action?.status || 'passed'
        if (st === 'passed') s.passed++
        else if (st === 'flagged') s.flagged++
        else s.blocked++
      })
      setStats(s)
    } catch (e) {
      console.error('Failed to load audits:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  return (
    <div className="view">
      <div className="view-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <AgentAvatar agent="governance" active={loading} />
          <div>
            <h2>Governance & Compliance</h2>
            <p className="view-sub">Final safety gate · Policy enforcement · Cross-agent audit</p>
          </div>
        </div>
        <button className="btn-primary" onClick={load} disabled={loading}>
          <Activity size={14} className={loading ? 'spin' : ''} />
          {loading ? 'Auditing...' : 'Refresh Audit Log'}
        </button>
      </div>

      <div className="stats-row">
        <Card>
          <div className="stat-label">Compliance Pass Rate</div>
          <div className="stat-value" style={{ color: '#34d399' }}>
            {stats.total > 0 ? ((stats.passed / stats.total) * 100).toFixed(0) : 0}%
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 4 }}>
            {stats.passed} of {stats.total} runs passed
          </div>
        </Card>
        <Card>
          <div className="stat-label">Flagged Issues</div>
          <div className="stat-value" style={{ color: '#fbbf24' }}>{stats.flagged}</div>
          <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 4 }}>Requires attention</div>
        </Card>
        <Card>
          <div className="stat-label">Hard Blocks</div>
          <div className="stat-value" style={{ color: '#fb7185' }}>{stats.blocked}</div>
          <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 4 }}>Policy violations stopped</div>
        </Card>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px', marginTop: '12px' }}>
        {/* Main Audit Feed */}
        <div>
          <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ClipboardList size={16} color="var(--text-3)" />
            <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-2)', margin: 0 }}>Recent Audit Verdicts</h3>
          </div>

          {loading ? <Spinner /> : audits.length === 0 ? <Empty msg="No governance audits found." /> : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {audits.map(audit => (
                <AuditCard key={audit.id} audit={audit} />
              ))}
            </div>
          )}
        </div>

        {/* Policy Reference Sidebar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <Card style={{ background: 'rgba(52, 211, 153, 0.03)', border: '1px solid rgba(52, 211, 153, 0.1)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
              <ShieldCheck size={18} color="#34d399" />
              <h3 style={{ fontSize: '15px', fontWeight: 700, color: '#fff', margin: 0 }}>Audit Standards</h3>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <PolicyItem
                title="Scenario 1: Liquidity"
                desc="High-value invoices (> $100k) must pass the 7-day liquidity gate or have Senior Manager sign-off."
              />
              <PolicyItem
                title="Scenario 2: Forensic"
                desc="Reconciliation anomalies must be linked to Credit Risk reassessment for AR protection."
              />
              <PolicyItem
                title="Scenario 3: Fiscal"
                desc="Budget utilization ≥ 100% is a Hard Stop. No exceptions without formal overrides."
              />
            </div>
          </Card>

          <Card style={{ opacity: 0.8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
              <Activity size={16} color="#a78bfa" />
              <h3 style={{ fontSize: '14px', fontWeight: 600, color: '#fff', margin: 0 }}>Compliance Engine</h3>
            </div>
            <p style={{ fontSize: '12px', color: 'var(--text-3)', lineHeight: 1.6, margin: 0 }}>
              The Auditor Agent runs after every multi-agent chain. It performs cross-agent validation by comparing technical data (e.g., balance numbers) against business justifications.
            </p>
          </Card>
        </div>
      </div>
    </div>
  )
}

function AuditCard({ audit }: { audit: AuditDecision }) {
  const status = audit.output_action?.status || 'passed'
  const Icon = status === 'passed' ? CheckCircle2 : status === 'flagged' ? AlertTriangle : ShieldOff
  const color = status === 'passed' ? '#34d399' : status === 'flagged' ? '#fbbf24' : '#fb7185'

  return (
    <Card style={{ padding: '20px', borderLeft: `4px solid ${color}` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ color }}>
            <Icon size={18} />
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: '14px', color: '#fff' }}>
              {audit.decision_type.replace(/_/g, ' ')}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-4)', marginTop: 2 }}>
              Entity: {audit.entity_table} · {new Date(audit.created_at).toLocaleString()}
            </div>
          </div>
        </div>
        <Badge
          label={status.toUpperCase()}
          color={color}
          bg={color + '15'}
        />
      </div>

      <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: '8px', padding: '12px', marginBottom: '12px' }}>
        <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-2)', lineHeight: 1.6 }}>
          {audit.business_explanation}
        </p>
      </div>

      {audit.output_action?.findings && audit.output_action.findings.length > 0 && (
        <div style={{ marginBottom: '12px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '6px' }}>Audit Findings</div>
          <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '11px', color: color + 'dd', lineHeight: 1.6 }}>
            {audit.output_action.findings.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button className="btn-sm" style={{ opacity: 0.7 }} onClick={() => window.location.href = `#/invoice?id=${audit.entity_id}`}>
          <ExternalLink size={11} /> View Entity
        </button>
      </div>
    </Card>
  )
}

function PolicyItem({ title, desc }: { title: string, desc: string }) {
  return (
    <div>
      <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', marginBottom: '4px' }}>{title}</div>
      <p style={{ fontSize: '11px', color: 'var(--text-4)', margin: 0, lineHeight: 1.5 }}>{desc}</p>
    </div>
  )
}
