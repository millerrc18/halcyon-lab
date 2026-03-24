# AGENTS.md — Halcyon Lab Governance Document

## Purpose

Halcyon Lab is an autonomous AI trading desk that scans, analyzes, and executes equity trades on the S&P 100 universe. It combines systematic technical scoring with LLM-generated institutional-quality trade commentary, multi-source data enrichment, bracket orders via Alpaca, a risk governor with kill switch, and a self-improving training pipeline.

**Core Principle:** Training data quality is our #1 competitive advantage. Never sacrifice quality for speed.

## Current System State

The system is live in **bootcamp mode** — shadow paper trading on Alpaca with full data enrichment, bracket orders, risk governor, daily/weekly auditor, validation holdout, A/B model evaluation, learned confidence, walk-forward backtesting, and a web dashboard.

## Architecture Overview

```
Universe (S&P 100)
  → Data Ingestion (yfinance OHLCV)
  → Feature Engine (technical indicators, regime, sector, earnings)
  → Data Enrichment (fundamentals, insiders, news, macro)
  → Ranking & Qualification (score 0-100)
  → Risk Governor (7 checks + kill switch)
  → LLM Packet Writer (Ollama/Qwen → prose commentary)
  → Shadow Execution (Alpaca bracket orders)
  → Training Loop (backfill → curriculum SFT → DPO → holdout → A/B eval)
```

## Data Sources (7+)

1. **Technical Data** — Price, volume, moving averages, RSI, ATR, trend state, relative strength
2. **Market Regime** — SPY trend, volatility, breadth, drawdown, regime classification
3. **Sector Context** — Sector relative strength rank, sector average score
4. **Fundamental Snapshot** — SEC EDGAR: revenue, margins, PE, growth rates
5. **Insider Activity** — Finnhub: buy/sell transactions, sentiment classification
6. **Recent News** — Finnhub Company News: headlines, simple sentiment scoring
7. **Macro Context** — FRED: Fed Funds rate, yield curve, unemployment, CPI, GDP

## Execution

- **Bracket Orders**: Entry + stop-loss + take-profit via Alpaca paper trading
- **Risk Governor**: 7 checks (max positions, sector caps, daily loss, correlation, volatility halt, position size, halt status)
- **Kill Switch**: `halt-trading` command or dashboard button halts all new positions immediately

## Training Pipeline

1. **Data Collection**: Historical backfill from real outcomes + live shadow trade outcomes
2. **Curriculum Classification**: Easy/medium/hard difficulty → 3-stage curriculum (structure/evidence/decision)
3. **Quality Scoring**: LLM-as-judge scores each example on 6 dimensions
4. **Contrastive Pairs**: Similar inputs with opposite outcomes teach nuanced analysis
5. **SFT Training**: Three-stage curriculum with decreasing learning rates
6. **DPO Refinement**: Preference pairs (best vs worst alternatives) for alignment
7. **Holdout Validation**: 15% chronological holdout with 5-day temporal gap
8. **A/B Shadow Evaluation**: New model runs in shadow alongside current model
9. **Auto-Rollback**: Performance regression triggers automatic rollback

## Communication

- **Email**: Morning watchlist, EOD recap, action packets, training reports, CTO reports
- **Auditor Agent**: Daily and weekly automated system audits with escalation
- **Dashboard**: Real-time web interface with WebSocket live updates

## Dashboard Pages

- Dashboard (overview metrics)
- Packets (trade recommendations)
- Shadow Ledger (open/closed trades)
- Training (pipeline status)
- Review (human evaluation)
- CTO Report (performance analytics)
- Settings (system configuration)

## CLI Commands (30+)

### Core Pipeline
`scan`, `morning-watchlist`, `eod-recap`, `ingest`, `send-test-email`, `init-db`, `demo-packet`

### Shadow Ledger
`shadow-status`, `shadow-history`, `shadow-close`, `shadow-account`

### Review
`review`, `mark-executed`, `review-scorecard`, `review-bootcamp`, `postmortems`, `postmortem`

### Training — Data
`training-status`, `training-history`, `training-report`, `bootstrap-training`, `backfill-training`

### Training — Quality
`classify-training-data`, `score-training-data`, `validate-training-data`, `generate-contrastive`, `generate-preferences`

### Training — Execution
`train [--force] [--rollback] [--export]`, `evaluate-holdout`

### Evaluation
`cto-report`, `feature-importance`, `backtest`, `compare-models`, `model-evaluation-status`, `promote-model`

### Operations
`preflight`, `watch`, `dashboard`, `halt-trading`, `resume-trading`

## Scope

### In Scope
- S&P 100 universe, long-only equity swing trades (1-15 day holds)
- Systematic scoring + LLM commentary + bracket execution
- Self-improving training pipeline with quality gates
- Risk management with automated safety rails

### Out of Scope
- Options, futures, crypto, forex
- Short selling
- High-frequency trading
- Portfolio-level optimization (future Phase 4)

### Future Scope (Gated by Performance)
- GRPO reinforcement learning
- Regime-specific LoRA adapters
- Expanded universe (S&P 500)
- Multi-strategy capability

## Governance Hierarchy

1. **AGENTS.md** — This document. Defines purpose, scope, and constraints
2. **Charter** — Operational rules and risk limits
3. **Blueprint** — Technical architecture (see docs/architecture.md)
4. **Code** — Implementation

## Technology Stack

- **Python 3.12+** — Core runtime
- **FastAPI + Uvicorn** — Dashboard API server
- **React 19 + Vite + Tailwind CSS 4** — Frontend dashboard
- **SQLite** — Journal, training data, model versions
- **yfinance** — Market data ingestion
- **Ollama + Qwen3-8B** — Local LLM inference
- **Unsloth + QLoRA** — Fine-tuning on RTX 3060 12GB
- **Anthropic Claude API** — Training data generation, quality scoring
- **Alpaca Markets API** — Paper trading execution
- **Finnhub API** — Insider activity, company news
- **FRED API** — Macroeconomic indicators
- **SEC EDGAR** — Fundamental data

## Roadmap

See docs/roadmap.md for the 5-phase development plan with performance gates.
