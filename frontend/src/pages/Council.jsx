import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import LoadingSpinner from '../components/LoadingSpinner'
import StatusBadge from '../components/StatusBadge'

const VOTE_COLORS = {
  strong_buy: 'var(--teal-400)',
  buy: 'var(--bullish)',
  hold: 'var(--amber-400)',
  sell: 'var(--amber-600)',
  strong_sell: 'var(--danger)',
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
    <div className="rounded-lg p-4" style={{
      background: 'var(--slate-700)',
      border: isDissenter ? '1px solid var(--amber-500)' : '1px solid var(--slate-600)',
    }}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm">{agent.name || agent.agent_id}</span>
          {isDissenter && (
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'rgba(245, 158, 11, 0.2)', color: 'var(--amber-400)' }}>
              Devil's Advocate
            </span>
          )}
        </div>
        <VoteBadge vote={agent.vote} />
      </div>
      <div className="text-xs mb-1" style={{ color: 'var(--slate-400)' }}>{agent.role || 'analyst'}</div>
      {agent.confidence != null && (
        <div className="text-xs mb-2" style={{ color: 'var(--slate-300)' }}>
          Confidence: <span style={{ fontFamily: 'var(--font-mono)' }}>{(agent.confidence * 100).toFixed(0)}%</span>
        </div>
      )}
      {agent.reasoning && (
        <p className="text-sm mt-2 leading-relaxed" style={{ color: 'var(--slate-300)' }}>
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
    <div className="flex items-center justify-between py-2 px-3 rounded"
      style={{ background: isLatest ? 'var(--slate-600)' : 'transparent' }}>
      <div className="flex items-center gap-3">
        <span className="text-sm" style={{ color: 'var(--slate-300)', fontFamily: 'var(--font-mono)' }}>{dateStr}</span>
        {session.ticker && (
          <span className="text-sm font-medium">{session.ticker}</span>
        )}
      </div>
      <div className="flex items-center gap-3">
        <span className="text-xs" style={{ color: 'var(--slate-400)' }}>
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
  const consensusColor = VOTE_COLORS[consensus] || 'var(--slate-100)'
  const sessions = history?.sessions || history || []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-medium" style={{ color: 'var(--slate-100)' }}>Advisory Council</h2>
        <button
          onClick={() => runCouncil.mutate()}
          disabled={runCouncil.isPending}
          className="px-4 py-2 rounded-lg font-medium text-sm text-white disabled:opacity-50 transition-colors"
          style={{ background: 'var(--teal-500)' }}
        >
          {runCouncil.isPending ? 'Running Council...' : 'Run Council Now'}
        </button>
      </div>

      {/* Consensus Vote */}
      {consensus && (
        <div className="rounded-lg p-6 text-center" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
          <div className="text-xs uppercase tracking-wide mb-2" style={{ color: 'var(--slate-400)' }}>
            Consensus Vote
          </div>
          <div className="text-3xl font-bold" style={{ fontFamily: 'var(--font-mono)', color: consensusColor }}>
            {(consensus || '').replace('_', ' ').toUpperCase()}
          </div>
          {session.ticker && (
            <div className="text-sm mt-2" style={{ color: 'var(--slate-300)' }}>
              Ticker: <span className="font-medium">{session.ticker}</span>
            </div>
          )}
          {session.summary && (
            <p className="text-sm mt-3 max-w-2xl mx-auto" style={{ color: 'var(--slate-300)' }}>
              {session.summary.slice(0, 400)}
            </p>
          )}
        </div>
      )}

      {/* Agent Cards */}
      {agents.length > 0 && (
        <div>
          <h3 className="text-sm uppercase tracking-wide mb-3" style={{ color: 'var(--slate-400)' }}>
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
        <div className="rounded-lg p-12 text-center" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
          <div className="text-sm" style={{ color: 'var(--slate-400)' }}>
            No council session yet. Click "Run Council Now" to start.
          </div>
        </div>
      )}

      {/* Session History */}
      <div className="rounded-lg p-4" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
        <h3 className="text-sm uppercase tracking-wide mb-3" style={{ color: 'var(--slate-400)' }}>
          Session History
        </h3>
        {sessions.length > 0 ? (
          <div className="space-y-1">
            {sessions.map((s, i) => (
              <SessionRow key={s.id || i} session={s} isLatest={i === 0} />
            ))}
          </div>
        ) : (
          <div className="text-center py-6 text-sm" style={{ color: 'var(--slate-400)' }}>
            No historical sessions
          </div>
        )}
      </div>
    </div>
  )
}
