import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import MetricCard from '../components/MetricCard'
import DataTable from '../components/DataTable'
import LoadingSpinner from '../components/LoadingSpinner'
import PnlText from '../components/PnlText'
import StatusBadge from '../components/StatusBadge'
import ActivityFeed from '../components/ActivityFeed'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts'

export default function Dashboard() {
  const queryClient = useQueryClient()
  const { data: status, isLoading: statusLoading } = useQuery({ queryKey: ['status'], queryFn: api.getStatus, refetchInterval: 60000 })
  const { data: openTrades } = useQuery({ queryKey: ['shadow-open'], queryFn: api.getOpenTrades, refetchInterval: 60000 })
  const { data: closedData } = useQuery({ queryKey: ['shadow-closed'], queryFn: () => api.getClosedTrades(30), refetchInterval: 60000 })
  const { data: training } = useQuery({ queryKey: ['training-status'], queryFn: api.getTrainingStatus, refetchInterval: 60000 })
  const { data: packets } = useQuery({ queryKey: ['packets'], queryFn: () => api.getPackets({ days: 1 }), refetchInterval: 60000 })
  const { data: haltData } = useQuery({ queryKey: ['halt-status'], queryFn: api.getHaltStatus, refetchInterval: 30000 })
  const { data: auditData } = useQuery({ queryKey: ['audit-latest'], queryFn: api.getLatestAudit, refetchInterval: 60000 })
  const { data: ctoData } = useQuery({ queryKey: ['cto-report'], queryFn: () => api.getCtoReport(7), refetchInterval: 60000 })

  const [toast, setToast] = useState(null)
  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(null), 3000) }

  const haltMutation = useMutation({
    mutationFn: () => haltData?.halted ? api.resumeTrading() : api.haltTrading(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['halt-status'] }),
  })

  const scanMutation = useMutation({
    mutationFn: api.triggerActionScan,
    onSuccess: () => showToast('Scan started...'),
    onError: (e) => showToast(`Scan failed: ${e.message}`),
  })
  const ctoMutation = useMutation({
    mutationFn: api.triggerCtoReport,
    onSuccess: () => showToast('CTO report generating...'),
    onError: (e) => showToast(`CTO report failed: ${e.message}`),
  })
  const collectMutation = useMutation({
    mutationFn: api.triggerCollectTraining,
    onSuccess: () => showToast('Training data collection started...'),
    onError: (e) => showToast(`Collection failed: ${e.message}`),
  })

  const isHalted = haltData?.halted || false
  const auditAssessment = auditData?.overall_assessment || auditData?.audit?.overall_assessment
  const auditSummary = auditData?.summary || auditData?.audit?.summary

  if (statusLoading) return <LoadingSpinner />

  const equity = status?.alpaca_equity || 0
  const equityDelta = equity - 100000

  // Build cumulative P&L chart data
  const chartData = (closedData?.trades || [])
    .filter(t => t.pnl_dollars != null)
    .reverse()
    .reduce((acc, t, i) => {
      const prev = acc.length > 0 ? acc[acc.length - 1].cumPnl : 0
      acc.push({ date: (t.created_at || '').slice(5, 10), cumPnl: prev + (t.pnl_dollars || 0) })
      return acc
    }, [])

  const tradeColumns = [
    { key: 'ticker', label: 'Ticker', type: 'text' },
    { key: 'entry_price', label: 'Entry', type: 'currency' },
    { key: 'current_price', label: 'Current', type: 'currency' },
    { key: 'pnl_dollars', label: 'P&L', type: 'currency' },
    { key: 'duration_days', label: 'Days', type: 'number' },
    { key: 'stop_price', label: 'Stop', type: 'currency' },
    { key: 'target_1', label: 'Target', type: 'currency' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-medium">Dashboard</h2>
        <button
          onClick={() => {
            if (isHalted || confirm('Are you sure? This stops all new trades.')) {
              haltMutation.mutate()
            }
          }}
          className={`px-4 py-2 rounded-lg font-medium text-sm ${
            isHalted
              ? 'bg-green-600 hover:bg-green-700 text-white'
              : 'bg-red-600 hover:bg-red-700 text-white'
          }`}
        >
          {isHalted ? 'RESUME TRADING' : 'HALT TRADING'}
        </button>
      </div>

      {/* Halt warning banner */}
      {isHalted && (
        <div className="bg-red-900/30 border border-red-500/50 rounded-lg p-3 text-red-300 text-sm">
          Trading is HALTED. No new positions will be opened. Click "Resume Trading" to resume.
        </div>
      )}

      {/* Audit warning banner */}
      {auditAssessment && auditAssessment !== 'green' && (
        <div className={`border rounded-lg p-3 text-sm ${
          auditAssessment === 'red'
            ? 'bg-red-900/30 border-red-500/50 text-red-300'
            : 'bg-yellow-900/30 border-yellow-500/50 text-yellow-300'
        }`}>
          <span className="font-medium uppercase">Audit: {auditAssessment}</span>
          {auditSummary && <span className="ml-2">— {auditSummary.slice(0, 200)}</span>}
        </div>
      )}

      {/* Toast notification */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 bg-[var(--bg-card)] border border-[var(--border)] rounded-lg px-4 py-2 text-sm shadow-lg">
          {toast}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs text-[var(--text-muted)] uppercase tracking-wide mr-2">Actions</span>
        <button onClick={() => scanMutation.mutate()} disabled={scanMutation.isPending}
          className="px-3 py-1.5 text-xs rounded-md bg-[var(--bg-tertiary)] border border-[var(--border)] hover:border-[var(--blue)] disabled:opacity-50">
          {scanMutation.isPending ? 'Scanning...' : 'Run Scan'}
        </button>
        <button onClick={() => ctoMutation.mutate()} disabled={ctoMutation.isPending}
          className="px-3 py-1.5 text-xs rounded-md bg-[var(--bg-tertiary)] border border-[var(--border)] hover:border-[var(--blue)] disabled:opacity-50">
          {ctoMutation.isPending ? 'Generating...' : 'Generate CTO Report'}
        </button>
        <button onClick={() => collectMutation.mutate()} disabled={collectMutation.isPending}
          className="px-3 py-1.5 text-xs rounded-md bg-[var(--bg-tertiary)] border border-[var(--border)] hover:border-[var(--blue)] disabled:opacity-50">
          {collectMutation.isPending ? 'Collecting...' : 'Collect Training Data'}
        </button>
      </div>

      {/* Headline KPIs */}
      {(() => {
        const kpis = ctoData?.headline_kpis || {}
        const ts = ctoData?.trade_summary || {}
        const hasTrades = (ts.trades_closed || 0) >= 5
        return (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-3">
              <div className="text-xs text-[var(--text-muted)]">Sharpe ratio</div>
              <div className={`text-xl font-mono font-medium ${hasTrades ? ((kpis.sharpe_ratio || 0) > 0.5 ? 'text-emerald-400' : (kpis.sharpe_ratio || 0) < 0 ? 'text-red-400' : '') : ''}`}>
                {hasTrades ? (kpis.sharpe_ratio || 0).toFixed(2) : '--'}
              </div>
            </div>
            <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-3">
              <div className="text-xs text-[var(--text-muted)]">Win rate</div>
              <div className={`text-xl font-mono font-medium ${hasTrades ? ((kpis.win_rate || 0) > 0.45 ? 'text-emerald-400' : 'text-red-400') : ''}`}>
                {hasTrades ? `${((kpis.win_rate || 0) * 100).toFixed(1)}%` : '--'}
              </div>
            </div>
            <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-3">
              <div className="text-xs text-[var(--text-muted)]">Max drawdown</div>
              <div className={`text-xl font-mono font-medium ${hasTrades ? ((kpis.max_drawdown_pct || 0) < 15 ? 'text-emerald-400' : 'text-red-400') : ''}`}>
                {hasTrades ? `${(kpis.max_drawdown_pct || 0).toFixed(1)}%` : '--'}
              </div>
            </div>
            <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-3">
              <div className="text-xs text-[var(--text-muted)]">Confidence cal.</div>
              <div className="text-xl font-mono font-medium">
                {(ts.trades_closed || 0) >= 10 ? (kpis.confidence_calibration || 0).toFixed(3) : '--'}
              </div>
            </div>
            <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-3">
              <div className="text-xs text-[var(--text-muted)]">Rubric score</div>
              <div className="text-xl font-mono font-medium">
                {kpis.avg_rubric_score != null ? `${kpis.avg_rubric_score.toFixed(1)}/5` : 'n/a'}
              </div>
            </div>
          </div>
        )
      })()}

      {/* System status cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard label="Shadow Equity" value={equity.toLocaleString(undefined, { minimumFractionDigits: 0 })} prefix="$" delta={equityDelta} />
        <MetricCard label="Open Trades" value={openTrades?.open_count || 0} />
        <MetricCard label="Win Rate" value={closedData?.metrics?.win_rate != null ? `${closedData.metrics.win_rate.toFixed(1)}%` : '--'} />
        <MetricCard label="Model Version" value={status?.model_version || 'base'} delta={training ? `${training.dataset_total} examples` : null} />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3 bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4">
          <h3 className="text-sm text-[var(--text-muted)] uppercase tracking-wide mb-4">Cumulative P&L</h3>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={chartData}>
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
                <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
                <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                <Area type="monotone" dataKey="cumPnl" stroke="var(--green)" fill="var(--green)" fillOpacity={0.1} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-center text-[var(--text-muted)] py-12 text-sm">No closed trades yet</div>
          )}
        </div>
        <div className="lg:col-span-2 bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4">
          <h3 className="text-sm text-[var(--text-muted)] uppercase tracking-wide mb-4">Training Progress</h3>
          {training && (
            <div className="space-y-3 text-sm">
              <div className="flex justify-between"><span className="text-[var(--text-secondary)]">Model</span><span>{training.model_name}</span></div>
              <div className="flex justify-between"><span className="text-[var(--text-secondary)]">Examples</span><span className="font-mono">{training.dataset_total}</span></div>
              <div className="flex justify-between"><span className="text-[var(--text-secondary)]">New</span><span className="font-mono">{training.new_since_last_train}</span></div>
              <div className="flex justify-between"><span className="text-[var(--text-secondary)]">Status</span>
                <StatusBadge text={training.train_queued ? 'Queued' : 'Collecting'} variant={training.train_queued ? 'warning' : 'info'} />
              </div>
              <div className="mt-2">
                <div className="h-2 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
                  <div className="h-full bg-[var(--blue)] rounded-full" style={{ width: `${Math.min(100, (training.new_since_last_train / 50) * 100)}%` }} />
                </div>
                <div className="text-xs text-[var(--text-muted)] mt-1">{training.new_since_last_train}/50 to next training</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Live Activity Feed */}
      <ActivityFeed />

      {/* Open trades table */}
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-sm text-[var(--text-muted)] uppercase tracking-wide mb-4">Open Shadow Trades</h3>
        <DataTable columns={tradeColumns} data={openTrades?.open_trades || []} />
      </div>

      {/* Today's packets */}
      {packets && packets.length > 0 && (
        <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4">
          <h3 className="text-sm text-[var(--text-muted)] uppercase tracking-wide mb-4">Today's Packets ({packets.length})</h3>
          <div className="space-y-3">
            {packets.slice(0, 5).map((p, i) => (
              <div key={i} className="border border-[var(--border)] rounded p-3">
                <div className="flex items-center gap-3 mb-1">
                  <span className="font-medium">{p.ticker}</span>
                  <span className="text-[var(--text-secondary)] text-sm">{p.company_name}</span>
                  <StatusBadge text={`Score: ${p.priority_score || 0}`} variant="info" />
                </div>
                <p className="text-sm text-[var(--text-secondary)]">{(p.thesis_text || '').slice(0, 200)}...</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
