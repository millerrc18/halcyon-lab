"""Tests for Traffic Light regime overlay."""
import sqlite3
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.features.traffic_light import (
    _classify_vix, _classify_trend, _classify_credit,
    _score_to_regime, compute_traffic_light,
)


class TestVIXClassifier:
    def test_low_vix_green(self):
        assert _classify_vix(15.0) == 0

    def test_mid_vix_yellow(self):
        assert _classify_vix(22.0) == 1

    def test_high_vix_red(self):
        assert _classify_vix(30.0) == 2

    def test_none_vix(self):
        assert _classify_vix(None) == 0


class TestTrendClassifier:
    def test_above_rising_green(self):
        # Create SPY data that's above and rising 200-DMA
        dates = pd.date_range("2025-01-01", periods=250)
        prices = pd.Series(np.linspace(100, 150, 250), index=dates)
        spy = pd.DataFrame({"Close": prices})
        assert _classify_trend(spy) == 0

    def test_below_200dma_red(self):
        # Create SPY data that drops below 200-DMA
        dates = pd.date_range("2025-01-01", periods=250)
        prices = pd.Series(
            list(np.linspace(100, 150, 200)) + list(np.linspace(150, 100, 50)),
            index=dates
        )
        spy = pd.DataFrame({"Close": prices})
        assert _classify_trend(spy) == 2

    def test_empty_dataframe(self):
        assert _classify_trend(pd.DataFrame()) == 0

    def test_none(self):
        assert _classify_trend(None) == 0


class TestScoreToRegime:
    def test_green_range(self):
        assert _score_to_regime(0) == "GREEN"
        assert _score_to_regime(2) == "GREEN"

    def test_yellow_range(self):
        assert _score_to_regime(3) == "YELLOW"
        assert _score_to_regime(4) == "YELLOW"

    def test_red_range(self):
        assert _score_to_regime(5) == "RED"
        assert _score_to_regime(6) == "RED"


class TestComputeTrafficLight:
    def test_returns_expected_keys(self, tmp_path):
        db = str(tmp_path / "tl.sqlite3")
        result = compute_traffic_light(vix=15.0, db_path=db)
        assert "regime_label" in result
        assert "total_score" in result
        assert "sizing_multiplier" in result
        assert "persistence_applied" in result

    def test_green_with_low_vix(self, tmp_path):
        db = str(tmp_path / "tl.sqlite3")
        result = compute_traffic_light(vix=12.0, db_path=db)
        assert result["regime_label"] == "GREEN"
        assert result["sizing_multiplier"] == 1.0

    def test_persistence_filter(self, tmp_path):
        db = str(tmp_path / "tl.sqlite3")
        # Create a bearish SPY (below 200-DMA) to push trend score to 2
        dates = pd.date_range("2025-01-01", periods=250)
        prices = pd.Series(
            list(np.linspace(100, 150, 200)) + list(np.linspace(150, 100, 50)),
            index=dates
        )
        bearish_spy = pd.DataFrame({"Close": prices})

        # First call: GREEN with low VIX and no SPY
        r1 = compute_traffic_light(vix=12.0, db_path=db)
        assert r1["regime_label"] == "GREEN"

        # Second call: high VIX + bearish SPY → raw score 4 (YELLOW) but persistence holds GREEN
        r2 = compute_traffic_light(spy=bearish_spy, vix=30.0, db_path=db)
        assert r2["persistence_applied"] is True
        assert r2["regime_label"] == "GREEN"  # Held by persistence

        # Third call: still bearish, now persistence allows switch
        r3 = compute_traffic_light(spy=bearish_spy, vix=30.0, db_path=db)
        assert r3["regime_label"] == "YELLOW"  # Switches after 2 consecutive
