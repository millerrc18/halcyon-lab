import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import MetricCard from '../components/MetricCard'
import DataTable from '../components/DataTable'
import LoadingSpinner from '../components/LoadingSpinner'
import EmptyState from '../components/EmptyState'
import { TrendingUp } from 'lucide-react'

export default function ShadowLedger() {
  const [tab, setTab] = useState('open')
  const { data: openData, isLoading: openLoading } = useQuery({ queryKey: ['shadow-open'], queryFn: api.getOpenTrades, refetchInterval: 30000 })
  const { data: closedData, isLoading: closedLoading } = useQuery({ queryKey: ['shadow-closed'], queryFn: () => api.getClosedTrades(30), refetchInterval: 30000 })

  const openCols = [
    { key: 'ticker', label: 'Ticker', type: 'text' },
    { key: 'entry_price', label: 'Entry', type: 'currency' },
    { key: 'current_price', label: 'Current', type: 'currency' },
    { key: 'pnl_dollars', label: 'P&L', type: 'currency' },
    { key: 'pnl_pct', label: 'P&L %', type: 'percent' },
    { key: 'duration_days', label: 'Days', type: 'number' },
    { key: 'stop_price', label: 'Stop', type: 'currency' },
    { key: 'target_1', label: 'Target 1', type: 'currency' },
  ]

  const closedCols = [
    { key: 'ticker', label: 'Ticker', type: 'text' },
    { key: 'entry_price', label: 'Entry', type: 'currency' },
    { key: 'pnl_dollars', label: 'P&L', type: 'currency' },
    { key: 'pnl_pct', label: 'P&L %', type: 'percent' },
    { key: 'duration_days', label: 'Days', type: 'number' },
    { key: 'exit_reason', label: 'Exit Reason', type: 'text' },
  ]

  const metrics = closedData?.metrics || {}

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-medium" style={{ color: 'var(--slate-100)' }}>Shadow Ledger</h2>

      {/* Account summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard label="Equity" value={(openData?.account_equity || 0).toLocaleString()} prefix="$" />
        <MetricCard label="Open Positions" value={openData?.open_count || 0} />
        <MetricCard label="Unrealized P&L" value={(openData?.total_unrealized_pnl || 0).toFixed(2)} prefix="$" delta={openData?.total_unrealized_pnl} />
        <MetricCard label="Win Rate" value={metrics.win_rate != null ? `${metrics.win_rate.toFixed(1)}%` : '--'} />
      </div>

      {/* Tab bar */}
      <div className="flex gap-1" style={{ borderBottom: '1px solid var(--slate-600)' }}>
        {['open', 'closed'].map(t => (
          <button key={t} onClick={() => setTab(t)}
            className="px-4 py-2 text-sm capitalize transition-colors"
            style={{
              color: tab === t ? 'var(--slate-50)' : 'var(--slate-400)',
              borderBottom: tab === t ? '2px solid var(--teal-400)' : '2px solid transparent',
            }}>
            {t} {t === 'open' ? `(${openData?.open_count || 0})` : `(${closedData?.trades?.length || 0})`}
          </button>
        ))}
      </div>

      {tab === 'open' ? (
        <div className="rounded-lg p-4" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
          {openLoading ? <LoadingSpinner /> :
           !openData?.open_trades?.length ? <EmptyState message="No open trades" icon={TrendingUp} /> :
           <DataTable columns={openCols} data={openData.open_trades} />}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <MetricCard label="Total Trades" value={metrics.total_trades || 0} />
            <MetricCard label="Avg Gain" value={(metrics.avg_gain || 0).toFixed(2)} prefix="$" />
            <MetricCard label="Avg Loss" value={(metrics.avg_loss || 0).toFixed(2)} prefix="$" />
            <MetricCard label="Expectancy" value={(metrics.expectancy || 0).toFixed(2)} prefix="$" delta={metrics.expectancy} />
            <MetricCard label="Total P&L" value={(metrics.total_pnl || 0).toFixed(2)} prefix="$" delta={metrics.total_pnl} />
          </div>
          <div className="rounded-lg p-4" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
            {closedLoading ? <LoadingSpinner /> :
             !closedData?.trades?.length ? <EmptyState message="No closed trades" icon={TrendingUp} /> :
             <DataTable columns={closedCols} data={closedData.trades} />}
          </div>
        </div>
      )}
    </div>
  )
}
