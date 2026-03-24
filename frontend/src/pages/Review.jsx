import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import LoadingSpinner from '../components/LoadingSpinner'
import EmptyState from '../components/EmptyState'
import PnlText from '../components/PnlText'
import StatusBadge from '../components/StatusBadge'
import { ClipboardCheck } from 'lucide-react'

export default function Review() {
  const { data: pending, isLoading } = useQuery({ queryKey: ['pending-reviews'], queryFn: api.getPendingReviews })
  const { data: postmortems } = useQuery({ queryKey: ['postmortems'], queryFn: () => api.getPostmortems({ limit: 10 }) })

  if (isLoading) return <LoadingSpinner />

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-medium">Review</h2>

      {/* Pending reviews */}
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-sm text-[var(--text-muted)] uppercase tracking-wide mb-4">Pending Reviews ({(pending || []).length})</h3>
        {(!pending || pending.length === 0) ? (
          <EmptyState message="No trades pending review" icon={ClipboardCheck} />
        ) : (
          <div className="space-y-2">
            {pending.map((r, i) => (
              <div key={r.recommendation_id || i} className="border border-[var(--border)] rounded p-3 flex items-center justify-between">
                <div>
                  <span className="font-medium">{r.ticker}</span>
                  <span className="text-[var(--text-muted)] ml-2 text-sm">{(r.created_at || '').slice(0, 10)}</span>
                </div>
                <div className="flex items-center gap-3">
                  <PnlText value={r.shadow_pnl_dollars} percent={r.shadow_pnl_pct} />
                  <span className="font-mono text-sm text-[var(--text-secondary)]">{r.entry_zone}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent postmortems */}
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-sm text-[var(--text-muted)] uppercase tracking-wide mb-4">Recent Postmortems</h3>
        {(!postmortems || postmortems.length === 0) ? (
          <EmptyState message="No postmortems yet" icon={ClipboardCheck} />
        ) : (
          <div className="space-y-2">
            {postmortems.map((p, i) => (
              <div key={i} className="border border-[var(--border)] rounded p-3">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-3">
                    <span className="font-medium">{p.ticker}</span>
                    <span className="text-[var(--text-muted)] text-sm">{p.date}</span>
                    <StatusBadge text={p.exit_reason} variant={p.pnl_dollars > 0 ? 'success' : 'danger'} />
                    <StatusBadge text={p.lesson_tag} variant="neutral" />
                  </div>
                  <PnlText value={p.pnl_dollars} />
                </div>
                <p className="text-sm text-[var(--text-secondary)] truncate">{p.postmortem?.split('\n')[0]}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
