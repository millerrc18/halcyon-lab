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
  if (score >= 70) return 'text-emerald-400'
  if (score >= 40) return 'text-yellow-400'
  return 'text-red-400'
}

function DimensionRow({ name, score, weight }) {
  const pct = Math.min(100, Math.max(0, score))
  const barColor = score >= 70 ? 'bg-emerald-500' : score >= 40 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-4">
      <div className="w-36 text-sm text-[var(--text-secondary)]">{DIMENSION_LABELS[name] || name}</div>
      <div className="flex-1 h-2 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="w-12 text-right text-sm font-mono">{score.toFixed(0)}</div>
      <div className="w-16 text-right text-xs text-[var(--text-muted)]">
        w={weight != null ? (weight * 100).toFixed(0) + '%' : '--'}
      </div>
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
      <h2 className="text-xl font-medium">System Health Score</h2>

      {/* Overall score + phase */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-6 text-center md:col-span-1">
          <div className="text-xs text-[var(--text-muted)] uppercase tracking-wide mb-2">
            HSHS Overall
          </div>
          <div className={`text-5xl font-bold font-mono ${overallColor(overall)}`}>
            {overall.toFixed(1)}
          </div>
          <div className="text-sm text-[var(--text-secondary)] mt-2">out of 100</div>
          <div className="mt-3 inline-block px-3 py-1 rounded-full text-xs bg-[var(--bg-tertiary)] text-[var(--text-secondary)]">
            {PHASE_LABELS[phase] || phase}
          </div>
        </div>

        {/* Radar Chart */}
        <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4 md:col-span-2">
          <h3 className="text-sm text-[var(--text-muted)] uppercase tracking-wide mb-2">
            Dimension Radar
          </h3>
          <ResponsiveContainer width="100%" height={280}>
            <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="70%">
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis
                dataKey="dimension"
                tick={{ fontSize: 11, fill: 'var(--text-secondary)' }}
              />
              <PolarRadiusAxis
                angle={90}
                domain={[0, 100]}
                tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
              />
              <Radar
                name="Score"
                dataKey="score"
                stroke="var(--blue)"
                fill="var(--blue)"
                fillOpacity={0.2}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Dimension Breakdown */}
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-sm text-[var(--text-muted)] uppercase tracking-wide mb-4">
          Dimensions
        </h3>
        <div className="space-y-3">
          {Object.keys(DIMENSION_LABELS).map((key) => (
            <DimensionRow
              key={key}
              name={key}
              score={dimensions[key] ?? 0}
              weight={weights[key]}
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
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-sm text-[var(--text-muted)] uppercase tracking-wide mb-3">
          Phase Weights ({PHASE_LABELS[phase] || phase})
        </h3>
        <div className="grid grid-cols-5 gap-2 text-center text-sm">
          {Object.entries(DIMENSION_LABELS).map(([key, label]) => (
            <div key={key}>
              <div className="text-[var(--text-muted)] text-xs mb-1">{label}</div>
              <div className="font-mono text-[var(--text-primary)]">
                {weights[key] != null ? `${(weights[key] * 100).toFixed(0)}%` : '--'}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Trend Line */}
      {trendData.length > 1 && (
        <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4">
          <h3 className="text-sm text-[var(--text-muted)] uppercase tracking-wide mb-4">
            Score Trend
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
              <Tooltip
                contentStyle={{
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Line
                type="monotone"
                dataKey="overall"
                stroke="var(--blue)"
                strokeWidth={2}
                dot={{ r: 3, fill: 'var(--blue)' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
