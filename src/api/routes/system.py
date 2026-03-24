"""System API routes."""
from fastapi import APIRouter
from src.config import load_config
from src.services.system_service import get_system_status

router = APIRouter(tags=["system"])


@router.get("/status")
def status():
    config = load_config()
    return get_system_status(config)


@router.get("/preflight")
def preflight():
    config = load_config()
    return get_system_status(config)


@router.get("/config")
def get_config():
    config = load_config()
    # Mask sensitive values
    safe = dict(config)
    if "email" in safe:
        email = dict(safe["email"])
        if "password" in email:
            email["password"] = "***"
        safe["email"] = email
    if "alpaca" in safe:
        alpaca = dict(safe["alpaca"])
        if "api_secret" in alpaca:
            alpaca["api_secret"] = "***"
        safe["alpaca"] = alpaca
    if "training" in safe:
        t = dict(safe["training"])
        if "anthropic_api_key" in t:
            t["anthropic_api_key"] = "***"
        safe["training"] = t
    return safe


@router.get("/cto-report")
def cto_report(days: int = 7):
    from src.evaluation.cto_report import generate_cto_report
    return generate_cto_report(days=days)


@router.post("/halt-trading")
def halt_trading():
    """Emergency halt — stops all new trade entry immediately."""
    from src.risk.governor import _global_halt
    _global_halt(True)
    return {"status": "halted", "message": "All trading halted. No new positions will be opened."}


@router.post("/resume-trading")
def resume_trading():
    """Resume trading after a halt."""
    from src.risk.governor import _global_halt
    _global_halt(False)
    return {"status": "resumed", "message": "Trading resumed."}


@router.get("/halt-status")
def halt_status():
    """Check if trading is halted."""
    from src.risk.governor import _is_halted
    return {"halted": _is_halted()}


@router.get("/audit/latest")
def latest_audit():
    """Get the most recent daily audit report."""
    from src.training.versioning import init_training_tables
    import sqlite3
    init_training_tables()
    with sqlite3.connect("ai_research_desk.sqlite3") as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM audit_reports ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if not row:
        return {"audit": None}
    import json
    result = dict(row)
    for key in ("flags", "metrics_to_watch"):
        if result.get(key):
            try:
                result[key] = json.loads(result[key])
            except (json.JSONDecodeError, TypeError):
                pass
    return result


@router.get("/audit/history")
def audit_history(days: int = 7):
    """Get audit reports for the last N days."""
    from src.training.versioning import init_training_tables
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    import sqlite3, json
    init_training_tables()
    et = ZoneInfo("America/New_York")
    cutoff = (datetime.now(et) - timedelta(days=days)).isoformat()
    with sqlite3.connect("ai_research_desk.sqlite3") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM audit_reports WHERE created_at >= ? ORDER BY created_at DESC",
            (cutoff,),
        ).fetchall()
    results = []
    for row in rows:
        r = dict(row)
        for key in ("flags", "metrics_to_watch"):
            if r.get(key):
                try:
                    r[key] = json.loads(r[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        results.append(r)
    return results


@router.put("/config")
def update_config(updates: dict):
    import yaml
    from pathlib import Path
    from src.config import reload_config

    config_path = Path(__file__).resolve().parent.parent.parent.parent / "config" / "settings.local.yaml"
    if not config_path.exists():
        return {"success": False, "error": "settings.local.yaml not found"}

    with open(config_path, "r") as f:
        current = yaml.safe_load(f) or {}

    for section, values in updates.items():
        if isinstance(values, dict) and section in current:
            current[section].update(values)
        else:
            current[section] = values

    with open(config_path, "w") as f:
        yaml.dump(current, f, default_flow_style=False)

    reload_config()
    return {"success": True}
