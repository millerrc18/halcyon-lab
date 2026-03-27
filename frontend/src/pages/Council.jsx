import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import LoadingSpinner from '../components/LoadingSpinner'
import StatusBadge from '../components/StatusBadge'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { ChevronDown, ChevronRight } from 'lucide-react'

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

const VOTE_BAR_COLORS = {
  strong_buy: '#2dd4bf',
  buy: '#34d399',
  hold: '#fbbf24',
  sell: '#f97316',
  strong_sell: '#ef4444',
}

function VoteBadge({ vote }) {
  const variant = VOTE_VARIANTS[vote] || 'neutral'
  const label = (vote || 'unknown').replace('_', ' ').toUpperCase()
  return <StatusBadge text={label} variant={variant} />
}

function AgentCard({ agent }) {
  const isDissenter = agent.role === 'devils_advocate' || agent.is_dissenter || agent.is_devils_advocate
  return (
    <div className="rounded-lg p-4" style={{
      background: 'var(--slate-700)',
      border: isDissenter ? '2px solid var(--amber-500)' : '1px solid var(--slate-600)',
    }}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm">{agent.agent_name || agent.name || agent.agent_id}</span>
          {isDissenter && (
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'rgba(245, 158, 11, 0.2)', color: 'var(--amber-400)' }}>
              Dissenter
            </span>
          )}
        </div>
        <VoteBadge vote={agent.position || agent.vote} />
      </div>
      {agent.confidence != null && (
        <div className="text-xs mb-2" style={{ color: 'var(--slate-300)' }}>
          Confidence: <span style={{ fontFamily: 'var(--font-mono)' }}>{(agent.confidence * 100).toFixed(0)}%</span>
        </div>
      )}
      {(agent.reasoning || agent.key_data_points) && (
        <p className="text-sm mt-2 leading-relaxed" style={{ color: 'var(--slate-300)' }}>
          {(agent.reasoning || (Array.isArray(agent.key_data_points) ? agent.key_data_points.join('. ') : '')).slice(0, 400)}
        </p>
      )}
      {agent.risk_flags && Array.isArray(agent.risk_flags) && agent.risk_flags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {agent.risk_flags.map((flag, i) => (
            <span key={i} className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#fca5a5' }}>
              {flag}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function VoteDistribution({ votes }) {
  if (!votes || votes.length === 0) return null
  const counts = {}
  for (const v of votes) {
    const pos = v.position || v.vote || 'unknown'
    counts[pos] = (counts[pos] || 0) + 1
  }
  const data = Object.entries(counts).map(([name, count]) => ({ name: name.replace('_', ' '), count, key: name }))

  return (
    <div className="rounded-lg p-4" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
      <h4 className="text-xs uppercase tracking-wide mb-3" style={{ color: 'var(--slate-400)' }}>Vote Distribution</h4>
      <ResponsiveContainer width="100%" height={120}>
        <BarChart data={data} layout="vertical">
          <XAxis type="number" tick={{ fontSize: 11, fill: 'var(--slate-400)' }} allowDecimals={false} />
          <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: 'var(--slate-300)' }} width={80} />
          <Tooltip contentStyle={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)', borderRadius: 8, fontSize: 12 }} />
          <Bar dataKey="count" radius={[0, 4, 4, 0]}>
            {data.map((entry) => (
              <Cell key={entry.key} fill={VOTE_BAR_COLORS[entry.key] || 'var(--slate-400)'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function ExpandableSessionRow({ session, isLatest }) {
  const [expanded, setExpanded] = useState(false)
  const { data: detail, isLoading } = useQuery({
    queryKey: ['council-session', session.session_id],
    queryFn: () => api.getCouncilSession(session.session_id),
    enabled: expanded && !!session.session_id,
  })

  const ts = session.created_at || session.timestamp
  const dateStr = ts ? new Date(ts).toLocaleString() : '--'
  const consensus = session.consensus_vote || session.consensus || '--'
  const votes = detail?.votes || []

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between py-2 px-3 rounded transition-colors"
        style={{ background: isLatest ? 'var(--slate-600)' : expanded ? 'rgba(100,116,139,0.2)' : 'transparent' }}
      >
        <div className="flex items-center gap-3">
          {expanded ? <ChevronDown size={14} style={{ color: 'var(--slate-400)' }} /> : <ChevronRight size={14} style={{ color: 'var(--slate-400)' }} />}
          <span className="text-sm" style={{ color: 'var(--slate-300)', fontFamily: 'var(--font-mono)' }}>{dateStr}</span>
          {session.ticker && (
            <span className="text-sm font-medium">{session.ticker}</span>
          )}
          {session.session_type && (
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'rgba(100,116,139,0.3)', color: 'var(--slate-300)' }}>
              {session.session_type}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {session.is_contested && (
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'rgba(245, 158, 11, 0.2)', color: 'var(--amber-400)' }}>
              Contested
            </span>
          )}
          <span className="text-xs" style={{ color: 'var(--slate-400)' }}>
            {(session.agent_count || session.agents?.length || 0) > 0
              ? `${session.agent_count || session.agents?.length} agents`
              : <span style={{ color: 'var(--amber-400)' }}>Session failed</span>}
          </span>
          <VoteBadge vote={consensus} />
        </div>
      </button>

      {expanded && (
        <div className="ml-6 mt-2 mb-4 space-y-4">
          {isLoading ? (
            <LoadingSpinner />
          ) : (
            <>
              {/* Session metadata */}
              {detail?.session && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                  {detail.session.trigger_reason && (
                    <div className="rounded-lg p-3" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
                      <div className="text-xs" style={{ color: 'var(--slate-400)' }}>Trigger</div>
                      <div style={{ color: 'var(--slate-200)' }}>{detail.session.trigger_reason}</div>
                    </div>
                  )}
                  {detail.session.confidence_weighted_score != null && (
                    <div className="rounded-lg p-3" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
                      <div className="text-xs" style={{ color: 'var(--slate-400)' }}>Confidence</div>
                      <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--slate-200)' }}>
                        {(detail.session.confidence_weighted_score * 100).toFixed(0)}%
                      </div>
                    </div>
                  )}
                  {detail.session.rounds_completed != null && (
                    <div className="rounded-lg p-3" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
                      <div className="text-xs" style={{ color: 'var(--slate-400)' }}>Rounds</div>
                      <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--slate-200)' }}>{detail.session.rounds_completed}</div>
                    </div>
                  )}
                  {detail.session.cost_dollars != null && (
                    <div className="rounded-lg p-3" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
                      <div className="text-xs" style={{ color: 'var(--slate-400)' }}>Cost</div>
                      <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--slate-200)' }}>${detail.session.cost_dollars?.toFixed(2)}</div>
                    </div>
                  )}
                </div>
              )}

              {/* Vote distribution */}
              <VoteDistribution votes={votes} />

              {/* Agent vote cards */}
              {votes.length > 0 && (
                <div>
                  <h4 className="text-xs uppercase tracking-wide mb-3" style={{ color: 'var(--slate-400)' }}>
                    Agent Votes ({votes.length})
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {votes.map((v, i) => (
                      <AgentCard key={v.vote_id || i} agent={v} />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
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

      {/* Agent Cards for latest session */}
      {agents.length > 0 && (
        <div>
          <h3 className="text-sm uppercase tracking-wide mb-3" style={{ color: 'var(--slate-400)' }}>
            Agent Assessments ({agents.length})
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {agents.map((agent, i) => (
              <AgentCard key={agent.agent_id || agent.vote_id || i} agent={agent} />
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

      {/* Session History — now expandable */}
      <div className="rounded-lg p-4" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
        <h3 className="text-sm uppercase tracking-wide mb-3" style={{ color: 'var(--slate-400)' }}>
          Session History
        </h3>
        {sessions.length > 0 ? (
          <div className="space-y-1">
            {sessions.map((s, i) => (
              <ExpandableSessionRow key={s.session_id || s.id || i} session={s} isLatest={i === 0} />
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
