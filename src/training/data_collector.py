"""Training data collection from closed trades."""

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from src.config import load_config
from src.llm.prompts import TRAINING_EXAMPLE_PROMPT
from src.training.claude_client import generate_training_example
from src.training.versioning import init_training_tables

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")


def _build_feature_input(rec: dict) -> str:
    """Build structured feature text from a recommendation record."""
    return f"""Ticker: {rec.get('ticker', 'N/A')} ({rec.get('company_name', 'N/A')})
Current Price: ${rec.get('price_at_recommendation', 0):.2f}
Trend State: {rec.get('trend_state', 'n/a')}
Relative Strength: {rec.get('relative_strength_state', 'n/a')}
Pullback Depth: {rec.get('pullback_depth_pct', 0):.1f}% from 50-day high
ATR(14): ${rec.get('atr', 0):.2f}
Volume State: {rec.get('volume_state', 'n/a')}
Score: {rec.get('priority_score', 0):.0f}/100 | Confidence: {rec.get('confidence_score', 0):.0f}/10
Entry Zone: {rec.get('entry_zone', 'n/a')} | Stop: {rec.get('stop_level', 'n/a')} | Targets: {rec.get('target_1', 'n/a')} / {rec.get('target_2', 'n/a')}
Event Risk: {rec.get('event_risk_flag', 'none')}"""


def _build_outcome_text(trade: dict) -> str:
    """Build outcome text from a closed shadow trade."""
    return f"""
=== ACTUAL OUTCOME ===
Exit Reason: {trade.get('exit_reason', 'n/a')}
P&L: ${trade.get('pnl_dollars', 0):.2f} ({trade.get('pnl_pct', 0):.1f}%)
Duration: {trade.get('duration_days', 0)} days
MFE: ${trade.get('max_favorable_excursion', 0):.2f} | MAE: ${trade.get('max_adverse_excursion', 0):.2f}"""


def collect_training_examples_from_closed_trades(
    db_path: str = "ai_research_desk.sqlite3",
) -> int:
    """Generate training examples from closed trades that don't already have one.

    Returns count of new examples created.
    """
    config = load_config()
    training_cfg = config.get("training", {})
    if not training_cfg.get("enabled", False):
        return 0

    init_training_tables(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        # Find closed trades without training examples
        rows = conn.execute("""
            SELECT st.*, r.*
            FROM shadow_trades st
            JOIN recommendations r ON st.recommendation_id = r.recommendation_id
            WHERE st.status = 'closed'
              AND st.recommendation_id NOT IN (
                  SELECT recommendation_id FROM training_examples
                  WHERE recommendation_id IS NOT NULL
              )
            ORDER BY st.actual_exit_time DESC
        """).fetchall()

    count = 0
    for row in rows:
        trade = dict(row)
        feature_input = _build_feature_input(trade)
        outcome_text = _build_outcome_text(trade)
        full_prompt = feature_input + "\n" + outcome_text

        response = generate_training_example(TRAINING_EXAMPLE_PROMPT, full_prompt)
        if response is None:
            logger.warning("[TRAINING] Failed to generate example for %s, skipping", trade.get("ticker"))
            continue

        pnl = trade.get("pnl_dollars", 0) or 0
        source = "outcome_win" if pnl > 0 else "outcome_loss"

        example_id = str(uuid.uuid4())
        created_at = datetime.now(ET).isoformat()

        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """INSERT INTO training_examples
                   (example_id, created_at, source, ticker, recommendation_id,
                    feature_snapshot, trade_outcome, instruction, input_text, output_text)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (example_id, created_at, source, trade.get("ticker"),
                 trade.get("recommendation_id"), feature_input, outcome_text,
                 TRAINING_EXAMPLE_PROMPT, full_prompt, response),
            )
            conn.commit()

        print(f"  [TRAINING] Generated example for {trade.get('ticker')} ({source})")
        count += 1

    return count
