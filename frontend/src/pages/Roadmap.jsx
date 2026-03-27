/**
 * Roadmap page — Halcyon Lab development and scaling roadmap.
 *
 * MAINTAINER NOTE (for Claude Code or any agent editing this file):
 * When the roadmap changes — phases added, gates updated, items completed,
 * costs revised — update the ROADMAP_DATA object below. The UI renders
 * entirely from this data. Do NOT hardcode roadmap content in JSX.
 *
 * Last updated: 2026-03-24
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, Circle, Loader2, ChevronDown, ChevronRight, Lock, ArrowRight } from 'lucide-react'
import RevenueProjection from '../components/RevenueProjection'

// ═══════════════════════════════════════════════════════════════
// ROADMAP DATA — Update this object when the roadmap changes.
// CC: when completing sprints, update item statuses here.
// ═══════════════════════════════════════════════════════════════
const ROADMAP_DATA = {
  lastUpdated: '2026-03-27',

  phases: [
    {
      id: 'phase-1',
      name: 'Phase 1 — Bootcamp',
      status: 'active', // active | completed | locked
      capital: '$100K paper + $100 live',
      monthlyCost: '~$64/mo',
      description: '30-day intensive paper trading. Prove the system has an edge.',
      gate: {
        label: '50+ closed trades, positive expectancy, system proves edge',
        metrics: [
          { key: 'trades_closed', label: 'Closed trades', target: 50, op: '>=' },
          { key: 'win_rate', label: 'Win rate', target: 0.45, op: '>=', fmt: 'pct' },
          { key: 'sharpe_ratio', label: 'Sharpe', target: 0.5, op: '>=' },
          { key: 'expectancy_dollars', label: 'Expectancy', target: 0, op: '>', fmt: 'dollar' },
          { key: 'avg_rubric_score', label: 'Rubric score', target: 3.5, op: '>=' },
        ],
      },
      items: [
        { label: '7-source data enrichment', status: 'done' },
        { label: 'Bracket orders via Alpaca', status: 'done' },
        { label: 'Risk governor (8 hard limits)', status: 'done' },
        { label: 'Auditor agent (daily + weekly)', status: 'done' },
        { label: 'Validation holdout + A/B eval', status: 'done' },
        { label: 'Walk-forward backtesting', status: 'done' },
        { label: 'Curriculum SFT (3-stage)', status: 'done' },
        { label: 'News enrichment (Finnhub)', status: 'done' },
        { label: 'Quality pipeline + LLM-as-judge', status: 'done' },
        { label: 'Dashboard + WebSocket', status: 'done' },
        { label: 'XML output format', status: 'done' },
        { label: 'Self-blinding training pipeline', status: 'done' },
        { label: 'Process-first quality rubric', status: 'done' },
        { label: 'Re-run backfill with new methodology (976 examples)', status: 'done' },
        { label: 'Score + classify + fine-tune halcyon-v1', status: 'in-progress' },
        { label: 'Fund metrics + metric history trending', status: 'done' },
        { label: 'API cost tracking', status: 'done' },
        { label: 'Database indexes + codebase audit', status: 'done' },
        { label: 'Leakage detector (balanced accuracy)', status: 'done' },
        { label: '24/7 overnight schedule (Phase A)', status: 'done' },
        { label: 'Dashboard action buttons', status: 'done' },
        { label: 'Live activity feed', status: 'done' },
        { label: 'Statistical validation framework (PSR, bootstrap)', status: 'done' },
        { label: '50-trade gate evaluation script', status: 'done' },
        { label: 'SEC EDGAR NLP features (L-M + cautionary phrases)', status: 'done' },
        { label: 'Thorp-style graduated drawdown reduction', status: 'done' },
        { label: 'Research intelligence collector (#13)', status: 'done' },
        { label: 'Cloud dashboard (40+ API endpoints)', status: 'done' },
        { label: 'Revenue projection model', status: 'done' },
      ],
    },
    {
      id: 'phase-2',
      name: 'Phase 2 — Micro live',
      status: 'locked',
      capital: '$100 → $1,000 live',
      monthlyCost: '~$125/mo',
      description: 'Expand to ~325 stocks. Auto-execute with risk governor. No human approval.',
      gate: {
        label: 'Live trading proves execution quality and real-money edge',
        metrics: [
          { key: 'live_trades', label: 'Live trades', target: 50, op: '>=' },
          { key: 'live_paper_delta', label: 'Live vs paper', target: 20, op: '<=', fmt: 'pctAbs' },
          { key: 'sharpe_ratio', label: 'Sharpe (live)', target: 0.75, op: '>=' },
          { key: 'max_drawdown_pct', label: 'Max DD', target: 20, op: '<=', fmt: 'pctVal' },
          { key: 'beta', label: 'Beta', target: 0.5, op: '<=', fmt: '' },
        ],
      },
      items: [
        { label: 'Expand universe: S&P 100 → ~325 stocks (S&P 500 filtered by $100M+ ADV)', status: 'pending' },
        { label: 'Add GICS sector as input feature (sector conditioning)', status: 'pending' },
        { label: 'Upgrade data API to Polygon.io ($199/mo) for full US equity coverage', status: 'pending' },
        { label: 'LLC formation + trader tax status consultation', status: 'pending' },
        { label: 'Interactive Brokers account + IB adapter', status: 'pending' },
        { label: 'IB paper testing (2 weeks) → live with $500-$1K', status: 'pending' },
        { label: 'HSHS dashboard page (5-dimension system health score)', status: 'pending' },
        { label: 'AI Council dashboard page — 7 agents for strategic decisions', status: 'pending' },
        { label: 'Passive options data collection (EOD chains, VIX term structure, IV surfaces)', status: 'pending' },
        { label: 'Options-as-equity-signal (IV rank, put/call ratio, skew → equity model)', status: 'pending' },
        { label: 'Scale to 3,000–5,000 training examples', status: 'pending' },
        { label: 'GRPO training (at 100+ closed trades)', status: 'pending' },
        { label: 'RTX 3090 upgrade (~$800)', status: 'pending' },
        { label: 'Merge-and-reset LoRA protocol', status: 'pending' },
        { label: 'Golden ratio data mixing (62/38)', status: 'pending' },
        { label: 'Research Analyst — 2nd paper account for training data volume', status: 'pending' },
        { label: 'Google Trends + GSCPI signals', status: 'pending' },
        { label: '24/7 overnight schedule (Phase B + C)', status: 'pending' },
      ],
    },
    {
      id: 'phase-3',
      name: 'Phase 3 — Growth + Second Strategy',
      status: 'locked',
      capital: '$1,000 → $5,000',
      monthlyCost: '~$155/mo',
      description: 'Tiered autonomy by conviction level. Multiple data feeds.',
      gate: {
        label: 'Institutional-quality risk-adjusted returns',
        metrics: [
          { key: 'sharpe_ratio', label: 'Sharpe', target: 1.0, op: '>=' },
          { key: 'sortino_ratio', label: 'Sortino', target: 1.5, op: '>=' },
          { key: 'max_drawdown_pct', label: 'Max DD', target: 15, op: '<=', fmt: 'pctVal' },
          { key: 'profitable_months', label: 'Profitable months', target: 3, op: '>=' },
        ],
      },
      items: [
        { label: 'Regime-specific LoRA adapters (HMM)', status: 'pending' },
        { label: 'Sector-specific LoRA adapters (Tech, Healthcare, Energy, Financials)', status: 'pending' },
        { label: 'FMP consensus/fundamentals data ($29/mo)', status: 'pending' },
        { label: 'Qwen 2.5 14B production model', status: 'pending' },
        { label: 'Multi-teacher data generation', status: 'pending' },
        { label: 'Tiered data architecture (core/archive/recent)', status: 'pending' },
        { label: 'Options: backtesting framework + strategy validation', status: 'pending' },
        { label: 'Options: volatility analyst LoRA adapter training', status: 'pending' },
        { label: 'Options: 15-check risk governor for non-linear risk', status: 'pending' },
      ],
    },
    {
      id: 'phase-4',
      name: 'Phase 4 — Full Autonomous + Options Research',
      status: 'locked',
      capital: '$5,000 → $25,000',
      monthlyCost: '~$220/mo',
      description: 'All trades auto-executed within hard risk limits.',
      gate: {
        label: 'Investor-ready track record across market regimes',
        metrics: [
          { key: 'profitable_months', label: 'Profitable months', target: 6, op: '>=' },
          { key: 'sharpe_ratio', label: 'Sharpe', target: 1.2, op: '>=' },
          { key: 'sortino_ratio', label: 'Sortino', target: 2.0, op: '>=' },
          { key: 'max_drawdown_pct', label: 'Max DD', target: 12, op: '<=', fmt: 'pctVal' },
          { key: 'calmar_ratio', label: 'Calmar', target: 1.0, op: '>=' },
        ],
      },
      items: [
        { label: 'Portfolio-level risk (correlation, concentration)', status: 'pending' },
        { label: 'Weekly deep audit with trend analysis', status: 'pending' },
        { label: 'Learned confidence calibration', status: 'pending' },
        { label: 'Institutional risk reporting (P&L attribution, factor exposure, stress tests)', status: 'pending' },
        { label: 'Verified track record export (IB statements, BarclayHedge)', status: 'pending' },
        { label: 'Investor-ready documentation (compliance manual, risk templates, ODD materials)', status: 'pending' },
        { label: 'Options: paper trading credit spreads + iron condors (3+ months)', status: 'pending' },
      ],
    },
    {
      id: 'phase-5',
      name: 'Phase 5 — Scale + Fund Preparation',
      status: 'locked',
      capital: '$25,000 → $100,000+',
      monthlyCost: '~$500+/mo',
      description: 'Fund formation, audit, PPM, GIPS compliance.',
      gate: {
        label: 'Institutional allocation threshold',
        metrics: [
          { key: 'track_record_months', label: 'Audited months', target: 12, op: '>=' },
          { key: 'sharpe_ratio', label: 'Sharpe', target: 1.5, op: '>=' },
          { key: 'max_drawdown_pct', label: 'Max DD', target: 10, op: '<=', fmt: 'pctVal' },
        ],
      },
      items: [
        { label: 'Multi-setup families (breakout, momentum, mean reversion)', status: 'pending' },
        { label: 'Russell 1000 expansion (~500-700 stocks) if alpha proven at 325', status: 'pending' },
        { label: 'Options: live trading credit spreads + iron condors ($2K+ dedicated capital)', status: 'pending' },
        { label: 'Options: XSP/SPX index options via IB (Section 1256 tax treatment)', status: 'pending' },
        { label: 'Verified track record (Interactive Brokers or equivalent)', status: 'pending' },
        { label: 'Tax structure optimization (LLC, trader tax status, MTM election)', status: 'pending' },
        { label: 'Multi-account strategy isolation', status: 'pending' },
        { label: 'Regulatory research (RIA registration path for external capital)', status: 'pending' },
        { label: 'Family LP structure (General Partner + Limited Partners)', status: 'pending' },
      ],
    },
    {
      id: 'phase-6',
      name: 'Phase 6+ — Multi-Desk Expansion',
      status: 'locked',
      capital: '$500K+ AUM',
      monthlyCost: 'TBD',
      description: '5-desk architecture, published research, external capital.',
      gate: {
        label: 'Proven multi-strategy returns with audited track record',
        metrics: [],
      },
      items: [
        { label: '5-desk architecture (equity pullback, breakout, options vol, macro, event-driven)', status: 'pending' },
        { label: 'Published research / thought leadership', status: 'pending' },
        { label: 'External capital onboarding', status: 'pending' },
        { label: 'Intraday trading capability', status: 'pending' },
        { label: 'Multi-model inference serving', status: 'pending' },
      ],
    },
  ],

  hardware: [
    {
      phase: 'Phase 2 Build',
      cost: '$1,500-2,000',
      items: [
        'RTX 3090 24GB ($700-900)',
        'Ryzen 5 5600 ($100-150)',
        '32GB DDR4 ($60-80)',
        '1TB NVMe ($80-100)',
        'B550 mobo ($80-100)',
        '750W PSU ($80-100)',
        'Case + UPS ($150-250)',
      ],
      unlocks: '14B model, GRPO training, 24/7 uninterrupted operation',
    },
    {
      phase: 'Phase 4+ Build',
      cost: '$4,000-6,000',
      items: [
        'RTX 4090 or 2x RTX 3090 ($2,000-3,500)',
        'Ryzen 9 7900X ($300-400)',
        '64GB DDR5 ($150-200)',
        '2TB NVMe + 4TB HDD ($200-300)',
        '2.5GbE + cellular failover ($100-200)',
      ],
      unlocks: 'Multi-model inference, parallel training, redundant networking',
    },
  ],

  monthlyCosts: [
    { phase: 'Phase 1', cost: '$64/mo' },
    { phase: 'Phase 2', cost: '$125/mo' },
    { phase: 'Phase 3', cost: '$155/mo' },
    { phase: 'Phase 4', cost: '$220/mo' },
    { phase: 'Phase 5+', cost: '$500+/mo' },
  ],

  trainingPipeline: [
    { label: 'Self-blinded generation', detail: 'No outcome leak' },
    { label: 'XML format', detail: 'Structured metadata' },
    { label: 'Curriculum SFT', detail: '3 stages, 3 learning rates' },
    { label: 'GRPO (Phase 2)', detail: 'Outcome-based rewards' },
  ],

  businessTarget: {
    line1: 'Business model: compound returns on growing capital under management',
    line2: 'Paper \u2192 $1K live \u2192 $25K \u2192 $100K+ \u2192 verified track record \u2192 external capital',
  },
}

// ═══════════════════════════════════════════════════════════════
// Components
// ═══════════════════════════════════════════════════════════════

function StatusIcon({ status }) {
  if (status === 'done') return <CheckCircle2 size={16} className="shrink-0" style={{ color: 'var(--teal-500)' }} />
  if (status === 'in-progress') return <Loader2 size={16} className="animate-spin shrink-0" style={{ color: 'var(--amber-500)' }} />
  return <Circle size={16} className="shrink-0" style={{ color: 'var(--slate-400)' }} />
}

function PhaseProgress({ items }) {
  const done = items.filter(i => i.status === 'done').length
  const inProgress = items.filter(i => i.status === 'in-progress').length
  const total = items.length
  const pct = Math.round(((done + inProgress * 0.5) / total) * 100)

  return (
    <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--slate-400)' }}>
      <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--slate-600)' }}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${pct}%`,
            background: pct === 100 ? 'var(--success)' : 'var(--teal-500)',
          }}
        />
      </div>
      <span>{done}/{total} complete</span>
    </div>
  )
}

const phaseColors = {
  active: 'var(--teal-500)',
  completed: 'var(--teal-500)',
  locked: 'var(--slate-600)',
}

function GateMetric({ metric, currentValue }) {
  const val = currentValue
  const hasData = val != null && val !== undefined

  let passed = false
  if (hasData) {
    if (metric.op === '>=') passed = val >= metric.target
    else if (metric.op === '>') passed = val > metric.target
    else if (metric.op === '<=') passed = val <= metric.target
  }

  let displayVal = '--'
  let displayTarget = `${metric.target}`
  if (hasData) {
    if (metric.fmt === 'pct') {
      displayVal = `${(val * 100).toFixed(1)}%`
      displayTarget = `${(metric.target * 100).toFixed(0)}%`
    } else if (metric.fmt === 'dollar') {
      displayVal = `$${val.toFixed(2)}`
      displayTarget = `$${metric.target}`
    } else if (metric.fmt === 'pctVal' || metric.fmt === 'pctAbs') {
      displayVal = `${val.toFixed(1)}%`
      displayTarget = `${metric.target}%`
    } else {
      displayVal = typeof val === 'number' ? (Number.isInteger(val) ? `${val}` : val.toFixed(2)) : `${val}`
    }
  }

  const opSymbol = metric.op === '>=' ? '\u2265' : metric.op === '>' ? '>' : metric.op === '<=' ? '\u2264' : metric.op

  return (
    <div className="flex items-center gap-2 text-xs">
      <div className="w-2 h-2 rounded-full shrink-0" style={{ background: hasData ? (passed ? 'var(--teal-500)' : 'var(--danger)') : 'var(--slate-400)' }} />
      <span className="w-28" style={{ color: 'var(--slate-400)' }}>{metric.label}</span>
      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500, color: hasData ? (passed ? 'var(--teal-400)' : 'var(--danger)') : 'var(--slate-400)' }}>
        {displayVal}
      </span>
      <span style={{ color: 'var(--slate-400)' }}>{opSymbol} {displayTarget}</span>
    </div>
  )
}

function PhaseCard({ phase, kpis }) {
  const [expanded, setExpanded] = useState(phase.status === 'active')
  const isLocked = phase.status === 'locked'

  return (
    <div
      className="rounded-lg overflow-hidden border-l-4"
      style={{ border: '1px solid var(--slate-600)', borderLeftColor: phaseColors[phase.status] || phaseColors.locked, borderLeftWidth: '4px' }}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 text-left transition-colors"
        onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(30, 41, 59, 0.5)'}
        onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            {isLocked && <Lock size={14} style={{ color: 'var(--slate-400)' }} />}
            <span className="font-medium" style={{ color: 'var(--slate-100)' }}>{phase.name}</span>
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'var(--slate-600)', color: 'var(--slate-400)' }}>
              {phase.capital}
            </span>
            <span className="text-xs" style={{ color: 'var(--slate-400)' }}>{phase.monthlyCost}</span>
          </div>
          <p className="text-sm mt-1" style={{ color: 'var(--slate-300)' }}>{phase.description}</p>
          {phase.status !== 'locked' && (
            <div className="mt-2">
              <PhaseProgress items={phase.items} />
            </div>
          )}
        </div>
        {expanded ? <ChevronDown size={18} className="shrink-0 ml-2" style={{ color: 'var(--slate-400)' }} /> : <ChevronRight size={18} className="shrink-0 ml-2" style={{ color: 'var(--slate-400)' }} />}
      </button>

      {expanded && (
        <div className="px-4 pb-4" style={{ borderTop: '1px solid var(--slate-600)' }}>
          <ul className="mt-3 space-y-1.5">
            {phase.items.map((item, i) => (
              <li key={i} className="flex items-center gap-2 text-sm">
                <StatusIcon status={item.status} />
                <span style={{ color: item.status === 'done' ? 'var(--slate-400)' : 'var(--slate-100)', textDecoration: item.status === 'done' ? 'line-through' : 'none' }}>
                  {item.label}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {phase.gate && (
        <div className="px-4 py-3" style={{ background: 'var(--slate-700)', borderTop: '1px solid var(--slate-600)' }}>
          <div className="flex items-center gap-2 text-xs mb-2">
            <Lock size={12} style={{ color: 'var(--amber-500)' }} className="shrink-0" />
            <span className="font-medium" style={{ color: 'var(--slate-300)' }}>Gate</span>
          </div>
          {phase.gate.metrics ? (
            <div className="space-y-1.5 ml-5">
              {phase.gate.metrics.map((m, i) => (
                <GateMetric key={i} metric={m} currentValue={kpis ? kpis[m.key] : null} />
              ))}
            </div>
          ) : (
            <div className="text-xs ml-5" style={{ color: 'var(--slate-400)' }}>{phase.gate.label}</div>
          )}
        </div>
      )}
    </div>
  )
}

function PipelineStep({ step, isLast }) {
  return (
    <div className="flex items-center gap-2">
      <div className="rounded-lg px-3 py-2 text-center min-w-[120px]" style={{ border: '1px solid var(--slate-600)' }}>
        <div className="text-sm font-medium" style={{ color: 'var(--slate-100)' }}>{step.label}</div>
        <div className="text-xs" style={{ color: 'var(--slate-400)' }}>{step.detail}</div>
      </div>
      {!isLast && <ArrowRight size={16} className="shrink-0" style={{ color: 'var(--slate-400)' }} />}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════
// Page
// ═══════════════════════════════════════════════════════════════

export default function Roadmap() {
  const data = ROADMAP_DATA

  const { data: ctoData } = useQuery({
    queryKey: ['cto-report'],
    queryFn: () => fetch('/api/cto-report?days=30').then(r => r.json()),
    refetchInterval: 60000,
  })

  // Build a flat kpis object from CTO report data
  const ts = ctoData?.trade_summary || {}
  const fm = ctoData?.fund_metrics || {}
  const kpis = {
    trades_closed: ts.trades_closed || 0,
    win_rate: ts.win_rate || 0,
    sharpe_ratio: ts.sharpe_ratio || 0,
    expectancy_dollars: ts.expectancy_dollars || 0,
    max_drawdown_pct: ts.max_drawdown_pct || 0,
    avg_rubric_score: ctoData?.headline_kpis?.avg_rubric_score || null,
    sortino_ratio: fm.sortino_ratio || null,
    calmar_ratio: fm.calmar_ratio || null,
    beta: fm.beta || null,
    profitable_months: fm.monthly_batting_avg != null ? Math.round((fm.monthly_batting_avg / 100) * (fm.total_months || 0)) : null,
    live_trades: null,       // Phase 2+
    live_paper_delta: null,  // Phase 2+
  }

  const totalItems = data.phases.flatMap(p => p.items)
  const doneCount = totalItems.filter(i => i.status === 'done').length
  const totalCount = totalItems.length

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-medium" style={{ color: 'var(--slate-100)' }}>Roadmap</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--slate-400)' }}>
          Every gate is performance-based, not time-based. Updated {data.lastUpdated}.
        </p>
        <div className="mt-3 flex items-center gap-3">
          <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: 'var(--slate-600)' }}>
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{ width: `${Math.round((doneCount / totalCount) * 100)}%`, background: 'var(--teal-500)' }}
            />
          </div>
          <span className="text-sm whitespace-nowrap" style={{ color: 'var(--slate-300)' }}>
            {doneCount}/{totalCount} items complete ({Math.round((doneCount / totalCount) * 100)}%)
          </span>
        </div>
      </div>

      <div className="space-y-3">
        {data.phases.map(phase => (
          <PhaseCard key={phase.id} phase={phase} kpis={kpis} />
        ))}
      </div>

      {/* Revenue Projection Model */}
      <div className="rounded-lg p-4" style={{ background: 'var(--slate-800)', border: '1px solid var(--slate-600)' }}>
        <RevenueProjection />
      </div>

      {/* Hardware Roadmap */}
      {data.hardware && (
        <div className="space-y-3">
          <h2 className="text-sm font-medium" style={{ color: 'var(--slate-100)' }}>Hardware Roadmap</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data.hardware.map((hw, i) => (
              <div key={i} className="rounded-lg p-4" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-sm" style={{ color: 'var(--slate-100)' }}>{hw.phase}</span>
                  <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'var(--slate-600)', color: 'var(--slate-300)' }}>{hw.cost}</span>
                </div>
                <ul className="space-y-1 mb-3">
                  {hw.items.map((item, j) => (
                    <li key={j} className="text-xs" style={{ color: 'var(--slate-300)' }}>{item}</li>
                  ))}
                </ul>
                <div className="text-xs pt-2" style={{ borderTop: '1px solid var(--slate-600)', color: 'var(--teal-400)' }}>
                  Unlocks: {hw.unlocks}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Monthly Cost Timeline */}
      {data.monthlyCosts && (
        <div className="rounded-lg p-4" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
          <h2 className="text-sm font-medium mb-3" style={{ color: 'var(--slate-100)' }}>Monthly Cost by Phase</h2>
          <div className="flex items-end gap-3 justify-around">
            {data.monthlyCosts.map((mc, i) => {
              const costNum = parseInt(mc.cost.replace(/[^0-9]/g, '')) || 0
              const height = Math.max(20, Math.min(120, costNum / 5))
              return (
                <div key={i} className="flex flex-col items-center gap-1">
                  <span className="text-xs font-medium" style={{ fontFamily: 'var(--font-mono)', color: 'var(--teal-400)' }}>{mc.cost}</span>
                  <div className="w-12 rounded-t" style={{ height: `${height}px`, background: 'var(--teal-500)', opacity: 0.6 + (i * 0.08) }} />
                  <span className="text-xs" style={{ color: 'var(--slate-400)' }}>{mc.phase}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      <div>
        <h2 className="text-sm font-medium mb-3" style={{ color: 'var(--slate-100)' }}>Training pipeline (research-validated)</h2>
        <div className="flex flex-wrap items-center gap-2">
          {data.trainingPipeline.map((step, i) => (
            <PipelineStep key={i} step={step} isLast={i === data.trainingPipeline.length - 1} />
          ))}
        </div>
      </div>

      <div className="rounded-lg p-4" style={{ border: '1px solid var(--slate-600)', background: 'var(--slate-700)' }}>
        <div className="text-sm font-medium" style={{ color: 'var(--slate-100)' }}>{data.businessTarget.line1}</div>
        <div className="text-xs mt-1" style={{ color: 'var(--slate-400)' }}>{data.businessTarget.line2}</div>
      </div>

      <p className="text-xs text-center pb-4" style={{ color: 'var(--slate-400)' }}>
        The moat: combinatorial fusion of signals in structured LLM training data. Every trade teaches the model.
      </p>
    </div>
  )
}
