"""Telegram notification client for Halcyon Lab.

Sends real-time alerts for trade opens/closes, scan results,
system events, and overnight pipeline status.

Setup:
1. Message @BotFather on Telegram, send /newbot, follow prompts
2. Copy the bot token
3. Message your new bot (send /start)
4. Get your chat_id: visit https://api.telegram.org/bot<TOKEN>/getUpdates
5. Add to config/settings.local.yaml:
   telegram:
     enabled: true
     bot_token: "your-bot-token"
     chat_id: "your-chat-id"
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from src.config import load_config

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _get_telegram_config() -> dict:
    """Load Telegram config from settings."""
    config = load_config()
    tg = config.get("telegram", {})
    return {
        "enabled": tg.get("enabled", False),
        "bot_token": tg.get("bot_token", ""),
        "chat_id": str(tg.get("chat_id", "")),
    }


def is_telegram_enabled() -> bool:
    """Check if Telegram notifications are configured and enabled."""
    cfg = _get_telegram_config()
    return cfg["enabled"] and bool(cfg["bot_token"]) and bool(cfg["chat_id"])


def send_telegram(message: str, parse_mode: str = "HTML") -> bool:
    """Send a message via Telegram Bot API.

    Args:
        message: Text to send (supports HTML formatting)
        parse_mode: "HTML" or "Markdown"

    Returns True on success, False on failure.
    """
    cfg = _get_telegram_config()
    if not cfg["enabled"] or not cfg["bot_token"] or not cfg["chat_id"]:
        return False

    try:
        url = TELEGRAM_API.format(token=cfg["bot_token"])
        resp = requests.post(
            url,
            json={
                "chat_id": cfg["chat_id"],
                "text": message,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return True
        else:
            logger.warning("[TELEGRAM] Send failed: %s %s", resp.status_code, resp.text[:200])
            return False
    except Exception as e:
        logger.warning("[TELEGRAM] Send error: %s", e)
        return False


# ── Pre-formatted alert functions ─────────────────────────────────────────


def notify_trade_opened(ticker: str, entry_price: float, stop: float,
                        target: float, score: int, shares: int) -> bool:
    """Alert: new trade opened."""
    pnl_risk = (entry_price - stop) * shares
    msg = (
        f"🟢 <b>TRADE OPENED: {ticker}</b>\n"
        f"Entry: ${entry_price:.2f} | Stop: ${stop:.2f} | Target: ${target:.2f}\n"
        f"Shares: {shares} | Risk: ${pnl_risk:.2f}\n"
        f"Score: {score}/100"
    )
    return send_telegram(msg)


def notify_trade_closed(ticker: str, pnl_dollars: float, pnl_pct: float,
                        exit_reason: str, days_held: int) -> bool:
    """Alert: trade closed."""
    emoji = "🟢" if pnl_dollars >= 0 else "🔴"
    msg = (
        f"{emoji} <b>TRADE CLOSED: {ticker}</b>\n"
        f"P&L: ${pnl_dollars:+.2f} ({pnl_pct:+.1f}%)\n"
        f"Reason: {exit_reason} | Held: {days_held} days"
    )
    return send_telegram(msg)


def notify_scan_complete(packets_count: int, trades_opened: int,
                         trades_closed: int) -> bool:
    """Alert: scan cycle complete (only if something happened)."""
    if packets_count == 0 and trades_opened == 0 and trades_closed == 0:
        return True  # Skip silent scans
    msg = (
        f"📊 <b>SCAN COMPLETE</b>\n"
        f"Packets: {packets_count} | Opened: {trades_opened} | Closed: {trades_closed}"
    )
    return send_telegram(msg)


def notify_risk_alert(alert_type: str, detail: str) -> bool:
    """Alert: risk governor event."""
    msg = f"⚠️ <b>RISK ALERT: {alert_type}</b>\n{detail}"
    return send_telegram(msg)


def notify_earnings_warning(tickers: list[str]) -> bool:
    """Alert: stocks reporting earnings soon."""
    if not tickers:
        return True
    ticker_list = "\n".join(f"  • {t}" for t in tickers)
    msg = f"📅 <b>EARNINGS THIS WEEK</b>\n{ticker_list}"
    return send_telegram(msg)


def notify_overnight_complete(results: dict) -> bool:
    """Alert: overnight data collection summary."""
    now = datetime.now(ET).strftime("%H:%M ET")
    lines = [f"🌙 <b>OVERNIGHT DATA COLLECTION</b> ({now})"]
    for key, val in results.items():
        if isinstance(val, str) and "error" in val.lower():
            lines.append(f"  ❌ {key}: {val[:60]}")
        else:
            lines.append(f"  ✅ {key}")
    return send_telegram("\n".join(lines))


def notify_system_event(event: str, detail: str = "") -> bool:
    """Alert: general system event."""
    msg = f"🔧 <b>{event}</b>"
    if detail:
        msg += f"\n{detail}"
    return send_telegram(msg)


def notify_daily_summary(total_pnl: float, open_trades: int,
                         closed_today: int, win_rate: float | None = None) -> bool:
    """Alert: end-of-day summary."""
    emoji = "🟢" if total_pnl >= 0 else "🔴"
    msg = (
        f"{emoji} <b>DAILY SUMMARY</b>\n"
        f"P&L Today: ${total_pnl:+.2f}\n"
        f"Open Trades: {open_trades} | Closed Today: {closed_today}"
    )
    if win_rate is not None:
        msg += f"\nWin Rate: {win_rate:.0%}"
    return send_telegram(msg)


def notify_model_event(event: str, model_name: str, detail: str = "") -> bool:
    """Alert: model training/promotion/rollback event."""
    msg = f"🧠 <b>MODEL: {event}</b>\nModel: {model_name}"
    if detail:
        msg += f"\n{detail}"
    return send_telegram(msg)


# ── Additional notification events ────────────────────────────────────────


def notify_watchlist(tickers: list[str], count: int,
                     watchlist_count: int = 0) -> bool:
    """Alert: morning watchlist with high-conviction (packet-worthy) names."""
    now = datetime.now(ET).strftime("%H:%M ET")
    msg = f"☀️ <b>MORNING WATCHLIST</b> ({now})\n"
    if tickers:
        msg += f"🎯 {count} packet-worthy (score 40+):\n"
        msg += "\n".join(f"  • {t}" for t in tickers[:10])
        if count > 10:
            msg += f"\n  ...and {count - 10} more"
        if watchlist_count:
            msg += f"\n📋 {watchlist_count} additional on watchlist (25-40)"
    else:
        msg += "No qualifying setups found."
    return send_telegram(msg)


def notify_scan_result(scan_number: int, total_scanned: int,
                       packet_worthy: int, watchlist: int) -> bool:
    """Alert: scan cycle result (fires every scan, not just when trades open)."""
    now = datetime.now(ET).strftime("%H:%M ET")
    msg = (
        f"📊 <b>SCAN #{scan_number}</b> ({now})\n"
        f"Scanned: {total_scanned} | Packet-worthy: {packet_worthy} | Watchlist: {watchlist}"
    )
    return send_telegram(msg)


def notify_premarket_complete(features_done: bool, training_gen: int,
                              news_scored: int, candidates: int) -> bool:
    """Alert: pre-market pipeline complete."""
    now = datetime.now(ET).strftime("%H:%M ET")
    msg = (
        f"🌅 <b>PRE-MARKET COMPLETE</b> ({now})\n"
        f"  {'✅' if features_done else '❌'} Rolling features\n"
        f"  ✅ Training examples generated: {training_gen}\n"
        f"  ✅ News items scored: {news_scored}\n"
        f"  ✅ Candidates pre-analyzed: {candidates}"
    )
    return send_telegram(msg)


def notify_vram_handoff(direction: str, success: bool, detail: str = "") -> bool:
    """Alert: VRAM transition between Ollama and PyTorch."""
    emoji = "✅" if success else "❌"
    if direction == "training":
        msg = f"{emoji} <b>VRAM → TRAINING</b>\nOllama unloaded, PyTorch subprocess launched"
    else:
        msg = f"{emoji} <b>VRAM → INFERENCE</b>\nTraining complete, Ollama loaded and warm"
    if detail:
        msg += f"\n{detail}"
    return send_telegram(msg)


def notify_overnight_training_complete(tasks_completed: int, tasks_total: int,
                                       details: dict | None = None) -> bool:
    """Alert: overnight training pipeline complete."""
    now = datetime.now(ET).strftime("%H:%M ET")
    msg = f"🌙 <b>OVERNIGHT TRAINING</b> ({now})\nTasks: {tasks_completed}/{tasks_total}"
    if details:
        for task, status in details.items():
            emoji = "✅" if status.get("success", False) else "❌"
            msg += f"\n  {emoji} {task}"
            if not status.get("success", False) and status.get("error"):
                msg += f": {str(status['error'])[:40]}"
    return send_telegram(msg)


def notify_scoring_summary(scored_today: int, backlog: int) -> bool:
    """Alert: daily scoring summary (end of market hours)."""
    msg = (
        f"📝 <b>SCORING SUMMARY</b>\n"
        f"Scored today: {scored_today}\n"
        f"Backlog remaining: {backlog}"
    )
    return send_telegram(msg)


def notify_schedule_health(gpu_util: float, scan_delay_max: float,
                           handoff_ok: bool, temp_max: int) -> bool:
    """Alert: daily schedule health check."""
    msg = (
        f"📈 <b>SCHEDULE HEALTH</b>\n"
        f"GPU utilization: {gpu_util:.1f}%\n"
        f"Max scan delay: {scan_delay_max:.1f}s\n"
        f"VRAM handoffs: {'✅' if handoff_ok else '❌'}\n"
        f"GPU temp max: {temp_max}°C"
    )
    return send_telegram(msg)


# ── Telegram Command Handler ──────────────────────────────────────────────

TELEGRAM_UPDATES_API = "https://api.telegram.org/bot{token}/getUpdates"


def poll_commands(last_update_id: int = 0) -> tuple[list[dict], int]:
    """Poll for incoming Telegram commands.

    Returns (commands, new_last_update_id).
    Each command is {"command": "/status", "args": "", "chat_id": "123"}.
    """
    cfg = _get_telegram_config()
    if not cfg["enabled"] or not cfg["bot_token"]:
        return [], last_update_id

    try:
        url = TELEGRAM_UPDATES_API.format(token=cfg["bot_token"])
        resp = requests.get(
            url,
            params={"offset": last_update_id + 1, "timeout": 1},
            timeout=5,
        )
        if resp.status_code != 200:
            return [], last_update_id

        data = resp.json()
        if not data.get("ok") or not data.get("result"):
            return [], last_update_id

        commands = []
        new_id = last_update_id
        for update in data["result"]:
            new_id = max(new_id, update["update_id"])
            msg = update.get("message", {})
            text = msg.get("text", "")
            chat_id = str(msg.get("chat", {}).get("id", ""))

            # Only process commands from our authorized chat
            if chat_id != cfg["chat_id"]:
                continue

            if text.startswith("/"):
                parts = text.split(maxsplit=1)
                cmd = parts[0].lower().split("@")[0]  # Strip @botname
                args = parts[1] if len(parts) > 1 else ""
                commands.append({"command": cmd, "args": args, "chat_id": chat_id})

        return commands, new_id

    except Exception as e:
        logger.debug("[TELEGRAM] Poll error: %s", e)
        return [], last_update_id


def handle_command(command: str, args: str) -> str:
    """Process a Telegram command and return the response text.

    Available commands:
    /status — System status summary
    /trades — Open trades list
    /pnl — Current P&L
    /scan — Last scan results
    /earnings — Upcoming earnings
    /schedule — Compute schedule status
    /scoring — Scoring backlog
    /help — List commands
    """
    try:
        if command == "/help" or command == "/start":
            return (
                "🤖 <b>HALCYON LAB COMMANDS</b>\n\n"
                "/status — System status\n"
                "/trades — Open trades\n"
                "/pnl — Current P&L\n"
                "/scan — Last scan result\n"
                "/earnings — Upcoming earnings\n"
                "/schedule — Compute schedule\n"
                "/scoring — Scoring backlog\n"
                "/health — GPU & system health\n"
                "/help — This message"
            )

        elif command == "/status":
            return _cmd_status()
        elif command == "/trades":
            return _cmd_trades()
        elif command == "/pnl":
            return _cmd_pnl()
        elif command == "/scan":
            return _cmd_last_scan()
        elif command == "/earnings":
            return _cmd_earnings()
        elif command == "/schedule":
            return _cmd_schedule()
        elif command == "/scoring":
            return _cmd_scoring()
        elif command == "/health":
            return _cmd_health()
        else:
            return f"Unknown command: {command}\nSend /help for available commands."

    except Exception as e:
        return f"❌ Error: {str(e)[:200]}"


def _cmd_status() -> str:
    """System status summary."""
    now = datetime.now(ET)

    # Check Ollama directly instead of importing is_llm_available
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        llm_ok = resp.status_code == 200
    except Exception:
        llm_ok = False

    try:
        from src.training.versioning import get_active_model_name, get_training_example_counts
        model = get_active_model_name()
        counts = get_training_example_counts()
        total = counts['total']
    except Exception:
        model = "unknown"
        total = "?"

    market_open = 9 <= now.hour < 16 and now.weekday() < 5

    return (
        f"🔧 <b>SYSTEM STATUS</b> ({now.strftime('%H:%M ET')})\n"
        f"LLM: {'✅' if llm_ok else '❌'} {model}\n"
        f"Training examples: {total}\n"
        f"Market: {'Open' if market_open else 'Closed'}"
    )


def _cmd_trades() -> str:
    """List open trades."""
    import sqlite3
    try:
        with sqlite3.connect("ai_research_desk.sqlite3") as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT ticker, entry_price, pnl_pct, pnl_dollars, created_at
                FROM shadow_trades WHERE status = 'open'
                ORDER BY created_at DESC"""
            ).fetchall()

        if not rows:
            return "📭 No open trades."

        lines = [f"📊 <b>OPEN TRADES</b> ({len(rows)})"]
        for r in rows:
            emoji = "🟢" if (r["pnl_pct"] or 0) >= 0 else "🔴"
            pnl = r["pnl_pct"] or 0
            # Compute days held
            try:
                from datetime import datetime
                opened = datetime.fromisoformat(r["created_at"][:19])
                days = (datetime.now() - opened).days
            except Exception:
                days = "?"
            lines.append(
                f"  {emoji} {r['ticker']}: ${r['entry_price']:.2f} "
                f"({pnl:+.1f}%) Day {days}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"📭 No open trades or error: {e}"


def _cmd_pnl() -> str:
    """Current P&L summary."""
    import sqlite3
    try:
        with sqlite3.connect("ai_research_desk.sqlite3") as conn:
            conn.row_factory = sqlite3.Row

            open_row = conn.execute(
                """SELECT COUNT(*) as cnt, COALESCE(SUM(pnl_dollars), 0) as total_pnl
                FROM shadow_trades WHERE status = 'open'"""
            ).fetchone()

            closed_row = conn.execute(
                """SELECT COUNT(*) as cnt, COALESCE(SUM(pnl_dollars), 0) as total_pnl,
                   COALESCE(AVG(CASE WHEN pnl_dollars > 0 THEN 1.0 ELSE 0.0 END), 0) as win_rate
                FROM shadow_trades WHERE status = 'closed'"""
            ).fetchone()

        open_pnl = open_row["total_pnl"]
        closed_pnl = closed_row["total_pnl"]
        total = open_pnl + closed_pnl
        emoji = "🟢" if total >= 0 else "🔴"

        return (
            f"{emoji} <b>P&L SUMMARY</b>\n"
            f"Open: {open_row['cnt']} trades, ${open_pnl:+.2f}\n"
            f"Closed: {closed_row['cnt']} trades, ${closed_pnl:+.2f}\n"
            f"Win rate: {closed_row['win_rate']:.0%}\n"
            f"Total: ${total:+.2f}"
        )
    except Exception:
        return "No P&L data available yet."


def _cmd_last_scan() -> str:
    """Last scan result."""
    import sqlite3
    try:
        with sqlite3.connect("ai_research_desk.sqlite3") as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT ticker, priority_score, created_at
                FROM recommendations ORDER BY created_at DESC LIMIT 5"""
            ).fetchall()

        if not rows:
            return "📭 No scans yet."

        lines = ["📊 <b>RECENT RECOMMENDATIONS</b>"]
        for r in rows:
            score = r["priority_score"] or 0
            lines.append(f"  • {r['ticker']} (score: {score:.0f}) — {r['created_at'][:16]}")
        return "\n".join(lines)
    except Exception:
        return "📭 No scan data available yet."


def _cmd_earnings() -> str:
    """Upcoming earnings."""
    try:
        from scripts.fetch_earnings_calendar import get_all_upcoming_earnings
        upcoming = get_all_upcoming_earnings(days=14)
        if not upcoming:
            return "📅 No earnings in the next 14 days."

        lines = [f"📅 <b>EARNINGS (next 14 days)</b> — {len(upcoming)} stocks"]
        for item in upcoming[:15]:
            lines.append(
                f"  • {item['ticker']} — {item['earnings_date']} "
                f"({item['days_away']}d) {item.get('earnings_time') or ''}"
            )
        if len(upcoming) > 15:
            lines.append(f"  ...and {len(upcoming) - 15} more")
        return "\n".join(lines)
    except Exception as e:
        return f"📅 Earnings data unavailable: {e}"


def _cmd_schedule() -> str:
    """Compute schedule status."""
    now = datetime.now(ET)
    hour = now.hour

    if 9 <= hour < 16 and now.weekday() < 5:
        phase = "🟢 MARKET HOURS — Scanning + between-scan scoring"
    elif 5 <= hour < 9:
        phase = "🌅 PRE-MARKET — Features, training gen, news scoring"
    elif 16 <= hour < 19:
        phase = "📝 POST-MARKET — Scoring, DPO generation"
    elif 19 <= hour or hour < 5:
        phase = "🌙 OVERNIGHT — Training pipeline active"
    else:
        phase = "⏸️ TRANSITION"

    return (
        f"⏰ <b>COMPUTE SCHEDULE</b> ({now.strftime('%H:%M ET')})\n"
        f"Phase: {phase}\n"
        f"Day: {'Weekday' if now.weekday() < 5 else 'Weekend'}\n"
        f"Target utilization: 73%"
    )


def _cmd_scoring() -> str:
    """Scoring backlog status."""
    import sqlite3
    try:
        with sqlite3.connect("ai_research_desk.sqlite3") as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM training_examples"
            ).fetchone()[0]
            scored = conn.execute(
                "SELECT COUNT(*) FROM training_examples WHERE quality_score IS NOT NULL"
            ).fetchone()[0]
            unscored = total - scored

        return (
            f"📝 <b>SCORING STATUS</b>\n"
            f"Total examples: {total}\n"
            f"Scored: {scored}\n"
            f"Backlog: {unscored}"
        )
    except Exception:
        return "📝 No scoring data available."


def _cmd_health() -> str:
    """GPU and system health."""
    import subprocess
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        parts = result.stdout.strip().split(", ")
        temp, util, mem_used, mem_total = parts[0], parts[1], parts[2], parts[3]
        return (
            f"🖥️ <b>SYSTEM HEALTH</b>\n"
            f"GPU Temp: {temp}°C\n"
            f"GPU Util: {util}%\n"
            f"VRAM: {mem_used}/{mem_total} MB"
        )
    except Exception:
        return "🖥️ GPU health data unavailable (nvidia-smi not found)"
