const variants = {
  success: 'bg-[var(--green-bg)] text-[var(--green)] border-[var(--green)]',
  danger: 'bg-[var(--red-bg)] text-[var(--red)] border-[var(--red)]',
  warning: 'bg-[var(--amber-bg)] text-[var(--amber)] border-[var(--amber)]',
  info: 'bg-[var(--blue-bg)] text-[var(--blue)] border-[var(--blue)]',
  neutral: 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)] border-[var(--border)]',
}

export default function StatusBadge({ text, variant = 'neutral' }) {
  return (
    <span className={`inline-block px-2 py-0.5 text-xs rounded border ${variants[variant] || variants.neutral}`}>
      {text}
    </span>
  )
}
