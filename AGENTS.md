# AGENTS.md — Halcyon Lab Governance Document

## Purpose

Halcyon Lab is an autonomous AI trading system that scans, analyzes, and executes equity trades. It combines systematic technical scoring with LLM-generated institutional-quality trade commentary, multi-source data enrichment, bracket orders via Alpaca, a risk governor with kill switch, and a self-improving training pipeline with quality gates.

**Core Principle:** Training data quality is our #1 competitive advantage. Never sacrifice quality for speed.

**Business Model:** Investing returns, not newsletter. Scale by growing capital under management. Family LP structure planned for external capital.

**Long-term Goal:** Quantitatively be the best AI autonomous trading platform with an unbeatable technological moat.

## Current System State

The system is live in **bootcamp mode** — shadow paper trading on Alpaca with halcyon-v1 (fine-tuned Qwen3 8B). Full data enrichment, bracket orders, risk governor, daily/weekly auditor, validation holdout, A/B model evaluation, learned confidence, walk-forward backtesting, 24/7 overnight schedule, comprehensive data collection pipeline, and a 9-page web dashboard.

**Active Model:** halcyon-v1 (Qwen3 8B fine-tuned on 790 examples via QLoRA)
**Training Data:** 976 self-blinded examples, scored with process-first rubric
**Universe:** S&P 100 (expanding to ~325 stocks in Phase 2)

## Architecture Overview

```
Universe (S&P 100 → expanding to ~325 stocks)
  → Data Ingestion (yfinance OHLCV)
  → Feature Engine (technical indicators, regime, sector, earnings)
  → Data Enrichment (fundamentals, insiders, news, macro)
  → Ranking & Qualification (score 0-100)
  → Risk Governor (8 checks + kill switch)
  → LLM Packet Writer (Ollama/halcyon-v1 → prose commentary)
  → Shadow Execution (Alpaca bracket orders)
  → Training Loop (self-blinding → scoring → leakage check → curriculum SFT → holdout → A/B eval)
  → Data Collection (options chains, VIX, macro, trends — overnight)
```

## Data Sources (7+ enrichment, 6 collection)

### Enrichment (used in every scan)
1. **Technical Data** — Price, volume, moving averages, RSI, ATR, trend state, relative strength
2. **Market Regime** — SPY trend, volatility, breadth, drawdown, regime classification
3. **Sector Context** — Sector relative strength rank, sector average score
4. **Fundamental Snapshot** — SEC EDGAR: revenue, margins, PE, growth rates
5. **Insider Activity** — Finnhub: buy/sell transactions, sentiment classification
6. **Recent News** — Finnhub Company News: headlines, simple sentiment scoring
7. **Macro Context** — FRED: Fed Funds rate, yield curve, unemployment, CPI, GDP + 9 expanded series

### Data Collection (overnight pipeline — irreplaceable daily snapshots)
1. **Options Chains** — Full EOD chain snapshots via yfinance (strikes, IV, Greeks, OI)
2. **Options Metrics** — Derived signals: IV rank, put/call ratios, IV skew, unusual activity
3. **VIX Term Structure** — VIX, VIX9D, VIX3M, VIX1Y + contango/backwardation classification
4. **CBOE Ratios** — Equity, index, and total put/call ratios
5. **FRED Macro (expanded)** — 19 series including GSCPI, yield curve, credit spreads, financial conditions, crude oil
6. **Google Trends** — Retail attention signal, batched rotation across universe
7. **Earnings Calendar** — Next earnings date for every ticker, flagging imminent reports

## Execution

- **Bracket Orders**: Entry + stop-loss + take-profit via Alpaca paper trading
- **Risk Governor**: 8 checks (emergency halt, daily loss, position size, max positions, sector concentration, correlation, volatility halt, duplicate check)
- **Kill Switch**: `halt-trading` command or dashboard button halts all new positions immediately

## Training Pipeline

1. **Self-Blinding Generation**: Claude generates commentary WITHOUT seeing outcomes (2-stage pipeline)
2. **Process-First Quality Scoring**: LLM-as-judge scores 6 dimensions, blind to trade outcome
3. **Outcome Leakage Detection**: Balanced accuracy classifier verifies pipeline integrity
4. **Curriculum Classification**: Easy/medium/hard difficulty → 3-stage curriculum
5. **SFT Training**: Three-stage curriculum with decreasing learning rates (PEFT + TRL 0.24)
6. **DPO Refinement**: Preference pairs for alignment (after 100+ pairs)
7. **Holdout Validation**: 15% chronological holdout with 5-day temporal gap
8. **A/B Shadow Evaluation**: New model runs alongside current model
9. **Auto-Rollback**: Performance regression triggers automatic rollback

## 24/7 Overnight Schedule

| Time (ET) | Task |
|-----------|------|
| 5:30 PM | Post-close capture (MFE/MAE update, regime logging) |
| 6:00 PM | Training data collection from closed trades |
| 9:30 PM | Comprehensive data collection (options, VIX, macro, trends) |
| 10:00 PM | Full universe news ingestion |
| 11:00 PM | Enrichment pre-caching for morning |
| 6:00 AM | Pre-market refresh |

## Dashboard Pages (9)

- **Dashboard** — KPIs, cumulative P&L, open trades, action buttons, live activity feed
- **Packets** — Trade recommendations with expandable analysis
- **Shadow Ledger** — Open/closed trades with account summary
- **Training** — Pipeline status, version history, action buttons
- **Review** — Human evaluation and postmortems
- **CTO Report** — Performance analytics, fund metrics, metric trends
- **Settings** — Configuration, API costs, data collection stats, system health
- **Roadmap** — 5-phase plan with live gate metrics
- **Docs** — 19 research documents + core documentation

## CLI Commands (44)

### Core Pipeline
`scan`, `morning-watchlist`, `eod-recap`, `ingest`, `send-test-email`, `init-db`, `demo-packet`

### Shadow Ledger
`shadow-status`, `shadow-history`, `shadow-close`, `shadow-account`

### Review
`review`, `mark-executed`, `review-scorecard`, `review-bootcamp`, `postmortems`, `postmortem`

### Training — Data
`training-status`, `training-history`, `training-report`, `bootstrap-training`, `backfill-training`

### Training — Quality
`classify-training-data`, `score-training-data`, `validate-training-data`, `generate-contrastive`, `generate-preferences`, `check-leakage`

### Training — Execution
`train [--force]`, `train-pipeline [--force]`, `evaluate-holdout`

### Evaluation
`cto-report`, `feature-importance`, `backtest`, `compare-models`, `model-evaluation-status`, `promote-model`

### Operations
`watch [--overnight]`, `dashboard`, `halt-trading`, `resume-trading`, `collect-data`

## Scope

### In Scope
- S&P 100 universe (expanding to ~325 stocks), long-only equity swing trades (2-15 day holds)
- Systematic scoring + LLM commentary + bracket execution
- Self-improving training pipeline with quality gates
- Risk management with automated safety rails
- Passive options/volatility data collection

### Out of Scope (Current Phase)
- Options trading (passive data collection only — strategy in Phase 3-4)
- Short selling
- High-frequency trading
- Live trading with real money (Phase 2)

### Future Scope (Gated by Performance)
- Universe expansion to ~325 stocks (Phase 2)
- GRPO reinforcement learning (Phase 2)
- Sector-specific LoRA adapters (Phase 3)
- Options trading: credit spreads, iron condors (Phase 3-5)
- Wyoming LLC + Section 475 MTM election (Phase 2)
- Interactive Brokers for verified track record (Phase 2)
- Family LP fund structure (Phase 5)

## Governance Hierarchy

1. **AGENTS.md** — This document. Defines purpose, scope, and constraints
2. **Charter** — Operational rules and risk limits
3. **Blueprint** — Technical architecture (see docs/architecture.md)
4. **Code** — Implementation

## Technology Stack

- **Python 3.12+** — Core runtime
- **FastAPI + Uvicorn** — Dashboard API server
- **React 18 + Vite + Tailwind CSS** — Frontend dashboard
- **SQLite** — Journal, training data, model versions, data collection
- **yfinance** — Market data ingestion + options chains
- **Ollama + halcyon-v1 (Qwen3-8B fine-tuned)** — Local LLM inference
- **PEFT + TRL 0.24 + BitsAndBytes** — Fine-tuning on RTX 3060 12GB
- **Anthropic Claude API (Haiku 4.5)** — Training data generation, quality scoring
- **Alpaca Markets API** — Paper trading execution
- **Finnhub API** — Insider activity, company news
- **FRED API** — Macroeconomic indicators (19 series)
- **SEC EDGAR** — Fundamental data

## Research Library (19 documents)

See the dashboard Docs page for the complete research library covering:
- Training methodology (formats, rubric, self-blinding, degradation prevention, gaps/innovation, GRPO)
- Strategy (alternative data, Halcyon Framework, optimal universe size, options trading)
- Business (fund path/regulatory/tax, scaling plan)
- Model selection (Qwen3 8B guide)

## Roadmap

See the dashboard Roadmap page or docs/roadmap.md for the 5-phase development plan:
1. **Bootcamp** (current) — Paper $100K, prove edge
2. **Micro Live** — $500-$1K, expand to ~325 stocks, LLC formation
3. **Growth** — $5K-$25K, sector LoRA adapters, options backtesting
4. **Full Autonomous** — $25K+, investor-ready track record
5. **Scale Capital** — $100K+, Russell 1000, options live, family LP
