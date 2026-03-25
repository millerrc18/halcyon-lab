"""Alpaca paper trading adapter with safety guardrails.

Uses the alpaca-py SDK for paper trading operations.
SAFETY: Will refuse to operate if not pointed at a paper trading endpoint.
"""

import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from src.config import load_config

logger = logging.getLogger(__name__)


class PaperTradingError(Exception):
    """Raised when paper trading safety checks fail."""


def _get_alpaca_config() -> dict:
    """Load Alpaca config from settings and environment, with safety checks."""
    config = load_config()
    alpaca_cfg = config.get("alpaca", {})
    shadow_cfg = config.get("shadow_trading", {})

    # Allow env vars to override config file
    api_key = os.environ.get("ALPACA_API_KEY", alpaca_cfg.get("api_key", ""))
    api_secret = os.environ.get("ALPACA_API_SECRET", alpaca_cfg.get("api_secret", ""))
    base_url = os.environ.get("ALPACA_BASE_URL", alpaca_cfg.get("base_url", "https://paper-api.alpaca.markets"))

    # SAFETY: Verify paper mode
    paper_env = os.environ.get("ALPACA_PAPER_TRADE", "true").lower()
    if "paper" not in base_url.lower() and paper_env != "true":
        raise PaperTradingError(
            "SAFETY VIOLATION: Alpaca base_url does not contain 'paper' and "
            "ALPACA_PAPER_TRADE is not 'true'. Refusing to connect to a live account."
        )

    return {
        "api_key": api_key,
        "api_secret": api_secret,
        "base_url": base_url,
        "enabled": shadow_cfg.get("enabled", False),
        "max_positions": shadow_cfg.get("max_positions", 10),
        "default_order_type": shadow_cfg.get("default_order_type", "market"),
        "timeout_days": shadow_cfg.get("timeout_days", 15),
    }


def _check_enabled() -> dict:
    """Check shadow trading is enabled and return config. Raises if disabled."""
    cfg = _get_alpaca_config()
    if not cfg["enabled"]:
        raise PaperTradingError(
            "Shadow trading is disabled. Set shadow_trading.enabled: true in config."
        )
    return cfg


def _get_trading_client():
    """Create and return an Alpaca TradingClient for paper trading."""
    cfg = _get_alpaca_config()
    from alpaca.trading.client import TradingClient
    return TradingClient(
        api_key=cfg["api_key"],
        secret_key=cfg["api_secret"],
        paper=True,
    )


def _get_data_client():
    """Create and return an Alpaca StockHistoricalDataClient."""
    cfg = _get_alpaca_config()
    from alpaca.data.historical import StockHistoricalDataClient
    return StockHistoricalDataClient(
        api_key=cfg["api_key"],
        secret_key=cfg["api_secret"],
    )


def get_account_info() -> dict:
    """Get paper account info: balance, buying power, equity, portfolio value."""
    client = _get_trading_client()
    account = client.get_account()
    return {
        "account_id": str(account.id),
        "status": str(account.status),
        "cash": float(account.cash),
        "buying_power": float(account.buying_power),
        "equity": float(account.equity),
        "portfolio_value": float(account.portfolio_value),
        "currency": str(account.currency),
    }


def place_paper_entry(
    ticker: str, shares: int, order_type: str = "market"
) -> dict:
    """Place a paper buy order. Returns order details dict."""
    _check_enabled()

    logger.info("[SHADOW] Placing paper BUY: %d shares of %s", shares, ticker)

    client = _get_trading_client()

    from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    if order_type == "market":
        request = MarketOrderRequest(
            symbol=ticker,
            qty=shares,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )
    else:
        raise PaperTradingError(f"Unsupported order type: {order_type}")

    order = client.submit_order(request)

    return {
        "order_id": str(order.id),
        "symbol": str(order.symbol),
        "qty": int(order.qty) if order.qty else shares,
        "side": str(order.side),
        "type": str(order.type),
        "status": str(order.status),
        "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
        "filled_at": str(order.filled_at) if order.filled_at else None,
        "created_at": str(order.created_at) if order.created_at else None,
    }


def place_paper_exit(
    ticker: str, shares: int, order_type: str = "market"
) -> dict:
    """Place a paper sell order. Returns order details dict."""
    _check_enabled()

    logger.info("[SHADOW] Placing paper SELL: %d shares of %s", shares, ticker)

    client = _get_trading_client()

    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    request = MarketOrderRequest(
        symbol=ticker,
        qty=shares,
        side=OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    )

    order = client.submit_order(request)

    return {
        "order_id": str(order.id),
        "symbol": str(order.symbol),
        "qty": int(order.qty) if order.qty else shares,
        "side": str(order.side),
        "type": str(order.type),
        "status": str(order.status),
        "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
        "filled_at": str(order.filled_at) if order.filled_at else None,
    }


def place_bracket_order(
    ticker: str,
    shares: int,
    take_profit_price: float,
    stop_loss_price: float,
    limit_price: float | None = None,
) -> dict:
    """Place a bracket order: entry + take-profit + stop-loss as one atomic order.

    When the entry fills, Alpaca automatically places:
    - A limit sell at take_profit_price
    - A stop sell at stop_loss_price
    When one exit triggers, the other auto-cancels.
    """
    _check_enabled()

    logger.info("[SHADOW] Placing BRACKET order: %d shares of %s "
                "(TP=$%.2f, SL=$%.2f)", shares, ticker,
                take_profit_price, stop_loss_price)
    logger.info("[SHADOW] Placing BRACKET order: %d shares of %s", shares, ticker)

    client = _get_trading_client()

    from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass

    if limit_price:
        request = LimitOrderRequest(
            symbol=ticker,
            qty=shares,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,
            limit_price=round(limit_price, 2),
            take_profit={"limit_price": round(take_profit_price, 2)},
            stop_loss={"stop_price": round(stop_loss_price, 2)},
        )
    else:
        request = MarketOrderRequest(
            symbol=ticker,
            qty=shares,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,
            take_profit={"limit_price": round(take_profit_price, 2)},
            stop_loss={"stop_price": round(stop_loss_price, 2)},
        )

    order = client.submit_order(request)

    return {
        "order_id": str(order.id),
        "symbol": str(order.symbol),
        "qty": int(order.qty) if order.qty else shares,
        "side": str(order.side),
        "type": str(order.type),
        "order_class": "bracket",
        "status": str(order.status),
        "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
        "legs": [str(leg.id) for leg in order.legs] if order.legs else [],
    }


def get_position(ticker: str) -> dict | None:
    """Get current position details for a ticker, or None if no position."""
    client = _get_trading_client()
    try:
        pos = client.get_open_position(ticker)
        return {
            "symbol": str(pos.symbol),
            "qty": int(pos.qty),
            "avg_entry_price": float(pos.avg_entry_price),
            "current_price": float(pos.current_price),
            "market_value": float(pos.market_value),
            "unrealized_pl": float(pos.unrealized_pl),
            "unrealized_plpc": float(pos.unrealized_plpc),
        }
    except Exception:
        return None


def get_all_positions() -> list[dict]:
    """Get all open positions."""
    client = _get_trading_client()
    positions = client.get_all_positions()
    return [
        {
            "symbol": str(pos.symbol),
            "qty": int(pos.qty),
            "avg_entry_price": float(pos.avg_entry_price),
            "current_price": float(pos.current_price),
            "market_value": float(pos.market_value),
            "unrealized_pl": float(pos.unrealized_pl),
            "unrealized_plpc": float(pos.unrealized_plpc),
        }
        for pos in positions
    ]


def get_current_price(ticker: str) -> float | None:
    """Get the latest trade price for a ticker."""
    try:
        client = _get_data_client()
        from alpaca.data.requests import StockLatestTradeRequest
        request = StockLatestTradeRequest(symbol_or_symbols=ticker)
        trades = client.get_stock_latest_trade(request)
        if ticker in trades:
            return float(trades[ticker].price)
        return None
    except Exception as e:
        logger.warning(f"Failed to get current price for {ticker}: {e}")
        return None


def get_order_status(order_id: str) -> dict:
    """Check the status of an order."""
    client = _get_trading_client()
    order = client.get_order_by_id(order_id)
    return {
        "order_id": str(order.id),
        "symbol": str(order.symbol),
        "status": str(order.status),
        "filled_qty": str(order.filled_qty) if order.filled_qty else "0",
        "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
        "filled_at": str(order.filled_at) if order.filled_at else None,
    }
