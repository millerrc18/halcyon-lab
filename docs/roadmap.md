# Halcyon Lab — Development Roadmap

**Last Updated:** 2026-03-25
**Principle:** Every gate is performance-based, not time-based.

## Phase 1: Bootcamp (ACTIVE)

**Capital:** Paper ($100K Alpaca)
**Monthly Cost:** $5/mo
**Goal:** Prove the system has an edge over 50+ closed trades.

### Gate Metrics
| Metric | Target |
|--------|--------|
| Closed trades | ≥ 50 |
| Win rate | ≥ 45% |
| Sharpe ratio | ≥ 0.5 |
| Expectancy | > $0 |
| Avg rubric score | ≥ 3.5 |

### Completed
- 7-source data enrichment, bracket orders, risk governor (8 checks)
- Auditor agent, validation holdout, A/B eval, walk-forward backtester
- Curriculum SFT (3-stage), news enrichment, quality pipeline + LLM-as-judge
- Dashboard + WebSocket, XML output format, self-blinding pipeline, process-first rubric
- Re-run backfill (976 examples), score + classify + fine-tune halcyon-v1
- Fund metrics + metric history trending, API cost tracking
- Database indexes + codebase audit, leakage detector (balanced accuracy)
- 24/7 overnight schedule (Phase A), unified train-pipeline command
- Dashboard action buttons, live activity feed
- Comprehensive data collection pipeline (options, VIX, macro, trends)

## Phase 2: Micro Live

**Capital:** $500–$1,000
**Monthly Cost:** ~$350/mo
**Goal:** Expand to ~325 stocks. Auto-execute with risk governor. No human approval.

### Gate Metrics
| Metric | Target |
|--------|--------|
| Live trades | ≥ 50 |
| Live vs paper delta | ≤ 20% |
| Sharpe (live) | ≥ 0.75 |
| Max drawdown | ≤ 20% |
| Beta | ≤ 0.5 |

### Items
- Expand universe: S&P 100 → ~325 stocks (S&P 500 filtered by $100M+ ADV)
- Add GICS sector as input feature (sector conditioning)
- Upgrade data API to Polygon.io ($199/mo)
- LLC formation + trader tax status consultation
- Interactive Brokers account + IB adapter
- IB paper testing (2 weeks) → live with $500-$1K
- HSHS dashboard page (5-dimension system health score)
- AI Council dashboard page — 7 agents for strategic decisions
- Passive options data collection (EOD chains, VIX term structure, IV surfaces)
- Options-as-equity-signal (IV rank, put/call ratio, skew → equity model)
- Scale to 3,000–5,000 training examples
- GRPO training (at 100+ closed trades)
- RTX 3090 upgrade (~$800)
- Merge-and-reset LoRA protocol
- Golden ratio data mixing (62/38)
- Research Analyst — 2nd paper account for training data volume
- Google Trends + GSCPI signals
- 24/7 overnight schedule (Phase B + C)

## Phase 3: Growth

**Capital:** $5K–$25K
**Monthly Cost:** ~$135/mo
**Goal:** Institutional-quality risk-adjusted returns.

### Gate Metrics
| Metric | Target |
|--------|--------|
| Sharpe | ≥ 1.0 |
| Sortino | ≥ 1.5 |
| Max drawdown | ≤ 15% |
| Profitable months | ≥ 3 |

### Items
- Regime-specific LoRA adapters (HMM)
- Sector-specific LoRA adapters (Tech, Healthcare, Energy, Financials)
- FMP consensus/fundamentals data ($29/mo)
- Qwen 2.5 14B production model
- Multi-teacher data generation
- Tiered data architecture (core/archive/recent)
- Options: backtesting framework + strategy validation
- Options: volatility analyst LoRA adapter training
- Options: 15-check risk governor for non-linear risk

## Phase 4: Full Autonomous

**Capital:** $25K+
**Monthly Cost:** ~$135/mo
**Goal:** Investor-ready track record across market regimes.

### Gate Metrics
| Metric | Target |
|--------|--------|
| Profitable months | ≥ 6 |
| Sharpe | ≥ 1.2 |
| Sortino | ≥ 2.0 |
| Max drawdown | ≤ 12% |
| Calmar | ≥ 1.0 |

### Items
- Portfolio-level risk (correlation, concentration)
- Weekly deep audit with trend analysis
- Learned confidence calibration
- Institutional risk reporting (P&L attribution, factor exposure, stress tests)
- Verified track record export (IB statements, BarclayHedge)
- Investor-ready documentation (compliance manual, risk templates, ODD materials)
- Options: paper trading credit spreads + iron condors (3+ months)

## Phase 5: Scale Capital

**Capital:** $100K+
**Monthly Cost:** ~$200/mo
**Goal:** Grow capital under management. Multi-strategy diversification.

### Gate Metrics
| Metric | Target |
|--------|--------|
| Audited months | ≥ 12 |
| Sharpe | ≥ 1.5 |
| Max drawdown | ≤ 10% |

### Items
- Multi-setup families (breakout, momentum, mean reversion)
- Russell 1000 expansion (~500-700 stocks) if alpha proven at 325
- Options: live trading credit spreads + iron condors ($2K+ dedicated capital)
- Options: XSP/SPX index options via IB (Section 1256 tax treatment)
- Verified track record (Interactive Brokers or equivalent)
- Tax structure optimization (LLC, trader tax status, MTM election)
- Multi-account strategy isolation
- Regulatory research (RIA registration path for external capital)
- Family LP structure (General Partner + Limited Partners)

## Hardware Scaling Plan

| Phase | GPU | VRAM | Notes |
|-------|-----|------|-------|
| 1 (Current) | RTX 3060 | 12GB | Training at 512 seq_len via PEFT |
| 2 | RTX 3090 | 24GB | Full Unsloth training at 2048, GGUF export |
| 3 | RTX 3090 | 24GB | Qwen 14B feasible |
| 4+ | Cloud A100 | 40GB+ | For ensemble/large-scale experiments |

## Data Subscription Plan

| Phase | Monthly Cost | Sources |
|-------|-------------|---------|
| 1 (Current) | $5 | yfinance, Finnhub free, FRED free, SEC EDGAR, Anthropic Haiku |
| 2 | ~$350 | + Polygon.io ($199), Unusual Whales ($50) |
| 3 | ~$400 | + FMP ($29) |
| 4 | ~$400 | Same |
| 5 | ~$500 | + additional data as needed |
