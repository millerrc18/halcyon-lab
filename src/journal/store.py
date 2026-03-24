import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.models import TradePacket


SCHEMA = """
CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    ticker TEXT NOT NULL,
    company_name TEXT,
    mode TEXT,
    setup_type TEXT,
    priority_score REAL,
    confidence_score REAL,
    packet_type TEXT,
    price_at_recommendation REAL,
    market_regime TEXT,
    sector_context TEXT,
    trend_state TEXT,
    relative_strength_state TEXT,
    pullback_depth_pct REAL,
    atr REAL,
    volume_state TEXT,
    recommendation TEXT,
    thesis_text TEXT,
    entry_zone TEXT,
    stop_level TEXT,
    target_1 TEXT,
    target_2 TEXT,
    expected_hold_period TEXT,
    position_size_dollars REAL,
    position_size_pct REAL,
    estimated_dollar_risk REAL,
    reasons_to_trade TEXT,
    reasons_to_pass TEXT,
    earnings_date TEXT,
    event_risk_flag TEXT,
    hold_window_overlaps_earnings INTEGER,
    event_risk_warning_text TEXT,
    conservative_sizing_applied INTEGER,
    packet_sent INTEGER,
    packet_sent_at TEXT,
    ryan_approved INTEGER,
    ryan_executed INTEGER,
    ryan_notes TEXT,
    shadow_entry_price REAL,
    shadow_entry_time TEXT,
    shadow_exit_price REAL,
    shadow_exit_time TEXT,
    shadow_pnl_dollars REAL,
    shadow_pnl_pct REAL,
    max_favorable_excursion REAL,
    max_adverse_excursion REAL,
    shadow_duration_days REAL,
    thesis_success INTEGER,
    assistant_postmortem TEXT,
    lesson_tag TEXT,
    user_grade TEXT,
    repeatable_setup INTEGER
);
"""


def initialize_database(db_path: str = "ai_research_desk.sqlite3") -> None:
    path = Path(db_path)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def log_recommendation(
    packet: TradePacket,
    features: dict,
    score: float,
    qualification: str,
    db_path: str = "ai_research_desk.sqlite3",
) -> str:
    """Write a recommendation row to the journal and return the recommendation_id."""
    initialize_database(db_path)

    rec_id = str(uuid.uuid4())
    et = ZoneInfo("America/New_York")
    created_at = datetime.now(et).isoformat()

    # Parse targets into target_1 and target_2
    targets_parts = packet.targets.split("/")
    target_1 = targets_parts[0].strip() if len(targets_parts) >= 1 else None
    target_2 = targets_parts[1].strip() if len(targets_parts) >= 2 else None

    # Volume state description
    vol_ratio = features.get("volume_ratio_20d", None)
    if vol_ratio is not None:
        if vol_ratio < 0.8:
            volume_state = "contracting"
        elif vol_ratio > 1.2:
            volume_state = "expanding"
        else:
            volume_state = "normal"
    else:
        volume_state = None

    row = {
        "recommendation_id": rec_id,
        "created_at": created_at,
        "ticker": packet.ticker,
        "company_name": packet.company_name,
        "mode": "short_swing",
        "setup_type": packet.setup_type,
        "priority_score": score,
        "confidence_score": float(packet.confidence),
        "packet_type": "action_packet",
        "price_at_recommendation": features.get("current_price"),
        "trend_state": features.get("trend_state"),
        "relative_strength_state": features.get("relative_strength_state"),
        "pullback_depth_pct": features.get("pullback_depth_pct"),
        "atr": features.get("atr_14"),
        "volume_state": volume_state,
        "recommendation": packet.recommendation,
        "thesis_text": packet.deeper_analysis,
        "entry_zone": packet.entry_zone,
        "stop_level": packet.stop_invalidation,
        "target_1": target_1,
        "target_2": target_2,
        "expected_hold_period": packet.expected_hold_period,
        "position_size_dollars": packet.position_sizing.allocation_dollars,
        "position_size_pct": packet.position_sizing.allocation_pct,
        "estimated_dollar_risk": packet.position_sizing.estimated_risk_dollars,
        "event_risk_flag": "none",
        "packet_sent": 0,
    }

    columns = ", ".join(row.keys())
    placeholders = ", ".join("?" for _ in row)
    values = list(row.values())

    with sqlite3.connect(db_path) as conn:
        conn.execute(f"INSERT INTO recommendations ({columns}) VALUES ({placeholders})", values)
        conn.commit()

    return rec_id
