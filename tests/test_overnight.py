"""Tests for the overnight training pipeline."""

import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ── OvernightPipeline init ───────────────────────────────────────────


def test_overnight_pipeline_creates_log_table(tmp_path):
    from src.scheduler.overnight import OvernightPipeline
    db = str(tmp_path / "test.db")
    pipeline = OvernightPipeline(db_path=db)

    with sqlite3.connect(db) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    table_names = [t[0] for t in tables]
    assert "overnight_run_log" in table_names


# ── Stop flag detection ──────────────────────────────────────────────


def test_should_stop_no_flag(tmp_path):
    from src.scheduler.overnight import OvernightPipeline
    db = str(tmp_path / "test.db")
    pipeline = OvernightPipeline(db_path=db)

    with patch("src.scheduler.overnight.STOP_FLAG_PATH",
               tmp_path / "STOP_OVERNIGHT"):
        assert pipeline._should_stop() is False


def test_should_stop_with_flag(tmp_path):
    from src.scheduler.overnight import OvernightPipeline
    db = str(tmp_path / "test.db")
    pipeline = OvernightPipeline(db_path=db)

    flag = tmp_path / "STOP_OVERNIGHT"
    flag.touch()
    with patch("src.scheduler.overnight.STOP_FLAG_PATH", flag):
        assert pipeline._should_stop() is True


# ── Task execution ───────────────────────────────────────────────────


def test_run_task_success(tmp_path):
    from src.scheduler.overnight import OvernightPipeline
    db = str(tmp_path / "test.db")
    pipeline = OvernightPipeline(db_path=db)

    result = pipeline._run_task("test_task", lambda: {"ok": True}, timeout_seconds=10)
    assert result["status"] == "completed"
    assert result["result"] == {"ok": True}

    # Check logged to DB
    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT task_name, status FROM overnight_run_log WHERE task_name='test_task'"
        ).fetchone()
    assert row is not None
    assert row[1] == "completed"


def test_run_task_failure(tmp_path):
    from src.scheduler.overnight import OvernightPipeline
    db = str(tmp_path / "test.db")
    pipeline = OvernightPipeline(db_path=db)

    def failing_func():
        raise ValueError("something broke")

    result = pipeline._run_task("fail_task", failing_func, timeout_seconds=10)
    assert result["status"] == "failed"
    assert "something broke" in result["error"]

    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT status, error FROM overnight_run_log WHERE task_name='fail_task'"
        ).fetchone()
    assert row[0] == "failed"
    assert "something broke" in row[1]


def test_run_task_timeout(tmp_path):
    import time as time_mod
    from src.scheduler.overnight import OvernightPipeline
    db = str(tmp_path / "test.db")
    pipeline = OvernightPipeline(db_path=db)

    def slow_func():
        time_mod.sleep(10)

    result = pipeline._run_task("slow_task", slow_func, timeout_seconds=1)
    assert result["status"] == "timeout"


def test_run_task_skipped_by_stop_flag(tmp_path):
    from src.scheduler.overnight import OvernightPipeline
    db = str(tmp_path / "test.db")
    pipeline = OvernightPipeline(db_path=db)

    flag = tmp_path / "STOP_OVERNIGHT"
    flag.touch()
    with patch("src.scheduler.overnight.STOP_FLAG_PATH", flag):
        result = pipeline._run_task("skipped_task", lambda: None)
    assert result["status"] == "stopped"


# ── No cascade failures ─────────────────────────────────────────────


def test_failures_dont_cascade(tmp_path):
    from src.scheduler.overnight import OvernightPipeline
    db = str(tmp_path / "test.db")
    pipeline = OvernightPipeline(db_path=db)

    call_log = []

    def task_fail():
        call_log.append("fail")
        raise RuntimeError("kaboom")

    def task_ok():
        call_log.append("ok")
        return {"good": True}

    # Monkey-patch the task list for testing
    with patch.object(pipeline, '_task_holdout_evaluation', task_fail), \
         patch.object(pipeline, '_task_dpo_generation', task_ok), \
         patch.object(pipeline, '_task_feature_importance', task_ok), \
         patch.object(pipeline, '_task_leakage_detection', task_ok), \
         patch.object(pipeline, '_task_rolling_statistics', task_ok), \
         patch.object(pipeline, '_task_database_maintenance', task_ok), \
         patch.object(pipeline, '_task_health_check', task_ok):
        results = pipeline.run()

    assert len(results) == 7
    assert results[0]["status"] == "failed"
    # Remaining tasks should still complete
    completed = [r for r in results if r["status"] == "completed"]
    assert len(completed) == 6


# ── Pipeline stops on flag ───────────────────────────────────────────


def test_pipeline_stops_on_flag(tmp_path):
    from src.scheduler.overnight import OvernightPipeline
    db = str(tmp_path / "test.db")
    pipeline = OvernightPipeline(db_path=db)

    flag = tmp_path / "STOP_OVERNIGHT"

    call_count = 0

    def task_creates_flag():
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            flag.touch()
        return {"n": call_count}

    with patch("src.scheduler.overnight.STOP_FLAG_PATH", flag), \
         patch.object(pipeline, '_task_holdout_evaluation', task_creates_flag), \
         patch.object(pipeline, '_task_dpo_generation', task_creates_flag), \
         patch.object(pipeline, '_task_feature_importance', task_creates_flag), \
         patch.object(pipeline, '_task_leakage_detection', task_creates_flag), \
         patch.object(pipeline, '_task_rolling_statistics', task_creates_flag), \
         patch.object(pipeline, '_task_database_maintenance', task_creates_flag), \
         patch.object(pipeline, '_task_health_check', task_creates_flag):
        results = pipeline.run()

    # Should have stopped after the flag was created
    assert len(results) < 7


# ── Individual tasks ─────────────────────────────────────────────────


def test_database_maintenance_task(tmp_path):
    from src.scheduler.overnight import OvernightPipeline
    db = str(tmp_path / "test.db")
    pipeline = OvernightPipeline(db_path=db)

    result = pipeline._task_database_maintenance()
    assert result["status"] == "vacuumed_and_analyzed"


def test_health_check_task(tmp_path):
    from src.scheduler.overnight import OvernightPipeline
    db = str(tmp_path / "test.db")
    pipeline = OvernightPipeline(db_path=db)

    result = pipeline._task_health_check()
    assert "db_size_mb" in result
    assert "table_count" in result
    assert "timestamp" in result


def test_rolling_statistics_empty(tmp_path):
    from src.scheduler.overnight import OvernightPipeline
    db = str(tmp_path / "test.db")
    pipeline = OvernightPipeline(db_path=db)

    with patch("src.journal.store.get_closed_shadow_trades", return_value=[]):
        result = pipeline._task_rolling_statistics()
    assert result["trades"] == 0


def test_rolling_statistics_with_trades(tmp_path):
    from src.scheduler.overnight import OvernightPipeline
    db = str(tmp_path / "test.db")
    pipeline = OvernightPipeline(db_path=db)

    mock_trades = [
        {"pnl_dollars": 100, "pnl_pct": 2.5},
        {"pnl_dollars": -50, "pnl_pct": -1.2},
        {"pnl_dollars": 75, "pnl_pct": 1.8},
    ]
    with patch("src.journal.store.get_closed_shadow_trades",
               return_value=mock_trades):
        result = pipeline._task_rolling_statistics()

    assert result["trades"] == 3
    assert result["wins"] == 2
    assert result["win_rate"] == 0.667
    assert result["total_pnl"] == 125.0
