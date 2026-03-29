# Risk budgeting for a 3-strategy equity system on small capital

**Equal-weight allocation wins until you have 200+ trades per strategy.** For Halcyon Lab's $5K–$25K system running pullback-in-uptrend, RSI(2) mean reversion, and evolved PEAD strategies on S&P 100 stocks, the estimation error from fewer than 200 trades per strategy overwhelms the marginal benefit of any sophisticated optimization. The portfolio's most valuable feature — the **ρ ≈ −0.35 negative correlation** between pullback and mean reversion — is already captured simply by running all three strategies simultaneously. DeMiguel, Garlappi & Uppal (2009) showed that equal weight beats optimized portfolios across 14 methods in most empirical settings, and that finding holds even more strongly here with only 3 assets and noisy parameter estimates. The practical path is to start with 1/N, graduate to Equal Risk Contribution at 200+ trades, and reserve Kelly-based sizing for 500+ trades when mean return estimates become marginally reliable.

---

## 1. Equal Risk Contribution captures the correlation structure with minimal estimation risk

Equal Risk Contribution (ERC) allocates capital so each strategy contributes equally to total portfolio variance. The risk contribution of strategy *i* is RC_i = w_i × (Σw)_i, and ERC requires RC_1 = RC_2 = RC_3. This is a convex optimization problem solvable with standard nonlinear solvers.

**With your specific correlation matrix** (pullback↔mean_reversion ρ = −0.35, pullback↔PEAD ρ = 0.05, mean_reversion↔PEAD ρ = 0.10):

| Scenario | Pullback | Mean Reversion | PEAD |
|----------|----------|----------------|------|
| Equal vol (σ = 15% each) | 32.7% | 32.7% | 34.6% |
| Heterogeneous vol (10%, 20%, 15%) | 44.9% | 21.8% | 33.3% |
| Inverse-volatility (for comparison) | 46.2% | 23.1% | 30.8% |
| Max Diversification | ~52% | ~17% | ~31% |

With equal volatilities, ERC degenerates to near-equal weight — only **1.3 percentage points** separate the highest and lowest allocations. The negative correlation between pullback and mean reversion subtly shifts weights, but the effect is minimal without volatility heterogeneity. With heterogeneous volatilities, ERC closely resembles inverse-volatility weighting because correlations contribute only a second-order correction when the correlation matrix is sparse and near-diagonal.

**Sensitivity to correlation misestimation matters.** If the true pullback↔mean_reversion correlation is −0.35 but estimated as −0.15 (a plausible error at N = 100), ERC weights shift by **±3 percentage points per strategy**. With all three correlations uncertain simultaneously, weight uncertainty compounds to ±5–7 percentage points. The standard error of a correlation estimate with N observations is SE(r) ≈ (1 − r²)/√(N − 2). At N = 100 with true ρ = −0.35, the 95% confidence interval spans roughly [−0.53, −0.15] — a wide band that produces meaningfully different allocations.

**Ledoit-Wolf shrinkage** helps modestly. The shrinkage estimator Σ_shrunk = δF + (1−δ)S pulls the sample covariance toward a structured target (typically scaled identity). For a 3×3 matrix with the ratio p/n ≈ 3/100 = 0.03, shrinkage intensity is low and improvement is modest. The bigger win is using `sklearn.covariance.OAS` (Oracle Approximating Shrinkage), which converges better for small samples under Gaussian assumptions. For <200 trades, supplement statistical estimates with domain-knowledge priors about expected strategy correlations.

```python
import numpy as np
from scipy.optimize import minimize

def risk_contribution(weights, cov_matrix):
    port_vol = np.sqrt(weights @ cov_matrix @ weights)
    marginal_contrib = cov_matrix @ weights
    return weights * marginal_contrib / port_vol

def erc_objective(weights, cov_matrix):
    rc = risk_contribution(weights, cov_matrix)
    target = np.mean(rc)
    return np.sum((rc - target) ** 2) * 1e6

def compute_erc_weights(cov_matrix, n=3):
    w0 = np.ones(n) / n
    constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]
    bounds = [(0.01, 0.99)] * n
    result = minimize(erc_objective, w0, args=(cov_matrix,),
                      method='SLSQP', bounds=bounds, constraints=constraints,
                      options={'ftol': 1e-15, 'maxiter': 1000})
    return result.x

# Your correlation matrix
corr = np.array([[1.00, -0.35, 0.05],
                 [-0.35, 1.00, 0.10],
                 [0.05,  0.10, 1.00]])
sigmas = np.array([0.10, 0.20, 0.15])
cov = np.outer(sigmas, sigmas) * corr

weights = compute_erc_weights(cov)
# → [0.449, 0.218, 0.333]
```

---

## 2. HRP degenerates to near-equal weight for 3 assets

Marcos López de Prado's Hierarchical Risk Parity (2016, Journal of Portfolio Management) was designed for large universes where covariance matrix inversion is unstable. The algorithm computes a distance matrix d(i,j) = √(0.5·(1−ρ_ij)), performs single-linkage hierarchical clustering, reorders the covariance matrix along the dendrogram, then recursively bisects clusters while allocating capital inversely proportional to cluster variance.

**For exactly 3 strategies, the dendrogram has only 2 merges.** Walking through your specific correlations:

- **Distances:** d(mean_rev, PEAD) = 0.671, d(pullback, PEAD) = 0.689, d(pullback, mean_rev) = 0.822
- **Merge 1:** mean_reversion + PEAD cluster first (smallest distance = highest positive correlation)
- **Merge 2:** pullback joins the cluster (it's the "outlier" due to its negative correlation with mean_reversion)
- **Leaf order:** [mean_rev, PEAD, pullback]

After recursive bisection with equal volatilities: **mean_rev 34.4%, PEAD 32.8%, pullback 32.8%**. The deviation from 1/N = 33.3% is only ~1%. With heterogeneous volatilities (10%, 20%, 15%), HRP produces weights of approximately 58.6%, 15.3%, 26.1% — essentially inverse-variance weighting with a negligible hierarchical twist.

**HRP's theoretical advantages evaporate for N = 3.** It doesn't require matrix inversion (but a 3×3 matrix inverts trivially). It handles ill-conditioned matrices (but 3×3 matrices with 6 parameters are never ill-conditioned). It captures hierarchical cluster structure (but 2 merges encode almost no information). **HRP adds implementation complexity without meaningful improvement over inverse-volatility weighting for this system.**

```python
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.spatial.distance import squareform

def hrp_portfolio(cov, corr, names):
    dist = np.sqrt(0.5 * (1 - corr))
    np.fill_diagonal(dist, 0)
    link = linkage(squareform(dist), method='single')
    sort_ix = list(leaves_list(link))
    
    weights = {names[i]: 1.0 for i in sort_ix}
    ordered = [names[i] for i in sort_ix]
    clusters = [ordered]
    
    while clusters:
        new_clusters = []
        for c in clusters:
            if len(c) > 1:
                mid = len(c) // 2
                c1, c2 = c[:mid], c[mid:]
                v1 = _cluster_var(cov, c1, names)
                v2 = _cluster_var(cov, c2, names)
                alpha = 1 - v1 / (v1 + v2)
                for n in c1: weights[n] *= alpha
                for n in c2: weights[n] *= (1 - alpha)
                new_clusters.extend([c1, c2])
        clusters = [c for c in new_clusters if len(c) > 1]
    
    return weights

def _cluster_var(cov, cluster, all_names):
    idx = [all_names.index(n) for n in cluster]
    sub = np.array(cov)[np.ix_(idx, idx)]
    ivp = 1.0 / np.diag(sub)
    ivp /= ivp.sum()
    return ivp @ sub @ ivp
```

---

## 3. Maximum Diversification adds modest value over ERC

The Maximum Diversification Portfolio (Choueifaty & Coignard, 2008) maximizes the Diversification Ratio DR = (w'σ) / √(w'Σw), where σ is the vector of individual volatilities and Σ is the covariance matrix. The DR measures how much the weighted average volatility exceeds the portfolio's actual volatility — a pure measure of diversification benefit.

With your correlation structure, Max Diversification weights tilt more aggressively toward the pullback strategy (**~52%** vs ERC's 44.9%) because it exploits the negative correlation with mean reversion more heavily. The diversification ratio is approximately **1.35**, meaning weighted average volatility exceeds portfolio volatility by 35%.

**Under constant equal pairwise correlations**, Max Diversification simplifies exactly to inverse-volatility weighting. Your correlations break this assumption — the ρ = −0.35 is substantially different from the other two near-zero correlations — so inverse-vol is an approximation, not exact. Max Diversification overweights pullback by ~6 percentage points relative to inverse-vol because of the hedging benefit with mean reversion.

**For 3 strategies, the difference between Max Diversification and ERC is 5–8 percentage points per strategy.** This is meaningful in theory but small enough that estimation error at N < 200 likely exceeds the true optimal difference. Max Diversification also tends to produce more concentrated portfolios, which is riskier when correlation estimates are uncertain. **ERC is the more robust choice.**

---

## 4. Kelly Criterion produces absurd leveraged allocations with uncertain parameters

The multivariate Kelly criterion f* = Σ⁻¹μ maximizes expected log wealth growth for a portfolio of correlated strategies. Applied to your system with per-trade returns μ = (0.5%, 0.3%, 0.4%) and per-trade volatilities σ = (2%, 1.5%, 1.8%):

**Full Kelly fractions: approximately f = [16.2×, 16.8×, 13.7×]** — total leverage of ~47×. This is absurd. The negative correlation between pullback and mean reversion actually *increases* optimal leverage because the strategies partially hedge each other. Even quarter-Kelly requires ~12× leverage, and **1/15 to 1/20 Kelly** is needed to reach un-leveraged allocations.

The deeper problem is estimation sensitivity. With N = 100 trades, σ = 2%/trade, and true μ = 0.5%/trade, the standard error of the mean is SE(μ) = 2%/√100 = 0.2%. The 95% confidence interval for the mean return is **[0.1%, 0.9%]**. Plugging these bounds into the single-strategy Kelly formula f* = μ/σ² produces Kelly fractions ranging from **2.5× to 22.5×** — a **9× range** across the confidence interval. Per Chopra & Ziemba (1993), errors in mean estimates are approximately **20× more important** than errors in covariance estimates for portfolio optimization. Kelly is mean-variance optimization with risk aversion λ = 1, so it suffers this sensitivity maximally.

**Kelly is inappropriate as the primary allocation method with <200 trades.** Ed Thorp succeeded with Kelly because casino games have *known* edges. Trading strategies have *estimated* edges with massive uncertainty at small sample sizes. Use Kelly only as a position-size ceiling or sanity check, never as the primary allocator.

```python
def kelly_fractions(mu, cov_matrix):
    """Full Kelly: f* = Σ^{-1} * μ"""
    return np.linalg.solve(cov_matrix, mu)

def fractional_kelly(mu, cov_matrix, fraction=0.25):
    return fraction * kelly_fractions(mu, cov_matrix)
```

---

## 5. Volatility targeting should scale with account size

To implement vol targeting, first compute base weights (via ERC or equal weight), then scale: w_final = k × w_base, where k = target_vol / (√(w_base'Σw_base) × √252). Scaling preserves the risk contribution properties of ERC weights.

The right volatility target depends on capital level and risk tolerance. Maximum drawdown empirically runs **2–3× annualized volatility**, so a 20% vol target implies potential 40–60% drawdowns.

| Capital | Recommended Vol Target | Expected Max DD | Rationale |
|---------|----------------------|-----------------|-----------|
| $5K | 10–12% | 20–35% | Protect scarce capital; $500–$1,750 max DD |
| $10K | 12–15% | 25–45% | Moderate growth; $2,500–$4,500 max DD |
| $25K | 15–20% | 30–60% | Growth-oriented; $7,500–$15,000 max DD |

**Dynamic vol targeting significantly improves risk-adjusted returns.** Moreira & Muir (2017) found that volatility-managed portfolios increase Sharpe ratios for equity factors, and Harvey et al. (2018, Man Group) confirmed that the improvement is strongest during high-volatility regimes. A simple VIX-based overlay:

- **VIX < 20:** Full target exposure
- **VIX 20–25:** Reduce to 75% exposure
- **VIX 25–30:** Reduce to 50%
- **VIX > 30:** Reduce to 30%

```python
def vol_targeted_weights(base_weights, cov_matrix, target_vol=0.15):
    port_vol_annual = np.sqrt(base_weights @ cov_matrix @ base_weights) * np.sqrt(252)
    k = target_vol / port_vol_annual
    return k * base_weights, k

def dynamic_scalar(current_vix, target_vol, realized_vol_20d):
    vol_forecast = max(realized_vol_20d, current_vix / 100)
    base = target_vol / (vol_forecast * np.sqrt(252))
    if current_vix > 30: return base * 0.3
    elif current_vix > 25: return base * 0.5
    elif current_vix > 20: return base * 0.75
    return min(base, 1.5)  # cap leverage at 1.5x
```

---

## 6. Monthly rebalancing with tolerance bands is optimal

The academic evidence is clear and consistent. A Vanguard study using a 60/40 portfolio back to 1926 found **no material differences in risk or returns for rebalancing frequencies from monthly to annual**. Daryanani's tolerance-band study found that threshold-based rebalancing consistently outperforms calendar-based approaches, with optimal bands of **±5 percentage points** relative to target allocation.

For 3 daily-trading strategies, **strategy-level correlations change slowly**. The pullback↔mean_reversion negative correlation reflects structural differences in signal construction, not transient market conditions. Correlations between strategy types (momentum, mean reversion, event-driven) shift meaningfully only during regime changes that occur at monthly or quarterly frequency.

**Recommended protocol: monthly calendar review with daily circuit-breaker monitoring.** On the first trading day of each month, check if any strategy's actual allocation has drifted more than 5 percentage points from target. If yes, rebalance. If no, take no action. Between monthly reviews, monitor drawdown circuit breakers daily (covered in Section 8).

---

## 7. Transaction costs are negligible at this capital level

On commission-free Alpaca trading S&P 100 stocks with position sizes of $500–$2,500:

- **Bid-ask spread:** S&P 100 stocks average ~3.7 bps quoted spread (Nasdaq analysis). Mega-caps like AAPL and MSFT run ~1 bps.
- **Round-trip spread cost:** ~2–4 bps per position
- **Market impact:** Effectively zero. Daily volume for S&P 100 stocks is $100M–$1B+; a $2,000 order is invisible.
- **Monthly rebalancing cost:** Adjusting 2–3 positions × $1,000 average × 3 bps = **$0.60–$0.90 per month**
- **Annual rebalancing friction:** **$7–$22** on $25K capital = 0.03–0.09%

**The real cost is taxes, not spreads.** A rebalancing trade realizing $200 in short-term gains at a 24% marginal rate costs $48 — roughly **50–100× the spread cost**. Mitigation: rebalance using new cash contributions first, direct new signals toward underweight strategies, and use tax-advantaged accounts when possible. Always use **limit orders** on Alpaca to mitigate any payment-for-order-flow execution quality concerns.

Transaction costs become material at **$100K+** where position sizes ($10K–$30K) may create modest market impact on less-liquid S&P 100 names.

---

## 8. Drawdown-conditional allocation requires Bayesian discipline

Harvey, Van Hemert, Rattray et al. (2020, Journal of Portfolio Management) provide the definitive framework. Their key finding: **when managers are of constant quality, drawdown-based rules destroy value** because reducing allocation locks in losses. But **when there's meaningful probability of skill decay**, drawdown rules protect capital. The critical challenge is distinguishing bad luck from genuine edge decay.

**Bayesian updating quantifies this.** Starting with a prior of Beta(55, 45) encoding belief in a 55% win rate, after 8 consecutive losses the posterior becomes Beta(55, 53) with mean 50.9%. The posterior probability that the true win rate has fallen below 50% is approximately **42%** — elevated but not conclusive. The standalone probability of 8 consecutive losses with a true 55% win rate is (0.45)⁸ = **1.68%** — rare but expected to occur at least once in 200 trades with ~7–10% probability across all possible starting points.

**Tiered circuit breaker protocol:**

| Trigger | Action | Recovery Requirement |
|---------|--------|---------------------|
| Strategy DD < 1.5× expected monthly DD | No action | — |
| Strategy DD = 1.5–2× expected monthly DD | Monitor; update Bayesian estimate | — |
| Strategy DD > 2× expected monthly DD | **Reduce allocation by 50%** | 1 month positive P&L |
| Strategy DD > 3× expected monthly DD | **Pause strategy** | 2 consecutive months positive |
| Strategy exceeds max backtest DD | Full investigation; consider removal | — |
| P(win_rate < 50%) > 65% | Flag for review | — |

**Freed capital from reduced or paused strategies redistributes proportionally to remaining active strategies.** This preserves portfolio-level exposure while protecting against edge decay.

```python
from scipy.stats import beta as beta_dist

class StrategyMonitor:
    def __init__(self, name, prior_wins=55, prior_losses=45):
        self.name = name
        self.alpha = prior_wins   # Beta distribution: wins
        self.beta_ = prior_losses  # Beta distribution: losses
        self.peak_equity = 0
        self.expected_monthly_dd = None  # Set from backtest
    
    def update_trade(self, is_win):
        if is_win: self.alpha += 1
        else: self.beta_ += 1
    
    @property
    def prob_edge_lost(self):
        """P(true_win_rate < 0.50 | data)"""
        return beta_dist.cdf(0.50, self.alpha, self.beta_)
    
    @property
    def posterior_win_rate(self):
        return self.alpha / (self.alpha + self.beta_)
```

---

## 9. Position sizing at $5K is the binding constraint, not allocation method

At **$5K with 1% risk per trade**, maximum loss is $50. For a $150 stock with a 3% stop ($4.50 risk/share), position size = $50 / $4.50 = 11 shares = **$1,667 — fully 33% of capital in a single position**. Maximum concurrent positions: 3. With 3 strategies needing 1–2 positions each, $5K simply cannot support full simultaneous deployment.

| Capital | 1% Risk $ | Position Size (typical) | Max Concurrent | Strategies Active |
|---------|-----------|------------------------|----------------|-------------------|
| $5,000 | $50 | $1,667 (33%) | 2–3 | 1–2 (sequential) |
| $10,000 | $100 | $3,333 (33%) | 3–4 | 3 (1 position each) |
| $25,000 | $250 | $8,333 (33%) | 5–8 | 3 (2–3 positions each) |

**Alpaca's fractional share support** (minimum $1 order) eliminates rounding problems for precise position sizing. Bracket orders (entry + stop-loss + take-profit submitted atomically) are essential for algorithmic execution. PDT rules apply below $25K for margin accounts — limit to 3 day trades per 5 business days. A **cash account** eliminates PDT entirely at the cost of T+1 settlement, which is acceptable for these swing strategies with 1–5+ day holding periods.

**Scaling protocol:**

At **$5K**: Run 1–2 strategies sequentially, not all 3 simultaneously. Prioritize RSI(2) mean reversion (highest frequency) or pullback-in-uptrend. Deploy PEAD only during earnings season. Use equal weight allocation. Consider a cash account to avoid PDT restrictions entirely.

At **$10K**: All 3 strategies can run simultaneously with 1 position each. Introduce inverse-volatility weighting if strategy volatilities differ by >50%. Implement account-level drawdown scaling: reduce risk to 0.75% at −5% drawdown, 0.5% at −10%, halt at −15%.

At **$25K**: Full ERC allocation with volatility targeting. PDT threshold cleared — can day trade freely with margin account. Implement the complete rebalancing engine with monthly reviews and daily circuit breakers. Target **15% annualized portfolio volatility** with VIX-based dynamic scaling.

```python
def compute_position_size(capital, risk_pct, entry, stop, strategy_weight=0.333,
                          min_dollars=200, max_pct=0.35):
    risk_per_share = abs(entry - stop)
    dollar_risk = capital * risk_pct
    shares = min(dollar_risk / risk_per_share,
                 capital * strategy_weight / entry,
                 capital * max_pct / entry)
    shares = round(shares, 4)  # Alpaca supports fractional
    position = shares * entry
    if position < min_dollars:
        return None  # Position too small
    return {'shares': shares, 'value': round(position, 2),
            'risk': round(shares * risk_per_share, 2),
            'pct_capital': round(position / capital, 3)}

def get_risk_params(capital, drawdown_pct=0.0):
    base_risk = 0.01
    if drawdown_pct >= 0.15: return {'risk': 0, 'note': 'HALT'}
    elif drawdown_pct >= 0.10: base_risk *= 0.5
    elif drawdown_pct >= 0.05: base_risk *= 0.75
    
    if capital < 10000: return {'risk': base_risk, 'max_pos': 3, 'strategies': 2}
    elif capital < 25000: return {'risk': base_risk, 'max_pos': 4, 'strategies': 3}
    else: return {'risk': base_risk, 'max_pos': 8, 'strategies': 3}
```

---

## 10. The 1/N puzzle resolves clearly in favor of simplicity at small sample sizes

DeMiguel, Garlappi & Uppal (2009, Review of Financial Studies) tested 14 optimization models against equal weight across 7 empirical datasets. **None consistently outperformed 1/N** in terms of Sharpe ratio, certainty-equivalent return, or turnover. They estimated that mean-variance optimization requires **~3,000 months (250 years!) of data** to reliably outperform 1/N with 25 assets. Extrapolating to 3 assets (only 6 covariance parameters vs. 325), the threshold drops to roughly **50–60 months** for MV optimization — but this still requires return estimates, which are the dominant error source.

For **risk-only methods** that don't require return forecasts (ERC, HRP, inverse-vol), the sample requirement is much lower because variances are approximately **10× easier to estimate than means** (Merton, 1980). With 3 strategies, ~60–120 observations give reasonably stable covariance estimates, meaning ERC can potentially outperform 1/N at 100+ trades if volatilities are heterogeneous.

**Expected Sharpe improvement of each method over equal weight for 3 strategies:**

| Method | Expected ΔSharpe | Minimum Trades | Primary Benefit |
|--------|-----------------|----------------|-----------------|
| Inverse-volatility | 0.00–0.05 | ~50 | Adjusts for vol differences |
| ERC | 0.02–0.08 | ~100–200 | Exploits ρ = −0.35 correlation |
| HRP | 0.01–0.05 | ~100 | ≈ Inverse-vol for N = 3 |
| Max Diversification | 0.02–0.08 | ~100–200 | Most aggressive correlation exploitation |
| Kelly (half) | −0.10 to +0.15 | ~500+ | High variance; often negative |

The marginal improvement from any sophisticated method is **at most 0.05–0.08 Sharpe ratio** with 3 strategies. This is a second-order optimization. Strategy quality is the first-order problem; allocation method is a distant second.

---

## Concrete implementation roadmap for Halcyon Lab

**Phase 1 — Now (<100 trades/strategy):** Use **equal weight** (1/3 each). At $5K, run only 1–2 strategies simultaneously. Use 1% risk per trade, cash account to avoid PDT. No rebalancing needed — just split capital equally. Focus entirely on validating strategy implementation and building track record.

**Phase 2 — Intermediate (100–200 trades/strategy):** If strategy volatilities differ by >50%, switch to **inverse-volatility weighting**: w_i = (1/σ_i) / Σ(1/σ_j). This requires only individual variance estimates (no correlation), which are reliable at ~50 trades. Apply Ledoit-Wolf shrinkage to the covariance matrix as a foundation for Phase 3. Monthly rebalancing with 5-percentage-point drift bands.

**Phase 3 — Established (200–500 trades/strategy):** Upgrade to **Equal Risk Contribution** with a 15% annualized vol target and VIX-based dynamic scaling. Implement the full rebalancing engine with monthly reviews and daily drawdown circuit breakers (reduce at 2× expected monthly DD, pause at 3×). At $25K+, this is the production allocation system.

**Phase 4 — Mature (500+ trades/strategy):** Consider supplementing ERC with **half-Kelly position size ceilings** as a growth accelerator. Mean return estimates become marginally reliable at 500+ observations, but always use Kelly as an upper bound, never the primary allocator. Compare half-Kelly-capped ERC against pure ERC on rolling out-of-sample windows before committing.

**The decision tree:**
```
IF trades_per_strategy < 100:    → Equal weight (1/3 each)
ELIF trades_per_strategy < 200:  → Inverse-vol (if σ's differ >50%), else equal weight
ELIF trades_per_strategy < 500:  → ERC with vol targeting
ELSE:                            → ERC + half-Kelly ceiling
```

The allocation method is a detail. **The portfolio's real edge is structural diversification** — three strategies with a −0.35 correlation, near-zero cross-correlations, and exposure to different market regimes. Getting the strategies right matters far more than optimizing how capital is split among them.