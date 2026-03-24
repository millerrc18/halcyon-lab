# Halcyon Lab — System Architecture

## System Pipeline

```
┌─────────────────────────────────────────────────────────┐
│                    SCAN CYCLE (30min)                     │
├─────────────────────────────────────────────────────────┤
│ Universe (S&P 100, 103 tickers)                         │
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
│ Risk Governor (7 checks + kill switch)                   │
│   ↓                                                     │
│ LLM Packet Writer (Ollama → prose commentary)           │
│   ↓                                                     │
│ Shadow Execution (Alpaca bracket orders)                │
│   ↓                                                     │
│ Journal + Email + Dashboard                              │
└─────────────────────────────────────────────────────────┘
```

## Database Schema

### recommendations
Core journal table. One row per trade recommendation.
- `recommendation_id` TEXT PK, `ticker`, `company_name`, `created_at`
- `score`, `qualification`, `confidence_score`, `entry_zone`, `stop_level`, `target_1`, `target_2`
- `thesis_text`, `deeper_analysis`, `event_risk`
- `model_version`, `enriched_prompt`, `llm_conviction`
- `shadow_entry_price`, `shadow_exit_price`, `shadow_pnl_dollars`, `shadow_pnl_pct`
- `user_grade`, `ryan_notes`, `repeatable_setup`, `assistant_postmortem`

### shadow_trades
Paper trade execution tracking.
- `trade_id` TEXT PK, `recommendation_id`, `ticker`, `direction`, `status`
- `entry_price`, `stop_price`, `target_1`, `target_2`, `planned_shares`
- `actual_entry_price`, `actual_exit_price`, `pnl_dollars`, `pnl_pct`
- `max_favorable_excursion`, `max_adverse_excursion`, `duration_days`
- `exit_reason`, `earnings_adjacent`

### training_examples
Training data store.
- `example_id` TEXT PK, `created_at`, `source`, `ticker`, `recommendation_id`
- `instruction`, `input_text`, `output_text`
- `quality_score`, `quality_score_auto`, `difficulty`, `curriculum_stage`

### model_versions
Model registry with versioning and holdout scores.
- `version_id` TEXT PK, `version_name`, `created_at`, `status`
- `training_examples_count`, `model_file_path`
- `holdout_score`, `holdout_details`

### model_evaluations
A/B testing between current and new models.

### preference_pairs
DPO training data (chosen vs rejected outputs).

### audit_reports
Daily and weekly system audit results.

## API Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/api/status` | GET | System status (preflight) |
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
| `/ws/live` | WebSocket | Real-time event stream |

## Training Pipeline Flow

```
Historical Backfill → Training Examples DB
                         ↓
                  Classify Difficulty (easy/medium/hard)
                         ↓
                  Assign Curriculum Stage (structure/evidence/decision)
                         ↓
                  LLM-as-Judge Quality Score (1-5 on 6 dimensions)
                         ↓
                  Quality Filter (score ≥ 3.0)
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

## Risk Governor Checks

1. **Max Open Positions** — Reject if at position limit
2. **Max Sector Concentration** — No sector > 30% of portfolio
3. **Max Correlated** — No more than 3 positions in same sector
4. **Daily Loss Limit** — Halt if portfolio drops 3% in a day
5. **Volatility Halt** — No new longs if VIX proxy > 35%
6. **Max Position Size** — No single position > 10% of equity
7. **Kill Switch** — Manual or automated halt status
