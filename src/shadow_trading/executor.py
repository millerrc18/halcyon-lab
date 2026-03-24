"""Shadow trade execution flow: entry and exit monitoring."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from src.config import load_config
from src.journal.store import (
    get_open_shadow_trades,
    get_open_shadow_trade_for_ticker,
    insert_shadow_trade,
    update_shadow_trade,
    close_shadow_trade,
    update_recommendation,
)
from src.models import TradePacket
from src.shadow_trading.models import ShadowTrade

logger = logging.getLogger(__name__)


def _parse_price(value) -> float:
    """Parse a price value that may be a string like '$78.82 area' or a float."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace("$", "").replace(",", "").split()[0]
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    return 0.0


def open_shadow_trade(
    recommendation_id: str,
    packet: TradePacket,
    features: dict,
    db_path: str = "ai_research_desk.sqlite3",
) -> str | None:
    """Open a shadow trade for a packet-worthy recommendation.

    Returns trade_id on success, None on failure.
    """
    config = load_config()
    shadow_cfg = config.get("shadow_trading", {})

    if not shadow_cfg.get("enabled", False):
        logger.info("Shadow trading disabled, skipping")
        return None

    # Risk governor check
    try:
        from src.risk.governor import RiskGovernor, get_portfolio_state
        governor = RiskGovernor(config)
        portfolio = get_portfolio_state(db_path)
        check = governor.check_trade(
            packet.ticker,
            packet.position_sizing.allocation_dollars,
            features,
            portfolio,
        )
        if not check["approved"]:
            reason = check.get("rejection_reason", "Risk check failed")
            logger.warning("[RISK] Trade rejected for %s: %s", packet.ticker, reason)
            print(f"[RISK] BLOCKED: {packet.ticker} — {reason}")
            return None
    except ImportError:
        pass  # Risk module not available, continue without
    except Exception as e:
        logger.warning("[RISK] Governor check failed: %s — continuing", e)

    # Position limit check (bootcamp overrides)
    bootcamp_cfg = config.get("bootcamp", {})
    if bootcamp_cfg.get("enabled", False):
        max_positions = bootcamp_cfg.get("max_positions", 50)
        logger.info(f"[BOOTCAMP] Position limit: {max_positions}")
    else:
        max_positions = shadow_cfg.get("max_positions", 10)

    open_trades = get_open_shadow_trades(db_path)
    if len(open_trades) >= max_positions:
        logger.info(f"[SHADOW] At position limit ({max_positions}), skipping")
        print(f"[SHADOW] At position limit ({max_positions}), skipping")
        return None

    ticker = packet.ticker

    # Check for duplicate open trade
    existing = get_open_shadow_trade_for_ticker(ticker, db_path)
    if existing:
        logger.info(f"[SHADOW] Already have open trade for {ticker}, skipping")
        print(f"[SHADOW] Already have open trade for {ticker}, skipping")
        return None

    # Parse packet values
    entry_price = _parse_price(packet.entry_zone)
    stop_price = _parse_price(packet.stop_invalidation)

    targets_parts = packet.targets.split("/")
    target_1 = _parse_price(targets_parts[0]) if len(targets_parts) >= 1 else 0.0
    target_2 = _parse_price(targets_parts[1]) if len(targets_parts) >= 2 else 0.0

    planned_shares = max(1, int(packet.position_sizing.allocation_dollars / entry_price)) if entry_price > 0 else 1
    planned_allocation = packet.position_sizing.allocation_dollars

    earnings_adjacent = features.get("event_risk_level", "none") in ("elevated", "imminent")

    et = ZoneInfo("America/New_York")
    now = datetime.now(et)

    trade = ShadowTrade(
        recommendation_id=recommendation_id,
        ticker=ticker,
        direction="long",
        status="pending",
        entry_price=entry_price,
        stop_price=stop_price,
        target_1=target_1,
        target_2=target_2,
        planned_shares=planned_shares,
        planned_allocation=planned_allocation,
        earnings_adjacent=earnings_adjacent,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )

    trade_data = trade.to_dict()

    # Try bracket order first, fall back to simple market order
    try:
        from src.shadow_trading.alpaca_adapter import place_bracket_order
        order = place_bracket_order(
            ticker,
            planned_shares,
            take_profit_price=target_1,
            stop_loss_price=stop_price,
        )
        trade_data["alpaca_order_id"] = order.get("order_id")
        trade_data["order_type"] = "bracket"

        fill_price = order.get("filled_avg_price")
        if fill_price:
            trade_data["actual_entry_price"] = fill_price
        else:
            trade_data["actual_entry_price"] = entry_price
        trade_data["actual_entry_time"] = now.isoformat()
        trade_data["status"] = "open"
        trade_data["max_favorable_excursion"] = 0.0
        trade_data["max_adverse_excursion"] = 0.0

    except Exception as e:
        logger.warning(f"[SHADOW] Bracket order failed for {ticker}: {e}, falling back to market")
        # Fall back to simple market order
        try:
            from src.shadow_trading.alpaca_adapter import place_paper_entry
            order = place_paper_entry(ticker, planned_shares)
            trade_data["alpaca_order_id"] = order.get("order_id")
            trade_data["order_type"] = "simple"

            fill_price = order.get("filled_avg_price")
            if fill_price:
                trade_data["actual_entry_price"] = fill_price
            else:
                trade_data["actual_entry_price"] = entry_price
            trade_data["actual_entry_time"] = now.isoformat()
            trade_data["status"] = "open"
            trade_data["max_favorable_excursion"] = 0.0
            trade_data["max_adverse_excursion"] = 0.0

        except Exception as e2:
            logger.warning(f"[SHADOW] Alpaca order failed for {ticker}: {e2}")
            print(f"[SHADOW] Alpaca order failed for {ticker}: {e2}, recording trade without Alpaca")
            trade_data["actual_entry_price"] = entry_price
            trade_data["actual_entry_time"] = now.isoformat()
            trade_data["status"] = "open"
            trade_data["order_type"] = "simple"
            trade_data["max_favorable_excursion"] = 0.0
            trade_data["max_adverse_excursion"] = 0.0

    trade_id = insert_shadow_trade(trade_data, db_path)

    # Update journal with shadow entry
    if recommendation_id:
        update_recommendation(
            recommendation_id,
            {
                "shadow_entry_price": trade_data.get("actual_entry_price"),
                "shadow_entry_time": trade_data.get("actual_entry_time"),
            },
            db_path,
        )

    actual_price = trade_data.get("actual_entry_price", entry_price)
    print(
        f"[SHADOW] Opened shadow trade for {ticker} at ${actual_price:.2f} "
        f"({planned_shares} shares)"
    )

    return trade_id


def check_and_manage_open_trades(
    db_path: str = "ai_research_desk.sqlite3",
) -> list[dict]:
    """Check all open shadow trades and manage exits.

    Returns a list of action dicts describing what happened.
    """
    config = load_config()
    shadow_cfg = config.get("shadow_trading", {})
    timeout_days = shadow_cfg.get("timeout_days", 15)

    open_trades = get_open_shadow_trades(db_path)
    actions = []

    et = ZoneInfo("America/New_York")
    now = datetime.now(et)

    for trade in open_trades:
        ticker = trade["ticker"]
        entry_price = trade.get("actual_entry_price") or trade.get("entry_price", 0)
        stop_price = trade.get("stop_price", 0)
        target_1 = trade.get("target_1", 0)
        target_2 = trade.get("target_2", 0)

        if entry_price <= 0:
            continue

        # Get current price
        current_price = _get_current_price_safe(ticker)
        if current_price is None:
            continue

        # Calculate unrealized P&L
        shares = trade.get("planned_shares", 1)
        unrealized_pnl = (current_price - entry_price) * shares
        unrealized_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

        # Update MFE/MAE
        mfe = trade.get("max_favorable_excursion") or 0.0
        mae = trade.get("max_adverse_excursion") or 0.0

        price_move = current_price - entry_price
        if price_move > mfe:
            mfe = price_move
        if price_move < mae:
            mae = price_move

        # Calculate days open
        entry_time_str = trade.get("actual_entry_time") or trade.get("created_at", "")
        try:
            entry_time = datetime.fromisoformat(entry_time_str)
            days_open = (now - entry_time).days
        except (ValueError, TypeError):
            days_open = 0

        # Update trade with current MFE/MAE and duration
        update_shadow_trade(
            trade["trade_id"],
            {
                "max_favorable_excursion": mfe,
                "max_adverse_excursion": mae,
                "duration_days": days_open,
            },
            db_path,
        )

        # For bracket orders, check Alpaca for exit fills
        bracket_exit = False
        if trade.get("order_type") == "bracket" and trade.get("alpaca_order_id"):
            try:
                from src.shadow_trading.alpaca_adapter import get_order_status
                order_status = get_order_status(trade["alpaca_order_id"])
                if order_status.get("status") in ("filled", "partially_filled"):
                    # Bracket order exited — determine which leg fired
                    exit_price = order_status.get("filled_avg_price")
                    if exit_price:
                        current_price = exit_price
                        bracket_exit = True
            except Exception:
                pass  # Fall through to polling logic

        # Check exit conditions
        exit_reason = None
        if current_price <= stop_price and stop_price > 0:
            exit_reason = "stop_hit"
        elif current_price >= target_2 and target_2 > 0:
            exit_reason = "target_2_hit"
        elif current_price >= target_1 and target_1 > 0:
            exit_reason = "target_1_hit"
        elif days_open >= timeout_days:
            exit_reason = "timeout"

        if exit_reason:
            pnl_dollars = (current_price - entry_price) * shares
            pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

            # Try to place paper sell
            try:
                from src.shadow_trading.alpaca_adapter import place_paper_exit
                place_paper_exit(ticker, shares)
            except Exception as e:
                logger.warning(f"[SHADOW] Alpaca sell failed for {ticker}: {e}")

            close_shadow_trade(
                trade["trade_id"],
                exit_price=current_price,
                exit_time=now.isoformat(),
                exit_reason=exit_reason,
                pnl_dollars=round(pnl_dollars, 2),
                pnl_pct=round(pnl_pct, 2),
                db_path=db_path,
            )

            # Also update final MFE/MAE and duration on the closed trade
            update_shadow_trade(
                trade["trade_id"],
                {
                    "max_favorable_excursion": mfe,
                    "max_adverse_excursion": mae,
                    "duration_days": days_open,
                },
                db_path,
            )

            # Update journal recommendation and generate postmortem
            rec_id = trade.get("recommendation_id")
            if rec_id:
                from src.journal.store import get_recommendation_by_id
                rec = get_recommendation_by_id(rec_id, db_path)

                # Build combined trade data for postmortem
                trade_for_postmortem = dict(trade)
                trade_for_postmortem.update({
                    "actual_exit_price": current_price,
                    "exit_reason": exit_reason,
                    "pnl_dollars": round(pnl_dollars, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "max_favorable_excursion": mfe,
                    "max_adverse_excursion": mae,
                    "duration_days": days_open,
                })
                if rec:
                    trade_for_postmortem["thesis_text"] = rec.get("thesis_text", "")
                    trade_for_postmortem["atr"] = rec.get("atr", 0)

                # Generate postmortem (rule-based, then LLM-enhanced)
                from src.evaluation.postmortem import generate_postmortem, determine_lesson_tag
                from src.llm.postmortem_writer import enhance_postmortem_with_llm
                rule_based_postmortem = generate_postmortem(trade_for_postmortem)
                postmortem_text = enhance_postmortem_with_llm(trade_for_postmortem, rule_based_postmortem)
                lesson_tag = determine_lesson_tag(trade_for_postmortem)

                update_recommendation(
                    rec_id,
                    {
                        "shadow_exit_price": current_price,
                        "shadow_exit_time": now.isoformat(),
                        "shadow_pnl_dollars": round(pnl_dollars, 2),
                        "shadow_pnl_pct": round(pnl_pct, 2),
                        "max_favorable_excursion": mfe,
                        "max_adverse_excursion": mae,
                        "shadow_duration_days": days_open,
                        "thesis_success": 1 if pnl_dollars > 0 else 0,
                        "assistant_postmortem": postmortem_text,
                        "lesson_tag": lesson_tag,
                    },
                    db_path,
                )

            action = {
                "type": "closed",
                "ticker": ticker,
                "exit_reason": exit_reason,
                "pnl_dollars": round(pnl_dollars, 2),
                "pnl_pct": round(pnl_pct, 2),
                "days_held": days_open,
                "trade_id": trade["trade_id"],
                "recommendation_id": rec_id,
            }
            actions.append(action)

            print(
                f"[SHADOW] Closed {ticker}: {exit_reason} | "
                f"P&L=${pnl_dollars:+.2f} ({pnl_pct:+.1f}%) | "
                f"held {days_open} days"
            )

    return actions


def _get_current_price_safe(ticker: str) -> float | None:
    """Get current price, trying Alpaca first then falling back to yfinance."""
    try:
        from src.shadow_trading.alpaca_adapter import get_current_price
        price = get_current_price(ticker)
        if price:
            return price
    except Exception:
        pass

    # Fallback to yfinance
    try:
        from src.data_ingestion.market_data import fetch_ohlcv
        data = fetch_ohlcv([ticker], period="5d")
        if ticker in data and not data[ticker].empty:
            return float(data[ticker]["Close"].iloc[-1])
    except Exception:
        pass

    return None
