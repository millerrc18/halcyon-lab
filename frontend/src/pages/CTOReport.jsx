import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import LoadingSpinner from '../components/LoadingSpinner'
import EmptyState from '../components/EmptyState'
import MetricCard from '../components/MetricCard'

export default function CTOReport() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['cto-report'],
    queryFn: () => fetch('/api/cto-report?days=7').then(r => r.json()),
    refetchInterval: 60000,
  })

  if (isLoading) return <LoadingSpinner />
  if (error) return (
    <div className="text-center py-12">
      <p className="text-red-400 mb-4">Failed to load CTO report</p>
      <button onClick={() => window.location.reload()}
        className="px-4 py-2 bg-blue-600 text-white rounded text-sm">Retry</button>
    </div>
  )
  if (!data) return <EmptyState message="No report data available" />

  const period = data.report_period || {}
  const perf = data.performance || {}
  const risk = data.risk_metrics || {}

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-medium text-[var(--text-primary)]">CTO Performance Report</h1>
          <p className="text-sm text-[var(--text-muted)]">
            {period.start} to {period.end}
          </p>
        </div>
        <button
          onClick={() => {
            navigator.clipboard.writeText(JSON.stringify(data, null, 2))
          }}
          className="px-3 py-1.5 text-xs bg-[var(--bg-tertiary)] border border-[var(--border)] rounded hover:bg-[var(--bg-secondary)]"
        >
          Copy JSON
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <MetricCard label="Total Trades" value={perf.total_trades || 0} />
        <MetricCard label="Win Rate" value={perf.win_rate ? `${perf.win_rate.toFixed(0)}%` : 'n/a'} />
        <MetricCard label="Expectancy" value={perf.expectancy ? `$${perf.expectancy.toFixed(2)}` : 'n/a'} />
        <MetricCard label="Total P&L" value={perf.total_pnl ? `$${perf.total_pnl.toFixed(2)}` : 'n/a'} />
      </div>

      {data.score_band_performance && (
        <div className="mb-6">
          <h2 className="text-sm font-medium text-[var(--text-secondary)] mb-3">Performance by Score Band</h2>
          <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  <th className="text-left p-3 text-[var(--text-muted)]">Score Band</th>
                  <th className="text-right p-3 text-[var(--text-muted)]">Trades</th>
                  <th className="text-right p-3 text-[var(--text-muted)]">Win Rate</th>
                  <th className="text-right p-3 text-[var(--text-muted)]">Avg P&L</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.score_band_performance).map(([band, stats]) => (
                  <tr key={band} className="border-b border-[var(--border)]/50">
                    <td className="p-3 text-[var(--text-primary)]">{band}</td>
                    <td className="p-3 text-right">{stats.count || 0}</td>
                    <td className="p-3 text-right">{stats.win_rate ? `${stats.win_rate.toFixed(0)}%` : 'n/a'}</td>
                    <td className={`p-3 text-right ${(stats.avg_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {stats.avg_pnl ? `$${stats.avg_pnl.toFixed(2)}` : 'n/a'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {data.recommendations && data.recommendations.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-[var(--text-secondary)] mb-3">Recommendations</h2>
          <ul className="space-y-2">
            {data.recommendations.map((rec, i) => (
              <li key={i} className="text-sm text-[var(--text-secondary)] bg-[var(--bg-secondary)] border border-[var(--border)] rounded p-3">
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
