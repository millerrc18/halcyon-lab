# Event calendar integration for S&P 100 pullback trading

**A 5-day earnings exclusion and 2-day FOMC buffer will eliminate roughly 15–17% of monthly trades but remove the worst-performing setups from the strategy.** The academic evidence is unambiguous: earnings proximity is the single highest-impact event for pullback entries, with return variance **5× higher** on announcement days (Dubinsky, Johannes, Kaeck & Seeger, 2019) and implied volatility expanding 40–80% above baseline in the final week. FOMC days rank second, with **60% wider SPY ranges** than normal sessions. Every other calendar event—OpEx, NFP, CPI, month-end flows—should modify position sizing rather than block entries entirely. The optimal system uses continuous 0–10 risk scoring with additive event compounding, linear position-size reduction with a 25% floor, and hard cutoffs only above score 8. This report synthesizes evidence from 40+ academic papers and practitioner studies into actionable rules, exact formulas, and a complete implementation specification.

---

## 1. Earnings proximity is the most dangerous event for pullback entries

The evidence against entering pullback trades near earnings is overwhelming across three independent channels: pre-earnings drift, IV distortion, and post-earnings regime change.

**Pre-earnings drift works against pullback signals.** Aboody, Lehavy, and Trueman (2010, *Review of Accounting Studies*) documented a **+1.58% average market-adjusted return in the 5 trading days before earnings** for stocks with strong prior 12-month returns, followed by a **−1.86% reversal in the 5 days after**. Linnainmaa and Zhang (2019) found daily abnormal returns of **33.3 basis points per day** during the 5-day pre-announcement window. This systematic upward drift means that pullback signals (downward price moves) immediately before earnings are fighting a documented statistical headwind—the market systematically buys these stocks ahead of announcements.

**IV expansion corrupts technical indicators.** Dubinsky et al. (2019, *Review of Financial Studies*) quantified mean earnings jump volatility at **8.5–10.4%**, with some firms exceeding 15%. Practitioner data shows IV rising ~22% above baseline at 14 days before earnings, ~44% at 7 days, and peaking at **60–80% above baseline** on the final pre-earnings trading day. This matters for pullback strategies because widening Bollinger Bands, expanding ATR, and compressed RSI readings mean a 3% decline that would normally constitute a meaningful pullback falls well within the expected range at elevated IV—generating **false pullback signals**. The Quantpedia database documents a six-fold increase in short-term return reversals during earnings windows versus non-announcement periods.

**The optimal exclusion window is 5 days pre-earnings and 3–5 days post-earnings.** The table below summarizes the evidence at each distance:

| Days before earnings | IV above baseline | Pre-earnings drift | Pullback reliability |
|---|---|---|---|
| 1 day | 60–80% | Strongest single day | Extremely poor |
| 2–3 days | 40–60% | Strong cumulative | Very poor |
| 5 days | 25–40% | +1.58% cumulative (Aboody et al.) | Poor |
| 7 days | 20–35% | Early drift phase | Marginal |
| 10 days | 10–20% | Minimal drift | Acceptable |
| 14+ days | Near zero | None measurable | Normal |

Post-earnings, Bernard and Thomas (1989, *Journal of Accounting Research*) established that post-earnings announcement drift (PEAD) persists for **60+ trading days**, with zero-investment portfolios generating ~8–9% abnormal returns per quarter. IV crush completes within 1–2 sessions (typical drop of **30–60%**), but the stock needs 3–5 days to establish a new post-earnings equilibrium where pullback signals become reliable again.

**BMO versus AMC timing requires no differentiation in exclusion window length.** Patell and Wolfson (1982) showed BMO announcements carry significantly higher mean earnings surprises (companies strategically release good news pre-market), while DellaVigna and Pollet (2009, *Journal of Finance*) found Friday/AMC announcements receive less investor attention. The practical difference is only in defining Day 0: for BMO, it equals the earnings date; for AMC, it equals the next trading day. Both warrant the same 5-day pre / 3-day post exclusion.

**Trade elimination cost during earnings season is substantial but manageable.** During peak earnings months (January, April, July, October), approximately 20–30 S&P 100 stocks report per week over 4–5 weeks. With a ±5-day exclusion window, an estimated **12–18 of the baseline 35 monthly trades are eliminated** during peak months—roughly 35–50%. During non-earnings months, the impact drops to 0–2 trades. The annualized cost is approximately **30–50 trades eliminated out of ~420**, or 7–12% of total annual trades.

---

## 2. FOMC meetings warrant a hard pause, but the pre-FOMC drift is dead

**The Lucca-Moench pre-FOMC drift no longer exists as a reliable anomaly.** Lucca and Moench (2015, *Journal of Finance*) documented that the S&P 500 rose an average of **49 basis points** in the 24 hours before scheduled FOMC announcements between 1994 and 2011, with roughly **80% of annual realized excess stock returns** earned during this narrow window. The annualized Sharpe ratio exceeded 1.1. However, Kurov, Halova Wolfe, and Gilbert (2021, *Finance Research Letters*) extended the sample through December 2019 and found the drift **essentially disappeared after 2015–2016**—the mean pre-FOMC return fell to near zero and became statistically indistinguishable from non-announcement days. This is consistent with McLean and Pontiff's (2016) broader finding that published anomalies decay post-publication.

**FOMC days themselves remain significantly more volatile.** SPY ranges are **40–60% wider** on FOMC days than normal sessions, with ~65% of initial FOMC moves reversing by close. The day after FOMC meetings is **down 66.7% of the time** (Option Alpha analysis). Hu, Pan, Wang, and Zhu (NBER) found average daily returns of **28.8 basis points** on FOMC release days versus ~2.5 bps on non-FOMC days. The press conference window (2:00–3:30 PM ET) concentrates the most violent price action, with Rosa (2013, NY Fed) estimating that markets take approximately **90 minutes** to fully absorb FOMC news.

**Dot-plot meetings are meaningfully more impactful than standard meetings.** The four annual Summary of Economic Projections releases (March, June, September, December) include the dot plot of rate projections from all 19 FOMC participants. These produce average SPY ranges of **2.0–2.5%** when the median dot shifts by 25+ basis points, versus somewhat lower ranges for the four non-dot-plot meetings. The scoring system should assign higher risk to dot-plot meetings.

**Fed minutes are a moderate event, not worth hard exclusion.** Rosa (2013, *FRBNY Economic Policy Review*) found that two-year Treasury yield volatility on minutes-release days was roughly **3× larger** than control days, but the equity market effect is smaller and the elevated volatility persists only 30–60 minutes. Fed minutes are comparable in impact to the ISM Manufacturing release.

**FOMC calendar math:** 8 meetings × 2-day buffer (day before + FOMC day) = **16 excluded trading days per year** (~6.3% of 252 trading days). Adding the day after for the 4 dot-plot meetings brings the total to **20 days** (~7.9%). This eliminates approximately **2 trades per month** from a 35-trade baseline.

**Other Fed events** carry variable but generally lower systematic impact. Jackson Hole (late August) is a once-per-year wildcard—Powell's 2022 hawkish speech triggered a **3.4% S&P 500 drop**, but the annual frequency makes systematic filtering impractical. Congressional testimony occurs twice per year with moderate intraday impact. Emergency meetings are by definition unpredictable.

---

## 3. Macro data releases reward being invested, but with modified sizing

Savor and Wilson's landmark study (2013, *Journal of Financial and Quantitative Analysis*) provides the strongest evidence against blanket exclusion of macro announcement days. They found average announcement-day excess returns of **11.4 basis points** versus just **1.1 basis points** on all other days between 1958 and 2009. Over **60% of the cumulative annual equity risk premium** is earned on the ~13% of trading days that carry scheduled macro announcements. The announcement-day Sharpe ratio is **10× higher** than non-announcement days. This finding argues powerfully against excluding NFP, CPI, or GDP days entirely—doing so would sacrifice the announcement premium.

**The correct approach is position-size reduction, not exclusion.** Individual release impacts vary considerably:

**Non-farm payrolls** (first Friday monthly) produce average absolute NDX moves of **±1.37%** versus ±0.86% on normal days—51 basis points of additional volatility. Counterintuitively, the VIX closed lower **70% of the time** on NFP days over a 34.5-year sample (Capstone Investment Advisors, 1990–2024), suggesting NFP resolves uncertainty rather than creating it. The initial spike at 8:30 AM is largely absorbed within 30–60 minutes.

**CPI** has become the most equity-sensitive macro release since the 2021–2023 inflation cycle. LSEG research quantified the largest 5-minute equity impact as **Core CPI month-over-month on Nasdaq 100 E-Mini**, with a quintile spread of **−0.70**—meaning hot CPI prints slam growth stocks hardest. Like NFP, the initial reaction completes within 30–60 minutes of the 8:30 AM release.

**GDP** is a lagging indicator with generally moderate and secondary impact. **PCE**, the Fed's preferred inflation gauge, has gained importance but is one of only a few releases that can actually increase equity implied volatility (most releases suppress it). **ISM Manufacturing/Services** carries impact comparable to Fed minutes. **Weekly jobless claims** are too frequent and too low-impact to filter—excluding 52 Thursdays per year would be excessive.

The recommended approach: reduce position sizes by **25–50%** on NFP and CPI release days. Proceed normally on GDP, PCE, ISM, and claims days. The intraday volatility spike typically resolves before the regular session open at 9:30 AM, so entries placed after 10:00 AM face minimal residual release impact.

---

## 4. Options expiration compresses pullbacks but doesn't break them

**Monthly OpEx creates a measurably different market regime.** Stivers and Sun (2013, *Journal of Banking & Finance*) found that S&P 100 stocks show **significantly higher average weekly returns during OpEx weeks**—over **50 basis points** of excess return versus non-OpEx weeks between 1988 and 2010. The mechanism is delta-hedge rebalancing: as near-term calls expire, market makers reduce short-stock hedges, creating temporary buying pressure.

**Stock pinning is real but limited in scope.** Ni, Pearson, and Poteshman (2005, *Journal of Financial Economics*) documented that on each expiration date, at least **2% of optionable stocks have their returns altered by an average of 16.5 basis points**, with aggregate market capitalization shifts of roughly **$9 billion per expiration**. Pinning is driven by delta-hedge rebalancing (not manipulation) and is concentrated in the **final 2 trading days before expiration**. Critically, weekly options show a **much weaker pinning effect** than monthly—the monthly OpEx filter is more actionable.

**Gamma regime determines pullback behavior.** In positive-gamma environments (dealers long gamma), dealer hedging suppresses volatility—pullbacks are compressed, mean-reversion win rates are higher, but profit potential is smaller. Anderegg, Ulmann, and Sornette (2022, *Journal of International Money and Finance*) confirmed empirically that negative dealer gamma **significantly increases** spot volatility while positive gamma decreases it. Ni et al. found that a one standard deviation increase in gamma imbalance reduces absolute returns by **over 20 basis points**. SpotGamma reports markets close within their flagged gamma levels **78% of the time**.

**Quarterly witching (March/June/September/December) amplifies these effects.** Trading volume runs **50–100% above normal** on quad-witching days, with the final trading hour historically bearish and chaotic. The week leading into witching tends to be bullish, but the **week after quad witching produces negative returns**, particularly in June and September.

**0DTE options have not destabilized daily pullback signals.** Despite now accounting for **~51% of total S&P 500 options volume**, the academic consensus (Amaya et al. 2025, Adams et al. 2024, Dim et al. 2024) finds no discernible change in close-to-close volatility patterns. CBOE's analysis of proprietary data shows net market maker gamma from 0DTE averaging only **0.04–0.17% of daily S&P futures liquidity**—the flows are remarkably balanced. Daily-timeframe pullback signals are unaffected.

**Practical OpEx rules:** Do not exclude OpEx-week entries (the bullish bias actually favors pullback resolution). Reduce position size by **30%** on OpEx day itself and the day after. During quad witching, reduce by **40%** and avoid entries in the final trading hour. Monitor GEX regime: positive gamma = proceed with confidence; negative gamma = reduce size further.

---

## 5. Month-end flows create false pullback signals that reverse early in the new month

**The turn-of-month effect has partially survived 90+ years of documentation.** Lakonishok and Smidt (1988, *Review of Financial Studies*) identified a 4-day window (last trading day through day +3) where the DJIA's average cumulative return was **0.473%**—virtually all positive monthly returns concentrated in just 4 days. McConnell and Xu (2008) confirmed persistence through 2005 across large and small caps. However, QuantSeeker's 2025 analysis found the classical narrow window effect has **largely disappeared** for U.S. equities in the past decade, though a broader 7-day window (days −3 to +3) still shows daily returns **5–12 basis points higher** than other days.

**Institutional rebalancing is the mechanism, and it's massive.** Harvey, Melone, and Mazzoleni (2025, NBER Working Paper #33554) estimate approximately **$20 trillion** in U.S. pension and target-date funds follow fixed-target rebalancing policies. Goldman Sachs estimated pension funds selling **$32 billion** in equities at Q1 2024 quarter-end alone (89th percentile over 3 years). After strong equity months, pension and balanced funds mechanically sell equities to restore 60/40 targets, creating temporary downward pressure on large caps in the **last 3–5 trading days**. This pressure reverses early in the new month as selling ceases and new cash inflows arrive.

**This creates a specific false-signal risk for pullback strategies.** A stock dipping in the last week of a strong-market month with no fundamental catalyst may be experiencing rebalancing flow, not genuine weakness. The distinguishing signals: broad-based weakness across sectors, elevated close-of-day volume, simultaneous bond rally (pension funds buying bonds with equity sale proceeds), and absence of company-specific news.

**Quarter-end window dressing amplifies the effect.** Fund managers buy recent winners and dump recent losers before quarter-end reporting. Agarwal, Gay, and Ling (*Review of Financial Studies*) found this accounts for approximately **1.2% of mutual funds' total trading volume**. Year-end window dressing is strongest. For pullback strategies, this means recent losers face extra selling pressure at quarter-end that may create genuine oversold conditions—potential opportunity rather than noise.

---

## 6. Holiday effects and index rebalancing have limited impact on large-cap pullbacks

**Pre-holiday returns are historically strong but the effect has faded for U.S. large caps.** Quantpedia's analysis shows pre-holiday day returns exceeding normal-day returns by **more than 10×** historically. The Santa Claus Rally (last 5 trading days of December + first 2 of January) has been positive **~78% of the time** since 1950, averaging **1.3–1.4%** over the 7-day window. However, Chong et al. (2005) found the pre-holiday effect has declined in the U.S. market. For a daily pullback strategy on S&P 100 stocks, holiday effects are a **low-priority filter**—worth noting but not worth systematically excluding.

**Three-day weekend gap risk is not directionally biased for large caps.** The Federal Reserve Bank of Boston found the negative weekend drift has disappeared for large-cap indices, with negative weekend returns now confined primarily to small-cap stocks. Evidence does **not support** systematically closing S&P 100 positions before 3-day weekends.

**The S&P 500 index addition/deletion effect has essentially vanished.** Greenwood (Harvard, 2023) found the average deletion effect was just **−0.6%** in 2010–2020, down from −16.1% in the 1990s—neither statistically distinguishable from zero. S&P Dow Jones Indices confirmed the structural decline. However, "pure" additions (companies leapfrogging from outside the S&P 1500) can still generate significant short-term moves. Dimensional Fund Advisors (2024) documented reconstitution-day price pressure of **30 basis points** for deletions at close, reversing **63 basis points** overnight—useful for short-term mean-reversion but not a systematic filter for the pullback strategy.

**Russell reconstitution is shifting to semi-annual in 2026** (June and December), with approximately **$10.6 trillion** benchmarked to Russell indexes. The June event remains one of the highest-volume days of the year (**$219.6 billion** traded at the 2024 close). For S&P 100 stocks that overlap Russell membership, reconstitution days may create temporary dislocations but the primary impact is on small-cap Russell 2000 constituents.

**Tax-loss selling in December** creates genuine opportunities primarily in smaller, beaten-down stocks. Sikes found a 1 percentage point increase in institutional Q4 realized losses generates a **47 basis points** increase in average daily returns over the first 3 January trading days. The effect is most pronounced in high-volatility, small-cap losers—not S&P 100 blue chips. Individual S&P 100 stocks with particularly poor years may experience some December selling pressure, creating modest pullback entries.

---

## 7. The event risk scoring algorithm: exact formula and thresholds

The optimal approach combines continuous scoring for position sizing with hard cutoffs at extreme levels, following Rob Carver's systematic risk management framework: proportional de-risking is superior to binary switches, which discard information and create cliff effects.

**Core scoring formula (additive with cap):**

```
total_score = min(10, Σ individual_event_scores)
```

**Individual event scores:**

| Event | Condition | Score |
|---|---|---|
| **Stock-specific earnings** | Within ±2 trading days | +7 |
| **Stock-specific earnings** | Within ±3–5 trading days | +3 |
| **FOMC (dot-plot)** | Day before or day of | +5 |
| **FOMC (standard)** | Day before or day of | +4 |
| **FOMC (any)** | Day after | +2 |
| **CPI release** | Day of | +2 |
| **NFP release** | Day of | +2 |
| **Monthly OpEx** | Day of or day after | +2 |
| **Quad witching** | Day of or day after | +3 |
| **Fed minutes** | Day of (afternoon) | +1 |
| **Month-end rebalancing** | Last 3 trading days (strong market month) | +1 |

**Position sizing formula:**

```
if score >= 8:
    position_size = 0  # No new entries
elif score >= 5:
    position_size = base_risk_pct × max(0.25, 1 - score/10)
    # Also require tighter entry criteria (deeper pullback, better volume)
else:
    position_size = base_risk_pct × (1 - score/10)
```

The 25% floor prevents going to zero on moderate events while still allowing high-conviction setups. This aligns with fractional Kelly best practices—most institutional traders use 25–50% of full Kelly. The three-tier structure (scores 0–4: size reduction only; scores 5–7: size reduction + tighter criteria; scores 8–10: no new entries) provides graduated risk management.

**Compounding example:** FOMC dot-plot day (5) + CPI release same morning (2) + monthly OpEx (2) = score 9 → no new entries. This triple convergence occurs roughly once per year and represents genuine regime-change risk.

---

## 8. Event impact matrix with evidence quality ratings

| Event type | Avg effect size | Optimal exclusion window | Evidence quality | Annual frequency | Trades affected/month |
|---|---|---|---|---|---|
| **Earnings (stock-specific)** | 5–10% implied move; 5× return variance | −5 to +3 trading days | ★★★★★ (thousands of papers) | ~400 events across 100 stocks | ~3–5 peak months; ~0 off-peak |
| **FOMC announcements** | 40–60% wider SPY range | −1 to +0 days (hard); +1 day (soft) | ★★★★☆ (Lucca-Moench, Hu et al.) | 8/year | ~2 |
| **Dot-plot FOMC** | 2.0–2.5% SPY range on shifts | −1 to +1 days | ★★★★☆ | 4/year | ~1 |
| **CPI release** | −0.70 quintile spread on Nasdaq | Day of (morning only) | ★★★☆☆ (LSEG, post-2021 regime) | 12/year | ~1 (sizing only) |
| **NFP release** | ±51 bps above normal | Day of (morning only) | ★★★★☆ (Capstone 34-year study) | 12/year | ~1 (sizing only) |
| **Monthly OpEx** | +50 bps excess return (OpEx week) | Day of + day after | ★★★☆☆ (Stivers & Sun 2013) | 12/year | ~1 (sizing only) |
| **Quad witching** | 50–100% volume; last-hour bearish | Day of + day after | ★★★☆☆ | 4/year | ~0.5 |
| **Fed minutes** | 3× Treasury vol; modest equity impact | Day of (2 PM window) | ★★★☆☆ (Rosa 2013) | 8/year | ~0 (note only) |
| **Month-end rebalancing** | $20–32B in flows; ~17 bps next-day | Last 3 days of month | ★★★☆☆ (Harvey et al. 2025 NBER) | 12/year | ~1 (awareness) |
| **Index rebalancing** | 9–30 bps at close; reverses overnight | Reconstitution day | ★★★☆☆ (Dimensional 2024) | 4/year | ~0 (affected names only) |
| **Holidays** | Pre-holiday returns 10× normal | Half-day sessions | ★★☆☆☆ (declining effect) | ~9/year | ~0 |

**Total estimated opportunity cost:** ~5–6 trades eliminated per month out of 35 (~15–17%), plus ~2–3 trades per month at 25–70% of normal size. During peak earnings months, the elimination rate rises to 35–50%.

---

## 9. Implementation specification with data sources and pseudocode

**Minimum viable event calendar** (covers ~80% of the value with 3 event types):

- **Earnings dates**: Finnhub API (`finnhub.io`, free tier, 60 calls/minute). Endpoint: `earnings_calendar(from, to)` returns date, symbol, EPS estimate/actual. Alternative: Financial Modeling Prep API.
- **FOMC dates**: Hardcode annually from `federalreserve.gov/monetarypolicy/fomccalendars.htm`. The 2026 schedule: Jan 28, Mar 18, May 6, Jun 17, Jul 29, Sep 16, Nov 4, Dec 16. Dot-plot meetings: Mar 18, Jun 17, Sep 16, Dec 16.
- **OpEx dates**: Compute programmatically (3rd Friday of each month). Quad witching = 3rd Friday of March/June/September/December.
- **Market holidays**: `pandas_market_calendars` Python library (122K weekly downloads). Use: `mcal.get_calendar('NYSE').schedule(start, end)`.
- **Economic releases**: Finnhub economic calendar endpoint or Trading Economics API (`tradingeconomics.com/api/calendar.aspx`). Both provide importance ratings.

**Complete scoring engine pseudocode:**

```python
import finnhub
import pandas_market_calendars as mcal
from datetime import datetime, timedelta

FOMC_2026 = ["2026-01-28", "2026-03-18", "2026-05-06", "2026-06-17",
             "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16"]
DOT_PLOT = ["2026-03-18", "2026-06-17", "2026-09-16", "2026-12-16"]

def business_days_between(date1, date2, calendar):
    """Count trading days between two dates."""
    schedule = calendar.schedule(start_date=min(date1,date2), end_date=max(date1,date2))
    return len(schedule) - 1

def event_risk_score(symbol, trade_date, earnings_map, calendar):
    score = 0

    # 1. EARNINGS (highest priority)
    if symbol in earnings_map:
        for ea_date in earnings_map[symbol]:
            days = business_days_between(trade_date, ea_date, calendar)
            if trade_date <= ea_date and days <= 2:
                score += 7   # Very close pre-earnings
            elif trade_date <= ea_date and days <= 5:
                score += 3   # Moderate pre-earnings
            elif trade_date > ea_date and days <= 1:
                score += 5   # Day after earnings
            elif trade_date > ea_date and days <= 3:
                score += 2   # Post-earnings normalization

    # 2. FOMC
    for fomc in FOMC_2026:
        fomc_dt = datetime.strptime(fomc, "%Y-%m-%d").date()
        days = business_days_between(trade_date, fomc_dt, calendar)
        is_dot_plot = fomc in DOT_PLOT
        if days == 0:  # FOMC day
            score += 5 if is_dot_plot else 4
        elif trade_date < fomc_dt and days == 1:  # Day before
            score += 3 if is_dot_plot else 2
        elif trade_date > fomc_dt and days == 1:  # Day after
            score += 2

    # 3. OPTIONS EXPIRATION
    opex = get_third_friday(trade_date.year, trade_date.month)
    days_to_opex = business_days_between(trade_date, opex, calendar)
    is_quad = trade_date.month in [3, 6, 9, 12]
    if days_to_opex == 0:
        score += 3 if is_quad else 2
    elif days_to_opex == 1 and trade_date > opex:
        score += 2 if is_quad else 1

    # 4. MACRO RELEASES (CPI, NFP on release day)
    if is_nfp_day(trade_date) or is_cpi_day(trade_date):
        score += 2

    return min(10, score)

def adjusted_position_size(base_risk_pct, score):
    if score >= 8:
        return 0.0  # No new entries
    return base_risk_pct * max(0.25, 1.0 - score / 10.0)
```

**Backtest framework design:** Run the identical pullback-in-uptrend strategy on historical S&P 100 data (point-in-time constituents to avoid survivorship bias) in three modes: (A) unfiltered baseline, (B) event-scored with position sizing only, (C) event-scored with position sizing + entry filtering. Compare Sharpe ratio, profit factor, maximum drawdown, win rate, and average trade P&L. Use walk-forward validation with 70/30 in-sample/out-of-sample split. Keep total free parameters under 5 to minimize overfitting risk—with only 8 FOMC meetings per year, even 10 years provides just 80 data points per event type. Expect live drawdowns to run **1.5–2× greater** than backtested drawdowns.

**Critical backtest pitfall:** Earnings dates must use the *announced* date at the time, not the actual report date—companies occasionally shift dates. Finnhub's historical calendar provides this data. Also ensure that the economic calendar uses the *scheduled* release time, not the actual time (for rare delays or early releases).

---

## Conclusion: a three-tier priority system for Halcyon Lab

The research converges on a clear hierarchy. **Tier 1 (must-implement immediately):** Stock-specific earnings exclusion (±5 pre / +3 post trading days) eliminates the single largest source of adverse pullback entries, backed by unambiguous evidence from Dubinsky et al., Aboody et al., and Bernard & Thomas. This alone will remove the strategy's worst trades at a cost of ~3–5 trades per month during earnings season. **Tier 2 (implement within 30 days):** FOMC meeting buffer (−1 to +0 hard pause, +1 soft for dot-plot meetings) and macro release day sizing reduction (25–50% for NFP/CPI). The Savor-Wilson finding that 60%+ of the equity risk premium is earned on announcement days argues against *excluding* macro days—instead, reduce sizing to capture the premium while managing whipsaw risk. **Tier 3 (implement when convenient):** OpEx-week gamma awareness (reduce size on OpEx day; monitor GEX regime), month-end rebalancing flags, and quad-witching buffers.

The total opportunity cost of the full event calendar is approximately **5–6 fewer trades per month** plus 2–3 at reduced sizing. The novel insight from this research: the pre-FOMC drift that would have justified long pullback entries before Fed meetings has **disappeared post-2015** (Kurov et al. 2021), while the OpEx-week bullish bias (Stivers & Sun 2013) actually *favors* pullback entries during expiration weeks. The system should avoid FOMC days but lean into OpEx-week pullbacks—the opposite of naive intuition. Start with the minimum viable calendar (earnings + FOMC + OpEx dates), validate against 10 years of backtest data, and only add complexity when the evidence supports it.