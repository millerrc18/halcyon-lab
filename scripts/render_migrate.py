"""Migrate Render Postgres schema to match local SQLite.

Usage:
    $env:DATABASE_URL = "your-external-database-url"
    python scripts/render_migrate.py
"""

import os
import sys

try:
    import psycopg2
except ImportError:
    print("Run: pip install psycopg2-binary")
    sys.exit(1)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("ERROR: Set DATABASE_URL environment variable first.")
    print("  PowerShell: $env:DATABASE_URL = \"your-external-url\"")
    sys.exit(1)

MIGRATIONS = [
    # shadow_trades — new columns from live trading + setup classifier
    ("shadow_trades", "source", "ALTER TABLE shadow_trades ADD COLUMN source TEXT"),
    ("shadow_trades", "setup_type", "ALTER TABLE shadow_trades ADD COLUMN setup_type TEXT"),
    ("shadow_trades", "setup_confidence", "ALTER TABLE shadow_trades ADD COLUMN setup_confidence REAL"),

    # recommendations — new columns added via ALTER TABLE in store.py
    ("recommendations", "enriched_prompt", "ALTER TABLE recommendations ADD COLUMN enriched_prompt TEXT"),
    ("recommendations", "setup_type", "ALTER TABLE recommendations ADD COLUMN setup_type TEXT"),
    ("recommendations", "setup_confidence", "ALTER TABLE recommendations ADD COLUMN setup_confidence REAL"),
    ("recommendations", "llm_conviction", "ALTER TABLE recommendations ADD COLUMN llm_conviction INTEGER"),
    ("recommendations", "llm_conviction_reason", "ALTER TABLE recommendations ADD COLUMN llm_conviction_reason TEXT"),
    ("recommendations", "model_version", "ALTER TABLE recommendations ADD COLUMN model_version TEXT"),

    # shadow_trades — new columns added via ALTER TABLE in store.py
    ("shadow_trades", "order_type", "ALTER TABLE shadow_trades ADD COLUMN order_type TEXT"),

    # New tables
    ("schedule_metrics", None, """CREATE TABLE IF NOT EXISTS schedule_metrics (
        id SERIAL PRIMARY KEY,
        metric_date TEXT,
        gpu_utilization REAL,
        scan_count INTEGER,
        scoring_count INTEGER,
        training_minutes REAL,
        created_at TEXT
    )"""),

    ("council_sessions", None, """CREATE TABLE IF NOT EXISTS council_sessions (
        session_id TEXT PRIMARY KEY,
        trigger TEXT,
        consensus TEXT,
        confidence REAL,
        summary TEXT,
        recommendation TEXT,
        rounds INTEGER,
        agent_count INTEGER,
        model TEXT,
        created_at TEXT
    )"""),

    ("council_votes", None, """CREATE TABLE IF NOT EXISTS council_votes (
        id SERIAL PRIMARY KEY,
        session_id TEXT,
        round INTEGER,
        agent_name TEXT,
        position TEXT,
        confidence REAL,
        recommendation TEXT,
        key_data_points TEXT,
        risk_flags TEXT,
        vote TEXT,
        is_devils_advocate INTEGER DEFAULT 0
    )"""),

    ("setup_signals", None, """CREATE TABLE IF NOT EXISTS setup_signals (
        id SERIAL PRIMARY KEY,
        ticker TEXT,
        scan_date TEXT,
        setup_type TEXT,
        confidence REAL,
        features_json TEXT,
        created_at TEXT
    )"""),

    ("canary_evaluations", None, """CREATE TABLE IF NOT EXISTS canary_evaluations (
        id SERIAL PRIMARY KEY,
        model_version TEXT,
        perplexity REAL,
        distinct_2 REAL,
        verdict TEXT,
        details TEXT,
        created_at TEXT
    )"""),

    ("quality_drift_metrics", None, """CREATE TABLE IF NOT EXISTS quality_drift_metrics (
        id SERIAL PRIMARY KEY,
        metric_date TEXT,
        avg_score REAL,
        score_std REAL,
        pass_rate REAL,
        template_fallback_rate REAL,
        created_at TEXT
    )"""),

    ("activity_log", None, """CREATE TABLE IF NOT EXISTS activity_log (
        id SERIAL PRIMARY KEY,
        event_type TEXT,
        detail TEXT,
        created_at TEXT
    )"""),

    ("sync_state", None, """CREATE TABLE IF NOT EXISTS sync_state (
        table_name TEXT PRIMARY KEY,
        last_synced_at TEXT
    )"""),

    # New data collection tables (Sprint: Free Data Collectors)
    ("edgar_filings", None, """CREATE TABLE IF NOT EXISTS edgar_filings (
        id SERIAL PRIMARY KEY,
        ticker TEXT NOT NULL,
        cik TEXT NOT NULL,
        form_type TEXT NOT NULL,
        filing_date TEXT NOT NULL,
        accession_number TEXT UNIQUE NOT NULL,
        filing_url TEXT,
        description TEXT,
        full_text TEXT,
        sections_json TEXT,
        word_count INTEGER,
        collected_at TEXT NOT NULL
    )"""),

    ("insider_transactions", None, """CREATE TABLE IF NOT EXISTS insider_transactions (
        id SERIAL PRIMARY KEY,
        ticker TEXT NOT NULL,
        insider_name TEXT,
        title TEXT,
        transaction_type TEXT,
        transaction_date TEXT,
        filing_date TEXT,
        shares REAL,
        price REAL,
        value REAL,
        shares_after REAL,
        source TEXT DEFAULT 'finnhub',
        collected_at TEXT NOT NULL
    )"""),

    ("short_interest", None, """CREATE TABLE IF NOT EXISTS short_interest (
        id SERIAL PRIMARY KEY,
        ticker TEXT NOT NULL,
        settlement_date TEXT NOT NULL,
        short_interest REAL,
        avg_daily_volume REAL,
        days_to_cover REAL,
        short_pct_float REAL,
        source TEXT DEFAULT 'finnhub',
        collected_at TEXT NOT NULL,
        UNIQUE(ticker, settlement_date)
    )"""),

    ("fed_communications", None, """CREATE TABLE IF NOT EXISTS fed_communications (
        id SERIAL PRIMARY KEY,
        comm_type TEXT NOT NULL,
        title TEXT,
        date TEXT NOT NULL,
        speaker TEXT,
        url TEXT,
        full_text TEXT,
        word_count INTEGER,
        collected_at TEXT NOT NULL,
        UNIQUE(comm_type, date, title)
    )"""),

    ("api_costs", None, """CREATE TABLE IF NOT EXISTS api_costs (
        id SERIAL PRIMARY KEY,
        model TEXT,
        purpose TEXT,
        input_tokens INTEGER,
        output_tokens INTEGER,
        estimated_cost REAL,
        created_at TEXT
    )"""),

    ("training_examples", None, """CREATE TABLE IF NOT EXISTS training_examples (
        id SERIAL PRIMARY KEY,
        example_id TEXT UNIQUE,
        ticker TEXT,
        trade_date TEXT,
        input_text TEXT,
        output_text TEXT,
        quality_score REAL,
        curriculum_stage TEXT,
        outcome TEXT,
        source TEXT,
        model_version TEXT,
        created_at TEXT
    )"""),

    ("analyst_estimates", None, """CREATE TABLE IF NOT EXISTS analyst_estimates (
        id SERIAL PRIMARY KEY,
        ticker TEXT NOT NULL,
        date TEXT NOT NULL,
        consensus_buy INTEGER,
        consensus_hold INTEGER,
        consensus_sell INTEGER,
        consensus_strong_buy INTEGER,
        consensus_strong_sell INTEGER,
        price_target_high REAL,
        price_target_low REAL,
        price_target_mean REAL,
        price_target_median REAL,
        num_analysts INTEGER,
        source TEXT DEFAULT 'finnhub',
        collected_at TEXT NOT NULL,
        UNIQUE(ticker, date, source)
    )"""),
]


def main():
    print(f"Connecting to Postgres...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    for table, column, sql in MIGRATIONS:
        try:
            cur.execute(sql)
            if column:
                print(f"  ✅ Added {table}.{column}")
            else:
                print(f"  ✅ Created/verified table: {table}")
        except psycopg2.errors.DuplicateColumn:
            conn.rollback()
            print(f"  ⏭️  {table}.{column} already exists")
        except psycopg2.errors.DuplicateTable:
            conn.rollback()
            print(f"  ⏭️  {table} already exists")
        except Exception as e:
            conn.rollback()
            print(f"  ❌ {table}: {e}")

    conn.close()
    print("\nDone! Render Postgres schema is up to date.")
    print("The sync thread will populate data on the next cycle (within 2 minutes).")


if __name__ == "__main__":
    main()
