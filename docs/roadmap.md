# Halcyon Lab — Development Roadmap

**Last Updated:** 2026-03-26
**Principle:** Every gate is performance-based, not time-based.

## Desk Architecture

Halcyon Lab is organized as a **multi-desk trading platform**. Each desk has its own model, strategy mandate, risk limits, P&L tracking, and paper/live account. Desks share platform infrastructure: data collection, compute scheduler, dashboard, Telegram, and the training pipeline.

```
Halcyon Lab (Platform)
├── Equity Swing Desk ───── Phase 1 (ACTIVE)
├── Equity Research Desk ── Phase 2
├── Options Volatility Desk Phase 3-4
├── Equity Momentum Desk ── Phase 5
└── Intraday Desk ───────── Phase 6+
```

Each desk is gated: the PREVIOUS desk must be profitable before the next desk launches. This prevents capital and attention fragmentation.

---

## Phase 1: Bootcamp — Equity Swing Desk (ACTIVE)

**Capital:** Paper ($100K Alpaca)
**Monthly Cost:** $5/mo
**Goal:** Prove the swing pullback strategy has an edge over 50+ closed trades.

**Desk: Equity Swing**
| Field | Value |
|-------|-------|
| Model | halcyonlatest (Qwen3 8B, fine-tuned on 790 examples) |
| Universe | S&P 100 (~103 tickers) |
| Timeframe | 2–15 day holds, daily bars |
| Strategy | Pullback in uptrend to moving average support |
| Account | Alpaca Paper #1 ($100K) |
| Entry | Bracket orders (entry + stop + target via Alpaca) |
| Exit | Mechanical: stop-loss (1-2 ATR), target (2-3 ATR), or 15-day timeout |

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
- 24/7 compute scheduler: between-scan scoring, VRAM handoffs, overnight training, pre-market inference (2%→73% GPU target)
- Comprehensive data collection pipeline (options, VIX, macro, trends, CBOE, earnings)
- Tech debt audit: 16 issues fixed, 257→363 tests passing
- Telegram push notifications for trade alerts and system events
- Earnings calendar with scan-time proximity checks
- 19 FRED series including credit spreads, financial conditions, breakeven inflation
- 19 research documents (regime timeline, company profiles, compute schedule, API comparison, options, fund path)
- Email CC support for secondary notification address

---

## Phase 2: Micro Live — Equity Swing Desk + Research Desk

**Capital:** $500–$1,000 (Swing) + $100K paper (Research)
**Monthly Cost:** ~$350/mo
**Goal:** Go live with real money on Swing Desk. Launch Research Desk for training data volume.

**Desk: Equity Swing (upgraded)**
| Field | Value |
|-------|-------|
| Universe | ~325 stocks (S&P 500 filtered by $100M+ ADV) |
| Account | Interactive Brokers ($500-$1K live) |
| Model | halcyon-v2+ (retrained with regime diversity, PASS examples) |

**Desk: Equity Research (NEW)**
| Field | Value |
|-------|-------|
| Model | Same halcyonlatest (shared with Swing) |
| Universe | Same ~325 stocks |
| Timeframe | Same 2–15 days |
| Strategy | Same pullback, but lower threshold (score ≥ 30) |
| Account | Alpaca Paper #2 (separate $100K) |
| Purpose | Volume data generation — takes more marginal trades for training signal |
| Config | `--desk equity-research --config research.yaml` |
| Tagging | All examples tagged `research_mode` — never pollutes primary track record |

### Gate Metrics (Swing Desk Live)
| Metric | Target |
|--------|--------|
| Live trades | ≥ 50 |
| Live vs paper delta | ≤ 20% |
| Sharpe (live) | ≥ 0.75 |
| Max drawdown | ≤ 20% |
| Beta | ≤ 0.5 |

### Items
- **Platform:** `--desk` flag for watch loop, desk-specific config/DB prefix/P&L tracking
- **Swing Desk:** Universe expansion to ~325 stocks, GICS sector conditioning, IB adapter
- **Research Desk:** Second Alpaca paper account, relaxed thresholds, silent mode, research_mode tags
- **Infrastructure:** Polygon.io ($199/mo), RTX 3090 (~$800), LLC formation + trader tax consultation
- **Training:** Scale to 3,000–5,000 examples, GRPO (at 100+ closed trades), golden ratio mixing, merge-and-reset LoRA
- **Dashboard:** HSHS health score page, AI Council page, desk-level P&L views
- **Data:** Options-as-equity-signal (IV rank, put/call ratio, skew → equity model features)

---

## Phase 3: Growth — Add Options Volatility Desk

**Capital:** $5K–$25K (Swing) + $2K paper (Options)
**Monthly Cost:** ~$400/mo
**Goal:** Institutional-quality risk-adjusted returns. Begin options strategy validation.

**Desk: Options Volatility (NEW — paper only)**
| Field | Value |
|-------|-------|
| Model | Separate LoRA adapter trained on options/volatility commentary |
| Universe | S&P 100 + SPX/XSP index options |
| Timeframe | 30–45 DTE credit spreads, iron condors, calendar spreads |
| Strategy | Sell premium when IV rank > 50 and IV > realized vol (VRP positive) |
| Account | Alpaca or IB Paper ($100K paper) |
| Entry | Credit spreads at 16-delta short strikes |
| Exit | 50% profit target, 2x loss stop, 21 DTE time exit, delta stop |
| Risk Governor | 15 checks (non-linear risk: max loss per spread, portfolio Greeks, correlation, margin) |
| Training Data | Self-blinded pipeline adapted for options: IV surface context, Greeks, term structure |

### Gate Metrics (Swing Desk)
| Metric | Target |
|--------|--------|
| Sharpe | ≥ 1.0 |
| Sortino | ≥ 1.5 |
| Max drawdown | ≤ 15% |
| Profitable months | ≥ 3 |

### Gate Metrics (Options Desk — paper validation)
| Metric | Target |
|--------|--------|
| Paper trades | ≥ 50 credit spreads |
| Win rate | ≥ 70% (defined-risk premium selling) |
| Avg P&L per trade | > $0 after fees |
| Max single loss | ≤ 2x credit received |

### Items
- **Options Desk:** Backtesting framework, strategy validation on historical IV data, LoRA adapter training
- **Options Risk Governor:** 15 checks for non-linear risk (max loss, portfolio delta/gamma/vega, margin, correlation)
- **Options Feature Engine:** IV surface fitting (SVI), term structure analysis, VRP computation, Greeks chain
- **Swing Desk:** Regime-specific LoRA adapters (HMM), sector-specific LoRA adapters
- **Platform:** Qwen 2.5 14B production model, multi-teacher data generation, tiered data architecture
- **Data:** FMP consensus/fundamentals ($29/mo), ORATS options analytics ($99/mo)

---

## Phase 4: Full Autonomous — Options Desk Goes Live

**Capital:** $25K+ (Swing) + $2K–$5K live (Options)
**Monthly Cost:** ~$400/mo
**Goal:** Investor-ready track record across market regimes. Options desk validates with real money.

**Desk: Options Volatility (upgraded to live)**
| Field | Value |
|-------|-------|
| Account | IB live ($2K–$5K dedicated capital, separate from equity) |
| Strategy | Credit spreads + iron condors on proven setups from Phase 3 paper |
| Tax | Section 1256 treatment on index options (60/40 long-term/short-term) |

### Gate Metrics (Combined)
| Metric | Target |
|--------|--------|
| Profitable months | ≥ 6 (combined equity + options) |
| Sharpe | ≥ 1.2 (combined) |
| Sortino | ≥ 2.0 |
| Max drawdown | ≤ 12% |
| Calmar | ≥ 1.0 |

### Items
- **Options Desk:** Live execution, 3+ months paper validation before live, Section 1256 tax optimization
- **Platform:** Portfolio-level risk (cross-desk correlation, concentration), institutional risk reporting
- **Swing Desk:** Learned confidence calibration, weekly deep audit with trend analysis
- **Compliance:** Verified track record export (IB statements), investor-ready documentation (ODD materials)

---

## Phase 5: Scale Capital — Add Equity Momentum Desk

**Capital:** $100K+ (combined)
**Monthly Cost:** ~$500/mo
**Goal:** Multi-strategy diversification. Grow capital under management.

**Desk: Equity Momentum (NEW)**
| Field | Value |
|-------|-------|
| Model | Separate LoRA adapter trained on breakout/momentum commentary |
| Universe | Russell 1000 (~500-700 stocks) |
| Timeframe | 5–30 day trend following |
| Strategy | Breakout continuation, relative strength momentum |
| Account | IB (dedicated allocation within fund) |
| Entry | Breakout above consolidation range on volume |
| Exit | Trailing stop (2-3 ATR), momentum exhaustion signal |
| Correlation | LOW correlation with Swing Desk (momentum ≠ pullback) — diversification benefit |

### Gate Metrics
| Metric | Target |
|--------|--------|
| Audited months | ≥ 12 (combined all desks) |
| Sharpe | ≥ 1.5 (combined) |
| Max drawdown | ≤ 10% |

### Items
- **Momentum Desk:** Russell 1000 universe, breakout detection features, momentum factor model
- **Options Desk:** XSP/SPX index options via IB, expanded to iron condors + calendar spreads
- **Platform:** Multi-account strategy isolation, cross-desk portfolio optimization
- **Business:** Tax structure optimization (LLC, MTM), regulatory research (RIA path), family LP structure
- **Data:** Additional data sources as needed (~$500/mo total)

---

## Phase 6+: Future Desks (Scoped, Not Scheduled)

**Desk: Intraday / Day Trading**
| Field | Value |
|-------|-------|
| Model | Completely separate model (trained on intraday data — no overlap with swing) |
| Universe | Liquid mega-caps only (~20-30 stocks, $500M+ ADV) |
| Timeframe | Intraday, 1-min/5-min bars |
| Strategy | Opening range breakout, VWAP reversion, mean reversion at extremes |
| Infrastructure | Real-time data feeds ($300-500/mo), sub-second execution, co-located or fast broker API |
| Compute | Dedicated GPU or time-shared (AM = day trades, PM = swing analysis) |
| Prerequisite | Swing + Momentum desks profitable for 6+ months, RTX 4090 or cloud GPU |

**Why this is Phase 6+:** Day trading requires fundamentally different infrastructure (intraday data, fast execution), a separately trained model (daily bars ≠ 1-min bars), and much higher capital velocity. The edge is harder to find and easier to lose. It only makes sense after the slower strategies are proven and the platform is mature enough to support concurrent desks sharing GPU.

**Other potential future desks:**
- **Event-Driven Desk** — Earnings plays, M&A arbitrage, FDA binary events
- **Macro/Rates Desk** — Treasury futures, rate-sensitive equity baskets
- **Crypto Desk** — 24/7 markets, different data infrastructure, regulatory considerations

Each future desk follows the same pattern: paper validate → gate metrics → live with small capital → scale if profitable.

---

## Hardware Scaling Plan

| Phase | GPU | VRAM | Desks Supported |
|-------|-----|------|-----------------|
| 1 (Current) | RTX 3060 | 12GB | 1 desk (Swing), time-shared inference/training |
| 2 | RTX 3090 | 24GB | 2 desks (Swing + Research), Qwen 14B feasible |
| 3-4 | RTX 3090 | 24GB | 3 desks, multiple LoRA adapters, switchable |
| 5+ | Cloud A100 or dual GPU | 40-80GB | 4+ desks, concurrent inference for multiple models |

## Data Subscription Plan

| Phase | Monthly Cost | Sources |
|-------|-------------|---------|
| 1 (Current) | $5 | yfinance, Finnhub free, FRED free, SEC EDGAR, Anthropic Haiku |
| 2 | ~$350 | + Polygon.io ($199), Unusual Whales ($50) |
| 3 | ~$430 | + FMP ($29), ORATS ($99) |
| 4 | ~$430 | Same |
| 5 | ~$500 | + additional as needed |
| 6+ | ~$800+ | + intraday data feeds ($300-500) |
