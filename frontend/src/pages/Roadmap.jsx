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
import { CheckCircle2, Circle, Loader2, ChevronDown, ChevronRight, Lock, ArrowRight } from 'lucide-react'

// ═══════════════════════════════════════════════════════════════
// ROADMAP DATA — Update this object when the roadmap changes.
// CC: when completing sprints, update item statuses here.
// ═══════════════════════════════════════════════════════════════
const ROADMAP_DATA = {
  lastUpdated: '2026-03-24',

  phases: [
    {
      id: 'phase-1',
      name: 'Phase 1 — Bootcamp',
      status: 'active', // active | completed | locked
      capital: 'Paper ($100K Alpaca)',
      monthlyCost: '$5/mo',
      description: '30-day intensive paper trading. Prove the system has an edge.',
      gate: {
        label: '50+ closed trades, positive expectancy, win rate > 45%',
      },
      items: [
        { label: '7-source data enrichment', status: 'done' },
        { label: 'Bracket orders via Alpaca', status: 'done' },
        { label: 'Risk governor (7 hard limits)', status: 'done' },
        { label: 'Auditor agent (daily + weekly)', status: 'done' },
        { label: 'Validation holdout + A/B eval', status: 'done' },
        { label: 'Walk-forward backtesting', status: 'done' },
        { label: 'Curriculum SFT (3-stage)', status: 'done' },
        { label: 'News enrichment (Finnhub)', status: 'done' },
        { label: 'Quality pipeline + LLM-as-judge', status: 'done' },
        { label: 'Dashboard + WebSocket', status: 'done' },
        { label: 'XML output format', status: 'in-progress' },
        { label: 'Self-blinding training pipeline', status: 'in-progress' },
        { label: 'Process-first quality rubric', status: 'in-progress' },
        { label: 'Re-run backfill with new methodology', status: 'pending' },
        { label: 'Score + classify + fine-tune halcyon-v1', status: 'pending' },
      ],
    },
    {
      id: 'phase-2',
      name: 'Phase 2 — Micro live',
      status: 'locked',
      capital: '$500–$1,000',
      monthlyCost: '$85/mo',
      description: 'Auto-execute with risk governor. No human approval. Shadow runs in parallel.',
      gate: {
        label: 'Live matches paper within 20%, 50+ live trades',
      },
      items: [
        { label: 'Options flow data ($50/mo Unusual Whales)', status: 'pending' },
        { label: 'Scale to 3,000–5,000 training examples', status: 'pending' },
        { label: 'GRPO training (at 100+ closed trades)', status: 'pending' },
        { label: 'RTX 3090 upgrade (~$800)', status: 'pending' },
        { label: 'Merge-and-reset LoRA protocol', status: 'pending' },
        { label: 'Golden ratio data mixing (62/38)', status: 'pending' },
        { label: 'Live Alpaca account + reconciliation', status: 'pending' },
        { label: 'Google Trends + GSCPI signals', status: 'pending' },
      ],
    },
    {
      id: 'phase-3',
      name: 'Phase 3 — Growth',
      status: 'locked',
      capital: '$5K–$25K',
      monthlyCost: '$135/mo',
      description: 'Tiered autonomy by conviction level. Multiple data feeds.',
      gate: {
        label: '3 months profitable, Sharpe > 1.0, max drawdown < 15%',
      },
      items: [
        { label: 'Regime-specific LoRA adapters (HMM)', status: 'pending' },
        { label: 'Polygon.io + FMP data ($51/mo)', status: 'pending' },
        { label: 'Qwen 2.5 14B production model', status: 'pending' },
        { label: 'Multi-teacher data generation', status: 'pending' },
        { label: 'Tiered data architecture (core/archive/recent)', status: 'pending' },
      ],
    },
    {
      id: 'phase-4',
      name: 'Phase 4 — Full autonomous',
      status: 'locked',
      capital: '$25K+',
      monthlyCost: '$135/mo',
      description: 'All trades auto-executed within hard risk limits.',
      gate: {
        label: '6 months profitable, consistent across market regimes',
      },
      items: [
        { label: 'Portfolio-level risk (correlation, concentration)', status: 'pending' },
        { label: 'Weekly deep audit with trend analysis', status: 'pending' },
        { label: 'Learned confidence calibration', status: 'pending' },
      ],
    },
    {
      id: 'phase-5',
      name: 'Phase 5 — Scale + monetize',
      status: 'locked',
      capital: 'Variable',
      monthlyCost: '$135/mo',
      description: 'Multi-strategy, newsletter launch, expanded universe.',
      gate: null,
      items: [
        { label: 'Multi-setup families (breakout, momentum, MR)', status: 'pending' },
        { label: 'Newsletter launch ($29–99/mo)', status: 'pending' },
        { label: 'S&P 500 expanded universe', status: 'pending' },
        { label: 'Signal marketplace (Collective2)', status: 'pending' },
        { label: 'Multi-account strategy isolation', status: 'pending' },
      ],
    },
  ],

  trainingPipeline: [
    { label: 'Self-blinded generation', detail: 'No outcome leak' },
    { label: 'XML format', detail: 'Structured metadata' },
    { label: 'Curriculum SFT', detail: '3 stages, 3 learning rates' },
    { label: 'GRPO (Phase 2)', detail: 'Outcome-based rewards' },
  ],

  businessTarget: {
    line1: 'Target: $500K–$1M ARR via newsletter ($29–99/mo) + signal marketplace',
    line2: 'Breakeven at 41 subscribers. 50%+ margins at scale. $5–15M exit at $1M ARR.',
  },
}

// ═══════════════════════════════════════════════════════════════
// Components
// ═══════════════════════════════════════════════════════════════

function StatusIcon({ status }) {
  if (status === 'done') return <CheckCircle2 size={16} className="text-emerald-500 shrink-0" />
  if (status === 'in-progress') return <Loader2 size={16} className="text-amber-500 animate-spin shrink-0" />
  return <Circle size={16} className="text-[var(--text-muted)] shrink-0" />
}

function PhaseProgress({ items }) {
  const done = items.filter(i => i.status === 'done').length
  const inProgress = items.filter(i => i.status === 'in-progress').length
  const total = items.length
  const pct = Math.round(((done + inProgress * 0.5) / total) * 100)

  return (
    <div className="flex items-center gap-3 text-xs text-[var(--text-muted)]">
      <div className="flex-1 h-1.5 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${pct}%`,
            background: pct === 100 ? 'var(--color-text-success, #22c55e)' : 'var(--color-text-info, #3b82f6)',
          }}
        />
      </div>
      <span>{done}/{total} complete</span>
    </div>
  )
}

const phaseColors = {
  active: 'border-l-emerald-500',
  completed: 'border-l-emerald-500',
  locked: 'border-l-[var(--border)]',
}

function PhaseCard({ phase }) {
  const [expanded, setExpanded] = useState(phase.status === 'active')
  const isLocked = phase.status === 'locked'

  return (
    <div
      className={`border border-[var(--border)] rounded-lg overflow-hidden border-l-4 ${phaseColors[phase.status] || phaseColors.locked}`}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-[var(--bg-tertiary)]/50 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            {isLocked && <Lock size={14} className="text-[var(--text-muted)]" />}
            <span className="font-medium text-[var(--text-primary)]">{phase.name}</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--bg-tertiary)] text-[var(--text-muted)]">
              {phase.capital}
            </span>
            <span className="text-xs text-[var(--text-muted)]">{phase.monthlyCost}</span>
          </div>
          <p className="text-sm text-[var(--text-secondary)] mt-1">{phase.description}</p>
          {phase.status !== 'locked' && (
            <div className="mt-2">
              <PhaseProgress items={phase.items} />
            </div>
          )}
        </div>
        {expanded ? <ChevronDown size={18} className="text-[var(--text-muted)] shrink-0 ml-2" /> : <ChevronRight size={18} className="text-[var(--text-muted)] shrink-0 ml-2" />}
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-[var(--border)]">
          <ul className="mt-3 space-y-1.5">
            {phase.items.map((item, i) => (
              <li key={i} className="flex items-center gap-2 text-sm">
                <StatusIcon status={item.status} />
                <span className={item.status === 'done' ? 'text-[var(--text-muted)] line-through' : 'text-[var(--text-primary)]'}>
                  {item.label}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {phase.gate && (
        <div className="px-4 py-2.5 bg-[var(--bg-tertiary)] border-t border-[var(--border)] flex items-center gap-2 text-xs">
          <Lock size={12} className="text-amber-500 shrink-0" />
          <span className="text-[var(--text-secondary)]">Gate: {phase.gate.label}</span>
        </div>
      )}
    </div>
  )
}

function PipelineStep({ step, isLast }) {
  return (
    <div className="flex items-center gap-2">
      <div className="border border-[var(--border)] rounded-lg px-3 py-2 text-center min-w-[120px]">
        <div className="text-sm font-medium text-[var(--text-primary)]">{step.label}</div>
        <div className="text-xs text-[var(--text-muted)]">{step.detail}</div>
      </div>
      {!isLast && <ArrowRight size={16} className="text-[var(--text-muted)] shrink-0" />}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════
// Page
// ═══════════════════════════════════════════════════════════════

export default function Roadmap() {
  const data = ROADMAP_DATA

  const totalItems = data.phases.flatMap(p => p.items)
  const doneCount = totalItems.filter(i => i.status === 'done').length
  const totalCount = totalItems.length

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-medium text-[var(--text-primary)]">Roadmap</h1>
        <p className="text-sm text-[var(--text-muted)] mt-1">
          Every gate is performance-based, not time-based. Updated {data.lastUpdated}.
        </p>
        <div className="mt-3 flex items-center gap-3">
          <div className="flex-1 h-2 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
            <div
              className="h-full bg-emerald-500 rounded-full transition-all duration-700"
              style={{ width: `${Math.round((doneCount / totalCount) * 100)}%` }}
            />
          </div>
          <span className="text-sm text-[var(--text-secondary)] whitespace-nowrap">
            {doneCount}/{totalCount} items complete ({Math.round((doneCount / totalCount) * 100)}%)
          </span>
        </div>
      </div>

      <div className="space-y-3">
        {data.phases.map(phase => (
          <PhaseCard key={phase.id} phase={phase} />
        ))}
      </div>

      <div>
        <h2 className="text-sm font-medium text-[var(--text-primary)] mb-3">Training pipeline (research-validated)</h2>
        <div className="flex flex-wrap items-center gap-2">
          {data.trainingPipeline.map((step, i) => (
            <PipelineStep key={i} step={step} isLast={i === data.trainingPipeline.length - 1} />
          ))}
        </div>
      </div>

      <div className="border border-[var(--border)] rounded-lg p-4 bg-[var(--bg-secondary)]">
        <div className="text-sm font-medium text-[var(--text-primary)]">{data.businessTarget.line1}</div>
        <div className="text-xs text-[var(--text-muted)] mt-1">{data.businessTarget.line2}</div>
      </div>

      <p className="text-xs text-[var(--text-muted)] text-center pb-4">
        The moat: combinatorial fusion of signals in structured LLM training data. Every trade teaches the model.
      </p>
    </div>
  )
}
