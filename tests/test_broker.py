"""Tests for broker abstraction layer."""

from unittest.mock import patch, MagicMock

import pytest

from src.shadow_trading.broker import AlpacaAdapter, BrokerAdapter, get_broker


class TestBrokerFactory:
    """Tests for get_broker factory function."""

    def test_alpaca_returns_adapter(self):
        broker = get_broker("alpaca")
        assert isinstance(broker, AlpacaAdapter)
        assert isinstance(broker, BrokerAdapter)

    def test_unknown_broker_raises(self):
        with pytest.raises(ValueError):
            get_broker("unknown_broker")

    def test_default_is_alpaca(self):
        broker = get_broker()
        assert isinstance(broker, AlpacaAdapter)


class TestAlpacaAdapterPlaceEntry:
    """Tests for AlpacaAdapter.place_entry."""

    @patch("src.shadow_trading.alpaca_adapter.place_live_entry")
    def test_place_entry_with_shares(self, mock_entry):
        mock_entry.return_value = {"order_id": "ord123", "symbol": "AAPL", "status": "accepted"}
        adapter = AlpacaAdapter()
        result = adapter.place_entry("AAPL", shares=10)
        assert result["order_id"] == "ord123"
        mock_entry.assert_called_once_with("AAPL", 10, notional=None)

    @patch("src.shadow_trading.alpaca_adapter.place_live_entry")
    def test_place_entry_with_notional(self, mock_entry):
        mock_entry.return_value = {"order_id": "ord456", "symbol": "AAPL", "status": "accepted"}
        adapter = AlpacaAdapter()
        result = adapter.place_entry("AAPL", shares=0, notional=500.0)
        assert result["symbol"] == "AAPL"
        mock_entry.assert_called_once_with("AAPL", 0, notional=500.0)


class TestAlpacaAdapterPlaceExit:
    """Tests for AlpacaAdapter.place_exit."""

    @patch("src.shadow_trading.alpaca_adapter.place_live_exit")
    def test_place_exit_with_shares(self, mock_exit):
        mock_exit.return_value = {"order_id": "exit123", "symbol": "AAPL", "status": "accepted"}
        adapter = AlpacaAdapter()
        result = adapter.place_exit("AAPL", shares=5)
        assert result["order_id"] == "exit123"
        mock_exit.assert_called_once_with("AAPL", 5)

    @patch("src.shadow_trading.alpaca_adapter.place_live_exit")
    def test_place_exit_all_shares(self, mock_exit):
        mock_exit.return_value = {"order_id": "exit456", "symbol": "AAPL", "status": "accepted"}
        adapter = AlpacaAdapter()
        result = adapter.place_exit("AAPL", shares=None)
        mock_exit.assert_called_once_with("AAPL", 0)


class TestAlpacaAdapterGetPositions:
    """Tests for AlpacaAdapter.get_positions."""

    @patch("src.shadow_trading.alpaca_adapter.get_live_positions")
    def test_get_positions(self, mock_positions):
        mock_positions.return_value = [
            {"symbol": "AAPL", "qty": 10.0, "avg_entry_price": 180.0,
             "current_price": 185.0, "unrealized_pl": 50.0},
        ]
        adapter = AlpacaAdapter()
        positions = adapter.get_positions()
        assert len(positions) == 1
        assert positions[0]["symbol"] == "AAPL"

    @patch("src.shadow_trading.alpaca_adapter.get_live_positions")
    def test_get_positions_empty(self, mock_positions):
        mock_positions.return_value = []
        adapter = AlpacaAdapter()
        assert adapter.get_positions() == []


class TestAlpacaAdapterGetAccount:
    """Tests for AlpacaAdapter.get_account."""

    @patch("src.shadow_trading.alpaca_adapter.get_account_info")
    def test_get_account(self, mock_account):
        mock_account.return_value = {
            "equity": 100500.0, "cash": 95000.0, "buying_power": 190000.0,
        }
        adapter = AlpacaAdapter()
        account = adapter.get_account()
        assert account["equity"] == 100500.0
        assert "cash" in account


class TestBrokerAbstraction:
    """Tests for the abstract BrokerAdapter interface."""

    def test_cannot_instantiate_abstract(self):
        """BrokerAdapter is abstract — cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BrokerAdapter()

    def test_alpaca_implements_all_methods(self):
        """AlpacaAdapter should implement all abstract methods."""
        adapter = AlpacaAdapter()
        assert hasattr(adapter, "place_entry")
        assert hasattr(adapter, "place_exit")
        assert hasattr(adapter, "get_positions")
        assert hasattr(adapter, "get_account")
        assert callable(adapter.place_entry)
        assert callable(adapter.place_exit)
        assert callable(adapter.get_positions)
        assert callable(adapter.get_account)
