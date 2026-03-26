"""Initialize Render Postgres tables matching the local SQLite schema.

Usage:
    DATABASE_URL=postgresql://... python scripts/render_init_db.py

Creates all tables that the sync thread pushes to. Uses IF NOT EXISTS
so it's safe to run multiple times.
"""

import os
import sys

# ── Postgres DDL ─────────────────────────────────────────────────────
# Mirrors the SQLite schema but adapted for Postgres types:
#   - TEXT PRIMARY KEY instead of INTEGER PRIMARY KEY AUTOINCREMENT
#   - SERIAL for auto-increment integer PKs
#   - BOOLEAN instead of INTEGER for flag columns
#   - No ON CONFLICT in DDL (handled at query time)

POSTGRES_SCHEMA = """
-- ── Core tables ─────────────────────────────────────────────────────

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
    repeatable_setup INTEGER,
    model_version TEXT
);

CREATE INDEX IF NOT EXISTS idx_recommendations_ticker ON recommendations(ticker);
CREATE INDEX IF NOT EXISTS idx_recommendations_created_at ON recommendations(created_at);


CREATE TABLE IF NOT EXISTS shadow_trades (
    trade_id TEXT PRIMARY KEY,
    recommendation_id TEXT,
    ticker TEXT NOT NULL,
    direction TEXT DEFAULT 'long',
    status TEXT DEFAULT 'pending',
    entry_price REAL,
    stop_price REAL,
    target_1 REAL,
    target_2 REAL,
    planned_shares INTEGER,
    planned_allocation REAL,
    actual_entry_price REAL,
    actual_entry_time TEXT,
    actual_exit_price REAL,
    actual_exit_time TEXT,
    exit_reason TEXT,
    pnl_dollars REAL,
    pnl_pct REAL,
    max_favorable_excursion REAL,
    max_adverse_excursion REAL,
    duration_days INTEGER,
    earnings_adjacent INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    alpaca_order_id TEXT,
    order_type TEXT,
    timeout_days INTEGER DEFAULT 15
);

CREATE INDEX IF NOT EXISTS idx_shadow_trades_status ON shadow_trades(status);
CREATE INDEX IF NOT EXISTS idx_shadow_trades_ticker ON shadow_trades(ticker);
CREATE INDEX IF NOT EXISTS idx_shadow_trades_recommendation_id ON shadow_trades(recommendation_id);
CREATE INDEX IF NOT EXISTS idx_shadow_trades_created_at ON shadow_trades(created_at);
CREATE INDEX IF NOT EXISTS idx_shadow_trades_status_exit ON shadow_trades(status, actual_exit_time);


-- ── Training tables ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS model_versions (
    version_id TEXT PRIMARY KEY,
    version_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    training_examples_count INTEGER,
    synthetic_examples_count INTEGER,
    outcome_examples_count INTEGER,
    model_file_path TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    notes TEXT,
    holdout_score REAL,
    holdout_details TEXT
);

CREATE INDEX IF NOT EXISTS idx_model_versions_status ON model_versions(status);


CREATE TABLE IF NOT EXISTS metric_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    metrics_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_metric_snapshots_date ON metric_snapshots(snapshot_date);


CREATE TABLE IF NOT EXISTS audit_reports (
    audit_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    audit_date TEXT NOT NULL,
    overall_assessment TEXT NOT NULL,
    summary TEXT,
    flags TEXT,
    metrics_to_watch TEXT,
    model_health TEXT,
    full_report TEXT
);


-- ── Schedule metrics ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS schedule_metrics (
    id SERIAL PRIMARY KEY,
    metric_date TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL,
    details TEXT
);

CREATE INDEX IF NOT EXISTS idx_schedule_metrics_date ON schedule_metrics(metric_date, metric_name);


-- ── Earnings calendar ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS earnings_calendar (
    id SERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    earnings_date TEXT NOT NULL,
    earnings_time TEXT,
    confirmed INTEGER DEFAULT 0,
    collected_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_earnings_ticker ON earnings_calendar(ticker);
CREATE INDEX IF NOT EXISTS idx_earnings_date ON earnings_calendar(earnings_date);
CREATE UNIQUE INDEX IF NOT EXISTS idx_earnings_ticker_date ON earnings_calendar(ticker, earnings_date);


-- ── Data collection snapshot tables (latest only) ───────────────────

CREATE TABLE IF NOT EXISTS options_metrics (
    id SERIAL PRIMARY KEY,
    collected_at TEXT NOT NULL,
    collected_date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    iv_rank REAL,
    iv_percentile REAL,
    put_call_volume_ratio REAL,
    put_call_oi_ratio REAL,
    atm_iv_30d REAL,
    iv_skew REAL,
    unusual_volume_flag INTEGER,
    max_unusual_volume_ratio REAL,
    total_call_volume INTEGER,
    total_put_volume INTEGER,
    total_call_oi INTEGER,
    total_put_oi INTEGER
);

CREATE INDEX IF NOT EXISTS idx_options_metrics_ticker_date ON options_metrics(ticker, collected_date);
CREATE INDEX IF NOT EXISTS idx_options_metrics_date ON options_metrics(collected_date);


CREATE TABLE IF NOT EXISTS vix_term_structure (
    id SERIAL PRIMARY KEY,
    collected_at TEXT NOT NULL,
    collected_date TEXT NOT NULL,
    vix REAL,
    vix9d REAL,
    vix3m REAL,
    vix1y REAL,
    term_structure_slope REAL,
    near_term_ratio REAL
);

CREATE INDEX IF NOT EXISTS idx_vix_ts_date ON vix_term_structure(collected_date);


CREATE TABLE IF NOT EXISTS macro_snapshots (
    id SERIAL PRIMARY KEY,
    collected_at TEXT NOT NULL,
    collected_date TEXT NOT NULL,
    series_id TEXT NOT NULL,
    series_name TEXT NOT NULL,
    value REAL,
    previous_value REAL,
    change_pct REAL
);

CREATE INDEX IF NOT EXISTS idx_macro_snapshots_date ON macro_snapshots(collected_date);
CREATE INDEX IF NOT EXISTS idx_macro_snapshots_series ON macro_snapshots(series_id, collected_date);


-- ── Council tables ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS council_sessions (
    session_id TEXT PRIMARY KEY,
    session_type TEXT NOT NULL,
    trigger_reason TEXT,
    created_at TEXT NOT NULL,
    consensus TEXT,
    confidence_weighted_score REAL,
    is_contested INTEGER DEFAULT 0,
    total_cost REAL,
    rounds_completed INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_council_sessions_created ON council_sessions(created_at);


CREATE TABLE IF NOT EXISTS council_votes (
    vote_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    round INTEGER NOT NULL,
    position TEXT,
    confidence INTEGER,
    recommendation TEXT,
    key_data_points TEXT,
    risk_flags TEXT,
    vote TEXT,
    is_devils_advocate INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES council_sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_council_votes_session ON council_votes(session_id);


-- ── Sync state (for tracking what has been synced) ──────────────────

CREATE TABLE IF NOT EXISTS sync_state (
    table_name TEXT PRIMARY KEY,
    last_synced_at TEXT NOT NULL
);
"""


def init_postgres(database_url: str) -> None:
    """Connect to Postgres and create all tables."""
    import psycopg2

    print(f"Connecting to Postgres...")
    conn = psycopg2.connect(database_url)
    try:
        cursor = conn.cursor()
        cursor.execute(POSTGRES_SCHEMA)
        conn.commit()
        cursor.close()
        print("All tables created successfully.")
    except Exception as exc:
        conn.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


def main():
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("ERROR: Set DATABASE_URL environment variable.", file=sys.stderr)
        print("  Example: DATABASE_URL=postgresql://user:pass@host:5432/halcyon", file=sys.stderr)
        sys.exit(1)

    init_postgres(database_url)


if __name__ == "__main__":
    main()
