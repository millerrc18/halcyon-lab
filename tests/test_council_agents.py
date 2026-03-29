"""Tests for council agent data gathering functions.

Verifies each agent can gather data without crashing on:
- Empty database (no data yet)
- Database with realistic data
- Missing tables handled gracefully
"""

import sqlite3
from datetime import datetime, timedelta

import pytest

from src.council.agents import (
    gather_risk_officer_data,
    gather_alpha_strategist_data,
    gather_data_scientist_data,
    gather_regime_analyst_data,
    gather_devils_advocate_data,
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temp DB with all required tables."""
    path = str(tmp_path / "test.sqlite3")
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS shadow_trades (
                trade_id TEXT PRIMARY KEY, ticker TEXT, direction TEXT,
                entry_price REAL, stop_price REAL, target_1 REAL, target_2 REAL,
                planned_shares INTEGER, status TEXT, source TEXT,
                actual_exit_price REAL, actual_exit_time TEXT,
                pnl_dollars REAL, pnl_pct REAL, exit_reason TEXT,
                max_adverse_excursion REAL, max_favorable_excursion REAL,
                created_at TEXT, updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS vix_term_structure (
                id INTEGER PRIMARY KEY, collected_at TEXT, collected_date TEXT,
                vix REAL, vix9d REAL, vix3m REAL, vix1y REAL,
                term_structure_slope REAL, near_term_ratio REAL
            );
            CREATE TABLE IF NOT EXISTS macro_snapshots (
                id INTEGER PRIMARY KEY, collected_at TEXT, collected_date TEXT,
                series_id TEXT, series_name TEXT, value REAL,
                previous_value REAL, change_pct REAL
            );
            CREATE TABLE IF NOT EXISTS recommendations (
                recommendation_id TEXT PRIMARY KEY, ticker TEXT, company_name TEXT,
                priority_score REAL, confidence_score REAL, setup_type TEXT,
                trend_state TEXT, relative_strength_state TEXT,
                pullback_depth_pct REAL, market_regime TEXT,
                entry_zone TEXT, stop_level TEXT, target_1 TEXT, target_2 TEXT,
                sector_context TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS training_examples (
                example_id TEXT PRIMARY KEY, created_at TEXT, source TEXT,
                quality_score_auto REAL, difficulty TEXT
            );
            CREATE TABLE IF NOT EXISTS model_versions (
                version_id TEXT PRIMARY KEY, version_name TEXT, status TEXT,
                created_at TEXT, training_examples_count INTEGER,
                synthetic_examples_count INTEGER, outcome_examples_count INTEGER,
                model_file_path TEXT
            );
            CREATE TABLE IF NOT EXISTS council_sessions (
                session_id TEXT PRIMARY KEY, session_type TEXT,
                consensus TEXT, confidence_weighted_score REAL,
                is_contested INTEGER, created_at TEXT
            );
        """)
    return path


@pytest.fixture
def populated_db(db_path):
    """DB with some realistic data."""
    # Use relative timestamps so tests don't break as time passes
    now = datetime.utcnow()
    recent = now.strftime("%Y-%m-%dT%H:%M:%S")
    two_days_ago = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
    today = now.strftime("%Y-%m-%d")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO shadow_trades (trade_id, ticker, direction, entry_price, stop_price, "
            "target_1, planned_shares, status, created_at) "
            "VALUES ('t1', 'AAPL', 'long', 250.0, 240.0, 270.0, 10, 'open', ?)",
            (recent,),
        )
        conn.execute(
            "INSERT INTO shadow_trades (trade_id, ticker, direction, entry_price, actual_exit_price, "
            "pnl_dollars, pnl_pct, exit_reason, status, created_at, actual_exit_time) "
            "VALUES ('t2', 'MSFT', 'long', 400.0, 420.0, 200.0, 5.0, 'target_hit', 'closed', "
            "?, ?)",
            (two_days_ago, yesterday),
        )
        conn.execute(
            "INSERT INTO vix_term_structure (collected_date, vix, vix9d, vix3m, vix1y, "
            "term_structure_slope, near_term_ratio) "
            "VALUES (?, 22.5, 24.0, 21.0, 20.0, -0.05, 1.08)",
            (today,),
        )
        conn.execute(
            "INSERT INTO macro_snapshots (collected_date, series_id, series_name, value) "
            "VALUES (?, 'BAMLH0A0HYM2', 'HY Spread', 3.45)",
            (today,),
        )
        conn.execute(
            "INSERT INTO macro_snapshots (collected_date, series_id, series_name, value) "
            "VALUES (?, 'NFCI', 'Financial Conditions', -0.35)",
            (today,),
        )
        conn.execute(
            "INSERT INTO recommendations (recommendation_id, ticker, priority_score, "
            "confidence_score, market_regime, sector_context, created_at) "
            "VALUES ('r1', 'CAT', 85, 7, 'TRANSITION', 'Industrials', ?)",
            (recent,),
        )
        conn.execute(
            "INSERT INTO training_examples (example_id, created_at, source, quality_score_auto, difficulty) "
            "VALUES ('ex1', ?, 'blinded_win', 4.2, 'medium')",
            (recent,),
        )
        conn.execute(
            "INSERT INTO model_versions (version_id, version_name, status, created_at, training_examples_count) "
            "VALUES ('v1', 'halcyon-v1.0.0', 'active', ?, 969)",
            (recent,),
        )
    return db_path


# ── Empty DB tests (no crashes) ──

def test_risk_officer_empty_db(db_path):
    result = gather_risk_officer_data(db_path)
    assert isinstance(result, dict)
    assert result.get("open_trade_count", 0) == 0


def test_alpha_strategist_empty_db(db_path):
    result = gather_alpha_strategist_data(db_path)
    assert isinstance(result, dict)


def test_data_scientist_empty_db(db_path):
    result = gather_data_scientist_data(db_path)
    assert isinstance(result, dict)


def test_regime_analyst_empty_db(db_path):
    result = gather_regime_analyst_data(db_path)
    assert isinstance(result, dict)


def test_devils_advocate_empty_db(db_path):
    result = gather_devils_advocate_data([], db_path)
    assert isinstance(result, dict)
    assert result["round1_assessments"] == []


# ── Populated DB tests (returns real data) ──

def test_risk_officer_with_data(populated_db):
    result = gather_risk_officer_data(populated_db)
    assert result["open_trade_count"] == 1
    assert len(result["open_trades"]) == 1
    assert result["open_trades"][0]["ticker"] == "AAPL"
    assert len(result["vix_data"]) == 1
    assert result["vix_data"][0]["vix_close"] == 22.5
    assert len(result["credit_spreads"]) == 1


def test_alpha_strategist_with_data(populated_db):
    result = gather_alpha_strategist_data(populated_db)
    assert len(result["top_candidates"]) == 1
    assert result["top_candidates"][0]["ticker"] == "CAT"
    assert result["current_regime"] == "TRANSITION"
    assert len(result["recent_performance"]) == 1
    assert "hold_days" in result["recent_performance"][0]


def test_data_scientist_with_data(populated_db):
    result = gather_data_scientist_data(populated_db)
    assert len(result["quality_samples"]) == 1
    assert result["quality_samples"][0]["quality_score"] == 4.2
    assert len(result["model_versions"]) == 1
    assert result["model_versions"][0]["version_name"] == "halcyon-v1.0.0"


def test_regime_analyst_with_data(populated_db):
    result = gather_regime_analyst_data(populated_db)
    assert len(result["macro_data"]) >= 1
    assert len(result["vix_term_structure"]) == 1
    assert result["vix_term_structure"][0]["vix_close"] == 22.5
    assert len(result["sector_breakdown"]) == 1
    assert len(result["financial_conditions"]) >= 1


def test_devils_advocate_with_round1(populated_db):
    mock_round1 = [
        {"agent": "risk_officer", "position": "defensive", "vote": "reduce_exposure"},
        {"agent": "alpha_strategist", "position": "offensive", "vote": "selective_buying"},
    ]
    result = gather_devils_advocate_data(mock_round1, populated_db)
    assert len(result["round1_assessments"]) == 2
    assert result["round1_assessments"][0]["agent"] == "risk_officer"
