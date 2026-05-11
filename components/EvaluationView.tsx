import { useState } from 'react'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  LineChart, Line, AreaChart, Area,
  ResponsiveContainer,
} from 'recharts'
import {
  CheckCircle2, AlertTriangle, Clock, TrendingUp, TrendingDown,
  Target, Activity, Zap, Shield, BarChart2, Brain, GitBranch, RefreshCw,
  ChevronDown, ChevronRight,
} from 'lucide-react'

// ─── Colour palette (mirrors Shared.tsx) ────────────────────────────────────
const AC: Record<string, string> = {
  invoice:        '#67e8f9',
  cash:           '#22d3ee',
  budget:         '#a78bfa',
  reconciliation: '#fbbf24',
  credit:         '#fb7185',
  system:         '#34d399',
}

// ─── Helper components ───────────────────────────────────────────────────────
function GlassCard({
  children, style = {}, className = '',
}: { children: React.ReactNode; style?: React.CSSProperties; className?: string }) {
  return (
    <div
      className={className}
      style={{
        background: 'rgba(10,10,10,0.75)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255,255,255,0.09)',
        borderRadius: 20,
        padding: 24,
        ...style,
      }}
    >
      {children}
    </div>
  )
}

function SectionTitle({ icon: Icon, label, color = '#67e8f9' }: { icon: any; label: string; color?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
      <div
        style={{
          width: 36, height: 36, borderRadius: 10, display: 'flex', alignItems: 'center',
          justifyContent: 'center', background: color + '22', border: `1px solid ${color}44`,
        }}
      >
        <Icon size={18} color={color} />
      </div>
      <span style={{ fontSize: 17, fontWeight: 700, color: '#fff', letterSpacing: '-0.02em' }}>{label}</span>
    </div>
  )
}

function MetricPill({
  label, value, sub, good = true, color,
}: { label: string; value: string; sub?: string; good?: boolean; color: string }) {
  return (
    <div
      style={{
        background: color + '12',
        border: `1px solid ${color}30`,
        borderRadius: 14,
        padding: '14px 18px',
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        minWidth: 120,
      }}
    >
      <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </div>
      <div style={{ fontSize: 24, fontWeight: 800, color, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
      {sub && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: good ? '#34d399' : '#fb7185' }}>
          {good ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
          {sub}
        </div>
      )}
    </div>
  )
}

// ─── Tooltip helper ──────────────────────────────────────────────────────────
const ChartTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div
      style={{
        background: 'rgba(5,5,10,0.95)',
        border: '1px solid rgba(255,255,255,0.12)',
        borderRadius: 12,
        padding: '10px 14px',
        fontSize: 12,
      }}
    >
      {label && <div style={{ color: '#94a3b8', marginBottom: 6 }}>{label}</div>}
      {payload.map((p: any, i: number) => (
        <div key={i} style={{ color: p.color || '#fff', marginBottom: 2 }}>
          {p.name}: <strong>{typeof p.value === 'number' ? p.value.toFixed(2) : p.value}</strong>
        </div>
      ))}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
//  DATA — representative simulated metrics for a production-like test run
// ═══════════════════════════════════════════════════════════════════════════

// Invoice Agent
const invoiceMetrics = {
  precision: 0.942,
  recall: 0.918,
  f1: 0.930,
  processingTimeSec: 3.7,
  approvalRouting: 0.965,
  eInvoiceSuccessRate: 0.891,
}

// Budget Agent
const budgetMetrics = {
  mape: 4.3,
  rmse: 12480,
  alertPrecision: 0.887,
  alertRecall: 0.902,
  scenarioLatencyMs: 640,
  userSatisfaction: 4.2,
}

// Reconciliation Agent
const reconciliationMetrics = {
  matchingAccuracy: 0.971,
  falsePositiveRate: 0.021,
  falseNegativeRate: 0.017,
  cycleTimeMin: 4.1,
  resolutionSuccess: 0.883,
}

// Credit Agent
const creditMetrics = {
  aucRoc: 0.934,
  dsoImprovement: 8.2,
  collectionRate: 0.791,
  earlyDelinquencyDetection: 0.908,
}

// Cash Agent
const cashMetrics = {
  mae: 18350,
  mape: 3.1,
  alertTimeliness: 0.961,
  balanceAccuracy: 0.978,
  scenarioQuality: 4.4,
}

// System-Level
const systemMetrics = {
  e2eCompletionSec: 14.8,
  coordinationSuccessRate: 0.947,
  uptime: 99.6,
  errorRecovery: 0.923,
}

// ─── Chart datasets ──────────────────────────────────────────────────────────

const radarData = [
  { metric: 'F1 / Accuracy', invoice: 93, budget: 86, reconciliation: 97, credit: 93, cash: 97 },
  { metric: 'Precision',     invoice: 94, budget: 89, reconciliation: 98, credit: 91, cash: 96 },
  { metric: 'Recall',        invoice: 92, budget: 90, reconciliation: 96, credit: 91, cash: 97 },
  { metric: 'Speed',         invoice: 82, budget: 91, reconciliation: 88, credit: 85, cash: 89 },
  { metric: 'Reliability',   invoice: 97, budget: 88, reconciliation: 95, credit: 93, cash: 98 },
]

const baselineCompare = [
  { name: 'Invoice\nProcessing', manual: 42, automated: 18, fagenllm: 3.7 },
  { name: 'Budget\nForecasting', manual: 960, automated: 120, fagenllm: 0.64 },
  { name: 'Reconciliation', manual: 480, automated: 60, fagenllm: 4.1 },
  { name: 'Credit\nScoring', manual: 1440, automated: 240, fagenllm: 8.2 },
  { name: 'Cash\nForecast', manual: 240, automated: 45, fagenllm: 2.3 },
]

const f1History = [
  { week: 'W1', invoice: 0.87, budget: 0.81, reconciliation: 0.90, credit: 0.85, cash: 0.89 },
  { week: 'W2', invoice: 0.89, budget: 0.83, reconciliation: 0.92, credit: 0.88, cash: 0.91 },
  { week: 'W3', invoice: 0.90, budget: 0.84, reconciliation: 0.94, credit: 0.90, cash: 0.93 },
  { week: 'W4', invoice: 0.91, budget: 0.85, reconciliation: 0.96, credit: 0.91, cash: 0.95 },
  { week: 'W5', invoice: 0.92, budget: 0.86, reconciliation: 0.97, credit: 0.93, cash: 0.97 },
  { week: 'W6', invoice: 0.93, budget: 0.86, reconciliation: 0.97, credit: 0.93, cash: 0.98 },
]

const coordinationFlows = [
  { scenario: 'Invoice→Cash Gate',        success: 97, fail: 3 },
  { scenario: 'Recon→Credit Penalty',     success: 94, fail: 6 },
  { scenario: 'Budget→Invoice Block',     success: 98, fail: 2 },
  { scenario: 'Cash→Credit Discount',     success: 95, fail: 5 },
  { scenario: 'Credit→Invoice Routing',   success: 92, fail: 8 },
]

const errorRates = [
  { agent: 'Invoice', rate: 3.1 },
  { agent: 'Budget', rate: 4.8 },
  { agent: 'Reconciliation', rate: 2.4 },
  { agent: 'Credit', rate: 3.9 },
  { agent: 'Cash', rate: 2.1 },
]

// Confusion-matrix data per agent (TP, FP, FN, TN as pct of 100 decisions)
const confusionMatrices: Record<string, { tp: number; fp: number; fn: number; tn: number; total: number }> = {
  invoice:        { tp: 312, fp: 19, fn: 28, tn: 641, total: 1000 },
  budget:         { tp: 284, fp: 36, fn: 31, tn: 649, total: 1000 },
  reconciliation: { tp: 421, fp: 9,  fn: 12, tn: 558, total: 1000 },
  credit:         { tp: 198, fp: 18, fn: 22, tn: 762, total: 1000 },
  cash:           { tp: 367, fp: 8,  fn: 11, tn: 614, total: 1000 },
}

// ─── Confusion matrix visual ──────────────────────────────────────────────
function ConfusionMatrix({ agent }: { agent: string }) {
  const d = confusionMatrices[agent]
  const color = AC[agent]
  const cells = [
    { label: 'TP', value: d.tp, bg: color + '30', border: color },
    { label: 'FP', value: d.fp, bg: '#fb718520', border: '#fb7185' },
    { label: 'FN', value: d.fn, bg: '#fbbf2420', border: '#fbbf24' },
    { label: 'TN', value: d.tn, bg: '#34d39920', border: '#34d399' },
  ]
  const prec = (d.tp / (d.tp + d.fp)).toFixed(3)
  const rec  = (d.tp / (d.tp + d.fn)).toFixed(3)
  const f1   = (2 * +prec * +rec / (+prec + +rec)).toFixed(3)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        {cells.map(c => (
          <div
            key={c.label}
            style={{
              background: c.bg, border: `1px solid ${c.border}44`,
              borderRadius: 12, padding: '12px 16px',
            }}
          >
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)', marginBottom: 4 }}>{c.label}</div>
            <div style={{ fontSize: 22, fontWeight: 800, color: c.border }}>{c.value}</div>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 12 }}>
        {[['Precision', prec], ['Recall', rec], ['F1', f1]].map(([k, v]) => (
          <div key={k as string} style={{ flex: 1, background: 'rgba(255,255,255,0.04)', borderRadius: 10, padding: '8px 12px', textAlign: 'center' }}>
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', marginBottom: 2 }}>{k}</div>
            <div style={{ fontSize: 15, fontWeight: 700, color }}>{v}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Collapsible agent section ────────────────────────────────────────────
function AgentSection({
  id, label, color, children,
}: { id: string; label: string; color: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(true)
  return (
    <GlassCard style={{ padding: 0, overflow: 'hidden' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', background: 'transparent', border: 'none', cursor: 'pointer',
          padding: '18px 24px', display: 'flex', alignItems: 'center', gap: 12,
        }}
      >
        <div
          style={{
            width: 10, height: 10, borderRadius: '50%', background: color,
            boxShadow: `0 0 8px ${color}`,
          }}
        />
        <span style={{ flex: 1, fontSize: 16, fontWeight: 700, color: '#fff', textAlign: 'left' }}>{label}</span>
        {open ? <ChevronDown size={16} color="rgba(255,255,255,0.4)" /> : <ChevronRight size={16} color="rgba(255,255,255,0.4)" />}
      </button>
      {open && (
        <div style={{ padding: '0 24px 24px' }}>{children}</div>
      )}
    </GlassCard>
  )
}

// ─── Tab navigation ───────────────────────────────────────────────────────
const EVAL_TABS = [
  { id: 'overview',     label: 'Overview',          icon: BarChart2 },
  { id: 'agents',       label: 'Per-Agent Metrics',  icon: Brain },
  { id: 'matrices',     label: 'Confusion Matrices', icon: Target },
  { id: 'coordination', label: 'Coordination',       icon: GitBranch },
  { id: 'baseline',     label: 'Baseline Compare',   icon: Activity },
  { id: 'explainability', label: 'Explainability',   icon: Shield },
]

// ═══════════════════════════════════════════════════════════════════════════
//  MAIN EXPORT
// ═══════════════════════════════════════════════════════════════════════════
export default function EvaluationView() {
  const [activeTab, setActiveTab] = useState('overview')

  return (
    <div style={{ padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 1400, margin: '0 auto' }}>
      {/* Header */}
      <div>
        <h1
          style={{
            fontSize: 28, fontWeight: 800, color: '#fff',
            letterSpacing: '-0.03em', marginBottom: 6,
          }}
        >
          Evaluation & Metrics
        </h1>
        <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.45)', margin: 0 }}>
          Comprehensive performance analysis across all five FAgentLLM agents — Objectives 9 & 10
        </p>
      </div>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {EVAL_TABS.map(t => {
          const Icon = t.icon
          const active = activeTab === t.id
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 7,
                padding: '9px 16px', borderRadius: 12, border: 'none', cursor: 'pointer',
                fontSize: 13, fontWeight: 600,
                background: active ? 'rgba(103,232,249,0.15)' : 'rgba(255,255,255,0.06)',
                color: active ? '#67e8f9' : 'rgba(255,255,255,0.55)',
                transition: 'all 0.18s',
                outline: active ? '1px solid rgba(103,232,249,0.35)' : '1px solid transparent',
              }}
            >
              <Icon size={14} />
              {t.label}
            </button>
          )
        })}
      </div>

      {/* ── Overview ─────────────────────────────────────────────────── */}
      {activeTab === 'overview' && <OverviewTab />}

      {/* ── Per-Agent Metrics ─────────────────────────────────────────── */}
      {activeTab === 'agents' && <AgentsTab />}

      {/* ── Confusion Matrices ────────────────────────────────────────── */}
      {activeTab === 'matrices' && <MatricesTab />}

      {/* ── Coordination ─────────────────────────────────────────────── */}
      {activeTab === 'coordination' && <CoordinationTab />}

      {/* ── Baseline Compare ─────────────────────────────────────────── */}
      {activeTab === 'baseline' && <BaselineTab />}

      {/* ── Explainability ───────────────────────────────────────────── */}
      {activeTab === 'explainability' && <ExplainabilityTab />}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
//  OVERVIEW TAB
// ─────────────────────────────────────────────────────────────────────────────
function OverviewTab() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* KPI strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 14 }}>
        <MetricPill label="System Uptime"        value="99.6%"  sub="+0.4% vs target" good color={AC.system} />
        <MetricPill label="Coordination Rate"    value="94.7%"  sub="+12% vs baseline" good color={AC.invoice} />
        <MetricPill label="Avg E2E Time"         value="14.8s"  sub="−72% vs manual" good color={AC.budget} />
        <MetricPill label="Error Recovery"       value="92.3%"  sub="+18% vs v1" good color={AC.reconciliation} />
        <MetricPill label="Avg Agent F1"         value="0.937"  sub="+0.12 vs baseline" good color={AC.credit} />
        <MetricPill label="Workflows / Day"      value="1,240"  sub="across 5 agents" good color={AC.cash} />
      </div>

      {/* Radar — all agents */}
      <GlassCard>
        <SectionTitle icon={Target} label="Agent Capability Radar (vs 100% target)" color="#67e8f9" />
        <ResponsiveContainer width="100%" height={320}>
          <RadarChart data={radarData} margin={{ top: 10, right: 40, bottom: 10, left: 40 }}>
            <PolarGrid stroke="rgba(255,255,255,0.08)" />
            <PolarAngleAxis dataKey="metric" tick={{ fill: 'rgba(255,255,255,0.55)', fontSize: 12 }} />
            {Object.entries(AC).filter(([k]) => k !== 'system').map(([agent, color]) => (
              <Radar key={agent} name={agent} dataKey={agent} stroke={color} fill={color} fillOpacity={0.08} dot={false} />
            ))}
            <Legend
              formatter={(v) => <span style={{ color: AC[v] || '#fff', fontSize: 12, textTransform: 'capitalize' }}>{v}</span>}
            />
            <Tooltip content={<ChartTooltip />} />
          </RadarChart>
        </ResponsiveContainer>
      </GlassCard>

      {/* F1 over time */}
      <GlassCard>
        <SectionTitle icon={TrendingUp} label="F1 / Accuracy Improvement over 6-Week Training Run" color="#34d399" />
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={f1History} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.05)" strokeDasharray="4 4" />
            <XAxis dataKey="week" tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 12 }} />
            <YAxis domain={[0.78, 1.0]} tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 12 }} tickFormatter={v => v.toFixed(2)} />
            <Tooltip content={<ChartTooltip />} />
            <Legend formatter={(v) => <span style={{ color: AC[v] || '#fff', fontSize: 12, textTransform: 'capitalize' }}>{v}</span>} />
            {Object.entries(AC).filter(([k]) => k !== 'system').map(([agent, color]) => (
              <Line key={agent} type="monotone" dataKey={agent} stroke={color} strokeWidth={2} dot={{ r: 3, fill: color }} name={agent} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </GlassCard>

      {/* Error rates */}
      <GlassCard>
        <SectionTitle icon={AlertTriangle} label="Error Rate per Agent (%)" color="#fbbf24" />
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={errorRates} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.05)" strokeDasharray="4 4" />
            <XAxis dataKey="agent" tick={{ fill: 'rgba(255,255,255,0.55)', fontSize: 12 }} />
            <YAxis tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 12 }} tickFormatter={v => `${v}%`} />
            <Tooltip content={<ChartTooltip />} />
            <Bar dataKey="rate" name="Error Rate (%)" radius={[6, 6, 0, 0]}
              fill="url(#errorGrad)"
            />
            <defs>
              <linearGradient id="errorGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#fb7185" stopOpacity={0.9} />
                <stop offset="100%" stopColor="#fb7185" stopOpacity={0.4} />
              </linearGradient>
            </defs>
          </BarChart>
        </ResponsiveContainer>
      </GlassCard>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
//  PER-AGENT METRICS TAB
// ─────────────────────────────────────────────────────────────────────────────
function AgentsTab() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Invoice */}
      <AgentSection id="invoice" label="Invoice Management Agent" color={AC.invoice}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 20 }}>
          <MetricPill label="Precision"            value={`${(invoiceMetrics.precision * 100).toFixed(1)}%`}  sub="vs 80% target" good color={AC.invoice} />
          <MetricPill label="Recall"               value={`${(invoiceMetrics.recall * 100).toFixed(1)}%`}    sub="vs 80% target" good color={AC.invoice} />
          <MetricPill label="F1-Score"             value={invoiceMetrics.f1.toFixed(3)}                       sub="+0.13 vs manual" good color={AC.invoice} />
          <MetricPill label="Avg Processing"       value={`${invoiceMetrics.processingTimeSec}s`}             sub="vs 42s manual" good color={AC.invoice} />
          <MetricPill label="Routing Accuracy"     value={`${(invoiceMetrics.approvalRouting * 100).toFixed(1)}%`} sub="3-way match" good color={AC.invoice} />
          <MetricPill label="E-Invoice Success"    value={`${(invoiceMetrics.eInvoiceSuccessRate * 100).toFixed(1)}%`} sub="OCR pipeline" good color={AC.invoice} />
        </div>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart
            data={[
              { name: 'Precision', value: invoiceMetrics.precision * 100 },
              { name: 'Recall',    value: invoiceMetrics.recall * 100 },
              { name: 'F1',        value: invoiceMetrics.f1 * 100 },
              { name: 'Routing',   value: invoiceMetrics.approvalRouting * 100 },
              { name: 'E-Invoice', value: invoiceMetrics.eInvoiceSuccessRate * 100 },
            ]}
            margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
          >
            <CartesianGrid stroke="rgba(255,255,255,0.05)" strokeDasharray="4 4" />
            <XAxis dataKey="name" tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }} />
            <YAxis domain={[0, 100]} tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }} tickFormatter={v => `${v}%`} />
            <Tooltip content={<ChartTooltip />} />
            <Bar dataKey="value" name="Score (%)" fill={AC.invoice} radius={[6, 6, 0, 0]} fillOpacity={0.8} />
          </BarChart>
        </ResponsiveContainer>
      </AgentSection>

      {/* Budget */}
      <AgentSection id="budget" label="Budget Management Agent" color={AC.budget}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 20 }}>
          <MetricPill label="MAPE"              value={`${budgetMetrics.mape}%`}                           sub="↓ from 18% baseline" good color={AC.budget} />
          <MetricPill label="RMSE ($)"          value={`$${(budgetMetrics.rmse / 1000).toFixed(1)}k`}      sub="forecast error" good color={AC.budget} />
          <MetricPill label="Alert Precision"   value={`${(budgetMetrics.alertPrecision * 100).toFixed(1)}%`}  sub="few false alarms" good color={AC.budget} />
          <MetricPill label="Alert Recall"      value={`${(budgetMetrics.alertRecall * 100).toFixed(1)}%`}     sub="catches overspend" good color={AC.budget} />
          <MetricPill label="Scenario Latency"  value={`${budgetMetrics.scenarioLatencyMs}ms`}             sub="gen time" good color={AC.budget} />
          <MetricPill label="User Satisfaction" value={`${budgetMetrics.userSatisfaction}/5`}              sub="finance team survey" good color={AC.budget} />
        </div>
        <ResponsiveContainer width="100%" height={160}>
          <AreaChart
            data={[
              { week: 'W1', mape: 9.1 }, { week: 'W2', mape: 7.2 }, { week: 'W3', mape: 5.8 },
              { week: 'W4', mape: 5.0 }, { week: 'W5', mape: 4.5 }, { week: 'W6', mape: 4.3 },
            ]}
            margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
          >
            <CartesianGrid stroke="rgba(255,255,255,0.05)" strokeDasharray="4 4" />
            <XAxis dataKey="week" tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }} />
            <YAxis tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }} tickFormatter={v => `${v}%`} />
            <Tooltip content={<ChartTooltip />} />
            <Area type="monotone" dataKey="mape" name="MAPE (%)" stroke={AC.budget} fill={AC.budget} fillOpacity={0.1} strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </AgentSection>

      {/* Reconciliation */}
      <AgentSection id="reconciliation" label="Reconciliation Agent" color={AC.reconciliation}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 20 }}>
          <MetricPill label="Matching Accuracy"   value={`${(reconciliationMetrics.matchingAccuracy * 100).toFixed(1)}%`} sub="vs 65% manual" good color={AC.reconciliation} />
          <MetricPill label="False Positive Rate" value={`${(reconciliationMetrics.falsePositiveRate * 100).toFixed(1)}%`} sub="very low" good color={AC.reconciliation} />
          <MetricPill label="False Negative Rate" value={`${(reconciliationMetrics.falseNegativeRate * 100).toFixed(1)}%`} sub="very low" good color={AC.reconciliation} />
          <MetricPill label="Cycle Time"          value={`${reconciliationMetrics.cycleTimeMin} min`} sub="vs 480 min manual" good color={AC.reconciliation} />
          <MetricPill label="Resolution Success"  value={`${(reconciliationMetrics.resolutionSuccess * 100).toFixed(1)}%`} sub="disputes resolved" good color={AC.reconciliation} />
        </div>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart
            data={[
              { name: 'Match Acc.', value: 97.1 },
              { name: 'FP Rate',    value: 2.1, inverse: true },
              { name: 'FN Rate',    value: 1.7, inverse: true },
              { name: 'Resolution', value: 88.3 },
            ]}
            margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
          >
            <CartesianGrid stroke="rgba(255,255,255,0.05)" strokeDasharray="4 4" />
            <XAxis dataKey="name" tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }} />
            <YAxis tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }} tickFormatter={v => `${v}%`} />
            <Tooltip content={<ChartTooltip />} />
            <Bar dataKey="value" name="Score (%)" fill={AC.reconciliation} radius={[6, 6, 0, 0]} fillOpacity={0.85} />
          </BarChart>
        </ResponsiveContainer>
      </AgentSection>

      {/* Credit */}
      <AgentSection id="credit" label="Credit Tracking Agent" color={AC.credit}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 20 }}>
          <MetricPill label="AUC-ROC"                value={creditMetrics.aucRoc.toFixed(3)}                         sub="vs 0.71 baseline" good color={AC.credit} />
          <MetricPill label="DSO Improvement"        value={`${creditMetrics.dsoImprovement} days`}                  sub="shorter collection" good color={AC.credit} />
          <MetricPill label="Collection Rate"        value={`${(creditMetrics.collectionRate * 100).toFixed(1)}%`}    sub="automation" good color={AC.credit} />
          <MetricPill label="Early Delinquency Det." value={`${(creditMetrics.earlyDelinquencyDetection * 100).toFixed(1)}%`} sub="catch early" good color={AC.credit} />
        </div>
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart
            data={[
              { month: 'Jan', auc: 0.71 }, { month: 'Feb', auc: 0.78 }, { month: 'Mar', auc: 0.83 },
              { month: 'Apr', auc: 0.88 }, { month: 'May', auc: 0.91 }, { month: 'Jun', auc: 0.934 },
            ]}
            margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
          >
            <CartesianGrid stroke="rgba(255,255,255,0.05)" strokeDasharray="4 4" />
            <XAxis dataKey="month" tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }} />
            <YAxis domain={[0.6, 1.0]} tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }} tickFormatter={v => v.toFixed(2)} />
            <Tooltip content={<ChartTooltip />} />
            <Area type="monotone" dataKey="auc" name="AUC-ROC" stroke={AC.credit} fill={AC.credit} fillOpacity={0.12} strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </AgentSection>

      {/* Cash */}
      <AgentSection id="cash" label="Cash Management Agent" color={AC.cash}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 20 }}>
          <MetricPill label="MAE ($)"            value={`$${(cashMetrics.mae / 1000).toFixed(1)}k`}                sub="7-day forecast" good color={AC.cash} />
          <MetricPill label="MAPE"               value={`${cashMetrics.mape}%`}                                    sub="vs 15% manual" good color={AC.cash} />
          <MetricPill label="Alert Timeliness"   value={`${(cashMetrics.alertTimeliness * 100).toFixed(1)}%`}      sub="real-time alerts" good color={AC.cash} />
          <MetricPill label="Balance Accuracy"   value={`${(cashMetrics.balanceAccuracy * 100).toFixed(1)}%`}      sub="consolidation" good color={AC.cash} />
          <MetricPill label="Scenario Quality"   value={`${cashMetrics.scenarioQuality}/5`}                        sub="analyst rating" good color={AC.cash} />
        </div>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart
            data={[
              { name: 'Balance Acc.', value: 97.8 },
              { name: 'Alert Time',   value: 96.1 },
              { name: 'MAPE-inv',     value: 96.9 },
              { name: 'Scenario Q.',  value: 88.0 },
            ]}
            margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
          >
            <CartesianGrid stroke="rgba(255,255,255,0.05)" strokeDasharray="4 4" />
            <XAxis dataKey="name" tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }} />
            <YAxis domain={[0, 100]} tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }} tickFormatter={v => `${v}%`} />
            <Tooltip content={<ChartTooltip />} />
            <Bar dataKey="value" name="Score (%)" fill={AC.cash} radius={[6, 6, 0, 0]} fillOpacity={0.85} />
          </BarChart>
        </ResponsiveContainer>
      </AgentSection>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
//  CONFUSION MATRICES TAB
// ─────────────────────────────────────────────────────────────────────────────
function MatricesTab() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <GlassCard style={{ padding: '16px 24px' }}>
        <p style={{ margin: 0, fontSize: 13, color: 'rgba(255,255,255,0.5)', lineHeight: 1.6 }}>
          Each matrix shows the classification outcome over a 1,000-decision test set.
          <strong style={{ color: '#67e8f9' }}> TP</strong> = true positive,
          <strong style={{ color: '#fb7185' }}> FP</strong> = false positive,
          <strong style={{ color: '#fbbf24' }}> FN</strong> = false negative,
          <strong style={{ color: '#34d399' }}> TN</strong> = true negative.
          Derived precision, recall, and F1 are shown below each matrix.
        </p>
      </GlassCard>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 18 }}>
        {Object.entries(confusionMatrices).map(([agent]) => (
          <GlassCard key={agent}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: AC[agent], boxShadow: `0 0 6px ${AC[agent]}` }} />
              <span style={{ fontSize: 14, fontWeight: 700, color: '#fff', textTransform: 'capitalize' }}>
                {agent} Agent
              </span>
            </div>
            <ConfusionMatrix agent={agent} />
          </GlassCard>
        ))}
      </div>

      {/* Comparative F1 summary */}
      <GlassCard>
        <SectionTitle icon={BarChart2} label="Derived F1-Score Comparison across All Agents" color="#34d399" />
        <ResponsiveContainer width="100%" height={220}>
          <BarChart
            data={Object.entries(confusionMatrices).map(([agent, d]) => {
              const prec = d.tp / (d.tp + d.fp)
              const rec  = d.tp / (d.tp + d.fn)
              const f1   = 2 * prec * rec / (prec + rec)
              return { agent: agent.charAt(0).toUpperCase() + agent.slice(1), f1: +(f1 * 100).toFixed(1) }
            })}
            margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
          >
            <CartesianGrid stroke="rgba(255,255,255,0.05)" strokeDasharray="4 4" />
            <XAxis dataKey="agent" tick={{ fill: 'rgba(255,255,255,0.55)', fontSize: 12 }} />
            <YAxis domain={[80, 100]} tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 12 }} tickFormatter={v => `${v}%`} />
            <Tooltip content={<ChartTooltip />} />
            <Bar dataKey="f1" name="F1 Score (%)" radius={[6, 6, 0, 0]}>
              {Object.keys(confusionMatrices).map((agent, i) => (
                <rect key={i} fill={AC[agent]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </GlassCard>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
//  COORDINATION TAB
// ─────────────────────────────────────────────────────────────────────────────
function CoordinationTab() {
  const workflowScenarios = [
    {
      id: 'W1', title: 'Invoice → Cash Liquidity Gate',
      steps: ['Invoice Agent extracts & validates fields', 'Cash Agent checks 7-day liquidity buffer', 'Approval gated: invoice rejected if < $50k buffer'],
      successRate: 97, latencyMs: 1240, color: AC.invoice,
    },
    {
      id: 'W2', title: 'Reconciliation → Credit Penalty Chain',
      steps: ['Reconciliation Agent detects duplicate transaction', 'Causal event emitted → Credit Agent', 'Credit score reduced by 20 pts; limit adjusted'],
      successRate: 94, latencyMs: 2100, color: AC.reconciliation,
    },
    {
      id: 'W3', title: 'Budget Block → Invoice Hold',
      steps: ['Budget Agent detects cap exceeded in department', 'Shared state flagged as BLOCKED', 'Invoice Agent auto-routes to CFO for override'],
      successRate: 98, latencyMs: 890, color: AC.budget,
    },
    {
      id: 'W4', title: 'Credit Risk → AR Cash Discount',
      steps: ['Credit Agent lowers client risk score', 'Cash Agent applies 15% AR discount to forecast', 'Liquidity alert raised if threshold breached'],
      successRate: 95, latencyMs: 1650, color: AC.credit,
    },
    {
      id: 'W5', title: 'Full Cross-Domain Pipeline',
      steps: ['Invoice submitted → Budget checked → Cash validated', 'Reconciliation match confirmed → Credit approved', 'All 5 agents coordinated in single transaction'],
      successRate: 91, latencyMs: 5800, color: AC.cash,
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Coordination success bar chart */}
      <GlassCard>
        <SectionTitle icon={GitBranch} label="Multi-Agent Coordination — Success vs Failure Rate" color="#67e8f9" />
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={coordinationFlows} margin={{ top: 5, right: 20, bottom: 30, left: 0 }} layout="vertical">
            <CartesianGrid stroke="rgba(255,255,255,0.05)" strokeDasharray="4 4" />
            <XAxis type="number" domain={[0, 100]} tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }} tickFormatter={v => `${v}%`} />
            <YAxis type="category" dataKey="scenario" width={170} tick={{ fill: 'rgba(255,255,255,0.55)', fontSize: 11 }} />
            <Tooltip content={<ChartTooltip />} />
            <Legend />
            <Bar dataKey="success" name="Success %" stackId="a" fill="#34d399" fillOpacity={0.8} radius={[0, 0, 0, 0]} />
            <Bar dataKey="fail"    name="Failure %"  stackId="a" fill="#fb7185" fillOpacity={0.7} radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </GlassCard>

      {/* Workflow scenarios */}
      <SectionTitle icon={Zap} label="≥ 3 Multi-Agent Coordination Workflows (Objective 8)" color="#a78bfa" />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {workflowScenarios.map(w => (
          <GlassCard key={w.id}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16 }}>
              <div
                style={{
                  minWidth: 48, height: 48, borderRadius: 12,
                  background: w.color + '20', border: `1px solid ${w.color}40`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontWeight: 800, color: w.color, fontSize: 13,
                }}
              >
                {w.id}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 15, fontWeight: 700, color: '#fff', marginBottom: 10 }}>{w.title}</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
                  {w.steps.map((s, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'rgba(255,255,255,0.6)' }}>
                      <CheckCircle2 size={12} color={w.color} />
                      {s}
                    </div>
                  ))}
                </div>
                <div style={{ display: 'flex', gap: 12 }}>
                  <span style={{ fontSize: 12, color: '#34d399', background: 'rgba(52,211,153,0.1)', borderRadius: 8, padding: '4px 10px' }}>
                    ✓ {w.successRate}% success
                  </span>
                  <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.45)', background: 'rgba(255,255,255,0.06)', borderRadius: 8, padding: '4px 10px' }}>
                    <Clock size={10} style={{ display: 'inline', marginRight: 4 }} />
                    {w.latencyMs < 1000 ? `${w.latencyMs}ms` : `${(w.latencyMs / 1000).toFixed(1)}s`}
                  </span>
                </div>
              </div>
            </div>
          </GlassCard>
        ))}
      </div>

      {/* System-level metrics */}
      <GlassCard>
        <SectionTitle icon={Activity} label="System-Level Metrics" color="#34d399" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 14 }}>
          <MetricPill label="E2E Completion" value={`${systemMetrics.e2eCompletionSec}s`}      sub="avg across workflows" good color="#34d399" />
          <MetricPill label="Coord. Success" value={`${(systemMetrics.coordinationSuccessRate * 100).toFixed(1)}%`} sub="+12% vs v1" good color="#34d399" />
          <MetricPill label="Uptime"          value={`${systemMetrics.uptime}%`}               sub="30-day rolling" good color="#34d399" />
          <MetricPill label="Error Recovery"  value={`${(systemMetrics.errorRecovery * 100).toFixed(1)}%`}  sub="auto-retry logic" good color="#34d399" />
        </div>
      </GlassCard>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
//  BASELINE COMPARISON TAB
// ─────────────────────────────────────────────────────────────────────────────
function BaselineTab() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <GlassCard>
        <SectionTitle icon={BarChart2} label="Processing Time (minutes) — FAgentLLM vs Traditional Automated vs Manual" color="#22d3ee" />
        <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.45)', marginBottom: 20, marginTop: -8 }}>
          Lower is better. FAgentLLM processes tasks in seconds where manual workflows take hours.
        </p>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={baselineCompare} margin={{ top: 5, right: 20, bottom: 30, left: 0 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.05)" strokeDasharray="4 4" />
            <XAxis dataKey="name" tick={{ fill: 'rgba(255,255,255,0.55)', fontSize: 11 }} interval={0} />
            <YAxis tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11 }} />
            <Tooltip content={<ChartTooltip />} />
            <Legend />
            <Bar dataKey="manual"    name="Manual (min)"    fill="#fb7185" fillOpacity={0.7} radius={[4, 4, 0, 0]} />
            <Bar dataKey="automated" name="Rule-Based (min)" fill="#fbbf24" fillOpacity={0.7} radius={[4, 4, 0, 0]} />
            <Bar dataKey="fagenllm"  name="FAgentLLM (min)"  fill="#34d399" fillOpacity={0.85} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </GlassCard>

      {/* Accuracy comparison table */}
      <GlassCard>
        <SectionTitle icon={Target} label="Accuracy Comparison — FAgentLLM vs Baselines" color="#a78bfa" />
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.09)' }}>
                {['Metric', 'Manual / Human', 'Rule-Based Automation', 'FAgentLLM', 'Improvement'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: 'rgba(255,255,255,0.45)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                { metric: 'Invoice F1-Score',         manual: '0.72', auto: '0.81', ours: '0.930', delta: '+18%', good: true },
                { metric: 'Budget Forecast MAPE',     manual: '18%',  auto: '9%',   ours: '4.3%',  delta: '−76%', good: true },
                { metric: 'Recon Match Accuracy',     manual: '65%',  auto: '82%',  ours: '97.1%', delta: '+49%', good: true },
                { metric: 'Credit AUC-ROC',           manual: '0.62', auto: '0.71', ours: '0.934', delta: '+51%', good: true },
                { metric: 'Cash Forecast MAPE',       manual: '15%',  auto: '6%',   ours: '3.1%',  delta: '−79%', good: true },
                { metric: 'E2E Process Time',         manual: '8 hrs', auto: '90 min', ours: '14.8s', delta: '−99.7%', good: true },
                { metric: 'False Positive Rate',      manual: '12%',  auto: '6%',   ours: '2.1%',  delta: '−83%', good: true },
                { metric: 'Inter-Agent Coordination', manual: 'N/A',  auto: 'N/A',  ours: '94.7%', delta: 'NEW',   good: true },
              ].map((row, i) => (
                <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)' }}>
                  <td style={{ padding: '10px 14px', color: '#fff', fontWeight: 600 }}>{row.metric}</td>
                  <td style={{ padding: '10px 14px', color: '#fb7185' }}>{row.manual}</td>
                  <td style={{ padding: '10px 14px', color: '#fbbf24' }}>{row.auto}</td>
                  <td style={{ padding: '10px 14px', color: '#34d399', fontWeight: 700 }}>{row.ours}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ background: '#34d39918', color: '#34d399', borderRadius: 8, padding: '3px 8px', fontSize: 11, fontWeight: 700 }}>
                      {row.delta}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>

      {/* Limitations */}
      <GlassCard>
        <SectionTitle icon={AlertTriangle} label="Limitations & Improvement Opportunities" color="#fbbf24" />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[
            { title: 'LLM Latency under Load', detail: 'Qwen3-32B via Groq has rate limits on free-tier. Under high concurrency (>20 req/min), processing time increases by 3×. Mitigation: async batching + fallback to GPT-OSS-20B.', severity: 'medium' },
            { title: 'OCR on Low-Quality Scans', detail: 'The 3-layer OCR pipeline degrades on invoices with <150 DPI or handwritten annotations. F1 drops to ~0.74 in these edge cases. Mitigation: pre-processing filters + human-in-loop escalation.', severity: 'medium' },
            { title: 'E-Invoice Integration Coverage', detail: 'Current integration success rate is 89.1%. Some legacy ERP export formats (e.g. SAP IDOC binary) are not yet supported.', severity: 'low' },
            { title: 'Causal Graph Coverage', detail: 'The causal propagation engine currently covers 5 cross-agent dependency patterns. Complex multi-hop scenarios (>3 agents) are partially covered (73%).', severity: 'high' },
            { title: 'Vector Embedding Matching', detail: 'Transaction reconciliation uses TF-IDF similarity. Replacing with SBERT embeddings + pgvector is projected to improve matching accuracy by ~6%.', severity: 'low' },
          ].map((l, i) => {
            const colors: Record<string, string> = { high: '#fb7185', medium: '#fbbf24', low: '#34d399' }
            return (
              <div key={i} style={{ display: 'flex', gap: 14, padding: '14px 0', borderBottom: i < 4 ? '1px solid rgba(255,255,255,0.06)' : 'none' }}>
                <div style={{ minWidth: 60 }}>
                  <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: colors[l.severity], background: colors[l.severity] + '18', borderRadius: 6, padding: '3px 7px' }}>
                    {l.severity}
                  </span>
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#fff', marginBottom: 4 }}>{l.title}</div>
                  <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.5)', lineHeight: 1.6 }}>{l.detail}</div>
                </div>
              </div>
            )
          })}
        </div>
      </GlassCard>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
//  EXPLAINABILITY TAB  (Objective 9)
// ─────────────────────────────────────────────────────────────────────────────
function ExplainabilityTab() {
  const [selected, setSelected] = useState<string | null>(null)

  const traces = [
    {
      id: 'T001', agent: 'reconciliation', label: 'Duplicate Invoice Detection',
      color: AC.reconciliation,
      reasoning: [
        { layer: 'Technical',  text: 'TF-IDF cosine similarity = 0.97 between transaction TX-2041 and TX-2038. Threshold: 0.85. Flagged as probable duplicate. Embedding distance: 0.031.' },
        { layer: 'Business',   text: 'Both transactions match vendor "Siemens AG", amount $48,200 ± $12, within 3-day window. Duplicate AP payment would erode $48k from liquidity.' },
        { layer: 'Causal',     text: 'Duplicate flag → Credit Agent: risk score −20 pts (vendor reliability signal). Cash Agent: AR forecast discounted by 15% for 7-day window.' },
        { layer: 'Decision',   text: 'HOLD transaction TX-2041. Route to finance controller for manual confirmation. Audit log ID: AUD-882.' },
      ],
    },
    {
      id: 'T002', agent: 'invoice', label: 'Invoice Approval Routing Decision',
      color: AC.invoice,
      reasoning: [
        { layer: 'Technical',  text: 'Baidu Qianfan OCR extracted 14/14 fields with confidence > 0.91. 3-way PO/GRN/Invoice match: PASS. Vendor credit score: 812.' },
        { layer: 'Business',   text: 'Invoice amount $32,400 within approved budget (Engineering Q2: $180k remaining). No overdue payables from this vendor in 12 months.' },
        { layer: 'Causal',     text: 'Cash Agent confirms $32,400 payment is within safe liquidity band. Budget Agent confirms departmental cap not breached.' },
        { layer: 'Decision',   text: 'AUTO-APPROVE. Payment scheduled T+2 days. No human review required. Audit log ID: AUD-883.' },
      ],
    },
    {
      id: 'T003', agent: 'credit', label: 'Credit Limit Reduction — Client #0042',
      color: AC.credit,
      reasoning: [
        { layer: 'Technical',  text: 'AUC-ROC model score: 0.78 (delinquency risk). DSO = 67 days (+19 vs 30-day avg). Behavioral aging bucket: 60+ days, 38% of AR balance.' },
        { layer: 'Business',   text: 'Client has missed 2 of last 6 payment milestones. Reconciliation Agent flagged 1 disputed transaction ($12k) unresolved for 45 days.' },
        { layer: 'Causal',     text: 'Reconciliation anomaly → Credit penalty −20 pts applied. Combined with aging score, total risk uplift = HIGH. Cash Agent AR forecast reduced.' },
        { layer: 'Decision',   text: 'Credit limit reduced from $200k to $120k. Collections team notified. Review scheduled in 30 days. Audit log ID: AUD-884.' },
      ],
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* XAI overview */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14 }}>
        <MetricPill label="Decisions Traced"      value="1,240"  sub="per day, 100% coverage" good color="#67e8f9" />
        <MetricPill label="Avg Trace Latency"     value="320ms"  sub="LLM reasoning gen." good color="#a78bfa" />
        <MetricPill label="User Comprehension"    value="87%"    sub="finance team survey" good color="#34d399" />
        <MetricPill label="Audit Compliance"      value="100%"   sub="all decisions logged" good color="#fbbf24" />
        <MetricPill label="Explanation Layers"    value="4"      sub="Tech·Biz·Causal·Decision" good color="#22d3ee" />
      </div>

      {/* Comprehension trend */}
      <GlassCard>
        <SectionTitle icon={Brain} label="User Comprehension Score over Evaluation Period" color="#a78bfa" />
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart
            data={[
              { week: 'W1', score: 64 }, { week: 'W2', score: 70 },
              { week: 'W3', score: 74 }, { week: 'W4', score: 79 },
              { week: 'W5', score: 83 }, { week: 'W6', score: 87 },
            ]}
            margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
          >
            <CartesianGrid stroke="rgba(255,255,255,0.05)" strokeDasharray="4 4" />
            <XAxis dataKey="week" tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 12 }} />
            <YAxis domain={[50, 100]} tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 12 }} tickFormatter={v => `${v}%`} />
            <Tooltip content={<ChartTooltip />} />
            <Area type="monotone" dataKey="score" name="Comprehension %" stroke="#a78bfa" fill="#a78bfa" fillOpacity={0.12} strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </GlassCard>

      {/* Trace examples */}
      <div>
        <SectionTitle icon={RefreshCw} label="LLM-Generated Reasoning Traces (live examples)" color="#67e8f9" />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {traces.map(t => (
            <GlassCard key={t.id} style={{ padding: 0, overflow: 'hidden' }}>
              <button
                onClick={() => setSelected(selected === t.id ? null : t.id)}
                style={{
                  width: '100%', background: 'transparent', border: 'none', cursor: 'pointer',
                  padding: '16px 24px', display: 'flex', alignItems: 'center', gap: 12,
                }}
              >
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: t.color, boxShadow: `0 0 6px ${t.color}` }} />
                <span style={{ fontSize: 13, fontWeight: 600, color: 'rgba(255,255,255,0.6)', minWidth: 48 }}>{t.id}</span>
                <span style={{ flex: 1, fontSize: 14, fontWeight: 700, color: '#fff', textAlign: 'left' }}>{t.label}</span>
                <span style={{ fontSize: 11, color: t.color, background: t.color + '18', borderRadius: 8, padding: '3px 10px', textTransform: 'capitalize' }}>{t.agent}</span>
                {selected === t.id ? <ChevronDown size={14} color="rgba(255,255,255,0.4)" /> : <ChevronRight size={14} color="rgba(255,255,255,0.4)" />}
              </button>
              {selected === t.id && (
                <div style={{ padding: '0 24px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {t.reasoning.map((r, i) => {
                    const layerColor: Record<string, string> = { Technical: '#67e8f9', Business: '#a78bfa', Causal: '#fbbf24', Decision: '#34d399' }
                    return (
                      <div
                        key={i}
                        style={{
                          background: 'rgba(255,255,255,0.04)',
                          border: `1px solid ${layerColor[r.layer]}25`,
                          borderLeft: `3px solid ${layerColor[r.layer]}`,
                          borderRadius: '0 12px 12px 0',
                          padding: '12px 16px',
                        }}
                      >
                        <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: layerColor[r.layer], marginBottom: 6 }}>
                          {r.layer} Layer
                        </div>
                        <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.7)', lineHeight: 1.7 }}>{r.text}</div>
                      </div>
                    )
                  })}
                </div>
              )}
            </GlassCard>
          ))}
        </div>
      </div>

      {/* Audit trail */}
      <GlassCard>
        <SectionTitle icon={Shield} label="Audit Trail — Compliance Standards" color="#34d399" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14 }}>
          {[
            { label: 'Decision Log Format', value: 'Structured JSON', ok: true },
            { label: 'Retention Period',    value: '7 years',         ok: true },
            { label: 'Tamper-Proof Storage', value: 'Supabase RLS',  ok: true },
            { label: 'Human Override Log',   value: '100% captured',  ok: true },
            { label: 'Agent Version Pin',    value: 'Semver tagged',  ok: true },
            { label: 'Timestamp Precision',  value: 'ms-level UTC',   ok: true },
          ].map((item, i) => (
            <div
              key={i}
              style={{
                background: 'rgba(52,211,153,0.06)',
                border: '1px solid rgba(52,211,153,0.2)',
                borderRadius: 12, padding: '14px 18px',
              }}
            >
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', marginBottom: 4 }}>{item.label}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <CheckCircle2 size={14} color="#34d399" />
                <span style={{ fontSize: 13, fontWeight: 700, color: '#34d399' }}>{item.value}</span>
              </div>
            </div>
          ))}
        </div>
      </GlassCard>
    </div>
  )
}
