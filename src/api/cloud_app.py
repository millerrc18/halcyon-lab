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
    allow_methods=["GET", "POST", "OPTIONS"],
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

@app.get("/healthz")
def healthz():
    """Unauthenticated health check for Render."""
    return {"status": "ok"}

@app.get("/api/auth", dependencies=[Depends(verify_auth)])
def auth_check():
    """Verify auth token without touching the database.

    Used by AuthGate to validate password on login.
    Returns 200 if token is valid, 401 if not.
    """
    return {"authenticated": True}

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
    """Documentation listing. Returns array matching local API format."""
    return [
        {"id": "agents", "title": "AGENTS.md — System Blueprint", "available": True},
        {"id": "architecture", "title": "Architecture Overview", "available": True},
        {"id": "roadmap", "title": "Development Roadmap", "available": True},
        {"id": "deployment", "title": "Cloud Deployment Guide", "available": True},
        {"id": "cli-reference", "title": "CLI Command Reference", "available": True},
        {"id": "telegram-commands", "title": "Telegram Commands", "available": True},
    ]


@app.get("/api/docs/{doc_id}", dependencies=[Depends(verify_auth)])
def get_doc(doc_id: str):
    """Individual doc. Cloud mode: return placeholder directing to local."""
    return {
        "id": doc_id,
        "title": doc_id,
        "content": f"# {doc_id}\n\nFull document content is available on the local dashboard.\n\nConnect to your local machine to view the complete document.",
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


# ── New endpoints — Categories 1-3 ────────────────────────────────


@app.get("/api/config", dependencies=[Depends(verify_auth)])
def get_config():
    """Return system config for the Settings page. Cloud mode: static config."""
    return {
        "risk": {"starting_capital": 100000, "planned_risk_pct_min": 0.005, "planned_risk_pct_max": 0.01, "max_open_positions": 50},
        "shadow_trading": {"enabled": True, "max_positions": 50, "timeout_days": 15},
        "llm": {"enabled": True, "model": "halcyonlatest", "temperature": 0.7},
        "bootcamp": {"enabled": True, "phase": 1, "qualification_threshold": 40, "email_mode": "daily_summary"},
        "automation": {"morning_watchlist_hour_et": 8, "eod_recap_hour_et": 16, "scan_interval_minutes": 30},
        "training": {"enabled": True, "claude_model": "claude-sonnet-4-20250514", "auto_train_threshold": 50},
        "environment": "cloud",
    }


@app.get("/api/halt-status", dependencies=[Depends(verify_auth)])
def halt_status():
    """Trading halt status. Cloud mode: always report not halted."""
    return {"halted": False, "reason": None, "halted_at": None}


@app.get("/api/costs", dependencies=[Depends(verify_auth)])
def costs(days: int = 30):
    """API cost summary from api_costs table."""
    try:
        cutoff = (datetime.now(ET) - timedelta(days=days)).isoformat()
        rows = _query(
            "SELECT model, purpose, SUM(input_tokens) as total_input, "
            "SUM(output_tokens) as total_output, SUM(estimated_cost) as total_cost, "
            "COUNT(*) as call_count "
            "FROM api_costs WHERE created_at >= %s "
            "GROUP BY model, purpose ORDER BY total_cost DESC",
            (cutoff,),
        )
        total = sum(r.get("total_cost", 0) or 0 for r in rows)
        return {"days": days, "total_cost": round(total, 4), "breakdown": rows}
    except Exception:
        return {"days": days, "total_cost": 0, "breakdown": []}


@app.get("/api/health/score", dependencies=[Depends(verify_auth)])
def health_score():
    """HSHS health score. Computed from available cloud data."""
    try:
        closed = _query_one("SELECT COUNT(*) as count FROM shadow_trades WHERE status = 'closed'")
        closed_count = closed["count"] if closed else 0

        examples = _query_one("SELECT COUNT(*) as count FROM training_examples")
        example_count = examples["count"] if examples else 0

        model = _query_one("SELECT version_name, status FROM model_versions ORDER BY created_at DESC LIMIT 1")
        canary = _query_one("SELECT verdict FROM canary_evaluations ORDER BY created_at DESC LIMIT 1")

        data_asset_score = min(100, (example_count / 2800) * 100) if example_count else 0
        flywheel_score = min(100, (closed_count / 50) * 100) if closed_count else 0
        overall = round(data_asset_score * 0.35 + flywheel_score * 0.20, 1)

        return {
            "score": {
                "overall": overall,
                "dimensions": {
                    "performance": 0,
                    "model_quality": 0,
                    "data_asset": round(data_asset_score, 1),
                    "flywheel_velocity": round(flywheel_score, 1),
                    "defensibility": 0,
                },
                "weights": {
                    "performance": 0.10,
                    "model_quality": 0.25,
                    "data_asset": 0.35,
                    "flywheel_velocity": 0.20,
                    "defensibility": 0.10,
                },
                "phase": "early",
            },
            "closed_trades": closed_count,
            "training_examples": example_count,
            "model": model,
            "canary": canary,
            "history": [],
        }
    except Exception as exc:
        return {"score": {"overall": 0, "dimensions": {}, "weights": {}, "phase": "early"}, "history": [], "error": str(exc)}


@app.get("/api/shadow/account", dependencies=[Depends(verify_auth)])
def shadow_account():
    """Shadow trading account summary."""
    try:
        open_trades = _query(
            "SELECT entry_price, planned_shares, pnl_dollars FROM shadow_trades WHERE status = 'open'"
        )
        closed_trades = _query(
            "SELECT pnl_dollars, pnl_pct FROM shadow_trades WHERE status = 'closed'"
        )
        starting_capital = 100000
        closed_pnl = sum(t.get("pnl_dollars", 0) or 0 for t in closed_trades)
        open_alloc = sum((t.get("entry_price", 0) or 0) * (t.get("planned_shares", 0) or 0) for t in open_trades)

        wins = [t for t in closed_trades if (t.get("pnl_dollars", 0) or 0) > 0]
        losses = [t for t in closed_trades if (t.get("pnl_dollars", 0) or 0) <= 0]

        return {
            "starting_capital": starting_capital,
            "equity": starting_capital + closed_pnl,
            "cash": starting_capital + closed_pnl - open_alloc,
            "open_positions": len(open_trades),
            "closed_pnl": round(closed_pnl, 2),
            "unrealized_pnl": 0,
            "win_rate": round(len(wins) / len(closed_trades), 3) if closed_trades else None,
            "total_closed": len(closed_trades),
            "wins": len(wins),
            "losses": len(losses),
        }
    except Exception as exc:
        return {"starting_capital": 100000, "equity": 100000, "error": str(exc)}


@app.get("/api/cto-report", dependencies=[Depends(verify_auth)])
def cto_report(days: int = 7):
    """Generate CTO report from cloud data."""
    try:
        cutoff = (datetime.now(ET) - timedelta(days=days)).isoformat()

        open_count = _query_one("SELECT COUNT(*) as c FROM shadow_trades WHERE status = 'open'")
        closed_recent = _query(
            "SELECT ticker, pnl_dollars, pnl_pct, exit_reason FROM shadow_trades "
            "WHERE status = 'closed' AND actual_exit_time >= %s ORDER BY actual_exit_time DESC",
            (cutoff,),
        )
        packet_count = _query_one("SELECT COUNT(*) as c FROM recommendations WHERE created_at >= %s", (cutoff,))
        latest_audit = _query_one("SELECT overall_assessment, summary FROM audit_reports ORDER BY created_at DESC LIMIT 1")

        # Compute basic KPIs
        pnls = [t.get("pnl_pct", 0) or 0 for t in closed_recent]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        win_rate = len(wins) / len(pnls) if pnls else 0
        total_pnl = sum(t.get("pnl_dollars", 0) or 0 for t in closed_recent)

        return {
            "report_period": {
                "start": cutoff[:10],
                "end": datetime.now(ET).strftime("%Y-%m-%d"),
            },
            "headline_kpis": {
                "sharpe_ratio": 0,
                "win_rate": win_rate,
                "max_drawdown_pct": 0,
                "confidence_calibration": 0,
                "avg_rubric_score": None,
            },
            "trade_summary": {
                "trades_closed": len(closed_recent),
                "trades_open": open_count["c"] if open_count else 0,
                "profit_factor": "n/a",
                "expectancy_dollars": round(total_pnl / len(closed_recent), 2) if closed_recent else None,
                "total_pnl": round(total_pnl, 2),
                "avg_winner_pct": round(sum(wins) / len(wins), 1) if wins else None,
                "avg_loser_pct": round(sum(losses) / len(losses), 1) if losses else None,
                "max_consecutive_losses": 0,
            },
            "system_status": {
                "model_version": "cloud",
                "dataset_size": 0,
            },
            "period_days": days,
            "packets_generated": packet_count["c"] if packet_count else 0,
            "latest_audit": latest_audit,
            "generated_at": datetime.now(ET).isoformat(),
        }
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/api/scan/latest", dependencies=[Depends(verify_auth)])
def scan_latest():
    """Latest scan results."""
    try:
        latest = _query(
            "SELECT * FROM recommendations ORDER BY created_at DESC LIMIT 10"
        )
        return {"recommendations": latest, "count": len(latest)}
    except Exception:
        return {"recommendations": [], "count": 0}


@app.get("/api/review/pending", dependencies=[Depends(verify_auth)])
def review_pending():
    """Trades pending review."""
    try:
        rows = _query(
            "SELECT * FROM shadow_trades WHERE status = 'closed' "
            "AND (exit_reason IS NOT NULL) ORDER BY actual_exit_time DESC LIMIT 20"
        )
        return rows
    except Exception:
        return []


@app.get("/api/review/scorecard", dependencies=[Depends(verify_auth)])
def review_scorecard(weeks: int = 4):
    """Review scorecard."""
    return {"weeks": weeks, "scorecard": []}


@app.get("/api/review/postmortems", dependencies=[Depends(verify_auth)])
def review_postmortems():
    """Recent postmortems."""
    return []


@app.get("/api/audit/history", dependencies=[Depends(verify_auth)])
def audit_history(days: int = 30):
    """Audit report history."""
    try:
        cutoff = (datetime.now(ET) - timedelta(days=days)).isoformat()
        rows = _query(
            "SELECT * FROM audit_reports WHERE created_at >= %s ORDER BY created_at DESC",
            (cutoff,),
        )
        return rows
    except Exception:
        return []


@app.get("/api/training/report", dependencies=[Depends(verify_auth)])
def training_report():
    """Training pipeline report."""
    try:
        total = _query_one("SELECT COUNT(*) as c FROM training_examples")
        scored = _query_one("SELECT COUNT(*) as c FROM training_examples WHERE quality_score IS NOT NULL")
        avg_score = _query_one("SELECT AVG(quality_score) as avg FROM training_examples WHERE quality_score IS NOT NULL")
        return {
            "total_examples": total["c"] if total else 0,
            "scored": scored["c"] if scored else 0,
            "unscored": (total["c"] if total else 0) - (scored["c"] if scored else 0),
            "avg_quality_score": round(avg_score["avg"], 2) if avg_score and avg_score["avg"] else None,
        }
    except Exception:
        return {"total_examples": 0, "scored": 0, "unscored": 0}


@app.get("/api/metric-history", dependencies=[Depends(verify_auth)])
def metric_history(days: int = 90):
    """Alias for metrics/history — some frontend pages use this path."""
    return metrics_history(days)


# ── POST action stubs (cloud mode) ──────────────────────────────

CLOUD_ACTION_MSG = {"error": "cloud_mode", "message": "This action is only available on the local dashboard."}


@app.post("/api/actions/scan", dependencies=[Depends(verify_auth)])
def action_scan():
    return CLOUD_ACTION_MSG


@app.post("/api/actions/cto-report", dependencies=[Depends(verify_auth)])
def action_cto_report():
    return CLOUD_ACTION_MSG


@app.post("/api/actions/collect-training", dependencies=[Depends(verify_auth)])
def action_collect_training():
    return CLOUD_ACTION_MSG


@app.post("/api/actions/train-pipeline", dependencies=[Depends(verify_auth)])
def action_train_pipeline():
    return CLOUD_ACTION_MSG


@app.post("/api/actions/score", dependencies=[Depends(verify_auth)])
def action_score():
    return CLOUD_ACTION_MSG


@app.post("/api/actions/council", dependencies=[Depends(verify_auth)])
def action_council():
    return CLOUD_ACTION_MSG


@app.post("/api/halt-trading", dependencies=[Depends(verify_auth)])
def halt_trading():
    return CLOUD_ACTION_MSG


@app.post("/api/resume-trading", dependencies=[Depends(verify_auth)])
def resume_trading():
    return CLOUD_ACTION_MSG


@app.post("/api/training/train", dependencies=[Depends(verify_auth)])
def action_train():
    return CLOUD_ACTION_MSG


@app.post("/api/training/bootstrap", dependencies=[Depends(verify_auth)])
def action_bootstrap():
    return CLOUD_ACTION_MSG


@app.post("/api/training/rollback", dependencies=[Depends(verify_auth)])
def action_rollback():
    return CLOUD_ACTION_MSG


@app.post("/api/shadow/close/{ticker}", dependencies=[Depends(verify_auth)])
def action_close_trade(ticker: str):
    return CLOUD_ACTION_MSG


# ── Additional GET endpoints ─────────────────────────────────────


@app.get("/api/market/overview", dependencies=[Depends(verify_auth)])
def market_overview():
    """Market overview — VIX, regime, macro summary."""
    try:
        vix = _query_one("SELECT * FROM vix_term_structure ORDER BY collected_date DESC LIMIT 1")
        macro = _query(
            "SELECT series_id, series_name, value, change_pct FROM macro_snapshots "
            "WHERE collected_date = (SELECT MAX(collected_date) FROM macro_snapshots)"
        )
        return {"vix": vix, "macro": macro}
    except Exception:
        return {"vix": None, "macro": []}


@app.get("/api/data-asset/growth", dependencies=[Depends(verify_auth)])
def data_asset_growth():
    """Data asset growth over time."""
    try:
        rows = _query(
            "SELECT DATE(created_at) as date, COUNT(*) as count "
            "FROM training_examples GROUP BY DATE(created_at) ORDER BY date"
        )
        return {"daily_counts": rows}
    except Exception:
        return {"daily_counts": []}


@app.get("/api/journal", dependencies=[Depends(verify_auth)])
def trade_journal(days: int = 90):
    """Trade journal — closed trades with recommendation context."""
    try:
        cutoff = (datetime.now(ET) - timedelta(days=days)).isoformat()
        rows = _query(
            "SELECT st.*, r.thesis_text, r.setup_type "
            "FROM shadow_trades st LEFT JOIN recommendations r "
            "ON st.recommendation_id = r.recommendation_id "
            "WHERE st.status = 'closed' AND st.actual_exit_time >= %s "
            "ORDER BY st.actual_exit_time DESC",
            (cutoff,),
        )
        return {"trades": rows, "count": len(rows)}
    except Exception as exc:
        return {"trades": [], "count": 0, "error": str(exc)}


@app.get("/api/signal-zoo", dependencies=[Depends(verify_auth)])
def signal_zoo(days: int = 7):
    """Signal zoo — setup signals with optional filters."""
    try:
        cutoff = (datetime.now(ET) - timedelta(days=days)).isoformat()
        rows = _query(
            "SELECT * FROM setup_signals WHERE created_at >= %s ORDER BY created_at DESC",
            (cutoff,),
        )
        for r in rows:
            _parse_json_fields(r, ["features_json"])
        return {"signals": rows, "count": len(rows)}
    except Exception:
        return {"signals": [], "count": 0}


@app.get("/api/macro/dashboard", dependencies=[Depends(verify_auth)])
def macro_dashboard():
    """Macro dashboard — latest values for each FRED series."""
    try:
        rows = _query(
            "SELECT DISTINCT ON (series_id) series_id, series_name, value, "
            "previous_value, change_pct, collected_date "
            "FROM macro_snapshots ORDER BY series_id, collected_date DESC"
        )
        return {"series": rows}
    except Exception:
        return {"series": []}
