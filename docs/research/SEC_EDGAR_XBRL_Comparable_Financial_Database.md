# Building a comparable financial database from SEC EDGAR XBRL

The most reliable path to structured, comparable financial data for S&P 100 algorithmic trading is the **Company-Facts bulk download** (`companyfacts.zip`), parsed with a priority-based tag mapping system, stored in a hybrid SQLite schema, and used to generate seasonal-random-walk earnings and revenue surprise signals for PEAD enrichment. This approach requires no paid data, no API keys, runs within SEC rate limits, and can be maintained by a solo operator with roughly one hour of quarterly attention. The critical implementation challenges are revenue tag inconsistency across companies (at least 6 common variants), the 8-K timing gap for earnings announcements, and point-in-time correctness for backtesting.

The SEC's free XBRL APIs at `data.sec.gov` provide pre-parsed JSON covering every standard-taxonomy concept reported since ~2009. The US-GAAP taxonomy contains **over 15,000 elements**, but only about **2,770 tags** appear in actual filings, mapping to roughly **234 standardized financial concepts** relevant to analysis. For PEAD signals, the seasonal random walk model—implementable entirely from XBRL data—produces meaningful drift signals, though analyst-based models from I/B/E/S generate approximately 50% larger drift according to Livnat and Mendenhall (2006). Combining earnings and revenue surprise in a double-sort yields approximately **12.5% annual abnormal returns** per Jegadeesh and Livnat (2006).

---

## 1. Three EDGAR XBRL APIs and when to use each

The SEC provides three complementary JSON APIs at `data.sec.gov`, all free, requiring no authentication—only a descriptive `User-Agent` header.

**Company-Facts API** (`/api/xbrl/companyfacts/CIK{cik}.json`) returns every XBRL concept ever reported by a single company across all filings. This is the workhorse for building time series. One call per company yields the complete history—revenue, EPS, assets, cash flows—in a single JSON payload of **5–20 MB** for large filers. The response nests facts under `facts.us-gaap.{ConceptName}.units.USD[]`, where each entry includes `end` (period end date), `start` (for duration concepts), `val` (numeric value), `accn` (accession number), `fy`/`fp` (fiscal year/period), `form` (10-K, 10-Q, etc.), `filed` (SEC acceptance date), and optionally `frame` (the canonical period identifier used by the Frames API).

**Company-Concept API** (`/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{concept}.json`) returns a single concept's full history for one company. Useful for targeted lookups—e.g., checking whether Apple reports under `Revenues` or `RevenueFromContractWithCustomerExcludingAssessedTax`—but inefficient for broad data collection since it requires one call per concept.

**Frames API** (`/api/xbrl/frames/{taxonomy}/{concept}/{unit}/{period}.json`) returns one de-duplicated fact per reporting entity across all filers for a single concept and period. The period format uses `CY2024Q4` for quarterly duration data (revenue, income) and `CY2024Q4I` for instantaneous balance-sheet data—the **`I` suffix denotes "instantaneous"** (point-in-time snapshots). This is ideal for cross-sectional screening but uses the last-filed value, creating potential lookahead bias.

**The recommended approach for S&P 100**: Download `companyfacts.zip` from `https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip` (~1 GB compressed, updated nightly at 3 AM ET). Extract the ~100 JSON files for your target CIKs and process locally with zero rate-limit concerns. For daily updates, poll individual Company-Facts endpoints at ≤10 requests/second.

### Rate limits and compliance

The SEC enforces **10 requests per second** per IP address across all `sec.gov` and `data.sec.gov` endpoints (effective since July 2021). Exceeding this triggers temporary IP-level blocking—typically HTTP 403 responses—that lifts automatically once the rate drops. Every automated request must include a `User-Agent` header in the format `CompanyName admin@company.com`. No API keys or registration are required.

```python
HEADERS = {
    "User-Agent": "HalcyonLab research@halcyonlab.com",
    "Accept-Encoding": "gzip, deflate",
}
# Sleep 0.11s between requests to stay safely under 10 req/sec
```

### Deduplication is essential

A single Company-Facts response contains duplicate values because annual 10-K filings restate prior-quarter figures as comparative data. Two deduplication strategies exist: filter to facts with a `frame` key (selects the SEC's canonical value per period, but uses the last-filed version), or deduplicate on unique `(end, start, val)` tuples while preferring the original filing form. For point-in-time correctness, always use the `filed` date—not `end`—as the data availability timestamp.

---

## 2. The 30 most important XBRL tags and their inconsistency problem

The US-GAAP taxonomy (currently version 2026, accepted by the SEC on March 17, 2026) is published annually by FASB each December and enabled on EDGAR each March. The taxonomy is massive, but practical financial analysis requires a focused set of tags—and the central challenge is that **companies use different tags for the same economic concept**.

### Income statement tags

| Concept | Primary Tag | Common Alternatives | Consistency |
|---------|------------|-------------------|-------------|
| Revenue | `Revenues` | `RevenueFromContractWithCustomerExcludingAssessedTax`, `RevenueFromContractWithCustomerIncludingAssessedTax`, `SalesRevenueNet` *(deprecated)* | **LOW** |
| Cost of Revenue | `CostOfRevenue` | `CostOfGoodsAndServicesSold`, `CostOfGoodsSold` | Medium |
| Gross Profit | `GrossProfit` | — | High |
| Operating Income | `OperatingIncomeLoss` | — | High |
| Net Income | `NetIncomeLoss` | `ProfitLoss`, `NetIncomeLossAvailableToCommonStockholdersBasic` | High |
| EPS Basic | `EarningsPerShareBasic` | — | **Highest** |
| EPS Diluted | `EarningsPerShareDiluted` | — | **Highest** |
| Income Tax | `IncomeTaxExpenseBenefit` | — | High |
| R&D | `ResearchAndDevelopmentExpense` | — | High* |
| SG&A | `SellingGeneralAndAdministrativeExpense` | `GeneralAndAdministrativeExpense`, `SellingAndMarketingExpense` | Medium |

### Balance sheet tags

| Concept | Primary Tag | Alternatives | Consistency |
|---------|------------|-------------|-------------|
| Total Assets | `Assets` | — | **Highest** |
| Total Liabilities | `Liabilities` | — | High |
| Stockholders' Equity | `StockholdersEquity` | `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` | High |
| Cash | `CashAndCashEquivalentsAtCarryingValue` | `CashCashEquivalentsAndShortTermInvestments` | Medium |
| Long-Term Debt | `LongTermDebtNoncurrent` | `LongTermDebt`, `LongTermDebtAndCapitalLeaseObligations` | Medium |
| Shares Outstanding | `CommonStockSharesOutstanding` | `dei:EntityCommonStockSharesOutstanding` | High |

### Cash flow statement tags

| Concept | Primary Tag | Alternatives | Consistency |
|---------|------------|-------------|-------------|
| Operating Cash Flow | `NetCashProvidedByUsedInOperatingActivities` | `...ContinuingOperations` variant | High (91%) |
| CapEx | `PaymentsToAcquirePropertyPlantAndEquipment` | `PaymentsToAcquireProductiveAssets` | High (~90%) |
| D&A | `DepreciationDepletionAndAmortization` | `DepreciationAndAmortization` | Medium |
| Dividends/Share | `CommonStockDividendsPerShareDeclared` | `CommonStockDividendsPerShareCashPaid` | High |

**Free Cash Flow** and **EBITDA** are not standard XBRL tags. Compute them: FCF = `NetCashProvidedByUsedInOperatingActivities` − `PaymentsToAcquirePropertyPlantAndEquipment`. EBITDA = `OperatingIncomeLoss` + `DepreciationDepletionAndAmortization` (top-down method) or `NetIncomeLoss` + `IncomeTaxExpenseBenefit` + `InterestExpense` + `DepreciationDepletionAndAmortization` (bottom-up).

### Revenue is the most inconsistent concept

Revenue tag usage shifted dramatically with **ASC 606** adoption in 2018. Microsoft alone used four different tags between 2010 and 2023: `Revenues` → `SalesRevenueNet` → `SalesRevenueGoodsNet` → `RevenueFromContractWithCustomerExcludingAssessedTax`. Building a revenue time series requires a priority-based fallback:

```python
REVENUE_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",  # Post-ASC 606, preferred
    "RevenueFromContractWithCustomerIncludingAssessedTax",  # Includes sales tax
    "Revenues",                                               # General/legacy
    "SalesRevenueNet",                                        # Deprecated 2018
    "SalesRevenueGoodsNet",                                   # Deprecated
]
```

Banks and financials present a structural divergence: they report `InterestIncomeExpenseNet` and `NoninterestIncome` rather than `RevenueFromContractWithCustomer*`, and they lack `CostOfRevenue` or `GrossProfit`. The EdgarTools analysis identified **42 XBRL tags that have different meanings depending on industry**, with **769 industry-specific mapping overrides** across Fama-French 48 industry groups.

---

## 3. Taxonomy evolution and building stable time series

FASB publishes a new US-GAAP taxonomy each December; the SEC enables it on EDGAR each March. Older versions are supported for approximately 2–3 years (the 2024 taxonomy will not be removed before June 2026). The biggest historical disruption was ASC 606 in 2018, which deprecated `SalesRevenueNet` and introduced the `RevenueFromContractWithCustomer*` family.

**Practical strategies for consistent time series** across taxonomy changes:

The most robust approach is a **concept equivalence mapping table** that groups tags representing the same economic reality. When extracting data, query all equivalent tags and take the first non-null value in priority order. Track which tag each company uses per filing period; when a company switches tags between filings (Apple switching from `Revenues` to `RevenueFromContractWithCustomerExcludingAssessedTax`), the mapping table ensures continuity.

The EdgarTools project, analyzing 32,240 SEC filings, developed a "same-label merging" technique: when a company reports under a new tag but the financial line item label hasn't changed, detect complementary rows (non-overlapping periods) and merge them into a unified series. This works because XBRL label linkbases often preserve human-readable names even when machine-readable tags change.

### Extension taxonomies and custom tags

Every XBRL filing includes a company-specific extension taxonomy that adds custom elements alongside standard US-GAAP tags. Custom tags represent approximately **18–20% of all tags** in typical filings, though this rate has been declining. Custom elements are identifiable by their namespace prefix—standard tags use `us-gaap:`, `dei:`, or `srt:`; anything else (e.g., `aapl:`, `msft:`) is a company extension.

Three methods resolve custom tags to standard equivalents. The **calculation linkbase** (`*_cal.xml`) defines mathematical relationships—if a custom tag is a calculation child of `us-gaap:Revenues`, it's a revenue sub-component. The **presentation linkbase** (`*_pre.xml`) shows where custom tags appear in the financial statement hierarchy. SEC rules now require custom tags to be **anchored** to the closest standard taxonomy element, and this anchor relationship is programmatically extractable. For Halcyon Lab's purposes, the ~50 key metrics are well-covered by standard tags for S&P 100 companies, and custom tags are primarily an issue in operating expense sub-lines and segment disclosures.

---

## 4. Point-in-time correctness and amendment handling

Lookahead bias is the most dangerous error in financial training data. Three sources must be controlled: reporting lag (using period-end dates as if data were available then), data revisions (using amended values that weren't known at the time), and index reconstitution (including companies that weren't in the S&P 100 at the historical date).

**Amended filings** (10-K/A, 10-Q/A) receive new accession numbers and new filing dates but reference the same reporting period. The accession number format is `{CIK}-{YY}-{sequence}`—e.g., `0000320193-25-000006` means Apple's 6th filing in 2025. Higher sequence numbers within the same year are later filings. The EDGAR XBRL APIs (including Frames) silently use the **last-filed value** for each period, which may come from an amendment filed months after the original.

**To build point-in-time data correctly**, always record the `filed` date from each fact and the `form` type. For backtesting, filter to `filed <= simulation_date` and exclude `/A` amendment forms for originally-reported values. The Company-Facts API provides all filing versions (both original and amended), enabling reconstruction of what was known at any historical date. The Frames API does not—it only provides the latest version.

The gap between period-end and filing date is substantial: a fiscal quarter ending December 31 may not have its 10-Q filed until early February. For a 10-K, the gap can be 60+ days. This means cross-sectional screens run on January 15 should only include data from filings accepted before that date—not from Q4 periods that haven't been filed yet.

---

## 5. Python tooling: edgartools is the clear winner

After evaluating 13+ Python libraries for SEC EDGAR data, **edgartools** (v5.26.1, MIT license) is the strongest choice for S&P 100 XBRL extraction in 2026. It is extremely actively maintained with multiple releases per month, supports native XBRL financial statement parsing with standardized labels, wraps all three EDGAR APIs, handles rate limiting automatically, and exports to pandas DataFrames.

```python
from edgar import *
set_identity("halcyonlab research@halcyonlab.com")

# Get all financial facts for Apple
facts = Company("AAPL").get_facts()
revenue_df = facts.to_pandas("us-gaap:Revenues")

# Get structured financial statements
financials = Company("MSFT").get_financials()
income = financials.income_statement()
balance = financials.balance_sheet()
cashflow = financials.cash_flow_statement()
```

For maximum control and minimal dependencies, **direct HTTP requests** to the Company-Facts API are equally viable. The pre-parsed JSON requires no XBRL library at all:

```python
import requests, pandas as pd, time

HEADERS = {"User-Agent": "HalcyonLab research@halcyonlab.com"}

def get_company_facts(cik: str) -> dict:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json"
    time.sleep(0.11)
    return requests.get(url, headers=HEADERS).json()

def extract_quarterly_metric(facts: dict, concept: str) -> pd.DataFrame:
    units = facts["facts"]["us-gaap"][concept]["units"]["USD"]
    df = pd.DataFrame(units)
    quarterly = df[df["form"] == "10-Q"].copy()
    quarterly["end"] = pd.to_datetime(quarterly["end"])
    return quarterly.sort_values("end").drop_duplicates(subset=["end"], keep="last")
```

**Other notable libraries**: `py-xbrl` (v3.0.2) handles low-level XBRL parsing for custom taxonomy work. `sec-edgar-downloader` (v5.1.0) downloads raw filings to disk. `sec-api.io` ($55–239/month) adds real-time filing streams and higher rate limits but is unnecessary for batch processing. `Calcbench` offers 1,000+ standardized metrics with point-in-time tracking but requires a paid subscription. `sec-parser` and `python-xbrl` are inactive/abandoned—avoid them.

The recommendation for a solo operator: use **edgartools** as the primary tool, understand the direct API approach as a fallback, and avoid paid services unless you need real-time filing alerts.

---

## 6. SQLite schema: hybrid EAV with materialized wide table

The optimal schema for S&P 100 algorithmic trading uses a **normalized EAV core** for flexible raw data storage alongside a **pre-pivoted wide table** for fast query execution. Pure EAV requires expensive pivot queries; pure wide tables break when new XBRL tags appear. The hybrid captures both flexibility and speed.

### Core tables

```sql
CREATE TABLE companies (
    company_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    cik             INTEGER NOT NULL UNIQUE,
    ticker          TEXT NOT NULL UNIQUE,
    company_name    TEXT NOT NULL,
    sic_code        INTEGER,
    sector          TEXT,
    fiscal_year_end_month INTEGER NOT NULL DEFAULT 12
);

CREATE TABLE filings (
    filing_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER NOT NULL REFERENCES companies(company_id),
    accession_number    TEXT NOT NULL UNIQUE,
    form_type           TEXT NOT NULL,       -- '10-K', '10-Q', '10-K/A', '10-Q/A'
    filing_date         TEXT NOT NULL,       -- SEC acceptance date (PIT anchor)
    period_end_date     TEXT NOT NULL,
    fiscal_year         INTEGER NOT NULL,
    fiscal_quarter      INTEGER,            -- 1-4, NULL for annual
    is_amendment        INTEGER DEFAULT 0,
    taxonomy_version    TEXT
);

CREATE TABLE concept_mappings (
    mapping_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    xbrl_tag        TEXT NOT NULL,
    canonical_name  TEXT NOT NULL,           -- 'Revenue', 'NetIncome', 'EPS_Diluted'
    statement_type  TEXT NOT NULL,           -- 'IS', 'BS', 'CF'
    priority        INTEGER DEFAULT 100,    -- lower = preferred
    industry_sic    TEXT,                    -- NULL=all, '6000-6999' for financials
    valid_from      TEXT,
    valid_to        TEXT
);

CREATE TABLE financial_facts (
    fact_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    filing_id       INTEGER NOT NULL REFERENCES filings(filing_id),
    company_id      INTEGER NOT NULL,
    xbrl_tag        TEXT NOT NULL,
    canonical_name  TEXT,
    value           REAL,
    period_end_date TEXT NOT NULL,
    period_type     TEXT NOT NULL,           -- 'instant' or 'duration'
    duration_months INTEGER,
    fiscal_year     INTEGER NOT NULL,
    fiscal_quarter  INTEGER,
    filing_date     TEXT NOT NULL,           -- for PIT queries
    is_amendment    INTEGER DEFAULT 0,
    version_number  INTEGER DEFAULT 1
);

-- Critical indexes for algorithmic trading:
CREATE INDEX idx_facts_ts ON financial_facts(company_id, canonical_name, period_end_date);
CREATE INDEX idx_facts_xs ON financial_facts(canonical_name, period_end_date, company_id);
CREATE INDEX idx_facts_pit ON financial_facts(company_id, filing_date, canonical_name);
```

### Materialized wide table for trading queries

```sql
CREATE TABLE financial_summary (
    company_id      INTEGER NOT NULL,
    filing_id       INTEGER NOT NULL,
    period_end_date TEXT NOT NULL,
    period_type     TEXT NOT NULL,     -- 'Q' or 'A'
    fiscal_year     INTEGER NOT NULL,
    fiscal_quarter  INTEGER,
    filing_date     TEXT NOT NULL,
    calendar_quarter TEXT,             -- 'CY2024-Q4' normalized
    is_latest_version INTEGER DEFAULT 1,

    -- Income Statement
    revenue         BIGINT, cost_of_revenue BIGINT, gross_profit BIGINT,
    operating_income BIGINT, net_income BIGINT,
    eps_basic REAL, eps_diluted REAL,

    -- Balance Sheet
    total_assets BIGINT, total_liabilities BIGINT, stockholders_equity BIGINT,
    cash_and_equivalents BIGINT, long_term_debt BIGINT,

    -- Cash Flow
    operating_cashflow BIGINT, capital_expenditures BIGINT,
    free_cash_flow BIGINT,   -- computed: operating - capex
    depreciation BIGINT,

    -- Derived
    gross_margin REAL, operating_margin REAL, net_margin REAL
);

CREATE INDEX idx_summary_ts ON financial_summary(company_id, period_end_date)
    WHERE is_latest_version = 1;
CREATE INDEX idx_summary_pit ON financial_summary(company_id, filing_date)
    WHERE is_latest_version = 1;
CREATE INDEX idx_summary_xs ON financial_summary(calendar_quarter, company_id)
    WHERE is_latest_version = 1;
```

### Fiscal year normalization

Not all S&P 100 companies use calendar quarters. Apple's fiscal year ends in September (Q1=Oct–Dec); Walmart's ends in January. The simplest effective approach is **closest-quarter mapping**: Apple's FQ1 ending December maps to CY Q4 because the period end falls in Q4. Store raw `period_start_date` and `period_end_date` as ground truth and compute the `calendar_quarter` label for cross-sectional analysis. For S&P 100 with ~100 companies × 40 quarters × 50 metrics, the entire `financial_summary` table holds roughly **200,000 rows**—trivially fitting in SQLite memory with WAL mode enabled.

### Point-in-time query example

```sql
-- What quarterly revenue was known for each company as of March 1, 2025?
SELECT c.ticker, fs.fiscal_year, fs.fiscal_quarter,
       fs.revenue / 1e9 AS revenue_b, fs.filing_date
FROM financial_summary fs
JOIN companies c ON c.company_id = fs.company_id
WHERE fs.filing_date <= '2025-03-01'
  AND fs.period_type = 'Q'
  AND fs.is_latest_version = 1
  AND fs.filing_date = (
      SELECT MAX(fs2.filing_date) FROM financial_summary fs2
      WHERE fs2.company_id = fs.company_id
        AND fs2.period_type = 'Q'
        AND fs2.filing_date <= '2025-03-01'
  )
ORDER BY c.ticker;
```

---

## 7. Computing earnings and revenue surprise for PEAD

Post-Earnings Announcement Drift—the tendency for stock prices to continue moving in the direction of an earnings surprise for 60+ trading days—is one of the most robust anomalies in finance. Bernard and Thomas (1989, 1990) documented it extensively: top-vs-bottom SUE decile spreads produced approximately **10–25% annualized returns** historically, with 25–30% of the total drift concentrating in the 3-day windows around the *next three subsequent* earnings announcements.

### The seasonal random walk model works without analyst data

The key practical question is whether XBRL data alone—without I/B/E/S analyst consensus—can generate useful PEAD signals. The answer is **yes, with moderately reduced signal strength**. Livnat and Mendenhall (2006) showed analyst-based surprise produces approximately 50% larger drift than the time-series model, but the seasonal random walk still generates statistically significant returns. The Columbia Business School PEAD study (2024) uses SRW-based SUE as its main specification specifically "to avoid the exclusion of smaller firms without analyst coverage, where PEAD tends to be larger."

**SUE via Seasonal Random Walk** (fully XBRL-implementable):

```
SUE(i,t) = [EPS(i, Q_t) - EPS(i, Q_{t-4})] / σ(past 8 seasonal differences)
```

Where σ is the standard deviation of `EPS(Q_{t-j}) - EPS(Q_{t-j-4})` for j = 1 through 8. Floor σ at a small positive value (e.g., 0.01) to prevent division by near-zero for companies with very stable earnings.

**Revenue surprise** adds approximately **40% incremental signal**. Jegadeesh and Livnat (2006) demonstrated that revenue surprise independently predicts future returns even after controlling for earnings surprise. Revenue-driven earnings growth is more persistent than expense-reduction-driven growth, which is why the market underreacts to it. A double-sort portfolio—long stocks with positive earnings AND revenue surprise, short the opposite—earned approximately **12.5% annual abnormal returns** in their sample.

```python
def compute_sue(eps_series: list, lookback: int = 8) -> float:
    """Seasonal random walk SUE from quarterly EPS series."""
    if len(eps_series) < 5:
        return float('nan')
    surprise = eps_series[-1] - eps_series[-5]  # current vs same quarter last year
    past = [eps_series[-(i+1)] - eps_series[-(i+5)]
            for i in range(1, min(lookback+1, len(eps_series)-4))]
    if len(past) < 4:
        return float('nan')
    sigma = max(np.std(past, ddof=1), 0.01)
    return surprise / sigma

def compute_revenue_surprise(rev_series: list, mktcap: float) -> float:
    """Market-cap-scaled revenue surprise."""
    if len(rev_series) < 5:
        return float('nan')
    return (rev_series[-1] - rev_series[-5]) / max(mktcap, 1e6)
```

### The income-based approach avoids stock split complications

Under ASC 260, stock splits require retroactive restatement of all prior-period EPS. This creates comparison hazards when stitching EPS across filings. **The cleanest solution**: use `NetIncomeLoss` divided by market cap instead of EPS. This is the approach used by Richardson et al. (2010) and eliminates split-adjustment issues entirely. Alternatively, pull both current and year-ago EPS from the *same* 10-Q filing, since comparative figures within a single filing are already split-adjusted.

### The 8-K timing gap is the biggest practical hurdle

Earnings are announced via 8-K (Item 2.02) typically **2–4 weeks before** the 10-Q is filed with XBRL data. The market reacts at the 8-K date, not the 10-Q date. Three approaches to handle this: use the 10-Q filing date as the signal date and accept that you capture only the remaining drift (still significant per Livnat & Livnat 2019); parse 8-K press release text with regex/NLP to extract EPS and revenue figures; or use XBRL data to construct the *surprise magnitude* but time the signal to the 8-K filing date found via EDGAR's full-text search index.

For Halcyon Lab, the pragmatic approach is to look up each company's 8-K Item 2.02 filing date for the relevant quarter and apply the XBRL-derived surprise signal as of that date. The 10-Q provides the clean, structured numbers; the 8-K provides the timing.

### Signal decay and portfolio construction

PEAD alpha peaks at approximately **60 trading days** (~one quarter) post-announcement and continues at diminishing rates for 9–12 months. The standard academic portfolio construction: enter positions on day T+2 after announcement, hold for 60–63 trading days or until the next quarterly announcement. Rank stocks into deciles by SUE; go long the top decile, short the bottom. For a combined signal, weight earnings surprise at ~60% and revenue surprise at ~40%.

Recent evidence indicates PEAD has **attenuated but not disappeared**. Estimates suggest **3–5% quarterly hedge returns** for broad portfolios in recent years, down from 5%+ in earlier decades. The decline is stronger for large-cap stocks. For S&P 100 specifically, the signal is weaker than for small-caps but still present, particularly when combining earnings and revenue surprise and when timed to initial 8-K announcements rather than delayed 10-Q filings.

---

## 8. Complete data pipeline for a solo operator

The end-to-end implementation for Halcyon Lab follows a straightforward architecture: nightly bulk download → tag resolution → SQLite insert → surprise computation → signal output.

```python
"""Halcyon Lab XBRL Pipeline — Minimal Maintenance Architecture"""
import requests, json, zipfile, sqlite3, pandas as pd, time, io
from pathlib import Path

HEADERS = {"User-Agent": "HalcyonLab research@halcyonlab.com"}
SP100_CIKS = {...}  # dict of ticker: CIK from company_tickers.json

# STEP 1: Bulk download (run nightly)
def download_company_facts():
    url = "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip"
    resp = requests.get(url, headers=HEADERS, stream=True)
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for ticker, cik in SP100_CIKS.items():
            fname = f"CIK{str(cik).zfill(10)}.json"
            with zf.open(fname) as f:
                yield ticker, cik, json.load(f)

# STEP 2: Tag resolution with priority fallback
TAG_MAP = {
    "Revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues", "SalesRevenueNet",
    ],
    "NetIncome": ["NetIncomeLoss", "ProfitLoss"],
    "EPS_Diluted": ["EarningsPerShareDiluted"],
    "OperatingCashFlow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "CapEx": ["PaymentsToAcquirePropertyPlantAndEquipment"],
}

def resolve_metric(facts_usga: dict, canonical: str, form_filter="10-Q"):
    for tag in TAG_MAP[canonical]:
        if tag in facts_usga:
            units = facts_usga[tag].get("units", {}).get("USD", [])
            records = [r for r in units if r["form"] == form_filter]
            if records:
                return tag, records
    return None, []

# STEP 3: Insert into SQLite with PIT tracking
# STEP 4: Compute SUE and revenue surprise from stored data
# STEP 5: Output signals ranked by composite surprise
```

### What this architecture provides

For ~100 companies × ~40 quarters of history × ~30 key metrics, the entire database fits in a **sub-100 MB SQLite file**. Nightly updates take under 5 minutes. The concept mapping table handles taxonomy evolution without code changes—just add new tag mappings as rows. Point-in-time correctness is maintained by filtering on `filing_date` rather than `period_end_date`. The seasonal random walk SUE and revenue surprise signals are computed entirely from the stored XBRL data, with no external data dependencies.

## Conclusion

Building a comparable financial database from EDGAR XBRL for S&P 100 algorithmic trading is achievable with free SEC data and open-source tooling, but the devil is in three details. First, **revenue tag inconsistency** across companies and across time requires a maintained priority-based mapping table—the concept_mappings table is the single most important piece of infrastructure. Second, **point-in-time correctness** demands using the `filed` date as the availability anchor and storing both original and amended filing values. Third, the **8-K timing gap** between earnings announcement and 10-Q XBRL availability means that PEAD signals derived purely from 10-Q data will miss the earliest portion of drift, though significant alpha remains.

The seasonal random walk model, applied to both earnings and revenue, provides a credible PEAD signal without any paid data sources. Combining the two in a double-sort (60% earnings, 40% revenue) historically produces approximately 12.5% annual abnormal returns per Jegadeesh and Livnat (2006), though this has attenuated in recent years for large-cap stocks. The key insight from Bernard and Thomas (1990) remains operational: stock prices behave as if investors use a naive seasonal random walk model and underestimate the autocorrelation structure of quarterly earnings, with 25–30% of total drift concentrating around subsequent earnings announcement windows—creating a natural rebalancing cadence for the Halcyon Lab system.