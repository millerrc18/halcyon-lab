"""Tests for the Render cloud API (read-only FastAPI)."""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    """Set DATABASE_URL for all tests."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/halcyon")
    monkeypatch.delenv("API_SECRET", raising=False)


@pytest.fixture
def client():
    """Create a test client for the cloud API."""
    # Re-import to pick up env vars
    from src.api.cloud_app import app
    return TestClient(app)


@pytest.fixture
def authed_client(monkeypatch):
    """Create a test client with API_SECRET set."""
    monkeypatch.setenv("API_SECRET", "test-secret-token")
    # Must re-import to pick up the new env var
    import importlib
    import src.api.cloud_app as cloud_mod
    importlib.reload(cloud_mod)
    return TestClient(cloud_mod.app)


# ── Mock helpers ─────────────────────────────────────────────────────

def _mock_query(return_value):
    """Return a patch for _query that returns the given value."""
    return patch("src.api.cloud_app._query", return_value=return_value)


def _mock_query_one(return_value):
    """Return a patch for _query_one that returns the given value."""
    return patch("src.api.cloud_app._query_one", return_value=return_value)


# ── Status endpoint ──────────────────────────────────────────────────

class TestStatusEndpoint:
    """Tests for /api/status."""

    @patch("src.api.cloud_app._query_one")
    @patch("src.api.cloud_app._query")
    def test_status_returns_structure(self, mock_query, mock_query_one, client):
        mock_query.return_value = [{"count": 3}]
        mock_query_one.return_value = {"version_name": "v1.0", "created_at": "2025-01-01", "status": "active"}

        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["environment"] == "cloud"
        assert "open_positions" in data
        assert "timestamp" in data
        assert data["llm_available"] is False

    @patch("src.api.cloud_app._query_one")
    @patch("src.api.cloud_app._query")
    def test_status_handles_db_error(self, mock_query, mock_query_one, client):
        mock_query.side_effect = Exception("connection error")

        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data


# ── Shadow trade endpoints ───────────────────────────────────────────

class TestShadowEndpoints:
    """Tests for shadow trading endpoints."""

    @patch("src.api.cloud_app._query")
    def test_shadow_open_returns_trades(self, mock_query, client):
        mock_query.return_value = [
            {"trade_id": "t1", "ticker": "AAPL", "status": "open"},
        ]
        resp = client.get("/api/shadow/open")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["trades"][0]["ticker"] == "AAPL"

    @patch("src.api.cloud_app._query")
    def test_shadow_closed_accepts_days_param(self, mock_query, client):
        mock_query.return_value = []
        resp = client.get("/api/shadow/closed?days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert data["days"] == 7

    @patch("src.api.cloud_app._query")
    def test_shadow_metrics_computes_stats(self, mock_query, client):
        mock_query.return_value = [
            {"pnl_dollars": 100.0, "pnl_pct": 5.0},
            {"pnl_dollars": -50.0, "pnl_pct": -2.5},
            {"pnl_dollars": 75.0, "pnl_pct": 3.0},
        ]
        resp = client.get("/api/shadow/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_trades"] == 3
        assert data["wins"] == 2
        assert data["losses"] == 1
        assert data["total_pnl"] == 125.0


# ── Packets endpoint ─────────────────────────────────────────────────

class TestPacketsEndpoint:
    """Tests for /api/packets."""

    @patch("src.api.cloud_app._query")
    def test_packets_returns_list(self, mock_query, client):
        mock_query.return_value = [
            {"recommendation_id": "r1", "ticker": "AAPL", "created_at": "2025-01-01"},
        ]
        resp = client.get("/api/packets")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1


# ── Training endpoints ───────────────────────────────────────────────

class TestTrainingEndpoints:
    """Tests for training endpoints."""

    @patch("src.api.cloud_app._query")
    @patch("src.api.cloud_app._query_one")
    def test_training_status(self, mock_one, mock_query, client):
        mock_one.return_value = {"version_name": "v1.0", "status": "active"}
        mock_query.return_value = [{"count": 5}]

        resp = client.get("/api/training/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_model" in data
        assert data["total_versions"] == 5

    @patch("src.api.cloud_app._query")
    def test_training_versions(self, mock_query, client):
        mock_query.return_value = [
            {"version_id": "v1", "version_name": "v1.0"},
            {"version_id": "v2", "version_name": "v2.0"},
        ]
        resp = client.get("/api/training/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2


# ── Metrics endpoint ─────────────────────────────────────────────────

class TestMetricsEndpoint:
    """Tests for /api/metrics/history."""

    @patch("src.api.cloud_app._query")
    def test_metrics_history(self, mock_query, client):
        mock_query.return_value = [
            {"snapshot_id": "s1", "metrics_json": '{"win_rate": 0.6}', "created_at": "2025-01-01"},
        ]
        resp = client.get("/api/metrics/history")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        # JSON field should be parsed
        assert data[0]["metrics_json"] == {"win_rate": 0.6}


# ── Schedule metrics endpoint ────────────────────────────────────────

class TestScheduleMetricsEndpoint:
    """Tests for /api/schedule-metrics."""

    @patch("src.api.cloud_app._query")
    def test_schedule_metrics(self, mock_query, client):
        mock_query.return_value = [
            {"metric_date": "2025-01-01", "metric_name": "gpu_util", "metric_value": 85.0},
        ]
        resp = client.get("/api/schedule-metrics")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ── Earnings endpoint ────────────────────────────────────────────────

class TestEarningsEndpoint:
    """Tests for /api/earnings."""

    @patch("src.api.cloud_app._query")
    def test_earnings(self, mock_query, client):
        mock_query.return_value = [
            {"ticker": "AAPL", "earnings_date": "2025-01-25", "earnings_time": "AMC"},
        ]
        resp = client.get("/api/earnings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["earnings"][0]["ticker"] == "AAPL"


# ── Audit endpoint ───────────────────────────────────────────────────

class TestAuditEndpoint:
    """Tests for /api/audit/latest."""

    @patch("src.api.cloud_app._query_one")
    def test_audit_latest(self, mock_one, client):
        mock_one.return_value = {
            "audit_id": "a1",
            "overall_assessment": "healthy",
            "flags": '["flag1"]',
            "metrics_to_watch": '{"win_rate": 0.55}',
        }
        resp = client.get("/api/audit/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_assessment"] == "healthy"
        assert data["flags"] == ["flag1"]

    @patch("src.api.cloud_app._query_one")
    def test_audit_latest_empty(self, mock_one, client):
        mock_one.return_value = None
        resp = client.get("/api/audit/latest")
        assert resp.status_code == 200
        assert resp.json()["audit"] is None


# ── Docs endpoint ────────────────────────────────────────────────────

class TestDocsEndpoint:
    """Tests for /api/docs."""

    def test_docs_returns_note(self, client):
        resp = client.get("/api/docs")
        assert resp.status_code == 200
        data = resp.json()
        assert "note" in data
        assert data["docs"] == []


# ── Council endpoints ────────────────────────────────────────────────

class TestCouncilEndpoints:
    """Tests for council endpoints."""

    @patch("src.api.cloud_app._query")
    @patch("src.api.cloud_app._query_one")
    def test_council_latest_with_votes(self, mock_one, mock_query, client):
        mock_one.return_value = {
            "session_id": "s1",
            "session_type": "weekly",
            "consensus": "bullish",
        }
        mock_query.return_value = [
            {"vote_id": "v1", "agent_name": "technician", "key_data_points": None, "risk_flags": None},
        ]
        resp = client.get("/api/council/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "s1"
        assert len(data["votes"]) == 1

    @patch("src.api.cloud_app._query_one")
    def test_council_latest_empty(self, mock_one, client):
        mock_one.return_value = None
        resp = client.get("/api/council/latest")
        assert resp.status_code == 200
        assert resp.json()["session"] is None

    @patch("src.api.cloud_app._query")
    def test_council_history(self, mock_query, client):
        mock_query.return_value = [
            {"session_id": "s1", "created_at": "2025-01-01"},
        ]
        resp = client.get("/api/council/history")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ── Auth tests ───────────────────────────────────────────────────────

class TestAuth:
    """Tests for bearer token authentication."""

    def test_no_auth_required_when_no_secret(self, client):
        """When API_SECRET is not set, all endpoints are accessible."""
        with patch("src.api.cloud_app._query", return_value=[{"count": 0}]), \
             patch("src.api.cloud_app._query_one", return_value=None):
            resp = client.get("/api/status")
            assert resp.status_code == 200

    def test_auth_required_when_secret_set(self, monkeypatch):
        """When API_SECRET is set, requests without token get 401."""
        monkeypatch.setenv("API_SECRET", "my-secret")
        import importlib
        import src.api.cloud_app as cloud_mod
        importlib.reload(cloud_mod)

        test_client = TestClient(cloud_mod.app)
        resp = test_client.get("/api/status")
        assert resp.status_code == 401

    def test_auth_succeeds_with_correct_token(self, monkeypatch):
        """Correct bearer token grants access."""
        monkeypatch.setenv("API_SECRET", "my-secret")
        import importlib
        import src.api.cloud_app as cloud_mod
        importlib.reload(cloud_mod)

        test_client = TestClient(cloud_mod.app)
        with patch.object(cloud_mod, "_query", return_value=[{"count": 0}]), \
             patch.object(cloud_mod, "_query_one", return_value=None):
            resp = test_client.get(
                "/api/status",
                headers={"Authorization": "Bearer my-secret"},
            )
            assert resp.status_code == 200

    def test_auth_fails_with_wrong_token(self, monkeypatch):
        """Wrong bearer token gets 401."""
        monkeypatch.setenv("API_SECRET", "my-secret")
        import importlib
        import src.api.cloud_app as cloud_mod
        importlib.reload(cloud_mod)

        test_client = TestClient(cloud_mod.app)
        resp = test_client.get(
            "/api/status",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 401


# ── No write endpoints test ──────────────────────────────────────────

class TestReadOnly:
    """Verify the cloud API has no write endpoints."""

    def test_no_post_endpoints(self, client):
        """Cloud API should not expose any POST endpoints."""
        routes = client.app.routes
        post_routes = []
        for route in routes:
            if hasattr(route, "methods") and "POST" in route.methods:
                post_routes.append(route.path)
        assert post_routes == [], f"Found POST endpoints: {post_routes}"

    def test_no_put_endpoints(self, client):
        """Cloud API should not expose any PUT endpoints."""
        routes = client.app.routes
        put_routes = []
        for route in routes:
            if hasattr(route, "methods") and "PUT" in route.methods:
                put_routes.append(route.path)
        assert put_routes == [], f"Found PUT endpoints: {put_routes}"

    def test_no_delete_endpoints(self, client):
        """Cloud API should not expose any DELETE endpoints."""
        routes = client.app.routes
        delete_routes = []
        for route in routes:
            if hasattr(route, "methods") and "DELETE" in route.methods:
                delete_routes.append(route.path)
        assert delete_routes == [], f"Found DELETE endpoints: {delete_routes}"

    def test_all_endpoints_are_get(self, client):
        """Every API endpoint should be GET-only."""
        routes = client.app.routes
        for route in routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                if route.path.startswith("/api/"):
                    allowed = route.methods - {"HEAD", "OPTIONS"}
                    assert allowed == {"GET"}, (
                        f"{route.path} has methods {allowed}, expected only GET"
                    )
