import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import LoadingSpinner from '../components/LoadingSpinner'
import StatusBadge from '../components/StatusBadge'

const VOTE_COLORS = {
  strong_buy: 'text-emerald-400',
  buy: 'text-green-400',
  hold: 'text-yellow-400',
  sell: 'text-orange-400',
  strong_sell: 'text-red-400',
}

const VOTE_VARIANTS = {
  strong_buy: 'success',
  buy: 'success',
  hold: 'warning',
  sell: 'danger',
  strong_sell: 'danger',
}

function VoteBadge({ vote }) {
  const variant = VOTE_VARIANTS[vote] || 'neutral'
  const label = (vote || 'unknown').replace('_', ' ').toUpperCase()
  return <StatusBadge text={label} variant={variant} />
}

function AgentCard({ agent }) {
  const isDissenter = agent.role === 'devils_advocate' || agent.is_dissenter
  return (
    <div className={`bg-[var(--bg-card)] border rounded-lg p-4 ${
      isDissenter ? 'border-orange-500/60' : 'border-[var(--border)]'
    }`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm">{agent.name || agent.agent_id}</span>
          {isDissenter && (
            <span className="text-xs bg-orange-500/20 text-orange-400 px-2 py-0.5 rounded-full">
              Devil's Advocate
            </span>
          )}
        </div>
        <VoteBadge vote={agent.vote} />
      </div>
      <div className="text-xs text-[var(--text-muted)] mb-1">{agent.role || 'analyst'}</div>
      {agent.confidence != null && (
        <div className="text-xs text-[var(--text-secondary)] mb-2">
          Confidence: <span className="font-mono">{(agent.confidence * 100).toFixed(0)}%</span>
        </div>
      )}
      {agent.reasoning && (
        <p className="text-sm text-[var(--text-secondary)] mt-2 leading-relaxed">
          {agent.reasoning.slice(0, 300)}{agent.reasoning.length > 300 ? '...' : ''}
        </p>
      )}
    </div>
  )
}

function SessionRow({ session, isLatest }) {
  const ts = session.created_at || session.timestamp
  const dateStr = ts ? new Date(ts).toLocaleString() : '--'
  const consensus = session.consensus_vote || session.consensus || '--'
  return (
    <div className={`flex items-center justify-between py-2 px-3 rounded ${
      isLatest ? 'bg-[var(--bg-tertiary)]' : ''
    }`}>
      <div className="flex items-center gap-3">
        <span className="text-sm text-[var(--text-secondary)] font-mono">{dateStr}</span>
        {session.ticker && (
          <span className="text-sm font-medium">{session.ticker}</span>
        )}
      </div>
      <div className="flex items-center gap-3">
        <span className="text-xs text-[var(--text-muted)]">
          {session.agent_count || session.agents?.length || 0} agents
        </span>
        <VoteBadge vote={consensus} />
      </div>
    </div>
  )
}

export default function Council() {
  const queryClient = useQueryClient()
  const { data: latest, isLoading } = useQuery({
    queryKey: ['council-latest'],
    queryFn: api.getCouncilLatest,
    refetchInterval: 60000,
  })
  const { data: history } = useQuery({
    queryKey: ['council-history'],
    queryFn: () => api.getCouncilHistory(30),
    refetchInterval: 60000,
  })

  const runCouncil = useMutation({
    mutationFn: api.triggerCouncil,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['council-latest'] })
      queryClient.invalidateQueries({ queryKey: ['council-history'] })
    },
  })

  if (isLoading) return <LoadingSpinner />

  const session = latest?.session || latest || {}
  const agents = session.agents || session.votes || []
  const consensus = session.consensus_vote || session.consensus
  const consensusColor = VOTE_COLORS[consensus] || 'text-[var(--text-primary)]'
  const sessions = history?.sessions || history || []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-medium">Advisory Council</h2>
        <button
          onClick={() => runCouncil.mutate()}
          disabled={runCouncil.isPending}
          className="px-4 py-2 rounded-lg font-medium text-sm bg-[var(--blue)] hover:opacity-90 text-white disabled:opacity-50"
        >
          {runCouncil.isPending ? 'Running Council...' : 'Run Council Now'}
        </button>
      </div>

      {/* Consensus Vote */}
      {consensus && (
        <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-6 text-center">
          <div className="text-xs text-[var(--text-muted)] uppercase tracking-wide mb-2">
            Consensus Vote
          </div>
          <div className={`text-3xl font-bold font-mono ${consensusColor}`}>
            {(consensus || '').replace('_', ' ').toUpperCase()}
          </div>
          {session.ticker && (
            <div className="text-sm text-[var(--text-secondary)] mt-2">
              Ticker: <span className="font-medium">{session.ticker}</span>
            </div>
          )}
          {session.summary && (
            <p className="text-sm text-[var(--text-secondary)] mt-3 max-w-2xl mx-auto">
              {session.summary.slice(0, 400)}
            </p>
          )}
        </div>
      )}

      {/* Agent Cards */}
      {agents.length > 0 && (
        <div>
          <h3 className="text-sm text-[var(--text-muted)] uppercase tracking-wide mb-3">
            Agent Assessments ({agents.length})
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {agents.map((agent, i) => (
              <AgentCard key={agent.agent_id || i} agent={agent} />
            ))}
          </div>
        </div>
      )}

      {/* No data state */}
      {!consensus && agents.length === 0 && (
        <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-12 text-center">
          <div className="text-[var(--text-muted)] text-sm">
            No council session yet. Click "Run Council Now" to start.
          </div>
        </div>
      )}

      {/* Session History */}
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-sm text-[var(--text-muted)] uppercase tracking-wide mb-3">
          Session History
        </h3>
        {sessions.length > 0 ? (
          <div className="space-y-1">
            {sessions.map((s, i) => (
              <SessionRow key={s.id || i} session={s} isLatest={i === 0} />
            ))}
          </div>
        ) : (
          <div className="text-center text-[var(--text-muted)] py-6 text-sm">
            No historical sessions
          </div>
        )}
      </div>
    </div>
  )
}
