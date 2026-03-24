export default function MetricCard({ label, value, delta, prefix = '' }) {
  const deltaColor = delta > 0 ? 'text-[var(--green)]' : delta < 0 ? 'text-[var(--red)]' : 'text-[var(--text-muted)]'
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4 hover:border-[var(--border-hover)]">
      <div className="text-[var(--text-muted)] text-xs uppercase tracking-wide mb-1">{label}</div>
      <div className="text-2xl font-mono text-[var(--text-primary)]">{prefix}{value}</div>
      {delta !== undefined && delta !== null && (
        <div className={`text-sm font-mono mt-1 ${deltaColor}`}>
          {delta > 0 ? '+' : ''}{typeof delta === 'number' ? delta.toFixed(2) : delta}
        </div>
      )}
    </div>
  )
}
