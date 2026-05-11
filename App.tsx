import { useState } from 'react'
import {
  ChevronRight
} from 'lucide-react'
import InvoiceView from './components/InvoiceView'
import CashView from './components/CashView'
import BudgetView from './components/BudgetView'
import ReconciliationView from './components/ReconciliationView'
import CreditView from './components/CreditView'
import OverviewView from './components/OverviewView'
import EvaluationView from './components/EvaluationView'
import VideoBackground from './components/VideoBackground'
import { getAgentAvatar, getLegacyAgentAvatar } from './components/Shared'
import './index.css'

type Tab = 'overview' | 'invoice' | 'cash' | 'budget' | 'reconciliation' | 'credit' | 'evaluation'

const NAV: { id: Tab; label: string; desc: string }[] = [
  { id: 'overview',       label: 'Overview',       desc: 'System status' },
  { id: 'invoice',        label: 'Invoice',        desc: 'OCR · approval' },
  { id: 'cash',           label: 'Cash',           desc: 'Liquidity gate' },
  { id: 'budget',         label: 'Budget',         desc: 'Spend control' },
  { id: 'reconciliation', label: 'Reconciliation', desc: 'TX matching' },
  { id: 'credit',         label: 'Credit',         desc: 'Risk scoring' },
  { id: 'evaluation',     label: 'Evaluation',     desc: 'Metrics & eval' },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('overview')

  return (
    <>
    <div style={{ position: 'fixed', inset: 0, zIndex: 0 }}>
      <VideoBackground />
    </div>
    <div className="layout" style={{ position: 'relative', zIndex: 1 }}>
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-icon">
            <img
              className="brand-logo-img"
              src="/assets/brand-logo.png"
              alt="FAgentLLM Logo"
            />
          </div>
          <div>
            <div className="brand-name">FAgentLLM</div>
            <div className="brand-sub">Financial Intelligence</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {NAV.map(n => (
            <button
              key={n.id}
              className={`nav-item ${tab === n.id ? 'active' : ''}`}
              onClick={() => setTab(n.id)}
            >
              <span className="nav-icon" style={{ minWidth: '40px', minHeight: '40px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <img
                  className="nav-avatar"
                  src={getAgentAvatar(n.id)}
                  alt={`${n.label} avatar`}
                  style={{ width: '40px', height: '40px', objectFit: 'contain' }}
                  onError={(e) => { e.currentTarget.src = getLegacyAgentAvatar(n.id) }}
                />
              </span>
              <span className="nav-text">
                <span className="nav-label">{n.label}</span>
                <span className="nav-desc">{n.desc}</span>
              </span>
              {tab === n.id && <ChevronRight size={14} className="nav-arrow" />}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="system-live">System live</div>
          <div>LangGraph · Supabase<br />Qwen3-32B · Baidu OCR</div>
        </div>
      </aside>

      <main className="main">
        {tab === 'overview'       && <OverviewView onNavigate={(id) => setTab(id as Tab)} />}
        {tab === 'invoice'        && <InvoiceView />}
        {tab === 'cash'           && <CashView />}
        {tab === 'budget'         && <BudgetView />}
        {tab === 'reconciliation' && <ReconciliationView />}
        {tab === 'credit'         && <CreditView />}
        {tab === 'evaluation'     && <EvaluationView />}
      </main>
    </div>
    </>
  )
}
