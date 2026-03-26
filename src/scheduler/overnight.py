"""Overnight GPU-intensive training pipeline.

Runs as a single long-running process that executes tasks sequentially.
Called as a subprocess by VRAMManager for clean VRAM isolation.

Weeknight schedule (6:55 PM - 5:15 AM = 10.3 hours):
1. Walk-forward backtesting via holdout evaluation (2.5h)
2. DPO preference pair generation (1.5h)
3. Feature importance computation (1.5h)
4. Leakage detector with full probe (1h)
5. Rolling statistics computation (1h)
6. Database maintenance (VACUUM, index optimization) (0.5h)
7. Metric snapshots and health checks (0.5h)
8. Buffer/slack (1.8h)
"""

import json
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

STOP_FLAG_PATH = Path("data/STOP_OVERNIGHT")


class OvernightPipeline:
    """Orchestrates GPU-intensive overnight training tasks."""

    def __init__(self, db_path: str = "ai_research_desk.sqlite3"):
        self.db_path = db_path
        self._init_run_log_table()

    def _init_run_log_table(self):
        """Create overnight_run_log table if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS overnight_run_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_date TEXT NOT NULL,
                    task_name TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    result TEXT,
                    error TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_overnight_run_log_date
                ON overnight_run_log(run_date)
            """)
            conn.commit()

    def _should_stop(self) -> bool:
        """Check if the stop flag file exists (morning shutdown signal)."""
        return STOP_FLAG_PATH.exists()

    def _log_task(self, task_name: str, status: str,
                  started_at: str, finished_at: str | None = None,
                  result: str | None = None, error: str | None = None):
        """Write task result to overnight_run_log."""
        run_date = datetime.now(ET).strftime("%Y-%m-%d")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO overnight_run_log "
                "(run_date, task_name, started_at, finished_at, status, result, error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_date, task_name, started_at, finished_at, status, result, error),
            )
            conn.commit()

    def _run_task(self, name: str, func, timeout_seconds: int = 7200) -> dict:
        """Execute a single task with timeout, logging, and error handling.

        Returns {"status": "completed"|"failed"|"stopped"|"timeout", ...}
        """
        if self._should_stop():
            logger.info("[OVERNIGHT] Stop flag detected, skipping %s", name)
            return {"status": "stopped", "task": name}

        started_at = datetime.now(ET).isoformat()
        logger.info("[OVERNIGHT] Starting task: %s", name)
        print(f"[OVERNIGHT] Starting: {name}")

        try:
            import threading

            result_container = [None]
            error_container = [None]

            def target():
                try:
                    result_container[0] = func()
                except Exception as e:
                    error_container[0] = str(e)

            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            thread.join(timeout=timeout_seconds)

            finished_at = datetime.now(ET).isoformat()

            if thread.is_alive():
                logger.warning("[OVERNIGHT] Task %s timed out after %ds",
                               name, timeout_seconds)
                self._log_task(name, "timeout", started_at, finished_at)
                return {"status": "timeout", "task": name}

            if error_container[0]:
                logger.error("[OVERNIGHT] Task %s failed: %s",
                             name, error_container[0])
                self._log_task(name, "failed", started_at, finished_at,
                               error=error_container[0])
                return {"status": "failed", "task": name,
                        "error": error_container[0]}

            result_str = json.dumps(result_container[0]) if result_container[0] else None
            self._log_task(name, "completed", started_at, finished_at,
                           result=result_str)
            logger.info("[OVERNIGHT] Completed: %s", name)
            print(f"[OVERNIGHT] Completed: {name}")
            return {"status": "completed", "task": name,
                    "result": result_container[0]}

        except Exception as e:
            finished_at = datetime.now(ET).isoformat()
            logger.error("[OVERNIGHT] Unexpected error in %s: %s", name, e)
            self._log_task(name, "failed", started_at, finished_at, error=str(e))
            return {"status": "failed", "task": name, "error": str(e)}

    def _task_holdout_evaluation(self):
        """Walk-forward backtesting via holdout evaluation."""
        from src.training.trainer import evaluate_on_holdout
        return evaluate_on_holdout()

    def _task_dpo_generation(self):
        """Generate DPO preference pairs if we have enough examples."""
        from src.training.dpo_pipeline import generate_preference_pairs
        return generate_preference_pairs(n_pairs=100)

    def _task_feature_importance(self):
        """Compute feature importance rankings."""
        from src.evaluation.feature_importance import compute_feature_importance
        return compute_feature_importance(days=30)

    def _task_leakage_detection(self):
        """Run leakage detector to check for outcome contamination."""
        from src.training.leakage_detector import check_outcome_leakage
        return check_outcome_leakage(self.db_path)

    def _task_rolling_statistics(self):
        """Compute rolling performance statistics."""
        from src.journal.store import get_closed_shadow_trades
        trades = get_closed_shadow_trades(days=90)
        if not trades:
            return {"trades": 0}

        wins = sum(1 for t in trades if (t.get("pnl_dollars") or 0) > 0)
        total_pnl = sum(t.get("pnl_dollars", 0) or 0 for t in trades)
        return {
            "trades": len(trades),
            "wins": wins,
            "win_rate": round(wins / len(trades), 3) if trades else 0,
            "total_pnl": round(total_pnl, 2),
            "expectancy": round(total_pnl / len(trades), 2) if trades else 0,
        }

    def _task_database_maintenance(self):
        """VACUUM and optimize database indexes."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("VACUUM")
            conn.execute("ANALYZE")
        return {"status": "vacuumed_and_analyzed"}

    def _task_health_check(self):
        """Final health check and metric snapshot."""
        import os
        db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0

        with sqlite3.connect(self.db_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()

        return {
            "db_size_mb": round(db_size / 1024 / 1024, 2),
            "table_count": len(tables),
            "timestamp": datetime.now(ET).isoformat(),
        }

    def run(self) -> list[dict]:
        """Execute all overnight tasks sequentially.

        Returns list of task results.
        """
        tasks = [
            ("holdout_evaluation", self._task_holdout_evaluation, 9000),
            ("dpo_generation", self._task_dpo_generation, 5400),
            ("feature_importance", self._task_feature_importance, 5400),
            ("leakage_detection", self._task_leakage_detection, 3600),
            ("rolling_statistics", self._task_rolling_statistics, 3600),
            ("database_maintenance", self._task_database_maintenance, 1800),
            ("health_check", self._task_health_check, 1800),
        ]

        results = []
        print(f"[OVERNIGHT] Pipeline starting with {len(tasks)} tasks")

        for name, func, timeout in tasks:
            if self._should_stop():
                logger.info("[OVERNIGHT] Stop flag detected, ending pipeline")
                print("[OVERNIGHT] Stop flag detected — shutting down")
                break
            result = self._run_task(name, func, timeout_seconds=timeout)
            results.append(result)

        completed = sum(1 for r in results if r["status"] == "completed")
        failed = sum(1 for r in results if r["status"] == "failed")
        print(f"[OVERNIGHT] Pipeline complete: {completed} completed, "
              f"{failed} failed, {len(tasks) - len(results)} skipped")

        return results
