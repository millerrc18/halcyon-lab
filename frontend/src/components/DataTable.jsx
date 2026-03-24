import { useState } from 'react'

export default function DataTable({ columns, data, onRowClick }) {
  const [sortKey, setSortKey] = useState(null)
  const [sortAsc, setSortAsc] = useState(true)

  const sorted = [...(data || [])].sort((a, b) => {
    if (!sortKey) return 0
    const av = a[sortKey], bv = b[sortKey]
    if (av == null) return 1
    if (bv == null) return -1
    const cmp = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv))
    return sortAsc ? cmp : -cmp
  })

  const handleSort = (key) => {
    if (sortKey === key) setSortAsc(!sortAsc)
    else { setSortKey(key); setSortAsc(true) }
  }

  const fmt = (val, type) => {
    if (val === null || val === undefined) return '--'
    switch (type) {
      case 'currency': return `$${Number(val).toFixed(2)}`
      case 'percent': return `${Number(val).toFixed(1)}%`
      case 'number': return Number(val).toFixed(2)
      default: return String(val)
    }
  }

  const numTypes = ['currency', 'percent', 'number']

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)]">
            {columns.map(col => (
              <th key={col.key}
                  className={`py-2 px-3 text-[var(--text-muted)] text-xs uppercase tracking-wide cursor-pointer hover:text-[var(--text-secondary)] ${numTypes.includes(col.type) ? 'text-right' : 'text-left'}`}
                  onClick={() => handleSort(col.key)}>
                {col.label} {sortKey === col.key ? (sortAsc ? '↑' : '↓') : ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr key={i}
                className={`border-b border-[var(--border)] hover:bg-[var(--bg-tertiary)] ${onRowClick ? 'cursor-pointer' : ''} ${i % 2 === 0 ? '' : 'bg-[var(--bg-secondary)]/30'}`}
                onClick={() => onRowClick?.(row)}>
              {columns.map(col => {
                const val = row[col.key]
                const isNum = numTypes.includes(col.type)
                let className = `py-2 px-3 ${isNum ? 'text-right font-mono' : ''}`
                if (col.type === 'currency' && val != null) {
                  className += val > 0 ? ' text-[var(--green)]' : val < 0 ? ' text-[var(--red)]' : ''
                }
                return <td key={col.key} className={className}>{fmt(val, col.type)}</td>
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {(!data || data.length === 0) && (
        <div className="text-center text-[var(--text-muted)] py-8">No data available</div>
      )}
    </div>
  )
}
