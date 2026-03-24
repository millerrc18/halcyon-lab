import { Outlet, NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { LayoutDashboard, FileText, TrendingUp, Brain, ClipboardCheck, BarChart3, Settings, Activity } from 'lucide-react'
import StatusBadge from './StatusBadge'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/packets', icon: FileText, label: 'Packets' },
  { to: '/shadow', icon: TrendingUp, label: 'Shadow Ledger' },
  { to: '/training', icon: Brain, label: 'Training' },
  { to: '/review', icon: ClipboardCheck, label: 'Review' },
  { to: '/cto-report', icon: BarChart3, label: 'CTO Report' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Layout() {
  const { data: status } = useQuery({ queryKey: ['status'], queryFn: api.getStatus })

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 bg-[var(--bg-secondary)] border-r border-[var(--border)] flex flex-col shrink-0">
        <div className="p-4 border-b border-[var(--border)]">
          <h1 className="text-lg font-medium text-[var(--text-primary)]">Halcyon Lab</h1>
          <div className="text-xs text-[var(--text-muted)] mt-1">AI Research Desk</div>
        </div>
        <nav className="flex-1 py-2">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2 text-sm ${isActive ? 'text-[var(--text-primary)] bg-[var(--bg-tertiary)]' : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)]/50'}`
              }>
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        {status && (
          <div className="p-4 border-t border-[var(--border)] text-xs space-y-1">
            <div className="flex justify-between">
              <span className="text-[var(--text-muted)]">LLM</span>
              <StatusBadge text={status.ollama_available ? 'Online' : 'Offline'} variant={status.ollama_available ? 'success' : 'danger'} />
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--text-muted)]">Model</span>
              <span className="text-[var(--text-secondary)]">{status.model_version}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--text-muted)]">Shadow</span>
              <StatusBadge text={status.shadow_trading_enabled ? 'Active' : 'Off'} variant={status.shadow_trading_enabled ? 'success' : 'neutral'} />
            </div>
          </div>
        )}
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto p-6">
        <Outlet />
      </main>
    </div>
  )
}
