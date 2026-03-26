"""Stripped-down read-only FastAPI for Render cloud deployment.

Reads exclusively from Postgres (no SQLite, no Ollama dependency).
Auth: optional bearer token via API_SECRET env var.
"""

import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

# ── App setup ────────────────────────────────────────────────────────

app = FastAPI(
    title="Halcyon Lab Cloud API",
    version="1.0.0",
    description="Read-only cloud API for the Halcyon Lab trading system",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# ── Auth ─────────────────────────────────────────────────────────────

API_SECRET = os.environ.get("API_SECRET", "")
security = HTTPBearer(auto_error=False)


def verify_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> None:
    """Verify bearer token if API_SECRET is set. No-op if unset."""
    if not API_SECRET:
        return  # Auth disabled
    if not credentials or credentials.credentials != API_SECRET:
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


# ── Database connection ──────────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL", "")


@contextmanager
def get_pg():
    """Yield a Postgres connection. Caller must NOT commit (read-only)."""
    import psycopg2
    import psycopg2.extras

    if not DATABASE_URL:
        raise HTTPException(status_code=503, detail="DATABASE_URL not configured")

    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.set_session(readonly=True, autocommit=True)
        yield conn
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Postgres connection error: %s", exc)
        raise HTTPException(status_code=503, detail="Database unavailable")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _query(sql: str, params: tuple = ()) -> list[dict]:
    """Execute a read query and return list of dicts."""
    import psycopg2.extras

    with get_pg() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]


def _query_one(sql: str, params: tuple = ()) -> dict | None:
    """Execute a read query and return one dict or None."""
    rows = _query(sql, params)
    return rows[0] if rows else None


def _parse_json_fields(row: dict, fields: list[str]) -> dict:
    """Attempt to parse JSON string fields into dicts/lists."""
    for field in fields:
        val = row.get(field)
        if val and isinstance(val, str):
            try:
                row[field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    return row


# ── Endpoints ────────────────────────────────────────────────────────


@app.get("/api/status", dependencies=[Depends(verify_auth)])
def status():
    """System status overview from cloud data."""
    try:
        open_trades = _query(
            "SELECT COUNT(*) as count FROM shadow_trades WHERE status = 'open'"
        )
        closed_trades = _query(
            "SELECT COUNT(*) as count FROM shadow_trades WHERE status = 'closed'"
        )
        latest_model = _query_one(
            "SELECT version_name, created_at, status FROM model_versions "
            "ORDER BY created_at DESC LIMIT 1"
        )
        latest_audit = _query_one(
            "SELECT overall_assessment, created_at FROM audit_reports "
            "ORDER BY created_at DESC LIMIT 1"
        )

        return {
            "environment": "cloud",
            "open_positions": open_trades[0]["count"] if open_trades else 0,
            "closed_trades": closed_trades[0]["count"] if closed_trades else 0,
            "latest_model": latest_model,
            "latest_audit": latest_audit,
            "llm_available": False,
            "timestamp": datetime.now(ET).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Status endpoint error: %s", exc)
        return {
            "environment": "cloud",
            "error": str(exc),
            "timestamp": datetime.now(ET).isoformat(),
        }


@app.get("/api/shadow/open", dependencies=[Depends(verify_auth)])
def shadow_open():
    """Open shadow trades."""
    try:
        rows = _query(
            "SELECT * FROM shadow_trades WHERE status = 'open' ORDER BY created_at DESC"
        )
        return {"trades": rows, "count": len(rows)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Shadow open error: %s", exc)
        return {"trades": [], "count": 0, "error": str(exc)}


@app.get("/api/shadow/closed", dependencies=[Depends(verify_auth)])
def shadow_closed(days: int = 30):
    """Closed shadow trades for the last N days."""
    try:
        cutoff = (datetime.now(ET) - timedelta(days=days)).isoformat()
        rows = _query(
            "SELECT * FROM shadow_trades WHERE status = 'closed' "
            "AND actual_exit_time >= %s ORDER BY actual_exit_time DESC",
            (cutoff,),
        )
        return {"trades": rows, "count": len(rows), "days": days}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Shadow closed error: %s", exc)
        return {"trades": [], "count": 0, "error": str(exc)}


@app.get("/api/shadow/metrics", dependencies=[Depends(verify_auth)])
def shadow_metrics(days: int = 30):
    """Computed metrics from closed trades."""
    try:
        cutoff = (datetime.now(ET) - timedelta(days=days)).isoformat()
        rows = _query(
            "SELECT pnl_dollars, pnl_pct FROM shadow_trades "
            "WHERE status = 'closed' AND actual_exit_time >= %s",
            (cutoff,),
        )
        if not rows:
            return {"total_trades": 0}

        pnls = [r["pnl_dollars"] or 0 for r in rows]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        total_pnl = sum(pnls)

        return {
            "total_trades": len(rows),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(rows), 3) if rows else 0,
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(sum(wins) / len(wins), 2) if wins else 0,
            "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0,
            "expectancy": round(total_pnl / len(rows), 2) if rows else 0,
            "days": days,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Shadow metrics error: %s", exc)
        return {"total_trades": 0, "error": str(exc)}


@app.get("/api/packets", dependencies=[Depends(verify_auth)])
def packets(days: int = 7):
    """Recent recommendations / trade packets."""
    try:
        cutoff = (datetime.now(ET) - timedelta(days=days)).isoformat()
        rows = _query(
            "SELECT * FROM recommendations WHERE created_at >= %s "
            "ORDER BY created_at DESC",
            (cutoff,),
        )
        return rows
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Packets error: %s", exc)
        return []


@app.get("/api/training/status", dependencies=[Depends(verify_auth)])
def training_status():
    """Training pipeline status from cloud data."""
    try:
        active_model = _query_one(
            "SELECT * FROM model_versions WHERE status = 'active' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        total_versions = _query(
            "SELECT COUNT(*) as count FROM model_versions"
        )
        return {
            "active_model": active_model,
            "total_versions": total_versions[0]["count"] if total_versions else 0,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Training status error: %s", exc)
        return {"active_model": None, "error": str(exc)}


@app.get("/api/training/versions", dependencies=[Depends(verify_auth)])
def training_versions():
    """All model versions."""
    try:
        rows = _query(
            "SELECT * FROM model_versions ORDER BY created_at DESC"
        )
        return rows
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Training versions error: %s", exc)
        return []


@app.get("/api/metrics/history", dependencies=[Depends(verify_auth)])
def metrics_history(days: int = 90):
    """Metric snapshots for trending charts."""
    try:
        cutoff = (datetime.now(ET) - timedelta(days=days)).isoformat()
        rows = _query(
            "SELECT * FROM metric_snapshots WHERE created_at >= %s "
            "ORDER BY snapshot_date ASC",
            (cutoff,),
        )
        for r in rows:
            _parse_json_fields(r, ["metrics_json"])
        return rows
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Metrics history error: %s", exc)
        return []


@app.get("/api/schedule-metrics", dependencies=[Depends(verify_auth)])
def schedule_metrics(days: int = 30):
    """Compute schedule metrics."""
    try:
        cutoff = (datetime.now(ET) - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = _query(
            "SELECT * FROM schedule_metrics WHERE metric_date >= %s "
            "ORDER BY metric_date DESC",
            (cutoff,),
        )
        return rows
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Schedule metrics error: %s", exc)
        return []


@app.get("/api/earnings", dependencies=[Depends(verify_auth)])
def earnings(days: int = 14):
    """Upcoming earnings from the earnings calendar."""
    try:
        today = datetime.now(ET).strftime("%Y-%m-%d")
        future = (datetime.now(ET) + timedelta(days=days)).strftime("%Y-%m-%d")
        rows = _query(
            "SELECT * FROM earnings_calendar "
            "WHERE earnings_date >= %s AND earnings_date <= %s "
            "ORDER BY earnings_date ASC",
            (today, future),
        )
        return {
            "days_ahead": days,
            "count": len(rows),
            "earnings": rows,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Earnings error: %s", exc)
        return {"days_ahead": days, "count": 0, "earnings": [], "error": str(exc)}


@app.get("/api/audit/latest", dependencies=[Depends(verify_auth)])
def audit_latest():
    """Most recent daily audit report."""
    try:
        row = _query_one(
            "SELECT * FROM audit_reports ORDER BY created_at DESC LIMIT 1"
        )
        if not row:
            return {"audit": None}
        _parse_json_fields(row, ["flags", "metrics_to_watch"])
        return row
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Audit latest error: %s", exc)
        return {"audit": None, "error": str(exc)}


@app.get("/api/docs", dependencies=[Depends(verify_auth)])
def docs_list():
    """Documentation listing (static, no file system access on Render)."""
    return {
        "note": "Full documentation is available on the local dashboard.",
        "docs": [],
    }


@app.get("/api/council/latest", dependencies=[Depends(verify_auth)])
def council_latest():
    """Latest council session with votes."""
    try:
        session = _query_one(
            "SELECT * FROM council_sessions ORDER BY created_at DESC LIMIT 1"
        )
        if not session:
            return {"session": None}

        votes = _query(
            "SELECT * FROM council_votes WHERE session_id = %s ORDER BY round, agent_name",
            (session["session_id"],),
        )
        for v in votes:
            _parse_json_fields(v, ["key_data_points", "risk_flags"])

        session["votes"] = votes
        return session
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Council latest error: %s", exc)
        return {"session": None, "error": str(exc)}


@app.get("/api/council/history", dependencies=[Depends(verify_auth)])
def council_history(days: int = 30):
    """Council session history."""
    try:
        cutoff = (datetime.now(ET) - timedelta(days=days)).isoformat()
        rows = _query(
            "SELECT * FROM council_sessions WHERE created_at >= %s "
            "ORDER BY created_at DESC",
            (cutoff,),
        )
        return rows
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Council history error: %s", exc)
        return []
