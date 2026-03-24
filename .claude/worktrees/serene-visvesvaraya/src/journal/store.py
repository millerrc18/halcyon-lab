import sqlite3
from pathlib import Path


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
