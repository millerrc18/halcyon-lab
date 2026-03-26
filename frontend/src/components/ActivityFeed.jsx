import { useEffect, useRef } from 'react'
import useWebSocket from '../hooks/useWebSocket'

const EVENT_COLORS = {
  trade_opened: 'bg-[var(--success)]',
  trade_closed: 'bg-[var(--success)]',
  training_complete: 'bg-[var(--success)]',
  action_complete: 'bg-[var(--success)]',
  scan_complete: 'bg-[var(--info)]',
  scan_started: 'bg-[var(--info)]',
  overnight_task: 'bg-[var(--info)]',
  pre_market_refresh: 'bg-[var(--info)]',
  training_started: 'bg-[var(--warning)]',
  training_collection: 'bg-[var(--warning)]',
  action_started: 'bg-[var(--warning)]',
  order_submitted: 'bg-[var(--warning)]',
  order_filled: 'bg-[var(--warning)]',
  action_error: 'bg-[var(--danger)]',
  error: 'bg-[var(--danger)]',
}

function getEventColor(evt) {
  if (evt.type === 'trade_closed') {
    return (evt.data?.pnl_dollars || 0) >= 0 ? 'bg-[var(--success)]' : 'bg-[var(--danger)]'
  }
  return EVENT_COLORS[evt.type] || 'bg-[var(--slate-400)]'
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
    <div className="rounded-lg p-4" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm uppercase tracking-wide" style={{ color: 'var(--slate-400)' }}>Live Activity</h3>
        <div className="flex items-center gap-3">
          {events.length > 0 && (
            <button
              onClick={clearEvents}
              className="text-xs hover:opacity-80"
              style={{ color: 'var(--slate-400)' }}
            >
              Clear
            </button>
          )}
          <div className="flex items-center gap-1.5">
            <div className={`w-2 h-2 rounded-full`} style={{ background: connected ? 'var(--success)' : 'var(--danger)' }} />
            <span className="text-xs" style={{ color: 'var(--slate-400)' }}>{connected ? 'Connected' : 'Disconnected'}</span>
          </div>
        </div>
      </div>
      <div ref={scrollRef} className="space-y-1 max-h-64 overflow-y-auto text-sm" style={{ fontFamily: 'var(--font-mono)' }}>
        {events.length === 0 && (
          <p className="text-xs" style={{ color: 'var(--slate-400)' }}>Waiting for events...</p>
        )}
        {events.map((evt, i) => (
          <div key={i} className="flex gap-2 items-start">
            <span className="text-xs shrink-0 pt-0.5" style={{ color: 'var(--slate-400)' }}>
              {new Date(evt.timestamp).toLocaleTimeString()}
            </span>
            <span className={`w-2 h-2 rounded-full shrink-0 mt-1.5 ${getEventColor(evt)}`} />
            <span style={{ color: 'var(--slate-300)' }}>{formatEvent(evt)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
