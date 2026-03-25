import { useEffect, useRef } from 'react'
import useWebSocket from '../hooks/useWebSocket'

const EVENT_COLORS = {
  trade_opened: 'bg-emerald-500',
  trade_closed: 'bg-emerald-500', // overridden per-event below
  training_complete: 'bg-emerald-500',
  action_complete: 'bg-emerald-500',
  scan_complete: 'bg-blue-500',
  scan_started: 'bg-blue-500',
  overnight_task: 'bg-blue-500',
  pre_market_refresh: 'bg-blue-500',
  training_started: 'bg-yellow-500',
  training_collection: 'bg-yellow-500',
  action_started: 'bg-yellow-500',
  order_submitted: 'bg-yellow-500',
  order_filled: 'bg-yellow-500',
  action_error: 'bg-red-500',
  error: 'bg-red-500',
}

function getEventColor(evt) {
  if (evt.type === 'trade_closed') {
    return (evt.data?.pnl_dollars || 0) >= 0 ? 'bg-emerald-500' : 'bg-red-500'
  }
  return EVENT_COLORS[evt.type] || 'bg-gray-500'
}

function formatEvent(evt) {
  const d = evt.data || {}
  switch (evt.type) {
    case 'scan_started':
      return 'Market scan started'
    case 'scan_complete':
      return `Scanned ${d.tickers_scanned || '?'} tickers, ${d.packets || 0} packets generated`
    case 'trade_opened':
      return `Opened ${d.side || 'BUY'} ${d.ticker || '?'}${d.score ? ` (score: ${d.score})` : ''}`
    case 'trade_closed': {
      const pnl = d.pnl_pct != null ? `${d.pnl_pct >= 0 ? '+' : ''}${d.pnl_pct.toFixed(1)}%` : ''
      const dollars = d.pnl_dollars != null ? ` ($${d.pnl_dollars >= 0 ? '+' : ''}${d.pnl_dollars.toFixed(2)})` : ''
      return `Closed ${d.ticker || '?'} ${pnl}${dollars}`
    }
    case 'training_started':
      return `Training pipeline started${d.examples ? ` (${d.examples} examples)` : ''}`
    case 'training_complete':
      return `Training complete: ${d.model || 'new model'}${d.loss ? ` (loss: ${d.loss.toFixed(4)})` : ''}`
    case 'training_collection':
      return `Collected ${d.examples_collected || 0} training examples`
    case 'overnight_task':
      return `${(d.task || 'task').replace(/_/g, ' ')}: ${d.status || '?'}${d.articles_cached ? ` (${d.articles_cached} articles)` : ''}${d.tickers_enriched ? ` (${d.tickers_enriched} tickers)` : ''}`
    case 'action_started':
      return `Action started: ${d.action || '?'}`
    case 'action_complete':
      return `Action complete: ${d.action || '?'}`
    case 'action_error':
      return `Action failed: ${d.action || '?'} — ${d.error || 'unknown error'}`
    case 'order_submitted':
      return `Order submitted: ${d.ticker || '?'} ${d.order_type || ''}`
    case 'order_filled':
      return `Order filled: ${d.ticker || '?'}${d.price ? ` @ $${d.price}` : ''}`
    default:
      return `${evt.type}: ${JSON.stringify(d).slice(0, 80)}`
  }
}

export default function ActivityFeed() {
  const { events, connected, clearEvents } = useWebSocket()
  const scrollRef = useRef(null)

  // Auto-scroll to newest (top of list since events are newest-first)
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0
    }
  }, [events.length])

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm text-[var(--text-muted)] uppercase tracking-wide">Live Activity</h3>
        <div className="flex items-center gap-3">
          {events.length > 0 && (
            <button
              onClick={clearEvents}
              className="text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
            >
              Clear
            </button>
          )}
          <div className="flex items-center gap-1.5">
            <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400' : 'bg-red-400'}`} />
            <span className="text-xs text-[var(--text-muted)]">{connected ? 'Connected' : 'Disconnected'}</span>
          </div>
        </div>
      </div>
      <div ref={scrollRef} className="space-y-1 max-h-64 overflow-y-auto text-sm font-mono">
        {events.length === 0 && (
          <p className="text-[var(--text-muted)] text-xs">Waiting for events...</p>
        )}
        {events.map((evt, i) => (
          <div key={i} className="flex gap-2 items-start">
            <span className="text-[var(--text-muted)] text-xs shrink-0 pt-0.5">
              {new Date(evt.timestamp).toLocaleTimeString()}
            </span>
            <span className={`w-2 h-2 rounded-full shrink-0 mt-1.5 ${getEventColor(evt)}`} />
            <span className="text-[var(--text-secondary)]">{formatEvent(evt)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
