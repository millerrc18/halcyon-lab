# Halcyon Lab — Development Roadmap

## Phase 1: Bootcamp (Current)

**Status**: Active

**What's Built**:
- Full scan pipeline with 7+ data sources
- Shadow paper trading with bracket orders
- Risk governor with 7 checks + kill switch
- Training pipeline: backfill, curriculum SFT, DPO, quality scoring
- Holdout validation and A/B model evaluation
- Learned confidence output with calibration tracking
- Walk-forward backtester and feature importance tracking
- Daily/weekly auditor agent with escalation rules
- CTO performance report
- React dashboard with WebSocket live updates
- 30+ CLI commands

**Criteria to Move to Phase 2**:
- ≥ 200 training examples with quality scores
- Win rate ≥ 55% over 50+ shadow trades
- Holdout score ≥ 3.5/5.0
- CTO report shows positive expectancy over 30 days
- No risk governor incidents in past 14 days

## Phase 2: Micro Live

**Scope**: Small real-money trades with tight risk limits

**Additions**:
- Real Alpaca execution (not paper)
- Tighter risk governor: max $50/trade risk, 2 positions max
- Hardware upgrade: RTX 4070 or better for faster training
- Live P&L tracking and real tax reporting
- Enhanced auditor with email alerts

**Decision Gate**: Positive expectancy over 100 real trades

## Phase 3: Growth

**Scope**: Scale position sizes and model sophistication

**Additions**:
- GRPO reinforcement learning from trade outcomes
- Regime-specific LoRA adapters (bull/bear/sideways)
- Data subscriptions: Polygon.io ($29/mo) for real-time data
- Expanded to additional data sources
- Sector-specific model fine-tuning

**Decision Gate**: Sharpe ratio > 1.0 over 6 months

## Phase 4: Full Autonomous

**Scope**: Portfolio-level optimization and deep automation

**Additions**:
- Portfolio-level risk management (correlation matrix, VAR)
- Weekly deep audit with performance attribution
- Multi-timeframe analysis
- Automated parameter optimization

**Decision Gate**: Consistent outperformance vs SPY over 12 months

## Phase 5: Scale

**Scope**: Multi-strategy and expanded universe

**Additions**:
- S&P 500 universe expansion
- Multiple strategy types (momentum, mean-reversion, event-driven)
- Model ensemble approach
- Cloud deployment option

## Hardware Scaling Plan

| Phase | GPU | VRAM | Training Speed |
|-------|-----|------|----------------|
| 1 (Current) | RTX 3060 | 12GB | ~45 min/epoch |
| 2 | RTX 4070 | 12GB | ~20 min/epoch |
| 3 | RTX 4090 | 24GB | ~10 min/epoch |
| 4+ | Cloud A100 | 40GB+ | ~5 min/epoch |

## Data Subscription Plan

| Phase | Monthly Cost | Sources |
|-------|-------------|---------|
| 1 (Current) | $0 | yfinance, Finnhub free, FRED free, SEC EDGAR |
| 2 | $0 | Same |
| 3 | $29 | + Polygon.io Basic |
| 4 | $51 | + Polygon.io Starter |
| 5 | $79 | + Polygon.io Developer |

## Decision Gates

All phase transitions are **performance-gated**, not time-gated. The system must demonstrate measurable improvement before advancing. No phase is skipped. Each gate requires:

1. Statistical significance (enough trades)
2. Risk-adjusted returns (not just raw P&L)
3. Model quality metrics (holdout scores)
4. System reliability (no incidents)
