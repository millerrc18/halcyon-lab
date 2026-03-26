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
│ Ranking (composite score 0-100)                         │
│   ↓                                                     │
│ Qualification (packet-worthy ≥70, watchlist ≥45)         │
│   ↓                                                     │
│ Risk Governor (8 checks + kill switch)                   │
│   ↓                                                     │
│ LLM Packet Writer (Ollama/halcyon-v1 → prose commentary)│
│   ↓                                                     │
│ Shadow Execution (Alpaca bracket orders)                │
│   ↓                                                     │
│ Journal + Email + Dashboard + WebSocket Broadcast        │
└─────────────────────────────────────────────────────────┘
```

## Database Schema (16 tables)

### Core Trading
- **recommendations** — Trade recommendations with scores, thesis, outcomes
- **shadow_trades** — Paper trade execution tracking with MFE/MAE/P&L

### Training Pipeline
- **training_examples** — Training data with input/output/scores/curriculum stage
- **model_versions** — Model registry with versioning, holdout scores, status
- **model_evaluations** — A/B testing between models
- **preference_pairs** — DPO training data (chosen vs rejected)

### Evaluation
- **audit_reports** — Daily and weekly system audit results
- **metric_snapshots** — Historical metrics for trending

### Operations
- **api_costs** — API call token usage and cost tracking
- **earnings_calendar** — Upcoming earnings dates per ticker

### Data Collection (overnight pipeline)
- **options_chains** — EOD options chain snapshots (strikes, IV, Greeks, OI)
- **options_metrics** — Derived per-ticker signals (IV rank, put/call ratios, skew)
- **vix_term_structure** — VIX family snapshots with term structure ratios
- **cboe_ratios** — Market-wide put/call ratios
- **macro_snapshots** — FRED macro indicator snapshots (19 series)
- **google_trends** — Retail attention signal by ticker

## API Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/api/status` | GET | System status |
| `/api/scan` | POST | Trigger scan |
| `/api/scan/latest` | GET | Most recent scan results |
| `/api/shadow/open` | GET | Open shadow trades |
| `/api/shadow/closed` | GET | Closed trades with metrics |
| `/api/shadow/account` | GET | Alpaca account info |
| `/api/training/status` | GET | Training pipeline status |
| `/api/training/history` | GET | Model version history |
| `/api/review/pending` | GET | Pending reviews |
| `/api/review/{id}` | GET/POST | Get or submit review |
| `/api/packets` | GET | Recent trade packets |
| `/api/cto-report` | GET | CTO performance report |
| `/api/costs` | GET | API cost summary |
| `/api/metric-history` | GET | Rolling metric snapshots |
| `/api/data-collection-stats` | GET | Data collection pipeline stats |
| `/api/docs` | GET | Documentation list |
| `/api/docs/{id}` | GET | Document content |
| `/api/actions/scan` | POST | Trigger scan (background) |
| `/api/actions/cto-report` | POST | Generate CTO report (background) |
| `/api/actions/collect-training` | POST | Collect training data (background) |
| `/api/actions/train-pipeline` | POST | Run full training pipeline (background) |
| `/api/actions/score` | POST | Score unscored examples (background) |
| `/api/actions/collect-data` | POST | Run data collection (background) |
| `/api/earnings` | GET | Upcoming earnings calendar |
| `/api/halt-trading` | POST | Emergency halt |
| `/api/resume-trading` | POST | Resume trading |
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

## 24/7 Overnight Schedule

```
5:30 PM  Post-close capture (final prices, MFE/MAE update)
6:00 PM  Training data collection (closed trade → training example)
9:30 PM  Data collection (options, VIX, macro, trends, CBOE, earnings)
10:00 PM News ingestion (full universe, Finnhub)
11:00 PM Enrichment pre-cache (fundamentals, insiders, macro)
6:00 AM  Pre-market refresh
```

Activated with `python -m src.main watch --overnight`
