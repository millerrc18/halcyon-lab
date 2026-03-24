export default function PnlText({ value, percent }) {
  if (value === null || value === undefined) return <span className="text-[var(--text-muted)]">--</span>
  const color = value > 0 ? 'text-[var(--green)]' : value < 0 ? 'text-[var(--red)]' : 'text-[var(--text-muted)]'
  const sign = value > 0 ? '+' : ''
  return (
    <span className={`font-mono ${color}`}>
      {sign}${value.toFixed(2)}
      {percent !== undefined && percent !== null && (
        <span className="ml-1 text-sm">({sign}{percent.toFixed(1)}%)</span>
      )}
    </span>
  )
}
