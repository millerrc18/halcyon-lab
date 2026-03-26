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
      <h2 className="text-xl font-medium" style={{ color: 'var(--slate-100)' }}>Review</h2>

      {/* Pending reviews */}
      <div className="rounded-lg p-4" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
        <h3 className="text-sm uppercase tracking-wide mb-4" style={{ color: 'var(--slate-400)' }}>Pending Reviews ({(pending || []).length})</h3>
        {(!pending || pending.length === 0) ? (
          <EmptyState message="No trades pending review" icon={ClipboardCheck} />
        ) : (
          <div className="space-y-2">
            {pending.map((r, i) => (
              <div key={r.recommendation_id || i} className="rounded p-3 flex items-center justify-between" style={{ border: '1px solid var(--slate-600)' }}>
                <div>
                  <span className="font-medium">{r.ticker}</span>
                  <span className="ml-2 text-sm" style={{ color: 'var(--slate-400)' }}>{(r.created_at || '').slice(0, 10)}</span>
                </div>
                <div className="flex items-center gap-3">
                  <PnlText value={r.shadow_pnl_dollars} percent={r.shadow_pnl_pct} />
                  <span className="text-sm" style={{ fontFamily: 'var(--font-mono)', color: 'var(--slate-300)' }}>{r.entry_zone}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent postmortems */}
      <div className="rounded-lg p-4" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
        <h3 className="text-sm uppercase tracking-wide mb-4" style={{ color: 'var(--slate-400)' }}>Recent Postmortems</h3>
        {(!postmortems || postmortems.length === 0) ? (
          <EmptyState message="No postmortems yet" icon={ClipboardCheck} />
        ) : (
          <div className="space-y-2">
            {postmortems.map((p, i) => (
              <div key={i} className="rounded p-3" style={{ border: '1px solid var(--slate-600)' }}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-3">
                    <span className="font-medium">{p.ticker}</span>
                    <span className="text-sm" style={{ color: 'var(--slate-400)' }}>{p.date}</span>
                    <StatusBadge text={p.exit_reason} variant={p.pnl_dollars > 0 ? 'success' : 'danger'} />
                    <StatusBadge text={p.lesson_tag} variant="neutral" />
                  </div>
                  <PnlText value={p.pnl_dollars} />
                </div>
                <p className="text-sm truncate" style={{ color: 'var(--slate-300)' }}>{p.postmortem?.split('\n')[0]}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
