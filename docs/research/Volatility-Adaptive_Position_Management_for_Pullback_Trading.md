# Volatility-adaptive position management for pullback trading

**The core finding: pullback strategies should not retreat from high volatility — they should adapt to it.** Nagel (2012) demonstrated that short-term reversal returns (the exact mechanism behind pullback strategies) increase enormously with VIX, with conditional Sharpe ratios during VIX >30 periods reaching multiples of calm-period levels. The problem isn't that the pullback edge disappears during volatility spikes — it actually amplifies. The problem is that fixed stops get overwhelmed by expanded noise. The solution is a coordinated system of wider ATR-based stops, smaller positions, shorter holding periods, and progressive stop tightening that together maintain constant risk exposure while harvesting the amplified reversal premium. This report synthesizes academic and practitioner evidence into a complete, implementable position management ruleset across three VIX regimes.

---

## 1. ATR expands 2–2.5× during VIX >30, demanding proportional stop adjustment

The relationship between VIX and individual stock ATR is approximately linear and well-documented. Since VIX represents annualized expected S&P 500 volatility, daily expected moves scale as VIX/√252. For S&P 100 stocks, empirical ATR expansion relative to a VIX 15 baseline follows a predictable pattern: **ATR roughly doubles when VIX moves from 15 to 30**, and triples near VIX 45. During the COVID crash of March 2020 (VIX >80), ATR expanded to **5–6× normal levels** for large-cap names.

| VIX Level | Daily Expected Move (% SPX) | ATR Expansion vs VIX 15 |
|---|---|---|
| 12–15 (calm) | 0.63–0.78% | 1.0× baseline |
| 20 | ~1.05% | ~1.3–1.6× |
| 25 | ~1.31% | ~1.7–2.0× |
| 30 | ~1.57% | ~2.0–2.4× |
| 35+ | ~1.83%+ | ~2.3–3.0× |

This expansion creates the core mechanical problem for bracket-order strategies: a **2× ATR(14) stop that sits comfortably outside noise at VIX 15 becomes equivalent to a 1× ATR stop in dollar terms when ATR doubles** at VIX 30. The stop hasn't moved, but the market's noise envelope has engulfed it.

Charles LeBeau, in *Computer Analysis of the Futures Markets* (1992), established the chandelier exit at **3× ATR(22)** as the default for trend-following exits — anchored to the highest high since entry and trailing downward only. Perry Kaufman, in *Trading Systems and Methods* (6th ed., Wiley), recommends volatility-adaptive stops and extensively covers ATR-based risk control, emphasizing robustness testing across parameter values rather than point optimization. For swing trading specifically (2–15 day holds), practitioner consensus clusters around **2.0–2.5× ATR(14)** as the optimal range. LuxAlgo research found that a 2× ATR stop-loss reduced maximum drawdowns by **32%** compared to static stops, while a 3× ATR multiplier boosted overall trading performance by **15%** versus fixed-distance stops.

The critical insight for pullback strategies is that stops must be wider than trend-following stops because the initial move against the position is *expected* — the trade enters into a declining stock anticipating reversion. Snorrason & Yusupov (2009) tested stop-loss levels from 5% to 55% on OMX Stockholm 30 stocks over 11 years and found the optimal trailing stop at **15%**, producing the highest average quarterly return of **1.47%**. Han, Zhou & Zhu's momentum stop-loss study showed that a 10% stop-loss level reduced monthly maximum losses from −49.79% to −11.34% while increasing average returns from 1.01% to **1.73% per month** — a 71% improvement with a simultaneous 23% standard deviation reduction.

### Optimal stop formulas by VIX regime

The evidence supports a regime-adaptive ATR multiple rather than a fixed stop:

| VIX Regime | ATR Multiple for Initial Stop | Rationale |
|---|---|---|
| Normal (<20) | 2.0× ATR(14) | Standard noise filter; captures ~95% of random daily moves |
| Elevated (20–30) | 2.5× ATR(14) | ATR already expanded; wider multiple prevents noise stop-outs |
| Crisis (>30) | 3.0× ATR(14) | Maximum noise; LeBeau's default. Must pair with reduced position size |

**Volatility-normalized alternative:** Rather than ATR multiples, some practitioners use stops at X standard deviations of recent daily returns. For liquid large-caps, 1 ATR ≈ 1.0–1.2 standard deviations. A **2σ stop** provides ~95% confidence that normal noise won't trigger it. ATR is preferred for practical stop placement because it captures gaps directly, while standard deviation is better suited for regime identification (e.g., Bollinger Band width for entry signals).

### The noise-versus-signal balance point

The fundamental tradeoff is well-characterized: tighter stops produce lower win rates but smaller average losses, while wider stops produce higher win rates but larger average losses. For pullback strategies with typical 60–75% win rates, the expectancy equation E = (Win% × AvgWin) − (Loss% × AvgLoss) shows that preserving the high win rate is paramount. A stop that's too tight destroys the edge by exiting before mean reversion completes. The balance point for pullback strategies sits at **2.0–2.5× ATR** in normal conditions — wide enough to survive typical noise (a 1× ATR stop triggers on ordinary daily moves ~50% of the time) but tight enough to limit damage on genuine failures.

---

## 2. Mean reversion accelerates during high volatility, justifying shorter holds

This is perhaps the most counterintuitive and practically important finding: **pullback trades should be held for shorter periods during high volatility, not longer.** Despite wider stops needing "more room to work," the evidence strongly shows that mean reversion completes faster during high-vol regimes.

**Nagel (2012), "Evaporating Liquidity" (Review of Financial Studies, 25(7), 2005–2039)** provides the definitive evidence. Nagel showed that short-term reversal strategy returns serve as a proxy for returns from liquidity provision, and these returns are **strongly time-varying and highly predictable with VIX**. During VIX >30 periods, expected returns from liquidity provision — the exact mechanism behind pullback profits — increase enormously. Not a single three-month period from 1998–2010 saw the reversal strategy lose money before trading costs. The returns are positively skewed, meaning downside risk is generally low. Nagel's regression of weekly reversal returns on VIX showed a strong, positive, statistically significant coefficient, with conditional Sharpe ratios during VIX >30 periods reaching **multiples of calm-period levels**.

**Dai, Medhat, Novy-Marx & Rizova (2024), "Reversals and the Returns to Liquidity Provision"** extended this analysis, finding that higher-volatility stocks exhibit faster but initially stronger reversals. For S&P 100 stocks (high turnover), reversals during high-vol periods are **stronger but shorter-lived**, dissipating within approximately two weeks.

**Daniel & Moskowitz (2016), "Momentum Crashes" (Journal of Financial Economics, 122(2), 221–247)** showed that the conditions devastating momentum traders — post-decline, high-VIX rebounds — are precisely the conditions maximizing pullback/mean-reversion profits. Past losers behave like call options during rebounds, with extreme positive returns. The reversal of losers during high-vol rebounds is the exact profit source of pullback strategies.

**Jegadeesh, Luo, Subrahmanyam & Titman (2022)** developed a model showing larger reversals when noise trading is more volatile, and found a negative relation between momentum and reversal profits — when reversals are strong (high-vol), momentum weakens, confirming the amplified pullback edge.

### Estimated time-to-target by VIX regime

Synthesizing evidence from Connors Research, Swanson's holding period backtests, and Canomi Trading's mean-reversion curve analysis:

| VIX Regime | Median Time to 2× ATR Target | Median Time to 3× ATR Target |
|---|---|---|
| VIX <20 | 5–8 trading days | 8–12 trading days |
| VIX 20–30 | 3–5 trading days | 5–8 trading days |
| VIX >30 | 1–3 trading days | 3–5 trading days |

The critical caveat: during VIX >30, ATR itself is 2–3× larger than during VIX <15, so a "2× ATR" target represents a much larger dollar move. The fact that it resolves in similar or fewer calendar days demonstrates the **dramatically higher velocity of mean reversion during crisis periods**.

### Recommended holding periods

| VIX Regime | Maximum Hold | Signal Exit | Rationale |
|---|---|---|---|
| Normal (<20) | 10 trading days | 5-day SMA cross or RSI >50 | Shallow pullbacks resolve slowly |
| Elevated (20–30) | 7 trading days | RSI >50 or 3-day SMA cross | Faster resolution; moderate risk |
| Crisis (>30) | 5 trading days | RSI >40 or first profitable close | Extreme dislocations resolve very quickly |

---

## 3. The pullback edge front-loads into days 1–5, making time exits essential

Connors Research and systematic backtesting provide compelling evidence that pullback profitability is **concave in holding period** — steeply positive in the first few days, then flattening rapidly.

Jeff Swanson (EasyLanguageMastery, 2013–2014) tested S&P 500 holding periods of 1–30 days after RSI(2) pullback signals and found: **days 1–3 showed the steepest P&L growth per day** (highest marginal edge), days 4–7 showed continued positive but decelerating returns, days 8–14 showed minimal marginal returns, and days 15–30 were essentially flat. The original Connors RSI exit (close above 5-day SMA) produced an average hold of ~4–5 days with an **82–83% win rate**. Connors Research co-author Cesar Alvarez confirmed that mean-reversion strategies perform optimally with 3–7 day holds and that traditional stop-losses actually hurt mean-reversion performance — a finding echoed by Curtis Faith and DE Shaw research.

**QuantifiedStrategies.com** analysis concluded that time-based exits are "very simple and often underrated," noting that complex exits (trailing stops, multiple profit targets) do not consistently outperform simpler time-constrained exits. Trading Strategy Guides backtests found that "on average your trades should reach the second target within 1–3 days. **The longer you keep your position open, the lower the chances of the trade succeeding.**"

### Day-by-day time exit schedule

The "stale trade" logic follows directly from edge decay:

**Days 1–3:** Normal development window. The core pullback edge is active. No action needed unless the stop is hit.

**Days 4–5:** If the position shows no appreciable movement (less than 0.5× ATR of favorable progress), the edge is decaying. In VIX >30 environments, consider exiting at close if flat.

**Days 6–7:** Edge substantially decayed. In elevated VIX (20–30), exit any position not showing at least 1× ATR of profit. In normal VIX, continue holding but tighten stops.

**Days 8–10:** Maximum hold for most regimes. Exit any remaining positions. The marginal edge per additional day held approaches zero.

### Interaction between time exits and stop widening

A critical principle emerges: **wider stops × shorter time exits ≈ constant maximum capital at risk**. If stops widen from 2× to 3× ATR (50% wider) during high vol, shortening the time exit from 10 to 5 days (50% shorter) roughly equalizes the cumulative risk-time exposure. This mirrors the constant-volatility-targeting logic of Daniel & Moskowitz (2016) and Moreira & Muir (2017).

---

## 4. Scaling out is mathematically suboptimal but situationally justified for pullbacks

The evidence on partial profit-taking is surprisingly clear: **for positive-expectancy strategies where the edge persists, scaling out reduces expected returns.**

Tom Bulkowski (ThePatternSite.com) tested scaling out across five hypothetical trade scenarios and concluded: "If you want to make less profit, then scale out of a trade. If you want to make more or retain more of your capital, then do not scale out of a trade." In trending markets, scaling out underperformed all-at-once exits in **3 of 5 scenarios**. The only scenarios where scaling out was superior involved price reaching a partial target then reversing to or below entry — effectively, scaling out acts as a partial hedge against reversal.

However, **pullback/mean-reversion strategies have a fundamentally different return distribution than trend-following**. Trend strategies produce positively-skewed returns (many small losses, occasional large wins) where partial exits truncate the valuable right tail. Mean-reversion strategies produce **negatively-skewed returns** (many small wins, occasional large losses) where the expected profit target is well-defined and bounded. Scaling out at 1R for a pullback trade makes more mathematical sense than for a trend trade because the reversion target is typically 1–2× ATR, and most of the alpha is captured in this initial mean-reversion move.

**Ralph Vince's optimal f framework** demonstrates that full Kelly sizing maximizes geometric growth rate but produces extreme volatility — requiring 1,000+ trades to demonstrate superiority (Frontiers in Applied Mathematics, 2020). **Van Tharp** in *Trade Your Way to Financial Freedom* emphasizes that position sizing and exits are more important than entries, and that the psychological benefits of booking partial profits can improve overall system discipline, even if mathematically suboptimal.

The **Almgren-Chriss optimal execution model (2000)** shows that for risk-averse traders, the optimal liquidation trajectory is front-loaded — liquidate most of the position quickly to reduce volatility risk. For retail-sized positions, market impact is negligible, so execution timing is driven purely by signal quality.

### Recommended partial profit protocol

For pullback strategies specifically, a modified approach is justified:

- **At 1× ATR profit:** Close 50% of position. Move stop on remainder to breakeven.
- **At 2× ATR profit (or signal exit):** Close remaining 50%.
- **Rationale:** Mean-reversion alpha is concentrated in the initial 1× ATR move. Beyond that, you're essentially holding a trend position in a stock selected for its reversion characteristics — a different, weaker edge.

### Alpaca API implementation note

Alpaca does **not** natively support partial closes within bracket orders. The bracket order is all-or-nothing. The workaround requires programmatic management: enter positions without bracket orders, submit separate limit sell orders for partial quantities, track remaining position via `GET /v2/positions/{symbol}`, and submit new protective stop orders for the remaining quantity. You cannot submit two conditional closing orders simultaneously for the same symbol, as Alpaca views one as exceeding available position quantity.

---

## 5. Pyramiding is viable but constrained at $100K scale

The anti-martingale principle — add to winners, cut losers — has theoretical support but practical limits for short-term equity strategies at modest account sizes.

**Moskowitz, Ooi & Pedersen (2012, Journal of Financial Economics)** documented significant time-series momentum across 58 liquid futures contracts, with returns strongest during 1–12 month holding periods. Critically, their strategy positions are **volatility-scaled** (each position sized to 40% annualized volatility), and Kim, Tse & Wald (2016) argued that much of the TSMOM alpha comes from this volatility-scaling rather than pure momentum signal. **Hurst, Ooi & Pedersen (2017)** confirmed effectiveness across 137 years (1880–2016) and 67 markets.

For pyramiding specifically, practitioner consensus requires:

- Each subsequent addition must be **smaller** than the previous (inverted pyramid: 1.0 → 0.75 → 0.50 lots)
- Stop must move to **breakeven before any addition**
- Add only after **1× ATR or 1R of favorable movement**
- Maximum **2–3 additions** per position
- Total risk of combined pyramid must **never exceed** the predefined single-trade risk tolerance

**Kelly Criterion application:** The Kelly formula f* = (bp − q)/b dictates the absolute maximum total position size including all pyramid additions. Practitioners universally recommend **Quarter-Kelly to Half-Kelly** (Maclean et al., 2010 showed fractional Kelly reduces volatility more than it proportionally reduces expected growth). If Quarter-Kelly suggests 5% max exposure, initial tranche plus all additions must not collectively exceed 5%.

### Practical constraints at $100K

With 1–2% risk per trade on a $100K account, maximum risk per position is $1,000–$2,000. For an S&P 100 stock with a 2× ATR stop of ~$5, this allows roughly 200–400 shares per position. Adding a half-size pyramid tranche requires the original stop to be at breakeven (eliminating its risk contribution) before allocating another $500–$1,000 of risk. **The math works but leaves minimal room for error** — only 1 pyramid addition is practical at this scale. At $100K, focus on position selection quality rather than pyramiding.

---

## 6. Moreira & Muir's volatility management produces 25% Sharpe improvement

**Moreira & Muir (2017), "Volatility-Managed Portfolios" (Journal of Finance, 72(4), 1611–1644)** is the foundational paper on VIX-conditional sizing. Their core finding: portfolios that scale exposure inversely with realized variance produce **large alphas (4.9% annualized for the market portfolio), substantially increase factor Sharpe ratios (approximately 25% improvement), and produce large utility gains** for mean-variance investors — equivalent to 65% of lifetime utility, nearly double the 35% gain from timing expected returns (Campbell & Thompson, 2008).

The strategy formula is elegantly simple: **w_t = c / σ²_{t−1}**, where c is a scaling constant and σ² is previous period's realized variance. This works because changes in factor volatilities are not offset by proportional changes in expected returns — a violation of standard risk-return theories that creates a persistent exploitable pattern.

**Important caveat:** Cederburg, O'Doherty, Wang & Yan (2020, Journal of Financial Economics) tested 103 equity strategies and found that out-of-sample, volatility-managed portfolios only generated higher Sharpe ratios in **53 of 103 cases**. The alpha from Moreira & Muir comes partly from combining scaled and unscaled portfolios with ex-post optimal weights. However, the approach is **most robust for momentum and mean-reversion-related strategies** (confirmed by Barroso & Santa-Clara, 2015; Daniel & Moskowitz, 2016).

**Harvey, Hoyle, Korgaonkar, Rattray, Sargaison & Van Hemert (Man Group)** confirmed that volatility targeting improves Sharpe ratios of risk assets specifically because of the leverage effect — the negative relationship between returns and volatility changes. It reduces the likelihood of extreme returns across all asset classes, with left-tail events less severe because they occur during elevated volatility when position sizes are already reduced.

### Implementation: hybrid continuous-bucket sizing

The evidence supports a **hybrid approach**: continuous scaling within hard-coded limits.

**Primary formula:**
```
VIX_adj = min(1.0, 20 / current_VIX)
Stop_distance = ATR_multiple × ATR(14)
Risk_dollars = Account_Equity × 0.01 × VIX_adj
Shares = Risk_dollars / Stop_distance
Max_position = Account_Equity × 0.10
Final_shares = min(Shares, Max_position / Stock_Price)
```

This formula simultaneously (a) normalizes risk per trade via ATR, (b) scales down in high-VIX environments via VIX_adj, and (c) caps individual position concentration. At VIX 30, positions are automatically 33% smaller. At VIX 40, they're 50% smaller.

### Position count interaction

When sizing smaller during high vol, **take fewer positions, not more**. The correlation evidence (next section) shows that during VIX >30, stock correlations increase dramatically — more positions provide illusory diversification. The correct response is fewer, higher-conviction positions with appropriate sizing, not a scattered portfolio of small bets that will all move together anyway.

| VIX Regime | Position Size (% of base) | Max Concurrent Positions |
|---|---|---|
| Normal (<20) | 100% | 8–10 |
| Elevated (20–30) | 67–75% | 5–7 |
| Crisis (>30) | 50% | 3–5 |

---

## 7. Correlations spike to near-unity during crises, requiring portfolio-level controls

The correlation asymmetry literature is unambiguous: **diversification benefits disappear precisely when they're most needed.**

**Longin & Solnik (2001), "Extreme Correlation of International Equity Markets" (Journal of Finance, 56(2), 649–676, 2,639 citations)** used extreme value theory to model tail dependence across the five largest stock markets from 1958–1996. They rejected multivariate normality for negative tails but not positive tails — correlations increase in bear markets but not in bull markets. The correlation was driven by market trend, not volatility per se.

**Ang & Chen (2002), "Asymmetric Correlations of Equity Portfolios" (Journal of Financial Economics, 63(3), 443–494, 1,587 citations)** found that correlations between US stocks and the aggregate market are "much greater for downside moves, especially for extreme downside moves." They developed the H-statistic for measuring correlation asymmetry and found that **conditional downside correlations exceed those implied by normal distributions by 11.6%**. Small stocks, value stocks, and past losers exhibit greater asymmetric correlation — precisely the stocks a pullback strategy selects. Ang, Chen & Xing (2002) found a **6.55% per annum premium** between portfolios of highest vs. lowest downside correlation stocks, confirming that investors are compensated for bearing this risk.

### Portfolio-level circuit breakers

**Grossman & Zhou (1993)** showed that optimal allocation to risky assets is proportional to the "cushion" between current drawdown and maximum acceptable drawdown: D_max − D_t. This provides theoretical grounding for tiered circuit breakers:

| Portfolio Drawdown | Action |
|---|---|
| −3% from peak | Alert: Reduce new entries. Tighten all stops to 1.5× ATR |
| −5% from peak | Defensive: Close weakest 30% of positions (lowest RS, nearest to stop). Halt new entries |
| −8% from peak | Crisis: Close all positions. Stand aside until VIX mean-reverts below 25 or 200-day MA is recaptured |

### Weakest position identification for priority exits

When reducing exposure, exit the position that contributes the most marginal risk. **Component VaR** decomposes portfolio VaR into additive contributions: Component VaR_i = w_i × β_{i,portfolio} × σ_portfolio. Positions with the highest component VaR — those with high beta to the portfolio, high individual volatility, and large weight — should exit first.

In practice, a simpler heuristic works: **rank positions by (Distance to Stop / ATR) × Relative Strength**. Positions that are closest to their stops (in ATR units) AND have the weakest relative strength are most likely to be stopped out and should be exited first. This captures both the "nearest to failure" and "weakest fundamental" dimensions without requiring a full covariance matrix.

### Immediate vs. staggered liquidation

For retail-sized portfolios ($100K, 5–10 positions), **exit immediately at signal**. Almgren-Chriss (2000) shows that gradual liquidation reduces market impact but increases volatility exposure. At retail scale, market impact is negligible — the entire portfolio could be liquidated in seconds with minimal slippage. The risk of continued adverse movement during a staggered exit far exceeds any market impact savings.

---

## 8. Stops should tighten progressively as the pullback edge decays

The "theta decay" analogy is apt: a pullback trade loses its informational edge over time, similar to options time decay. The entry signal (oversold RSI, price below moving average) becomes stale information as days pass. If the stock hasn't reverted, the original thesis is weakening.

LeBeau recommended tightening the chandelier multiplier from 3× to 2.5× once a trade moves "deep into profit." Kaufman's *Trading Systems and Methods* covers time stops as complementary to volatility stops, recommending stops derived from market environment rather than fixed parameters. The practitioner consensus favors **step-function tightening** over linear or exponential approaches, because mean-reversion trades have discrete phases (entry → initial bounce → full reversion → overshoot).

### Recommended time-weighted stop schedule

**Normal VIX (<20):**
| Day | Stop Level | Condition |
|---|---|---|
| 1–3 | 2.0× ATR below entry | Initial development |
| 4–5 | Move to breakeven if ≥1× ATR profit; else maintain 2.0× ATR | Early confirmation |
| 6–8 | 1.5× ATR trailing from highest close | Partial edge remaining |
| 9–10 | Time exit at close | Edge exhausted |

**Elevated VIX (20–30):**
| Day | Stop Level | Condition |
|---|---|---|
| 1–2 | 2.5× ATR below entry | High-noise development |
| 3–4 | Move to breakeven if ≥1× ATR profit; else maintain 2.0× ATR | Faster confirmation expected |
| 5–6 | 1.5× ATR trailing from highest close | Decaying edge |
| 7 | Time exit at close | Edge exhausted |

**Crisis VIX (>30):**
| Day | Stop Level | Condition |
|---|---|---|
| 1 | 3.0× ATR below entry | Maximum noise buffer |
| 2–3 | Move to breakeven if ≥1× ATR profit; else tighten to 2.0× ATR | Rapid confirmation expected |
| 4 | 1.5× ATR trailing from highest close | Edge nearly gone |
| 5 | Time exit at close | Edge exhausted |

### ATR contraction during holding period

If ATR contracts during the trade (volatility subsiding), stops should tighten with it. Recalculate ATR(14) daily and apply the current-day's ATR to the stop formula. This naturally tightens stops as the volatility event passes, which is precisely what you want — the wider buffer was needed for the initial high-noise period, and as conditions normalize, the stop should reflect the new, calmer environment.

---

## 9. Complete position management decision table

### Master ruleset by VIX regime

| Parameter | Normal (VIX <20) | Elevated (VIX 20–30) | Crisis (VIX >30) |
|---|---|---|---|
| **Initial stop-loss** | 2.0× ATR(14) | 2.5× ATR(14) | 3.0× ATR(14) |
| **Profit target** | 2.0× ATR(14) | 2.5× ATR(14) | 3.0× ATR(14) |
| **R:R ratio** | ~1:1 | ~1:1 | ~1:1 |
| **Position size** | 1% risk / stop distance | 0.75% risk / stop distance | 0.5% risk / stop distance |
| **VIX size multiplier** | min(1.0, 20/VIX) | min(1.0, 20/VIX) | min(1.0, 20/VIX) |
| **Max hold** | 10 days | 7 days | 5 days |
| **Partial profit** | 50% at 1× ATR | 50% at 1× ATR | 50% at 1× ATR |
| **Breakeven stop** | After 1× ATR profit | After 1× ATR profit | After 1× ATR profit |
| **Day 3 stop** | Maintain initial | Tighten to 2.0× ATR | Tighten to 2.0× ATR |
| **Day 5 stop** | Tighten to 1.5× ATR trailing | Time exit if no progress | Time exit at close |
| **Day 7 stop** | 1.0× ATR trailing | Time exit at close | N/A (already exited) |
| **Max concurrent positions** | 8–10 | 5–7 | 3–5 |
| **Portfolio heat (total risk)** | 6% of equity | 4% of equity | 3% of equity |
| **Drawdown alert (−3%)** | Tighten stops | Tighten + halt entries | Tighten + halt entries |
| **Drawdown defense (−5%)** | Close weakest 30% | Close weakest 50% | Close all |
| **Drawdown circuit breaker** | −8%: close all | −6%: close all | −5%: close all |
| **Pyramid adds** | 1 add at +1× ATR, half-size | Not recommended | Not recommended |
| **Entry selectivity** | Standard RSI/pullback criteria | Require RSI <10 (deeper pullback) | Require RSI <5 and sector RS >50 |

### Position sizing formula (complete)

```
# Inputs
account_equity = 100000
base_risk_pct = 0.01  # 1% base risk
current_VIX = get_current_VIX()
stock_ATR14 = get_ATR(symbol, period=14)
stock_price = get_price(symbol)

# VIX regime determination
if current_VIX < 20:
    regime = "NORMAL"
    atr_multiple = 2.0
    risk_pct = base_risk_pct
    max_positions = 10
    max_hold = 10
elif current_VIX < 30:
    regime = "ELEVATED"
    atr_multiple = 2.5
    risk_pct = base_risk_pct * 0.75
    max_positions = 7
    max_hold = 7
else:
    regime = "CRISIS"
    atr_multiple = 3.0
    risk_pct = base_risk_pct * 0.50
    max_positions = 5
    max_hold = 5

# Continuous VIX adjustment (smooth scaling)
vix_adj = min(1.0, 20.0 / current_VIX)

# Stop distance
stop_distance = atr_multiple * stock_ATR14

# Position sizing
risk_dollars = account_equity * risk_pct * vix_adj
shares = int(risk_dollars / stop_distance)
max_shares = int(account_equity * 0.10 / stock_price)  # 10% max
final_shares = min(shares, max_shares)

# Entry prices
entry_price = stock_price
stop_price = entry_price - stop_distance
target_price = entry_price + stop_distance  # 1:1 R:R
partial_target = entry_price + stock_ATR14  # 1× ATR for 50% exit
```

### Bracket order management pseudocode for Alpaca

```python
import alpaca_trade_api as tradeapi
from datetime import datetime, timedelta

class PullbackPositionManager:
    def __init__(self, api, account_equity=100000):
        self.api = api
        self.equity = account_equity
        self.positions = {}  # {symbol: position_data}

    def enter_position(self, symbol, regime_params):
        """Enter without bracket — manage exits programmatically"""
        shares = regime_params['shares']

        # Submit market entry
        entry = self.api.submit_order(
            symbol=symbol, qty=shares, side='buy',
            type='market', time_in_force='day'
        )

        # Submit partial profit limit (50% at 1× ATR)
        partial_qty = shares // 2
        partial_limit = self.api.submit_order(
            symbol=symbol, qty=partial_qty, side='sell',
            type='limit', limit_price=regime_params['partial_target'],
            time_in_force='gtc'
        )

        # Submit stop for full position
        stop = self.api.submit_order(
            symbol=symbol, qty=shares, side='sell',
            type='stop', stop_price=regime_params['stop_price'],
            time_in_force='gtc'
        )

        self.positions[symbol] = {
            'entry_date': datetime.now(),
            'entry_price': regime_params['entry_price'],
            'initial_stop': regime_params['stop_price'],
            'current_stop': regime_params['stop_price'],
            'target': regime_params['target_price'],
            'partial_target': regime_params['partial_target'],
            'shares': shares, 'partial_qty': partial_qty,
            'remaining_qty': shares,
            'stop_order_id': stop.id,
            'partial_order_id': partial_limit.id,
            'max_hold': regime_params['max_hold'],
            'regime': regime_params['regime'],
            'atr': regime_params['atr'],
            'partial_filled': False,
            'highest_close': regime_params['entry_price']
        }

    def daily_management(self):
        """Run daily after close for all open positions"""
        for symbol, pos in list(self.positions.items()):
            days_held = (datetime.now() - pos['entry_date']).days
            current_price = self.get_close(symbol)
            current_atr = self.get_atr(symbol)
            pos['highest_close'] = max(pos['highest_close'], current_price)

            # Check if partial filled — update stop qty
            if not pos['partial_filled']:
                partial_order = self.api.get_order(pos['partial_order_id'])
                if partial_order.status == 'filled':
                    pos['partial_filled'] = True
                    pos['remaining_qty'] = pos['shares'] - pos['partial_qty']
                    # Cancel old stop, submit new for remaining qty
                    self.api.cancel_order(pos['stop_order_id'])
                    # Move stop to breakeven
                    new_stop = self.api.submit_order(
                        symbol=symbol, qty=pos['remaining_qty'],
                        side='sell', type='stop',
                        stop_price=pos['entry_price'],
                        time_in_force='gtc'
                    )
                    pos['stop_order_id'] = new_stop.id
                    pos['current_stop'] = pos['entry_price']

            # Time-weighted stop tightening
            new_stop_price = self.calculate_tightened_stop(
                pos, days_held, current_price, current_atr
            )
            if new_stop_price > pos['current_stop']:
                self.api.cancel_order(pos['stop_order_id'])
                updated = self.api.submit_order(
                    symbol=symbol, qty=pos['remaining_qty'],
                    side='sell', type='stop',
                    stop_price=round(new_stop_price, 2),
                    time_in_force='gtc'
                )
                pos['stop_order_id'] = updated.id
                pos['current_stop'] = new_stop_price

            # Time exit
            if days_held >= pos['max_hold']:
                self.close_position(symbol, 'TIME_EXIT')

    def calculate_tightened_stop(self, pos, days_held, price, atr):
        """Step-function stop tightening by regime"""
        regime = pos['regime']
        profit_atr = (price - pos['entry_price']) / pos['atr']

        if regime == "NORMAL":
            if days_held <= 3:
                return pos['initial_stop']
            elif days_held <= 5:
                if profit_atr >= 1.0:
                    return pos['entry_price']  # Breakeven
                return pos['initial_stop']
            elif days_held <= 8:
                return pos['highest_close'] - 1.5 * atr
            else:
                return pos['highest_close'] - 1.0 * atr

        elif regime == "ELEVATED":
            if days_held <= 2:
                return pos['initial_stop']
            elif days_held <= 4:
                if profit_atr >= 1.0:
                    return pos['entry_price']
                return price - 2.0 * atr
            else:
                return pos['highest_close'] - 1.5 * atr

        else:  # CRISIS
            if days_held <= 1:
                return pos['initial_stop']
            elif days_held <= 3:
                if profit_atr >= 1.0:
                    return pos['entry_price']
                return price - 2.0 * atr
            else:
                return pos['highest_close'] - 1.5 * atr

    def portfolio_circuit_breaker(self):
        """Check portfolio-level drawdown"""
        account = self.api.get_account()
        equity = float(account.equity)
        peak = float(account.last_equity)  # Track separately
        drawdown = (peak - equity) / peak

        if drawdown > 0.08:
            self.close_all_positions('CIRCUIT_BREAKER_8PCT')
        elif drawdown > 0.05:
            self.close_weakest_positions(pct=0.50)
        elif drawdown > 0.03:
            self.tighten_all_stops(multiplier=0.75)
```

---

## Conclusion: coordinated adaptation beats any single adjustment

The evidence converges on a unified principle: **no single parameter change fixes high-volatility underperformance — the entire position management system must adapt simultaneously.** Widening stops without reducing position size increases dollar risk. Reducing position size without shortening holds wastes capital in positions whose edge has decayed. Shortening holds without widening stops increases whipsaw rates. The system works as an integrated whole.

The three most impactful changes, ranked by evidence strength, are: **first**, VIX-conditional position sizing (Moreira & Muir's 25% Sharpe improvement is the largest documented effect); **second**, time-based exit compression (front-loaded edge decay means shorter holds during high vol capture most of the alpha while avoiding extended exposure); and **third**, ATR-proportional stop widening (prevents the noise-triggered stop-out problem that originally motivated this research). Partial profit-taking at 1× ATR and progressive stop tightening provide incremental improvements but are secondary to getting the sizing-holding-stop trifecta right.

The paradox revealed by Nagel (2012) deserves emphasis: **VIX >30 periods are the most profitable per-trade for pullback strategies**, not the least. The system's underperformance during these periods is purely a risk management failure — fixed stops being overwhelmed by expanded noise — not an edge failure. The regime-adaptive framework above preserves access to these amplified reversal profits while controlling the expanded risk through coordinated sizing, timing, and stop adjustments.