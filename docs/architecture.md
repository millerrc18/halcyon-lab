<!-- Counts verified 2026-03-28: 35 DB tables, 109 API routes, 141 Python files, 1064 tests. -->
# Halcyon Lab — System Architecture

## System Pipeline

```
┌─────────────────────────────────────────────────────────┐
│                    SCAN CYCLE (30min)                     │
├─────────────────────────────────────────────────────────┤
│ Universe (S&P 100 → ~325 stocks in Phase 2)             │
│   ↓                                                     │
│ Data Ingestion (yfinance OHLCV + SPY benchmark)         │
│   ↓                                                     │
│ Feature Engine (20+ indicators per ticker)               │
│   ↓                                                     │
│ Data Enrichment (fundamentals + insiders + news + macro) │
│   ↓                                                     │
│ Setup Classifier (6 setup types per ticker)              │
│   ↓                                                     │
│ Ranking (composite score 0-100)                         │
│   ↓                                                     │
│ Qualification (packet-worthy ≥70, watchlist ≥45)         │
│   ↓                                                     │
│ Risk Governor (8 checks + kill switch)                   │
│   ↓                                                     │
│ LLM Packet Writer (Ollama/halcyon-v1 → prose commentary)│
│   ↓                                                     │
│ Dual Execution (paper + live if enabled)                │
│   ↓                                                     │
│ Journal + Telegram + Dashboard + WebSocket Broadcast     │
└─────────────────────────────────────────────────────────┘
```

## Database Schema (35 tables)

### Core Trading
- **recommendations** — Trade recommendations with scores, thesis, outcomes
- **shadow_trades** — Paper and live trade execution tracking with MFE/MAE/P&L

### Training Pipeline
- **training_examples** — Training data with input/output/scores/curriculum stage
- **model_versions** — Model registry with versioning, holdout scores, status
- **model_evaluations** — A/B testing between models
- **preference_pairs** — DPO training data (chosen vs rejected)
- **canary_evaluations** — Canary model evaluation checkpoints
- **quality_drift_metrics** — Training data quality drift tracking

### Evaluation & Audit
- **audit_reports** — Daily and weekly system audit results
- **metric_snapshots** — Historical metrics for trending

### Operations
- **api_costs** — API call token usage and cost tracking
- **activity_log** — System activity event log
- **overnight_run_log** — Overnight schedule execution log
- **schedule_metrics** — Compute schedule utilization metrics
- **sync_state** — Render sync state tracking (last_synced_at per table)

### Data Collection (overnight pipeline — 12 collectors)
- **options_chains** — EOD options chain snapshots (strikes, IV, Greeks, OI)
- **options_metrics** — Derived per-ticker signals (IV rank, put/call ratios, skew)
- **vix_term_structure** — VIX family snapshots with term structure ratios
- **cboe_ratios** — Market-wide put/call ratios
- **macro_snapshots** — FRED macro indicator snapshots (34+ series)
- **google_trends** — Market-wide sentiment terms (crash, recession, inflation, etc.)
- **edgar_filings** — SEC 10-K, 10-Q, 8-K filings with parsed sections
- **insider_transactions** — Form 4 insider buy/sell activity via Finnhub
- **short_interest** — FINRA short interest snapshots (biweekly)
- **analyst_estimates** — Consensus recommendations and price targets
- **fed_communications** — FOMC statements, minutes, Beige Book, speeches
- **setup_signals** — Setup classifier results per ticker per scan

### Research Intelligence
- **research_papers** — Collected ML/finance research papers with abstracts
- **research_digests** — AI-generated summaries of research paper batches
- **research_docs** — Internal research documents (strategy, infrastructure, branding)

### Scanning & Signals
- **scan_metrics** — Per-scan cycle performance metrics (duration, ticker counts)
- **validation_results** — System validation dashboard results

### AI Council
- **council_sessions** — Council deliberation session metadata and consensus
- **council_votes** — Individual agent votes per round per session

## API Routes (109 — 49 local + 60 cloud)

### System & Status
| Route | Method | Description |
|-------|--------|-------------|
| `/api/diagnostics` | GET | DB table health check (pass/fail per table) |
| `/api/status` | GET | System status |
| `/api/preflight` | GET | Preflight health check |
| `/api/config` | GET | Current configuration |
| `/api/config` | PUT | Update configuration |
| `/api/cto-report` | GET | CTO performance report |
| `/api/costs` | GET | API cost summary |
| `/api/halt-trading` | POST | Emergency halt |
| `/api/resume-trading` | POST | Resume trading |
| `/api/halt-status` | GET | Current halt status |
| `/api/audit/latest` | GET | Latest audit report |
| `/api/audit/history` | GET | Audit report history |
| `/api/metric-history` | GET | Rolling metric snapshots |
| `/api/data-collection-stats` | GET | Data collection pipeline stats |
| `/api/earnings` | GET | Upcoming earnings calendar |
| `/api/activity-log` | GET | Recent activity events |
| `/api/schedule-metrics` | GET | Compute schedule utilization |

### Scanning
| Route | Method | Description |
|-------|--------|-------------|
| `/api/scan` | POST | Trigger scan |
| `/api/scan/latest` | GET | Most recent scan results |
| `/api/morning-watchlist` | POST | Generate morning watchlist |
| `/api/eod-recap` | POST | Generate EOD recap |

### Shadow & Live Trading
| Route | Method | Description |
|-------|--------|-------------|
| `/api/shadow/open` | GET | Open shadow trades |
| `/api/shadow/closed` | GET | Closed trades with metrics |
| `/api/shadow/account` | GET | Alpaca account info |
| `/api/shadow/metrics` | GET | Shadow trading metrics |
| `/api/shadow/close/{ticker}` | POST | Close a shadow position |

### Packets
| Route | Method | Description |
|-------|--------|-------------|
| `/api/packets` | GET | Recent trade packets |
| `/api/packets/{id}` | GET | Single packet detail |

### Review
| Route | Method | Description |
|-------|--------|-------------|
| `/api/review/pending` | GET | Pending reviews |
| `/api/review/scorecard` | GET | Review scorecard |
| `/api/review/postmortems` | GET | Postmortem list |
| `/api/review/postmortem/{id}` | GET | Postmortem detail |
| `/api/review/{id}` | GET | Get recommendation for review |
| `/api/review/{id}` | POST | Submit review |
| `/api/review/mark-executed/{ticker}` | POST | Mark trade as executed |

### Training
| Route | Method | Description |
|-------|--------|-------------|
| `/api/training/status` | GET | Training pipeline status |
| `/api/training/versions` | GET | Model version history |
| `/api/training/report` | GET | Training report |
| `/api/training/bootstrap` | POST | Bootstrap training data |
| `/api/training/train` | POST | Trigger training |
| `/api/training/rollback` | POST | Rollback model |

### Documentation
| Route | Method | Description |
|-------|--------|-------------|
| `/api/docs` | GET | Documentation list (35+ docs from research_docs table) |
| `/api/docs/{id}` | GET | Document content from research_docs |
| `/api/council/session/{id}` | GET | Full council session detail with agent votes |
| `/api/activity/feed` | GET | Recent activity log entries (limit, event_type) |
| `/api/live/trades` | GET | Live trades (source='live' in shadow_trades) |
| `/api/live/summary` | GET | Live account summary metrics |
| `/api/settings` | GET | Current safe config values |
| `/api/settings` | POST | Update config (local only) |
| `/api/live/reconcile` | POST | Trigger live trade reconciliation (local CLI only) |

### Background Actions
| Route | Method | Description |
|-------|--------|-------------|
| `/api/actions/scan` | POST | Trigger scan (background) |
| `/api/actions/cto-report` | POST | Generate CTO report (background) |
| `/api/actions/collect-training` | POST | Collect training data (background) |
| `/api/actions/train-pipeline` | POST | Run full training pipeline (background) |
| `/api/actions/score` | POST | Score unscored examples (background) |
| `/api/actions/collect-data` | POST | Run data collection (background) |

### WebSocket
| Route | Protocol | Description |
|-------|----------|-------------|
| `/ws/live` | WebSocket | Real-time event stream |

## Training Pipeline Flow

```
Self-Blinding Generation (Claude — NO outcome visibility)
                         ↓
               Quality Scoring (LLM-as-judge, 6 dimensions)
                         ↓
               Outcome Leakage Detection (balanced accuracy)
                         ↓
               Classify Difficulty → Assign Curriculum Stage
                         ↓
              ┌──────────┼──────────┐
              ↓          ↓          ↓
        Stage 1      Stage 2     Stage 3
       Structure    Evidence    Decision
       (lr=3e-4)   (lr=2e-4)   (lr=1e-4)
              └──────────┼──────────┘
                         ↓
                   DPO Refinement (if ≥100 preference pairs)
                         ↓
                   Holdout Evaluation
                         ↓
                   A/B Shadow Evaluation
                         ↓
                   Promote or Rollback
```

## Risk Governor Checks (8)

1. **Emergency Halt** — Kill switch check (file-based persistence)
2. **Daily Loss Limit** — Halt if portfolio drops 3% in a day
3. **Position Size** — No single position > 10% of equity
4. **Max Open Positions** — Reject if at position limit
5. **Sector Concentration** — No sector > 30% of portfolio
6. **Correlation** — No more than 3 positions in same sector
7. **Volatility Halt** — No new longs if VIX proxy > 35%
8. **Duplicate Check** — No duplicate positions in same ticker

## Live Trading Dual Execution Flow

When live trading is enabled, every scan cycle runs dual execution: one paper trade (shadow) and one live trade for each qualifying recommendation. This allows continued model training from paper results while deploying real capital.

```
Packet-Worthy Recommendation
              ↓
    ┌─────────┴─────────┐
    ↓                   ↓
Paper Execution     Live Execution
(always runs)       (if enabled)
    ↓                   ↓
Risk Governor       Live Risk Governor
(8 checks)          (8 checks + extra guards)
    ↓                   ↓
Paper Bracket       Live Bracket Order
Order (Alpaca)      (Alpaca live account)
    ↓                   ↓
shadow_trades       shadow_trades
source="paper"      source="live"
```

**Live-only safety guards** (in addition to standard 8 risk checks):
- Capital guard: halt if equity drops below 50% of starting capital
- Daily loss limit: halt if daily P&L exceeds -5% of capital
- LLM commentary required (no template fallback)
- Min score filter (configurable via `live_trading.min_score`)
- Max price filter (configurable via `live_trading.max_price`)
- First scan of day (9:30 AM) is skipped to avoid opening-volatility entries

Both paper and live trades are stored in the same `shadow_trades` table, distinguished by the `source` column (`paper` vs `live`). Dashboard, Telegram commands, and CLI all show paper/live breakdowns.

## AI Council Data Flow

The AI Council implements a modified Delphi protocol with 5 specialized agents deliberating across 3 rounds to produce market positioning consensus.

```
Trigger (daily schedule, strategic event, or on-demand)
                    ↓
        Build Shared Context
   (market regime, open trades, recent P&L,
    sector analysis, macro indicators)
                    ↓
           ┌────────┼────────┐
           ↓        ↓        ↓
     Round 1: Independent Assessment
   ┌────────┬────────┬────────┬────────┬────────┐
   │ Risk   │ Alpha  │ Data   │ Regime │ Devil's│
   │Officer │Strat.  │Sci.    │Analyst │Advocate│
   └────┬───┴────┬───┴────┬───┴────┬───┴────┬───┘
        └────────┼────────┼────────┼────────┘
                 ↓
     Round 2: Cross-Examination
   (agents see each other's R1 positions,
    challenge reasoning, update views)
                 ↓
     Round 3: Final Vote
   (binding position + confidence 1-10)
                 ↓
        Tally Votes (confidence-weighted)
                 ↓
   ┌─────────────┴─────────────┐
   ↓                           ↓
council_sessions            council_votes
(consensus, confidence,     (per-agent, per-round
 contested flag)             positions and rationale)
```

**Agent specializations:**
- **Risk Officer** — Portfolio risk, drawdown, correlation, position sizing
- **Alpha Strategist** — Trade opportunities, sector rotation, entry timing
- **Data Scientist** — Statistical signals, model performance, data quality
- **Regime Analyst** — Market regime, macro conditions, trend assessment
- **Devil's Advocate** — Challenges consensus, surfaces blind spots

## Render Sync Architecture

A background daemon thread syncs local SQLite data to a Render-hosted Postgres instance for the cloud dashboard, running every 120 seconds.

```
Local SQLite (ai_research_desk.sqlite3)
              ↓
     sync_state table
     (last_synced_at per table)
              ↓
  ┌───────────┴───────────┐
  ↓                       ↓
Incremental             Latest-only
(rows where             (drop + re-insert
 updated_at >            latest snapshot)
 last_synced_at)
  ↓                       ↓
  └───────────┬───────────┘
              ↓
     Render Postgres
     (cloud dashboard)
```

**Synced tables (25+):** shadow_trades, recommendations, model_versions, metric_snapshots, audit_reports, schedule_metrics, earnings_calendar, options_metrics, vix_term_structure, macro_snapshots, council_sessions, council_votes, insider_transactions, short_interest, analyst_estimates, fed_communications, edgar_filings, api_costs, training_examples, activity_log, setup_signals, quality_drift_metrics, canary_evaluations, research_papers, research_digests, scan_metrics, research_docs, validation_results. Modes: incremental (keyed on updated_at/created_at), latest_only (snapshot replacement), or full (complete re-sync).

Failures are logged and retried next cycle. The sync thread never crashes the main process.

## Setup Classifier Pipeline

Every scan cycle classifies each stock into one of 6 setup types using 5 discriminative features. Results are stored for desk routing and future multi-strategy support.

```
OHLCV Data (60-day window)
         ↓
5 Discriminative Features
  ├── ADX (trend strength)
  ├── ATR/Price ratio (volatility profile)
  ├── Volume profile (avg volume ratio)
  ├── Price vs MAs (50/200 day position)
  └── RSI (momentum state)
         ↓
Rule-Based Classifier
         ↓
6 Setup Types
  ├── pullback_in_uptrend   → Equity Swing Desk (current)
  ├── breakout_momentum     → Equity Momentum Desk (Phase 5)
  ├── mean_reversion        → Intraday Desk (Phase 6)
  ├── volatility_squeeze    → Options Volatility Desk (Phase 3-4)
  ├── trend_continuation    → Equity Swing Desk (current)
  └── range_bound           → Options Volatility Desk (Phase 3-4)
         ↓
setup_signals table
(ticker, setup_type, confidence, desk_routing)
```

Each classification includes a confidence score and desk routing recommendation. The current Equity Swing Desk uses `pullback_in_uptrend` and `trend_continuation` setups. Other setup types are logged for future desk launches.

## 24/7 Overnight Schedule

```
5:30 PM  Post-close capture (final prices, MFE/MAE update)
6:00 PM  Training data collection (closed trade → training example)
6:45 PM  DPO preference pair generation
7:00 PM  Walk-forward backtesting
9:30 PM  Data collection (12 collectors: options, VIX, macro, trends, CBOE, earnings,
                          EDGAR, insider, short interest, Fed comms, analyst estimates)
10:00 PM News ingestion (full universe, Finnhub)
11:00 PM Enrichment pre-cache (fundamentals, insiders, macro)
11:05 PM Auxiliary model training (regime classifier)
1:00 AM  Feature importance computation
2:30 AM  Leakage detector with model probing
4:30 AM  DB maintenance, health checks, backups
6:00 AM  Pre-market refresh
```

Activated with `python -m src.main watch --overnight`
