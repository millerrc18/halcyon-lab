"""Historical backfill orchestrator for high-quality training data generation.

Downloads real historical price data, runs the scoring engine against it,
tracks real outcomes, and generates gold-standard commentary from real
setups with real results.
"""

import json
import logging
import random
import sqlite3
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from src.llm.prompts import HISTORICAL_TRAINING_PROMPT
from src.training.claude_client import generate_training_example
from src.training.historical_data import fetch_historical_universe
from src.training.historical_scanner import (
    compute_outcome,
    generate_backfill_example,
    scan_historical_date,
)
from src.training.versioning import init_training_tables

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")


def estimate_backfill_cost(n_examples: int) -> float:
    """Estimate Claude API cost for generating N backfill examples.

    Each example: ~600 input tokens (features + outcome) + ~800 output tokens (commentary)
    Haiku 4.5: $1/MTok input, $5/MTok output
    """
    input_cost = n_examples * 600 * 1.0 / 1_000_000
    output_cost = n_examples * 800 * 5.0 / 1_000_000
    return round(input_cost + output_cost, 2)


def _get_trading_days(spy_df: pd.DataFrame, start_date: str, end_date: str) -> list[str]:
    """Get actual trading days from SPY index between start and end dates."""
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    mask = (spy_df.index >= start_ts) & (spy_df.index <= end_ts)
    return [d.strftime("%Y-%m-%d") for d in spy_df.index[mask]]


def _deduplicate_candidates(candidates: list[dict], min_gap_days: int = 5) -> list[dict]:
    """Remove consecutive-day entries for the same ticker.

    If the same ticker qualifies on consecutive days, keep only the first
    occurrence. Require at least min_gap_days trading days between entries
    for the same ticker.
    """
    last_seen: dict[str, str] = {}  # ticker -> last scan_date
    result = []

    # Sort by scan_date, then score descending
    candidates.sort(key=lambda x: (x["scan_date"], -x["score"]))

    for c in candidates:
        ticker = c["ticker"]
        scan_date = c["scan_date"]

        if ticker in last_seen:
            last_date = pd.Timestamp(last_seen[ticker])
            current_date = pd.Timestamp(scan_date)
            gap = (current_date - last_date).days
            if gap < min_gap_days:
                continue

        last_seen[ticker] = scan_date
        result.append(c)

    return result


def _balance_dataset(
    examples: list[dict], target_win_ratio: float = 0.6
) -> list[dict]:
    """Balance win/loss ratio by downsampling the majority class.

    Aims for roughly 60/40 win/loss. Losing trades are more instructionally
    valuable and should be proportionally overrepresented vs natural frequency.
    """
    wins = [e for e in examples if e["outcome"]["outcome_quality"] == "clean_win"]
    losses = [e for e in examples if e["outcome"]["outcome_quality"] == "clean_loss"]
    other = [e for e in examples if e["outcome"]["outcome_quality"] not in ("clean_win", "clean_loss")]

    if not losses:
        return examples

    # Target: wins should be target_win_ratio of (wins + losses)
    # So wins = target_win_ratio / (1 - target_win_ratio) * losses
    target_wins = int(len(losses) * target_win_ratio / (1 - target_win_ratio))

    if len(wins) > target_wins:
        random.shuffle(wins)
        wins = wins[:target_wins]

    return wins + losses + other


def _cap_and_diversify(
    examples: list[dict],
    max_examples: int,
    max_per_ticker: int = 30,
) -> list[dict]:
    """Cap total examples and ensure diversity.

    Prioritize:
    - Higher scores first
    - Diverse tickers (no more than max_per_ticker per ticker)
    - Even distribution across the time period
    """
    # First cap per-ticker
    ticker_counts: Counter = Counter()
    ticker_capped = []
    # Sort by score descending
    examples.sort(key=lambda x: -x["candidate"]["score"])

    for ex in examples:
        ticker = ex["candidate"]["ticker"]
        if ticker_counts[ticker] >= max_per_ticker:
            continue
        ticker_counts[ticker] += 1
        ticker_capped.append(ex)

    if len(ticker_capped) <= max_examples:
        return ticker_capped

    # Distribute evenly across time periods (quarters)
    by_month: defaultdict[str, list] = defaultdict(list)
    for ex in ticker_capped:
        month_key = ex["candidate"]["scan_date"][:7]  # YYYY-MM
        by_month[month_key].append(ex)

    months = sorted(by_month.keys())
    per_month = max(1, max_examples // len(months))
    result = []

    for month in months:
        month_examples = by_month[month]
        # Sort by score within month
        month_examples.sort(key=lambda x: -x["candidate"]["score"])
        result.extend(month_examples[:per_month])

    # If still under cap, fill from remaining
    if len(result) < max_examples:
        used = {(e["candidate"]["ticker"], e["candidate"]["scan_date"]) for e in result}
        remaining = [e for e in ticker_capped
                     if (e["candidate"]["ticker"], e["candidate"]["scan_date"]) not in used]
        remaining.sort(key=lambda x: -x["candidate"]["score"])
        result.extend(remaining[:max_examples - len(result)])

    return result[:max_examples]


def _example_exists(db_path: str, ticker: str, scan_date: str) -> bool:
    """Check if a backfill example already exists for this ticker + date."""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """SELECT 1 FROM training_examples
               WHERE source = 'historical_backfill'
               AND ticker = ?
               AND feature_snapshot LIKE ?
               LIMIT 1""",
            (ticker, f"%{scan_date}%"),
        ).fetchone()
    return row is not None


def run_historical_backfill(
    months: int = 12,
    min_score: float = 70,
    quality_filter: list[str] | None = None,
    max_examples: int = 2000,
    db_path: str = "ai_research_desk.sqlite3",
) -> dict:
    """Run the complete historical backfill pipeline.

    Args:
        months: How many months of history to scan (default 12).
        min_score: Minimum score to include (default 70).
        quality_filter: Which outcome_quality values to include.
            Default: ["clean_win", "clean_loss"].
        max_examples: Maximum examples to generate (to control API costs).
        db_path: Database path for storing examples.

    Returns:
        Stats dict with counts, cost, and distribution info.
    """
    if quality_filter is None:
        quality_filter = ["clean_win", "clean_loss"]

    start_time = time.time()
    init_training_tables(db_path)

    # Step 1: Download data
    print("[BACKFILL] Step 1/10: Downloading historical data...")
    data = fetch_historical_universe(lookback_years=2)
    spy_df = data["spy"]

    # Step 2: Generate scan dates
    print("[BACKFILL] Step 2/10: Generating scan dates...")
    end_date = datetime.now() - timedelta(days=20)  # 20-day buffer for outcomes
    start_date = end_date - timedelta(days=months * 30)
    scan_dates = _get_trading_days(
        spy_df, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
    )
    total_dates = len(scan_dates)
    print(f"[BACKFILL] Will scan {total_dates} trading days")

    # Step 3: Scan each date
    print("[BACKFILL] Step 3/10: Scanning historical dates for qualifying setups...")
    all_candidates = []
    for i, scan_date in enumerate(scan_dates):
        candidates = scan_historical_date(data, scan_date)
        # Filter by min_score
        candidates = [c for c in candidates if c["score"] >= min_score]
        all_candidates.extend(candidates)

        if (i + 1) % 20 == 0:
            print(f"[BACKFILL] Scanned {i + 1}/{total_dates} dates, "
                  f"{len(all_candidates)} candidates so far...")

    print(f"[BACKFILL] Scan complete: {len(all_candidates)} candidates from {total_dates} dates")

    # Step 4: Compute outcomes
    print("[BACKFILL] Step 4/10: Computing trade outcomes...")
    candidates_with_outcomes = []
    for c in all_candidates:
        outcome = compute_outcome(
            data, c["ticker"], c["scan_date"],
            c["entry_price"], c["stop_price"],
            c["target_1"], c["target_2"],
        )
        if outcome is not None:
            candidates_with_outcomes.append({
                "candidate": c,
                "outcome": outcome,
            })

    total_with_outcomes = len(candidates_with_outcomes)
    print(f"[BACKFILL] Outcomes computed: {total_with_outcomes} with valid outcomes")

    # Step 5: Quality filter
    print("[BACKFILL] Step 5/10: Applying quality filter...")
    quality_filtered = [
        e for e in candidates_with_outcomes
        if e["outcome"]["outcome_quality"] in quality_filter
    ]
    print(f"[BACKFILL] Quality filtered: {len(quality_filtered)} "
          f"({', '.join(quality_filter)})")

    # Step 6: Balance dataset
    print("[BACKFILL] Step 6/10: Balancing win/loss ratio...")
    balanced = _balance_dataset(quality_filtered)
    outcome_counts = Counter(e["outcome"]["outcome_quality"] for e in balanced)
    print(f"[BACKFILL] After balancing: {len(balanced)} "
          f"(wins: {outcome_counts.get('clean_win', 0)}, "
          f"losses: {outcome_counts.get('clean_loss', 0)})")

    # Step 7: Deduplicate
    print("[BACKFILL] Step 7/10: Deduplicating consecutive entries...")
    # Extract candidates for dedup, then reassemble
    candidate_list = [e["candidate"] for e in balanced]
    deduped_candidates = _deduplicate_candidates(candidate_list)
    deduped_keys = {(c["ticker"], c["scan_date"]) for c in deduped_candidates}
    deduped = [
        e for e in balanced
        if (e["candidate"]["ticker"], e["candidate"]["scan_date"]) in deduped_keys
    ]
    print(f"[BACKFILL] After deduplication: {len(deduped)}")

    # Step 8: Cap and diversify
    print("[BACKFILL] Step 8/10: Capping and diversifying...")
    final_examples = _cap_and_diversify(deduped, max_examples)
    print(f"[BACKFILL] Final candidate count: {len(final_examples)}")

    est_cost = estimate_backfill_cost(len(final_examples))
    print(f"[BACKFILL] Estimated API cost: ${est_cost:.2f}")

    # Step 9: Generate commentary via Claude API
    print("[BACKFILL] Step 9/10: Generating commentary via Claude API...")
    examples_generated = 0
    examples_skipped = 0
    actual_outcomes: Counter = Counter()
    tickers_seen: set[str] = set()

    for i, ex in enumerate(final_examples):
        candidate = ex["candidate"]
        outcome = ex["outcome"]
        ticker = candidate["ticker"]
        scan_date = candidate["scan_date"]

        # Resumability: skip if already exists
        if _example_exists(db_path, ticker, scan_date):
            examples_skipped += 1
            continue

        # Build training example
        training_ex = generate_backfill_example(candidate, outcome)

        # Call Claude API
        response = generate_training_example(
            training_ex["instruction"],
            training_ex["input_text"],
        )

        if response is None:
            logger.warning("[BACKFILL] Claude API failed for %s on %s, skipping",
                           ticker, scan_date)
            continue

        # Store in database
        example_id = str(uuid.uuid4())
        created_at = datetime.now(ET).isoformat()

        metadata = training_ex["metadata"]
        feature_snapshot = json.dumps({
            "scan_date": scan_date,
            "features": candidate["features"],
            "score": candidate["score"],
            "entry_price": candidate["entry_price"],
            "stop_price": candidate["stop_price"],
            "target_1": candidate["target_1"],
            "target_2": candidate["target_2"],
        })
        trade_outcome = json.dumps(outcome)

        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """INSERT INTO training_examples
                   (example_id, created_at, source, ticker, recommendation_id,
                    feature_snapshot, trade_outcome, instruction, input_text, output_text)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (example_id, created_at, "historical_backfill", ticker, None,
                 feature_snapshot, trade_outcome,
                 HISTORICAL_TRAINING_PROMPT,
                 training_ex["input_text"], response),
            )
            conn.commit()

        examples_generated += 1
        actual_outcomes[outcome["outcome_quality"]] += 1
        tickers_seen.add(ticker)

        if examples_generated % 25 == 0:
            spent = estimate_backfill_cost(examples_generated)
            total_target = len(final_examples) - examples_skipped
            pct = examples_generated / total_target * 100 if total_target > 0 else 0
            print(f"[BACKFILL] Generated {examples_generated}/{total_target} "
                  f"examples ({pct:.1f}%) — est. ${spent:.2f} spent")

        # Rate limiting
        time.sleep(0.5)

    # Step 10: Report results
    elapsed = (time.time() - start_time) / 60
    actual_cost = estimate_backfill_cost(examples_generated)

    stats = {
        "total_dates_scanned": total_dates,
        "total_candidates_found": len(all_candidates),
        "total_with_outcomes": total_with_outcomes,
        "quality_filtered": len(quality_filtered),
        "examples_generated": examples_generated,
        "examples_skipped": examples_skipped,
        "examples_by_outcome": dict(actual_outcomes),
        "estimated_cost": actual_cost,
        "tickers_represented": len(tickers_seen),
        "avg_score": (
            sum(e["candidate"]["score"] for e in final_examples) / len(final_examples)
            if final_examples else 0
        ),
        "elapsed_minutes": round(elapsed, 1),
    }

    print(f"\n[BACKFILL] Step 10/10: Complete!")
    return stats
