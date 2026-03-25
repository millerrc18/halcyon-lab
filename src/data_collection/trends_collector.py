"""Google Trends attention signal collector.

Uses pytrends to fetch relative search interest for ticker symbols.
Rate-limited: batches of 5 tickers, max 20 per night, 10s sleep between batches.
Rotates through the full universe over multiple nights.
"""

import logging
import sqlite3
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

DB_PATH = "ai_research_desk.sqlite3"

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS google_trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collected_at TEXT NOT NULL,
    collected_date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    search_interest REAL,
    interest_vs_90d_avg REAL,
    spike_flag INTEGER
);

CREATE INDEX IF NOT EXISTS idx_google_trends_ticker_date
    ON google_trends(ticker, collected_date);
"""


def _init_table(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_INIT_SQL)


def _get_tickers_to_collect(
    tickers: list[str], batch_size: int, db_path: str
) -> list[str]:
    """Pick tickers that haven't been collected recently (past 5 days).

    Rotates through the full universe over multiple nights.
    """
    cutoff = (datetime.now(ET) - timedelta(days=5)).strftime("%Y-%m-%d")
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT ticker FROM google_trends WHERE collected_date >= ?",
            (cutoff,),
        ).fetchall()
    recent = {r[0] for r in rows}
    pending = [t for t in tickers if t not in recent]
    if not pending:
        # All covered in last 5 days — restart from beginning
        pending = list(tickers)
    return pending[:batch_size]


def collect_google_trends(
    tickers: list[str],
    batch_size: int = 20,
    db_path: str = DB_PATH,
) -> dict:
    """Collect Google Trends data for a batch of tickers.

    Returns: {"tickers_collected": int, "spikes_detected": int}
    """
    _init_table(db_path)

    try:
        from pytrends.request import TrendReq
    except ImportError:
        logger.warning("[TRENDS] pytrends not installed, skipping")
        return {"tickers_collected": 0, "spikes_detected": 0, "error": "pytrends not installed"}

    now = datetime.now(ET)
    today_str = now.strftime("%Y-%m-%d")

    to_collect = _get_tickers_to_collect(tickers, batch_size, db_path)
    if not to_collect:
        return {"tickers_collected": 0, "spikes_detected": 0}

    tickers_collected = 0
    spikes_detected = 0

    # Process in sub-batches of 5 (Google Trends limit per request)
    pytrends = TrendReq(hl="en-US", tz=300)

    for i in range(0, len(to_collect), 5):
        batch = to_collect[i : i + 5]
        # Append " stock" to each ticker for better search relevance
        keywords = [f"{t} stock" for t in batch]

        try:
            pytrends.build_payload(keywords, timeframe="today 3-m")
            interest = pytrends.interest_over_time()

            if interest is None or interest.empty:
                logger.debug("[TRENDS] No data returned for batch %s", batch)
                continue

            with sqlite3.connect(db_path) as conn:
                for j, ticker in enumerate(batch):
                    keyword = keywords[j]
                    if keyword not in interest.columns:
                        continue

                    series = interest[keyword]
                    if series.empty:
                        continue

                    current_value = float(series.iloc[-1])

                    # Compute 90-day average
                    avg_90d = float(series.mean()) if len(series) > 0 else None
                    vs_avg = None
                    if avg_90d and avg_90d > 0:
                        vs_avg = round(current_value / avg_90d, 4)

                    # Spike detection: > 2σ above 30-day mean
                    spike_flag = 0
                    if len(series) >= 7:
                        recent = series.tail(30)
                        mean_30d = float(recent.mean())
                        std_30d = float(recent.std())
                        if std_30d > 0 and current_value > mean_30d + 2 * std_30d:
                            spike_flag = 1
                            spikes_detected += 1

                    conn.execute(
                        """INSERT INTO google_trends
                        (collected_at, collected_date, ticker,
                         search_interest, interest_vs_90d_avg, spike_flag)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            now.isoformat(),
                            today_str,
                            ticker,
                            current_value,
                            vs_avg,
                            spike_flag,
                        ),
                    )
                    tickers_collected += 1

        except Exception as e:
            logger.warning("[TRENDS] Batch failed for %s: %s", batch, e)

        # Rate limit: 10s between batches
        if i + 5 < len(to_collect):
            time.sleep(10)

    result = {"tickers_collected": tickers_collected, "spikes_detected": spikes_detected}
    logger.info("[TRENDS] Collection complete: %s", result)
    return result
