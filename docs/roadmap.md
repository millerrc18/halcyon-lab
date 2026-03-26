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

**Capital:** Paper ($100K Alpaca) + Live ($100 Alpaca, fractional shares)
**Monthly Cost:** ~$43/mo (Render $7, Polygon $29 planned, domain $7)
**Goal:** Prove the swing pullback strategy has an edge over 50+ closed trades.

**Desk: Equity Swing**
| Field | Value |
|-------|-------|
| Model | halcyonlatest (Qwen3 8B, fine-tuned on 790 examples) |
| Universe | S&P 100 (~103 tickers) |
| Timeframe | 2–15 day holds, daily bars |
| Strategy | Pullback in uptrend to moving average support |
| Paper Account | Alpaca Paper ($100K), 50 max positions |
| Live Account | Alpaca Live ($100), 2 max positions, fractional shares |
| Entry | Bracket orders (entry + stop + target via Alpaca) |
| Exit | Mechanical: stop-loss (1-2 ATR), target (2-3 ATR), or 15-day timeout |
| Live Exit | Tighter: 1 ATR stop, 2 ATR target, 7-day timeout |

### Gate Metrics
| Metric | Target |
|--------|--------|
| Closed trades | ≥ 50 |
| Win rate | ≥ 45% |
| Sharpe ratio | ≥ 0.5 |
| Expectancy | > $0 |
| Avg rubric score | ≥ 3.5 |

### Cloud & Mobile
| Platform | URL | Status |
|----------|-----|--------|
| Cloud Dashboard | halcyonlab.app | ✅ LIVE (Render, password-protected) |
| Cloud API | api.halcyonlab.app | ✅ LIVE (read-only, bearer token auth) |
| Cloud Database | Render Postgres ($7/mo) | ✅ Synced every 2 min from local SQLite |
| iOS/iPad PWA | halcyonlab.app (Add to Home Screen) | ✅ Installable as app |
| Telegram Bot | @HalcyonLabBot | ✅ 24 notification types + 12 commands |

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
- Telegram: 24 notification types (scheduled + event-triggered) + 12 interactive commands
- Earnings calendar with scan-time proximity checks
- 19 FRED series including credit spreads, financial conditions, breakeven inflation
- 29 research documents across strategy, training, infrastructure, market, branding, competitive analysis
- Email CC support for secondary notification address
- **Mega Sprint:** AI Council (5-agent Modified Delphi), Render cloud deployment, setup classifier + signal zoo, options/events/sector in features, regime-adaptive thresholds, canary set + quality drift monitoring
- **Cleanup Sprint:** Flywheel fix (scan→trade→close→training connected), live trading dual execution ($100), activity logging, command reference docs, AuthGate cloud authentication
- **Brand Sprint:** Kingfisher palette (teal/amber/slate), Space Grotesk + Inter + JetBrains Mono, all 11 pages + 12 components themed
- **PWA:** Installable on iPhone/iPad via Add to Home Screen, service worker for offline shell caching
- **Competitive benchmark:** 28/100 overall score (honest baseline), 15-dimension scorecard tracking monthly

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
- **Swing Desk:** Universe expansion to ~325 stocks, IB adapter
- **Research Desk:** Second Alpaca paper account, relaxed thresholds, silent mode, research_mode tags
- **Infrastructure:** Polygon.io Starter ($29/mo → Developer $79/mo), RTX 3090 (~$800), LLC formation + trader tax consultation
- **Training:** Scale to 3,000–5,000 examples, GRPO (at 100+ closed trades), golden ratio mixing, merge-and-reset LoRA
- **Dashboard:** ~~HSHS health score page, AI Council page~~ (DONE in Phase 1), desk-level P&L views
- **Data:** ~~Options-as-equity-signal~~ (DONE in Phase 1), SEC EDGAR (free), FINRA short interest (free), deprecate Google Trends per-ticker
- **Mobile:** Capacitor wrapper for native iOS/iPad App Store distribution (optional — PWA already live)

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

---

## Financial Projections

### Return Assumptions

Based on the Halcyon Framework research and fund path analysis. S&P 100 swing trading with 2-15 day holds, ~15% annualized volatility.

| Scenario | Sharpe | Annual Return | Basis |
|----------|--------|---------------|-------|
| Conservative | 1.0 | 15% | Acceptable threshold for emerging managers |
| Base case | 1.5 | 22% | Competitive — top quartile emerging quant |
| Optimistic | 2.0 | 30% | Exceptional — institutional-grade |

**Critical caveat:** 30-50% performance degradation from backtest to live is typical. For liquid S&P 100 names with medium-term holds, expect 15-25% degradation. These projections assume live performance, not backtested.

### Phase-by-Phase Financial Milestones

#### Phase 1: Bootcamp (Current — Month 1-6)

| Item | Value |
|------|-------|
| Capital | $100K paper (no real money at risk) |
| Operating cost | ~$60/year ($5/mo data + electricity) |
| Revenue | $0 |
| Net P&L | -$60/year (pure R&D cost) |
| **Milestone** | **Prove positive expectancy on 50+ closed trades** |

#### Phase 2: Micro Live (Month 7-12)

| Scenario | Starting Capital | Annual Return | Trading P&L | Operating Cost | Net P&L |
|----------|-----------------|---------------|-------------|----------------|---------|
| Conservative | $1,000 | 15% | $150 | $4,200/yr | -$4,050 |
| Base case | $5,000 | 22% | $1,100 | $4,200/yr | -$3,100 |
| Optimistic | $10,000 | 30% | $3,000 | $4,200/yr | -$1,200 |

**Key insight:** Phase 2 is NOT profitable. You're paying ~$350/mo for data/infra while proving the strategy works with real money. This is an investment in track record, not a moneymaker. The $1K-$10K in capital is a calibration instrument.

**Legal costs (one-time):** Wyoming LLC $100 + securities attorney $2,000-$5,000 = ~$3,000

| **Milestone** | **Value** |
|---------------|-----------|
| First live trade with real money | Priceless (track record clock starts) |
| Section 475 MTM election filed | Within 75 days of LLC formation |
| IB account opened | GIPS-verified returns begin |

#### Phase 3: Growth (Month 13-24)

| Scenario | Capital (start) | Annual Return | Trading P&L | Operating Cost | Net P&L |
|----------|----------------|---------------|-------------|----------------|---------|
| Conservative | $25,000 | 15% | $3,750 | $5,200/yr | -$1,450 |
| Base case | $25,000 | 22% | $5,500 | $5,200/yr | +$300 |
| Optimistic | $50,000 | 30% | $15,000 | $5,200/yr | +$9,800 |

**Break-even capital at base case (22% return):** ~$24,000 covers $5,200/yr operating costs.

This is the phase where the Options Desk starts paper trading. No additional capital required for options paper — uses existing IB paper account.

| **Milestone** | **Value** |
|---------------|-----------|
| Break-even on operating costs | ~$25K capital at base case |
| 12 months live track record | Institutional clock milestone |
| Options desk paper validation | 50+ credit spreads on paper |

#### Phase 4: Full Autonomous (Month 25-36)

| Scenario | Capital (start) | Annual Return | Trading P&L | Operating Cost | Net P&L |
|----------|----------------|---------------|-------------|----------------|---------|
| Conservative | $50,000 | 15% | $7,500 | $5,200/yr | +$2,300 |
| Base case | $100,000 | 22% | $22,000 | $5,200/yr | +$16,800 |
| Optimistic | $150,000 | 30% | $45,000 | $5,200/yr | +$39,800 |

Capital grows through reinvested profits + additional personal allocation as confidence builds. The Options Desk goes live with $2-5K.

| **Milestone** | **Value** |
|---------------|-----------|
| $100K personal capital deployed | Full conviction in strategy |
| $10K+ annual trading profit | Strategy covers all costs with headroom |
| 3-year audited track record begins | Incubator fund structure ($2,500-$5,000) |
| Investor-ready documentation | ODD materials, risk reports, compliance manual |

#### Phase 5: Scale Capital (Month 37-60)

This is where the economics transform. External capital changes everything.

**Personal capital only (no external investors):**

| Scenario | Capital | Annual Return | Trading P&L | Operating Cost | Net P&L |
|----------|---------|---------------|-------------|----------------|---------|
| Conservative | $200,000 | 15% | $30,000 | $6,000/yr | +$24,000 |
| Base case | $300,000 | 22% | $66,000 | $6,000/yr | +$60,000 |
| Optimistic | $500,000 | 30% | $150,000 | $6,000/yr | +$144,000 |

**With external capital (fund structure):**

| AUM | Mgmt Fee (1.5%) | Perf Fee (17.5% on 22%) | Gross Revenue | Fund OpEx | Net to Manager |
|-----|-----------------|------------------------|---------------|-----------|----------------|
| $1M | $15,000 | $38,500 | $53,500 | $60,000 | -$6,500 |
| $3M | $45,000 | $115,500 | $160,500 | $75,000 | +$85,500 |
| $5M | $75,000 | $192,500 | $267,500 | $85,000 | +$182,500 |
| $10M | $150,000 | $385,000 | $535,000 | $100,000 | +$435,000 |
| $25M | $375,000 | $962,500 | $1,337,500 | $150,000 | +$1,187,500 |

**Fund break-even AUM:** ~$2M at base case returns (mgmt fee + perf fee covers $60K operating costs).

**Fund formation costs (one-time):** $15K-$50K (legal), or $10K-$20K via Repool/similar platform.

**Annual fund operating costs:**
| Item | Cost |
|------|------|
| Fund administrator | $10,000-$25,000 |
| Annual audit | $15,000-$25,000 |
| Outsourced CCO | $10,000-$25,000 |
| Legal retainer | $5,000-$10,000 |
| Insurance (E&O, D&O, cyber) | $12,000-$20,000 |
| Technology + data | $6,000-$10,000 |
| **Total lean** | **$60,000-$100,000** |

| **Milestone** | **Value** |
|---------------|-----------|
| Fund break-even | ~$2M AUM |
| Manager comp exceeds W-2 salary | ~$5-10M AUM (depends on salary) |
| Sustainable fund business | ~$10M AUM ($435K net at base case) |

### Capital Growth Trajectory (Base Case — 22% Annual Return)

Assumes reinvested profits + periodic personal capital additions.

| Month | Phase | Personal Capital | External AUM | Total AUM | Annual Trading P&L | Annual Fund Revenue | Net to You |
|-------|-------|-----------------|-------------|-----------|-------------------|--------------------|-----------| 
| 0-6 | 1 | $0 (paper) | $0 | $0 | $0 | $0 | -$60 |
| 7-12 | 2 | $5,000 | $0 | $5,000 | $1,100 | $0 | -$3,100 |
| 13-24 | 3 | $25,000 | $0 | $25,000 | $5,500 | $0 | +$300 |
| 25-36 | 4 | $100,000 | $0 | $100,000 | $22,000 | $0 | +$16,800 |
| 37-48 | 5a | $150,000 | $500,000 | $650,000 | $143,000 | $25,000 | +$108,000 |
| 49-60 | 5b | $200,000 | $3,000,000 | $3,200,000 | $704,000 | $160,000 | +$604,000 |

**Year 5 cumulative investment:** ~$20K (operating costs + legal + fund formation)
**Year 5 annual income (base case):** ~$600K (personal returns + fund fees)
**Strategy capacity ceiling:** $500M-$1B+ (S&P 100 liquidity)

### Legal Structure Timeline

| Phase | Structure | Cost | Tax Treatment |
|-------|-----------|------|---------------|
| 1 | Personal account | $0 | Short-term capital gains (ordinary rates) |
| 2 | Wyoming LLC + Section 475 MTM | $3,100 | Ordinary income, full loss deduction, expense deduction |
| 3-4 | Same LLC, incubator fund prep | $2,500-$5,000 | Same |
| 5 | Full private fund (DE LP + WY GP) | $15,000-$50,000 setup | Fund-level: pass-through. Manager: fee income + carry |
| 5+ | ERA filing ($150/yr) | $150/year | Same |

### Risk-Adjusted Scenarios

**What if the strategy doesn't work?**
- Phase 1 cost: $60 (electricity). Zero financial risk.
- Phase 2 max loss: $1,000-$10,000 in capital + $4,200 operating costs. Painful but survivable.
- Phase 3+ losses are bounded by risk governor (max drawdown ≤15%). At $25K, worst case is -$3,750.
- Total maximum cumulative loss through Phase 3 if strategy fails completely: ~$20,000.

**What if it works but Sharpe is only 0.5 (mediocre)?**
- 7.5% annual return. $25K → $1,875/yr. Never covers operating costs with personal capital alone.
- Fund path is not viable at Sharpe 0.5. Stay personal, keep it as a side income/hobby.
- Decision point: if Sharpe < 0.75 after 12 months live, reassess strategy fundamentally.

**What if it works AND Sharpe > 2.0?**
- 30%+ annual return. Capital compounds aggressively. External capital arrives faster.
- $10M AUM by Year 4 becomes realistic (3-year track record + exceptional returns).
- Year 5 income could exceed $1M (personal returns + fund fees on $10M+ AUM).
