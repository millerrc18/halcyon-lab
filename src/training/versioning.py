"""Model versioning and performance tracking for the training pipeline."""

import sqlite3
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

TRAINING_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_versions (
    version_id TEXT PRIMARY KEY,
    version_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    training_examples_count INTEGER,
    synthetic_examples_count INTEGER,
    outcome_examples_count INTEGER,
    model_file_path TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    notes TEXT
);

CREATE TABLE IF NOT EXISTS training_examples (
    example_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL,
    ticker TEXT,
    recommendation_id TEXT,
    feature_snapshot TEXT,
    trade_outcome TEXT,
    instruction TEXT NOT NULL,
    input_text TEXT NOT NULL,
    output_text TEXT NOT NULL,
    quality_score REAL
);

-- Training table indexes
CREATE INDEX IF NOT EXISTS idx_training_examples_source ON training_examples(source);
CREATE INDEX IF NOT EXISTS idx_training_examples_ticker ON training_examples(ticker);
CREATE INDEX IF NOT EXISTS idx_training_examples_created_at ON training_examples(created_at);
CREATE INDEX IF NOT EXISTS idx_training_examples_recommendation_id ON training_examples(recommendation_id);
CREATE INDEX IF NOT EXISTS idx_model_versions_status ON model_versions(status);
"""


def init_training_tables(db_path: str = "ai_research_desk.sqlite3") -> None:
    """Create training tables if they don't exist."""
    with sqlite3.connect(db_path) as conn:
        conn.executescript(TRAINING_SCHEMA)
        conn.commit()

        # Migration: add holdout_score to model_versions
        try:
            conn.execute("ALTER TABLE model_versions ADD COLUMN holdout_score REAL")
            conn.commit()
        except sqlite3.OperationalError:
            pass

        # Migration: add holdout_details (JSON blob) to model_versions
        try:
            conn.execute("ALTER TABLE model_versions ADD COLUMN holdout_details TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass

        # Migration: add curriculum columns to training_examples
        for col, col_type in [("difficulty", "TEXT"), ("curriculum_stage", "TEXT"),
                               ("quality_score_auto", "REAL")]:
            try:
                conn.execute(f"ALTER TABLE training_examples ADD COLUMN {col} {col_type}")
                conn.commit()
            except sqlite3.OperationalError:
                pass

        # Model evaluations table for A/B testing
        conn.execute("""
            CREATE TABLE IF NOT EXISTS model_evaluations (
                evaluation_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                recommendation_id TEXT,
                ticker TEXT,
                input_text TEXT NOT NULL,
                current_model TEXT NOT NULL,
                current_output TEXT,
                current_score REAL,
                new_model TEXT NOT NULL,
                new_output TEXT,
                new_score REAL,
                winner TEXT,
                score_delta REAL
            )
        """)
        conn.commit()

        # Audit reports table
        conn.execute("""
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
            )
        """)
        conn.commit()


def get_active_model_version(db_path: str = "ai_research_desk.sqlite3") -> dict | None:
    """Return the currently active model version, or None if using base."""
    init_training_tables(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM model_versions WHERE status = 'active' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def register_model_version(
    version_name: str,
    examples_count: int,
    synthetic_count: int,
    outcome_count: int,
    model_file_path: str,
    db_path: str = "ai_research_desk.sqlite3",
    holdout_score: float | None = None,
    holdout_details: str | None = None,
    status: str = "active",
) -> str:
    """Retire current active version and register new one. Returns version_id."""
    init_training_tables(db_path)
    version_id = str(uuid.uuid4())
    created_at = datetime.now(ET).isoformat()

    with sqlite3.connect(db_path) as conn:
        if status == "active":
            # Retire current active version
            conn.execute(
                "UPDATE model_versions SET status = 'retired' WHERE status = 'active'"
            )
        # Insert new version
        conn.execute(
            """INSERT INTO model_versions
               (version_id, version_name, created_at, training_examples_count,
                synthetic_examples_count, outcome_examples_count,
                model_file_path, status, holdout_score, holdout_details)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (version_id, version_name, created_at, examples_count,
             synthetic_count, outcome_count, model_file_path, status,
             holdout_score, holdout_details),
        )
        conn.commit()
    return version_id


def get_evaluation_model(db_path: str = "ai_research_desk.sqlite3") -> dict | None:
    """Return a model in 'evaluation' status, or None."""
    init_training_tables(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM model_versions WHERE status = 'evaluation' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def promote_evaluation_model(db_path: str = "ai_research_desk.sqlite3") -> dict | None:
    """Promote the evaluation model to active status."""
    init_training_tables(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        eval_model = conn.execute(
            "SELECT * FROM model_versions WHERE status = 'evaluation' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if not eval_model:
            return None
        conn.execute("UPDATE model_versions SET status = 'retired' WHERE status = 'active'")
        conn.execute("UPDATE model_versions SET status = 'active' WHERE version_id = ?",
                     (eval_model["version_id"],))
        conn.commit()
    return dict(eval_model)


def reject_evaluation_model(db_path: str = "ai_research_desk.sqlite3") -> dict | None:
    """Reject the evaluation model (set to rejected status)."""
    init_training_tables(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        eval_model = conn.execute(
            "SELECT * FROM model_versions WHERE status = 'evaluation' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if not eval_model:
            return None
        conn.execute("UPDATE model_versions SET status = 'rejected' WHERE version_id = ?",
                     (eval_model["version_id"],))
        conn.commit()
    return dict(eval_model)


def rollback_model(db_path: str = "ai_research_desk.sqlite3") -> dict | None:
    """Roll back active model to previous retired version. Returns restored version or None."""
    init_training_tables(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row

        # Set active to rolled_back
        conn.execute(
            "UPDATE model_versions SET status = 'rolled_back' WHERE status = 'active'"
        )

        # Find most recent retired version
        row = conn.execute(
            "SELECT * FROM model_versions WHERE status = 'retired' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()

        if row:
            conn.execute(
                "UPDATE model_versions SET status = 'active' WHERE version_id = ?",
                (row["version_id"],),
            )
            conn.commit()
            return dict(row)

        conn.commit()
    return None


def get_model_history(db_path: str = "ai_research_desk.sqlite3") -> list[dict]:
    """Return all model versions ordered by created_at descending."""
    init_training_tables(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM model_versions ORDER BY created_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_active_model_name(db_path: str = "ai_research_desk.sqlite3") -> str:
    """Return active model version name, or 'base' if none exists."""
    version = get_active_model_version(db_path)
    return version["version_name"] if version else "base"


def get_performance_by_version(db_path: str = "ai_research_desk.sqlite3") -> list[dict]:
    """Query closed shadow trades grouped by model_version on their recommendation."""
    from src.journal.store import initialize_database
    initialize_database(db_path)
    init_training_tables(db_path)

    # Ensure model_version column exists
    _migrate_model_version_column(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT
                COALESCE(r.model_version, 'base') as version_name,
                COUNT(*) as trade_count,
                SUM(CASE WHEN st.pnl_dollars > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN st.pnl_dollars <= 0 THEN 1 ELSE 0 END) as losses,
                AVG(CASE WHEN st.pnl_dollars > 0 THEN st.pnl_dollars END) as avg_gain,
                AVG(CASE WHEN st.pnl_dollars <= 0 THEN st.pnl_dollars END) as avg_loss,
                AVG(st.pnl_dollars) as expectancy,
                SUM(st.pnl_dollars) as total_pnl
            FROM shadow_trades st
            JOIN recommendations r ON st.recommendation_id = r.recommendation_id
            WHERE st.status = 'closed'
            GROUP BY COALESCE(r.model_version, 'base')
            ORDER BY MIN(r.created_at) DESC
        """).fetchall()

    results = []
    for row in rows:
        d = dict(row)
        d["win_rate"] = (d["wins"] / d["trade_count"] * 100) if d["trade_count"] > 0 else 0
        results.append(d)
    return results


def get_training_example_counts(db_path: str = "ai_research_desk.sqlite3") -> dict:
    """Return counts of training examples by source."""
    init_training_tables(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT source, COUNT(*) as count FROM training_examples GROUP BY source"
        ).fetchall()

    counts = {"total": 0, "historical_backfill": 0, "synthetic_claude": 0, "outcome_win": 0, "outcome_loss": 0}
    for row in rows:
        counts[row["source"]] = row["count"]
        counts["total"] += row["count"]
    return counts


def get_new_examples_since(since_date: str, db_path: str = "ai_research_desk.sqlite3") -> int:
    """Count training examples created after the given date."""
    init_training_tables(db_path)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM training_examples WHERE created_at > ?",
            (since_date,),
        ).fetchone()
    return row[0] if row else 0


def _migrate_model_version_column(db_path: str = "ai_research_desk.sqlite3") -> None:
    """Add model_version column to recommendations table if it doesn't exist."""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("ALTER TABLE recommendations ADD COLUMN model_version TEXT")
            conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
