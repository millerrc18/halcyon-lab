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
