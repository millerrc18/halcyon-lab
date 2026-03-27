import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import MetricCard from '../components/MetricCard'
import LoadingSpinner from '../components/LoadingSpinner'
import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Tooltip, LineChart, Line, XAxis, YAxis, CartesianGrid,
} from 'recharts'

const DIMENSION_LABELS = {
  performance: 'Performance',
  model_quality: 'Model Quality',
  data_asset: 'Data Asset',
  flywheel_velocity: 'Flywheel Velocity',
  defensibility: 'Defensibility',
}

const PHASE_LABELS = {
  early: 'Early (Months 1-6)',
  growth: 'Growth (Months 7-18)',
  mature: 'Mature (18+)',
}

function overallColor(score) {
  if (score >= 70) return 'var(--teal-400)'
  if (score >= 40) return 'var(--amber-400)'
  return 'var(--danger)'
}

function MetricDetail({ label, value, unit = '' }) {
  return (
    <div className="flex justify-between text-xs py-0.5">
      <span style={{ color: 'var(--slate-400)' }}>{label}</span>
      <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--slate-200)' }}>{value}{unit}</span>
    </div>
  )
}

function DimensionRow({ name, score, weight, metrics }) {
  const pct = Math.min(100, Math.max(0, score))
  const barColor = score >= 70 ? 'var(--teal-500)' : score >= 40 ? 'var(--amber-500)' : 'var(--danger)'
  return (
    <div className="rounded-lg p-3" style={{ background: 'rgba(100,116,139,0.1)' }}>
      <div className="flex items-center gap-4">
        <div className="w-36 text-sm font-medium" style={{ color: 'var(--slate-200)' }}>{DIMENSION_LABELS[name] || name}</div>
        <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: 'var(--slate-600)' }}>
          <div className="h-full rounded-full" style={{ width: `${pct}%`, background: barColor }} />
        </div>
        <div className="w-12 text-right text-sm font-medium" style={{ fontFamily: 'var(--font-mono)', color: barColor }}>{score.toFixed(0)}</div>
        <div className="w-16 text-right text-xs" style={{ color: 'var(--slate-400)' }}>
          w={weight != null ? (weight * 100).toFixed(0) + '%' : '--'}
        </div>
      </div>
      {/* Metric breakdown */}
      {metrics && (
        <div className="mt-2 ml-36 pl-4" style={{ borderLeft: '2px solid var(--slate-600)' }}>
          {metrics.status && (
            <div className="text-xs py-0.5" style={{ color: 'var(--amber-400)' }}>{metrics.status}</div>
          )}
          {name === 'performance' && !metrics.status && (
            <>
              <MetricDetail label="Win Rate" value={(metrics.win_rate * 100).toFixed(1)} unit="%" />
              <MetricDetail label="Sharpe" value={metrics.sharpe} />
              <MetricDetail label="Profit Factor" value={metrics.profit_factor} />
              <MetricDetail label="Max Drawdown" value={metrics.max_drawdown_pct} unit="%" />
              <MetricDetail label="Net P&L" value={`$${metrics.net_pnl}`} />
              <MetricDetail label="Trades" value={metrics.trade_count} />
            </>
          )}
          {name === 'performance' && metrics.target && (
            <div className="mt-1">
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--slate-600)', maxWidth: '200px' }}>
                <div className="h-full rounded-full" style={{ background: 'var(--amber-500)', width: `${Math.min(100, (metrics.trade_count / metrics.target) * 100)}%` }} />
              </div>
              <div className="text-xs mt-0.5" style={{ color: 'var(--slate-500)' }}>{metrics.trade_count}/{metrics.target} trades</div>
            </div>
          )}
          {name === 'model_quality' && (
            <>
              <MetricDetail label="Template Fallback" value={(metrics.template_fallback_rate * 100).toFixed(1)} unit="%" />
              {metrics.canary_verdict && <MetricDetail label="Canary" value={metrics.canary_verdict} />}
              {metrics.perplexity != null && <MetricDetail label="Perplexity" value={metrics.perplexity} />}
              {metrics.distinct_2 != null && <MetricDetail label="Distinct-2" value={metrics.distinct_2} />}
            </>
          )}
          {name === 'data_asset' && (
            <>
              <MetricDetail label="Examples" value={`${metrics.example_count} / ${metrics.target}`} />
              <MetricDetail label="Progress" value={metrics.progress_pct?.toFixed(1)} unit="%" />
            </>
          )}
          {name === 'flywheel_velocity' && (
            <>
              <MetricDetail label="Closed Trades" value={`${metrics.closed_trades} / ${metrics.target}`} />
              <MetricDetail label="Open Trades" value={metrics.open_trades} />
            </>
          )}
          {name === 'defensibility' && (
            <>
              <MetricDetail label="Training Examples" value={metrics.example_count} />
              <MetricDetail label="Regime Coverage" value={`${metrics.regime_coverage} / ${metrics.regime_target}`} />
              <MetricDetail label="Ticker Coverage" value={metrics.ticker_coverage} />
              {metrics.source_diversity && typeof metrics.source_diversity === 'object' && (
                <MetricDetail label="Sources" value={Object.keys(metrics.source_diversity).join(', ')} />
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default function Health() {
  const { data, isLoading } = useQuery({
    queryKey: ['health-score'],
    queryFn: api.getHealthScore,
    refetchInterval: 60000,
  })

  if (isLoading) return <LoadingSpinner />

  const score = data?.score || data || {}
  const overall = score.overall ?? 0
  const dimensions = score.dimensions || {}
  const dimensionMetrics = score.dimension_metrics || {}
  const weights = score.weights || {}
  const phase = score.phase || 'early'
  const history = data?.history || []

  // Build radar data
  const radarData = Object.entries(DIMENSION_LABELS).map(([key, label]) => ({
    dimension: label,
    score: dimensions[key] ?? 0,
    fullMark: 100,
  }))

  // Build trend data
  const trendData = history.map((h) => ({
    date: (h.date || h.created_at || '').slice(0, 10),
    overall: h.overall ?? h.score ?? 0,
  }))

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-medium" style={{ color: 'var(--slate-100)' }}>System Health Score</h2>

      {/* Overall score + phase */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-lg p-6 text-center md:col-span-1" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
          <div className="text-xs uppercase tracking-wide mb-2" style={{ color: 'var(--slate-400)' }}>
            HSHS Overall
          </div>
          <div className="text-5xl font-bold" style={{ fontFamily: 'var(--font-mono)', color: overallColor(overall) }}>
            {overall.toFixed(1)}
          </div>
          <div className="text-sm mt-2" style={{ color: 'var(--slate-300)' }}>out of 100</div>
          <div className="mt-3 inline-block px-3 py-1 rounded-full text-xs" style={{ background: 'var(--slate-600)', color: 'var(--slate-300)' }}>
            {PHASE_LABELS[phase] || phase}
          </div>
        </div>

        {/* Radar Chart */}
        <div className="rounded-lg p-4 md:col-span-2" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
          <h3 className="text-sm uppercase tracking-wide mb-2" style={{ color: 'var(--slate-400)' }}>
            Dimension Radar
          </h3>
          <ResponsiveContainer width="100%" height={280}>
            <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="70%">
              <PolarGrid stroke="var(--slate-600)" />
              <PolarAngleAxis
                dataKey="dimension"
                tick={{ fontSize: 11, fill: 'var(--slate-300)' }}
              />
              <PolarRadiusAxis
                angle={90}
                domain={[0, 100]}
                tick={{ fontSize: 10, fill: 'var(--slate-400)' }}
              />
              <Radar
                name="Score"
                dataKey="score"
                stroke="var(--teal-400)"
                fill="var(--teal-400)"
                fillOpacity={0.2}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--slate-700)',
                  border: '1px solid var(--slate-600)',
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Dimension Breakdown */}
      <div className="rounded-lg p-4" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
        <h3 className="text-sm uppercase tracking-wide mb-4" style={{ color: 'var(--slate-400)' }}>
          Dimensions
        </h3>
        <div className="space-y-3">
          {Object.keys(DIMENSION_LABELS).map((key) => (
            <DimensionRow
              key={key}
              name={key}
              score={dimensions[key] ?? 0}
              weight={weights[key]}
              metrics={dimensionMetrics[key]}
            />
          ))}
        </div>
      </div>

      {/* Metric cards for each dimension */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {Object.entries(DIMENSION_LABELS).map(([key, label]) => (
          <MetricCard key={key} label={label} value={(dimensions[key] ?? 0).toFixed(0)} />
        ))}
      </div>

      {/* Phase weight explanation */}
      <div className="rounded-lg p-4" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
        <h3 className="text-sm uppercase tracking-wide mb-3" style={{ color: 'var(--slate-400)' }}>
          Phase Weights ({PHASE_LABELS[phase] || phase})
        </h3>
        <div className="grid grid-cols-5 gap-2 text-center text-sm">
          {Object.entries(DIMENSION_LABELS).map(([key, label]) => (
            <div key={key}>
              <div className="text-xs mb-1" style={{ color: 'var(--slate-400)' }}>{label}</div>
              <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--slate-100)' }}>
                {weights[key] != null ? `${(weights[key] * 100).toFixed(0)}%` : '--'}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Trend Line */}
      {trendData.length > 1 && (
        <div className="rounded-lg p-4" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
          <h3 className="text-sm uppercase tracking-wide mb-4" style={{ color: 'var(--slate-400)' }}>
            Score Trend
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--slate-600)" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'var(--slate-400)' }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: 'var(--slate-400)' }} />
              <Tooltip
                contentStyle={{
                  background: 'var(--slate-700)',
                  border: '1px solid var(--slate-600)',
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Line
                type="monotone"
                dataKey="overall"
                stroke="var(--teal-400)"
                strokeWidth={2}
                dot={{ r: 3, fill: 'var(--teal-400)' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
