"""Broker abstraction layer.

Defines a minimal interface that any broker adapter must implement.
This prevents lock-in to Alpaca and makes adding Interactive Brokers
(or any other broker) in Phase 2 straightforward.

Current implementation: AlpacaAdapter wraps the existing alpaca_adapter.py functions.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BrokerAdapter(ABC):
    """Abstract base class for broker integrations."""

    @abstractmethod
    def place_entry(self, ticker: str, shares: int, notional: float | None = None) -> dict:
        """Place a buy order.

        Args:
            ticker: Stock symbol
            shares: Number of shares (0 if using notional)
            notional: Dollar amount (for fractional shares)

        Returns:
            Order result dict with at minimum: order_id, symbol, status
        """
        ...

    @abstractmethod
    def place_exit(self, ticker: str, shares: int | None = None) -> dict:
        """Close a position.

        Args:
            ticker: Stock symbol
            shares: Number of shares to sell (None = close entire position)

        Returns:
            Order result dict
        """
        ...

    @abstractmethod
    def get_positions(self) -> list[dict]:
        """Get all open positions.

        Returns:
            List of position dicts with: symbol, qty, avg_entry_price, current_price, unrealized_pnl
        """
        ...

    @abstractmethod
    def get_account(self) -> dict:
        """Get account summary.

        Returns:
            Dict with: equity, cash, buying_power
        """
        ...


class AlpacaAdapter(BrokerAdapter):
    """Alpaca Markets broker adapter using existing alpaca_adapter.py functions."""

    def place_entry(self, ticker: str, shares: int, notional: float | None = None) -> dict:
        from src.shadow_trading.alpaca_adapter import place_live_entry
        return place_live_entry(ticker, shares, notional=notional)

    def place_exit(self, ticker: str, shares: int | None = None) -> dict:
        from src.shadow_trading.alpaca_adapter import place_live_exit
        return place_live_exit(ticker, shares or 0)

    def get_positions(self) -> list[dict]:
        from src.shadow_trading.alpaca_adapter import get_live_positions
        return get_live_positions()

    def get_account(self) -> dict:
        from src.shadow_trading.alpaca_adapter import get_account_info
        return get_account_info()


def get_broker(name: str = "alpaca") -> BrokerAdapter:
    """Factory function to get the configured broker adapter."""
    if name == "alpaca":
        return AlpacaAdapter()
    raise ValueError(f"Unknown broker: {name}. Available: alpaca")
