import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { api } from '../api'
import MetricCard from '../components/MetricCard'
import StatusBadge from '../components/StatusBadge'
import LoadingSpinner from '../components/LoadingSpinner'

export default function Training() {
  const { data: status, isLoading } = useQuery({ queryKey: ['training-status'], queryFn: api.getTrainingStatus, refetchInterval: 60000 })
  const { data: history } = useQuery({ queryKey: ['training-versions'], queryFn: api.getTrainingVersions, refetchInterval: 60000 })
  const [toast, setToast] = useState(null)
  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(null), 3000) }

  const trainMutation = useMutation({
    mutationFn: api.triggerTrainPipeline,
    onSuccess: () => showToast('Training pipeline started (this will take a while)...'),
    onError: (e) => showToast(`Training failed: ${e.message}`),
  })
  const scoreMutation = useMutation({
    mutationFn: api.triggerScore,
    onSuccess: () => showToast('Scoring started...'),
    onError: (e) => showToast(`Scoring failed: ${e.message}`),
  })

  if (isLoading) return <LoadingSpinner />

  const versions = history?.versions || []

  return (
    <div className="space-y-6">
      {toast && (
        <div className="fixed top-4 right-4 z-50 bg-[var(--bg-card)] border border-[var(--border)] rounded-lg px-4 py-2 text-sm shadow-lg">
          {toast}
        </div>
      )}

      <div className="flex items-center justify-between">
        <h2 className="text-xl font-medium">Training Pipeline</h2>
        <div className="flex items-center gap-2">
          <button onClick={() => scoreMutation.mutate()} disabled={scoreMutation.isPending}
            className="px-3 py-1.5 text-xs rounded-md bg-[var(--bg-tertiary)] border border-[var(--border)] hover:border-[var(--blue)] disabled:opacity-50">
            {scoreMutation.isPending ? 'Scoring...' : 'Score Unscored'}
          </button>
          <button onClick={() => { if (confirm('This will run the full training pipeline and may take a long time. Continue?')) trainMutation.mutate() }}
            disabled={trainMutation.isPending}
            className="px-3 py-1.5 text-xs rounded-md bg-[var(--blue)] text-white hover:opacity-90 disabled:opacity-50">
            {trainMutation.isPending ? 'Training...' : 'Run Training Pipeline'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard label="Active Model" value={status?.model_name || 'base'} />
        <MetricCard label="Dataset Size" value={status?.dataset_total || 0} />
        <MetricCard label="New Examples" value={status?.new_since_last_train || 0} />
        <MetricCard label="Status" value={status?.train_queued ? 'Queued' : 'Collecting'} />
      </div>

      {/* Dataset breakdown */}
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-sm text-[var(--text-muted)] uppercase tracking-wide mb-4">Dataset Breakdown</h3>
        <div className="flex gap-1 h-4 rounded-full overflow-hidden bg-[var(--bg-tertiary)]">
          {status?.dataset_total > 0 && (
            <>
              <div className="bg-[var(--blue)]" style={{ width: `${(status.dataset_synthetic / status.dataset_total) * 100}%` }} />
              <div className="bg-[var(--green)]" style={{ width: `${(status.dataset_wins / status.dataset_total) * 100}%` }} />
              <div className="bg-[var(--red)]" style={{ width: `${(status.dataset_losses / status.dataset_total) * 100}%` }} />
            </>
          )}
        </div>
        <div className="flex gap-6 mt-2 text-xs text-[var(--text-secondary)]">
          <span><span className="inline-block w-2 h-2 rounded-full bg-[var(--blue)] mr-1" />Synthetic: {status?.dataset_synthetic || 0}</span>
          <span><span className="inline-block w-2 h-2 rounded-full bg-[var(--green)] mr-1" />Wins: {status?.dataset_wins || 0}</span>
          <span><span className="inline-block w-2 h-2 rounded-full bg-[var(--red)] mr-1" />Losses: {status?.dataset_losses || 0}</span>
        </div>
      </div>

      {/* Training progress */}
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-sm text-[var(--text-muted)] uppercase tracking-wide mb-4">Next Training</h3>
        <div className="h-3 bg-[var(--bg-tertiary)] rounded-full overflow-hidden mb-2">
          <div className="h-full bg-[var(--blue)] rounded-full transition-all" style={{ width: `${Math.min(100, ((status?.new_since_last_train || 0) / 50) * 100)}%` }} />
        </div>
        <p className="text-sm text-[var(--text-secondary)]">{status?.train_reason}</p>
        <p className="text-xs text-[var(--text-muted)] mt-1">Rollback: {status?.rollback_status}</p>
      </div>

      {/* Version history */}
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-sm text-[var(--text-muted)] uppercase tracking-wide mb-4">Version History</h3>
        <div className="space-y-3">
          {versions.map((v, i) => (
            <div key={v.version_id || i} className="flex items-center gap-4 border-l-2 pl-4 py-2"
              style={{ borderColor: v.status === 'active' ? 'var(--green)' : v.status === 'rolled_back' ? 'var(--red)' : 'var(--border)' }}>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{v.version_name}</span>
                  <StatusBadge text={v.status} variant={v.status === 'active' ? 'success' : v.status === 'rolled_back' ? 'danger' : 'neutral'} />
                </div>
                <div className="text-xs text-[var(--text-muted)] mt-0.5">{v.created_at ? v.created_at.slice(0, 10) : '--'}</div>
              </div>
              <div className="text-sm font-mono text-right">
                <div>{v.training_examples_count || '--'} examples</div>
                <div className="text-xs text-[var(--text-muted)]">
                  {v.trade_count > 0 ? `${v.win_rate?.toFixed(1)}% WR | $${v.expectancy?.toFixed(2)} exp` : 'No trades yet'}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
