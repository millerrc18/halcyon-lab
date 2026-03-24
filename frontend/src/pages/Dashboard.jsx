import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import MetricCard from '../components/MetricCard'
import DataTable from '../components/DataTable'
import LoadingSpinner from '../components/LoadingSpinner'
import PnlText from '../components/PnlText'
import StatusBadge from '../components/StatusBadge'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts'

export default function Dashboard() {
  const queryClient = useQueryClient()
  const { data: status, isLoading: statusLoading } = useQuery({ queryKey: ['status'], queryFn: api.getStatus })
  const { data: openTrades } = useQuery({ queryKey: ['shadow-open'], queryFn: api.getOpenTrades })
  const { data: closedData } = useQuery({ queryKey: ['shadow-closed'], queryFn: () => api.getClosedTrades(30) })
  const { data: training } = useQuery({ queryKey: ['training-status'], queryFn: api.getTrainingStatus })
  const { data: packets } = useQuery({ queryKey: ['packets'], queryFn: () => api.getPackets({ days: 1 }) })
  const { data: haltData } = useQuery({ queryKey: ['halt-status'], queryFn: api.getHaltStatus, refetchInterval: 30000 })
  const { data: auditData } = useQuery({ queryKey: ['audit-latest'], queryFn: api.getLatestAudit })

  const haltMutation = useMutation({
    mutationFn: () => haltData?.halted ? api.resumeTrading() : api.haltTrading(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['halt-status'] }),
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

      {/* Metric cards */}
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
