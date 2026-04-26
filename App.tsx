import { useState } from 'react'
import {
  FileText, DollarSign, RefreshCw, Users, TrendingUp, ChevronRight, Activity, Zap
} from 'lucide-react'
import InvoiceView from './components/InvoiceView'
import CashView from './components/CashView'
import BudgetView from './components/BudgetView'
import ReconciliationView from './components/ReconciliationView'
import CreditView from './components/CreditView'
import './index.css'

type Tab = 'invoice' | 'cash' | 'budget' | 'reconciliation' | 'credit'

const NAV: { id: Tab; label: string; icon: React.ReactNode; desc: string }[] = [
  { id: 'invoice',        label: 'Invoice',        icon: <FileText size={18} />,    desc: 'OCR + approval' },
  { id: 'cash',           label: 'Cash',           icon: <DollarSign size={18} />,  desc: 'Liquidity gate' },
  { id: 'budget',         label: 'Budget',         icon: <TrendingUp size={18} />,  desc: 'Spend control' },
  { id: 'reconciliation', label: 'Reconciliation', icon: <RefreshCw size={18} />,   desc: 'TX matching' },
  { id: 'credit',         label: 'Credit',         icon: <Users size={18} />,       desc: 'Risk scoring' },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('invoice')

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-icon"><Zap size={18} /></div>
          <div>
            <div className="brand-name">FAgentLLM</div>
            <div className="brand-sub">Financial Intelligence</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {NAV.map(n => (
            <button key={n.id} className={`nav-item ${tab === n.id ? 'active' : ''}`}
              onClick={() => setTab(n.id)}>
              <span className="nav-icon">{n.icon}</span>
              <span className="nav-text">
                <span className="nav-label">{n.label}</span>
                <span className="nav-desc">{n.desc}</span>
              </span>
              {tab === n.id && <ChevronRight size={14} className="nav-arrow" />}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <Activity size={12} color="#22c55e" />
            <span style={{ fontSize: 11, color: '#22c55e', fontWeight: 500 }}>System live</span>
          </div>
          <div style={{ fontSize: 10, color: '#64748b', lineHeight: 1.4 }}>
            LangGraph · Supabase<br />Qwen3-32B · Baidu OCR
          </div>
        </div>
      </aside>

      <main className="main">
        {tab === 'invoice'        && <InvoiceView />}
        {tab === 'cash'           && <CashView />}
        {tab === 'budget'         && <BudgetView />}
        {tab === 'reconciliation' && <ReconciliationView />}
        {tab === 'credit'         && <CreditView />}
      </main>
    </div>
  )
}
