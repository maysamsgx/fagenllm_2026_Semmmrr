import { useState } from 'react'
import {
  ChevronRight
} from 'lucide-react'
import InvoiceView from './components/InvoiceView'
import CashView from './components/CashView'
import BudgetView from './components/BudgetView'
import ReconciliationView from './components/ReconciliationView'
import CreditView from './components/CreditView'
import VideoBackground from './components/VideoBackground'
import { getAgentAvatar, getLegacyAgentAvatar } from './components/Shared'
import './index.css'

type Tab = 'invoice' | 'cash' | 'budget' | 'reconciliation' | 'credit'

const NAV: { id: Tab; label: string; desc: string }[] = [
  { id: 'invoice',        label: 'Invoice',        desc: 'OCR · approval' },
  { id: 'cash',           label: 'Cash',           desc: 'Liquidity gate' },
  { id: 'budget',         label: 'Budget',         desc: 'Spend control' },
  { id: 'reconciliation', label: 'Reconciliation', desc: 'TX matching' },
  { id: 'credit',         label: 'Credit',         desc: 'Risk scoring' },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('invoice')

  return (
    <>
    <div style={{ position: 'fixed', inset: 0, zIndex: 0 }}>
      <VideoBackground />
    </div>
    <div className="layout" style={{ position: 'relative', zIndex: 1 }}>
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-icon">
            <video
              className="brand-logo-img"
              src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260424_090051_64ea5059-da6b-492b-a171-aa7ecc767dc3.mp4"
              autoPlay
              loop
              muted
              playsInline
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
              <span className="nav-icon">
                <img
                  className="nav-avatar"
                  src={getAgentAvatar(n.id)}
                  alt={`${n.label} avatar`}
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
        {tab === 'invoice'        && <InvoiceView />}
        {tab === 'cash'           && <CashView />}
        {tab === 'budget'         && <BudgetView />}
        {tab === 'reconciliation' && <ReconciliationView />}
        {tab === 'credit'         && <CreditView />}
      </main>
    </div>
    </>
  )
}
