"""Tests for the AI Council system.

Mocks the Claude API to test agent data payloads, protocol rounds,
vote tallying, devil's advocate rotation, and session storage.
"""

import json
import sqlite3
import uuid
from datetime import datetime
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo

import pytest

ET = ZoneInfo("America/New_York")

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_agent_response(
    agent: str,
    position: str = "neutral",
    confidence: int = 7,
    vote: str = "hold_steady",
) -> str:
    """Build a mock Claude response string for a given agent."""
    return json.dumps(
        {
            "agent": agent,
            "position": position,
            "confidence": confidence,
            "recommendation": f"Mock analysis from {agent}.",
            "key_data_points": [f"{agent}_point_1", f"{agent}_point_2"],
            "risk_flags": [],
            "vote": vote,
        }
    )


@pytest.fixture
def council_db(tmp_path):
    """Create a test database with the council and supporting tables."""
    db_path = str(tmp_path / "test_council.sqlite3")
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS council_sessions (
            session_id TEXT PRIMARY KEY,
            session_type TEXT NOT NULL,
            trigger_reason TEXT,
            created_at TEXT NOT NULL,
            consensus TEXT,
            confidence_weighted_score REAL,
            is_contested INTEGER DEFAULT 0,
            total_cost REAL,
            rounds_completed INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS council_votes (
            vote_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            round INTEGER NOT NULL,
            position TEXT,
            confidence INTEGER,
            recommendation TEXT,
            key_data_points TEXT,
            risk_flags TEXT,
            vote TEXT,
            is_devils_advocate INTEGER DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES council_sessions(session_id)
        );

        CREATE TABLE IF NOT EXISTS recommendations (
            recommendation_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            ticker TEXT NOT NULL,
            company_name TEXT,
            priority_score REAL,
            confidence_score REAL,
            setup_type TEXT,
            trend_state TEXT,
            relative_strength_state TEXT,
            pullback_depth_pct REAL,
            market_regime TEXT,
            entry_zone TEXT,
            stop_level TEXT,
            target_1 TEXT,
            target_2 TEXT,
            sector_context TEXT,
            recommendation TEXT,
            thesis_text TEXT,
            enriched_prompt TEXT
        );

        CREATE TABLE IF NOT EXISTS shadow_trades (
            trade_id TEXT PRIMARY KEY,
            recommendation_id TEXT,
            ticker TEXT NOT NULL,
            direction TEXT DEFAULT 'long',
            status TEXT NOT NULL,
            entry_price REAL,
            stop_price REAL,
            target_1 REAL,
            target_2 REAL,
            planned_shares INTEGER,
            actual_exit_price REAL,
            pnl_dollars REAL,
            pnl_pct REAL,
            exit_reason TEXT,
            max_favorable_excursion REAL,
            max_adverse_excursion REAL,
            actual_exit_time TEXT,
            created_at TEXT NOT NULL,
            shadow_duration_days REAL
        );

        CREATE TABLE IF NOT EXISTS vix_daily (
            date TEXT PRIMARY KEY,
            vix_open REAL,
            vix_high REAL,
            vix_low REAL,
            vix_close REAL
        );

        CREATE TABLE IF NOT EXISTS fred_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            series_id TEXT,
            date TEXT,
            value REAL
        );

        CREATE TABLE IF NOT EXISTS training_examples (
            example_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            quality_score REAL,
            quality_grade TEXT,
            purpose TEXT
        );

        CREATE TABLE IF NOT EXISTS model_versions (
            version_id TEXT PRIMARY KEY,
            version_name TEXT,
            status TEXT,
            created_at TEXT,
            training_examples_count INTEGER,
            trade_count INTEGER,
            win_rate REAL
        );
        """
    )
    # Seed some test data
    now = datetime.now(ET).isoformat()
    conn.execute(
        "INSERT INTO recommendations VALUES (?, ?, 'AAPL', 'Apple', 85.0, 8, "
        "'momentum', 'uptrend', 'strong', 2.5, 'risk_on', '175-177', '170', "
        "'185', '195', 'Technology', 'BUY', 'Strong momentum', NULL)",
        (str(uuid.uuid4()), now),
    )
    conn.execute(
        "INSERT INTO shadow_trades VALUES (?, NULL, 'AAPL', 'long', 'open', "
        "176.0, 170.0, 185.0, 195.0, 50, NULL, NULL, NULL, NULL, NULL, NULL, NULL, ?, NULL)",
        (str(uuid.uuid4()), now),
    )
    conn.execute(
        "INSERT INTO vix_daily VALUES (?, 15.0, 16.0, 14.5, 15.2)",
        (datetime.now(ET).strftime("%Y-%m-%d"),),
    )
    conn.commit()
    conn.close()
    return db_path


# ---------------------------------------------------------------------------
# Agent data payload tests
# ---------------------------------------------------------------------------


class TestAgentDataPayloads:
    """Test that each agent's data gathering function returns a dict."""

    def test_risk_officer_returns_dict(self, council_db):
        from src.council.agents import gather_risk_officer_data

        result = gather_risk_officer_data(db_path=council_db)
        assert isinstance(result, dict)
        assert "open_trades" in result
        assert "vix_data" in result

    def test_alpha_strategist_returns_dict(self, council_db):
        from src.council.agents import gather_alpha_strategist_data

        result = gather_alpha_strategist_data(db_path=council_db)
        assert isinstance(result, dict)
        assert "top_candidates" in result

    def test_data_scientist_returns_dict(self, council_db):
        from src.council.agents import gather_data_scientist_data

        result = gather_data_scientist_data(db_path=council_db)
        assert isinstance(result, dict)
        assert "score_distribution" in result

    def test_regime_analyst_returns_dict(self, council_db):
        from src.council.agents import gather_regime_analyst_data

        result = gather_regime_analyst_data(db_path=council_db)
        assert isinstance(result, dict)
        assert "vix_term_structure" in result

    def test_devils_advocate_returns_dict(self, council_db):
        from src.council.agents import gather_devils_advocate_data

        mock_assessments = [{"agent": "risk_officer", "vote": "hold_steady"}]
        result = gather_devils_advocate_data(mock_assessments, db_path=council_db)
        assert isinstance(result, dict)
        assert "round1_assessments" in result
        assert result["round1_assessments"] == mock_assessments

    def test_data_functions_return_empty_on_bad_db(self):
        """All data functions should return empty dict on failure."""
        from src.council.agents import (
            gather_risk_officer_data,
            gather_alpha_strategist_data,
            gather_data_scientist_data,
            gather_regime_analyst_data,
        )

        bad_path = "/nonexistent/path/db.sqlite3"
        assert gather_risk_officer_data(db_path=bad_path) == {}
        assert gather_alpha_strategist_data(db_path=bad_path) == {}
        assert gather_data_scientist_data(db_path=bad_path) == {}
        assert gather_regime_analyst_data(db_path=bad_path) == {}


# ---------------------------------------------------------------------------
# Protocol round tests
# ---------------------------------------------------------------------------


class TestProtocolRounds:
    """Test the three-round Delphi protocol logic."""

    @patch("src.council.protocol._call_claude")
    def test_round_1_produces_5_assessments(self, mock_claude, council_db):
        """Round 1 should produce one assessment per agent (5 total)."""
        from src.council.protocol import run_round_1, build_shared_context

        # Mock Claude to return valid JSON for each agent
        def side_effect(system_prompt, user_prompt, temperature=0.8):
            # Determine which agent from the system prompt
            for name in [
                "risk_officer",
                "alpha_strategist",
                "data_scientist",
                "regime_analyst",
                "devils_advocate",
            ]:
                if name in system_prompt.lower().replace(" ", "_").replace("'", ""):
                    return _make_agent_response(name)
            return _make_agent_response("unknown")

        mock_claude.side_effect = side_effect

        context = build_shared_context(council_db)
        assessments = run_round_1(context, db_path=council_db)

        assert len(assessments) == 5
        agent_names = {a["agent"] for a in assessments}
        assert "risk_officer" in agent_names
        assert "devils_advocate" in agent_names

    @patch("src.council.protocol._call_claude")
    def test_round_2_produces_5_assessments(self, mock_claude, council_db):
        """Round 2 should produce one assessment per agent."""
        from src.council.protocol import run_round_2

        mock_claude.return_value = _make_agent_response("test_agent")

        round1 = [
            json.loads(_make_agent_response(name))
            for name in [
                "risk_officer",
                "alpha_strategist",
                "data_scientist",
                "regime_analyst",
                "devils_advocate",
            ]
        ]

        assessments = run_round_2(round1)
        assert len(assessments) == 5

    @patch("src.council.protocol._call_claude")
    def test_round_3_produces_5_assessments(self, mock_claude, council_db):
        """Round 3 should produce one assessment per agent."""
        from src.council.protocol import run_round_3

        mock_claude.return_value = _make_agent_response("test_agent")

        round2 = [
            json.loads(_make_agent_response(name))
            for name in [
                "risk_officer",
                "alpha_strategist",
                "data_scientist",
                "regime_analyst",
                "devils_advocate",
            ]
        ]

        assessments = run_round_3(round2)
        assert len(assessments) == 5

    @patch("src.council.protocol._call_claude")
    def test_round_1_handles_api_failure(self, mock_claude, council_db):
        """If Claude returns None, agents should get default responses."""
        from src.council.protocol import run_round_1, build_shared_context

        mock_claude.return_value = None

        context = build_shared_context(council_db)
        assessments = run_round_1(context, db_path=council_db)

        assert len(assessments) == 5
        for a in assessments:
            assert a["confidence"] == 3  # default
            assert a["vote"] == "hold_steady"  # default

    @patch("src.council.protocol._call_claude")
    def test_round_1_handles_malformed_json(self, mock_claude, council_db):
        """Malformed JSON should trigger fallback to default response."""
        from src.council.protocol import run_round_1, build_shared_context

        mock_claude.return_value = "This is not valid JSON at all {{{}"

        context = build_shared_context(council_db)
        assessments = run_round_1(context, db_path=council_db)

        assert len(assessments) == 5
        for a in assessments:
            assert a["vote"] == "hold_steady"


# ---------------------------------------------------------------------------
# Vote tallying tests
# ---------------------------------------------------------------------------


class TestVoteTallying:
    def test_clear_supermajority(self):
        """When one vote has >66% weighted confidence, consensus is reached."""
        from src.council.protocol import tally_votes

        assessments = [
            {"agent": "a", "vote": "hold_steady", "confidence": 9},
            {"agent": "b", "vote": "hold_steady", "confidence": 8},
            {"agent": "c", "vote": "hold_steady", "confidence": 7},
            {"agent": "d", "vote": "increase_exposure", "confidence": 3},
            {"agent": "e", "vote": "reduce_exposure", "confidence": 2},
        ]

        result = tally_votes(assessments)
        assert result["consensus"] == "hold_steady"
        assert result["is_contested"] is False
        assert result["confidence_weighted_score"] > 66.0

    def test_contested_vote(self):
        """When no vote reaches 66%, result is contested."""
        from src.council.protocol import tally_votes

        assessments = [
            {"agent": "a", "vote": "hold_steady", "confidence": 5},
            {"agent": "b", "vote": "hold_steady", "confidence": 4},
            {"agent": "c", "vote": "increase_exposure", "confidence": 5},
            {"agent": "d", "vote": "increase_exposure", "confidence": 4},
            {"agent": "e", "vote": "reduce_exposure", "confidence": 5},
        ]

        result = tally_votes(assessments)
        assert result["is_contested"] is True
        assert result["consensus"] == "contested"
        assert "human review" in result["reason"]

    def test_unanimous_vote(self):
        """Unanimous vote should have 100% weighted score."""
        from src.council.protocol import tally_votes

        assessments = [
            {"agent": f"agent_{i}", "vote": "reduce_exposure", "confidence": 8}
            for i in range(5)
        ]

        result = tally_votes(assessments)
        assert result["consensus"] == "reduce_exposure"
        assert result["confidence_weighted_score"] == 100.0
        assert result["is_contested"] is False

    def test_empty_assessments(self):
        """Empty list should return contested hold_steady."""
        from src.council.protocol import tally_votes

        result = tally_votes([])
        assert result["is_contested"] is True
        assert result["consensus"] == "hold_steady"

    def test_confidence_weighting_matters(self):
        """A minority with high confidence can tip the balance."""
        from src.council.protocol import tally_votes

        # 2 agents vote increase with confidence 10 each = 20
        # 3 agents vote hold with confidence 3 each = 9
        # Total = 29, increase = 20/29 = 69% > 66%
        assessments = [
            {"agent": "a", "vote": "increase_exposure", "confidence": 10},
            {"agent": "b", "vote": "increase_exposure", "confidence": 10},
            {"agent": "c", "vote": "hold_steady", "confidence": 3},
            {"agent": "d", "vote": "hold_steady", "confidence": 3},
            {"agent": "e", "vote": "hold_steady", "confidence": 3},
        ]

        result = tally_votes(assessments)
        assert result["consensus"] == "increase_exposure"
        assert result["is_contested"] is False


# ---------------------------------------------------------------------------
# Devil's Advocate rotation
# ---------------------------------------------------------------------------


class TestDevilsAdvocate:
    @patch("src.council.protocol._call_claude")
    def test_devils_advocate_sees_round1(self, mock_claude, council_db):
        """The devil's advocate should receive all Round 1 assessments."""
        from src.council.protocol import run_round_1, build_shared_context

        calls = []

        def capture_calls(system_prompt, user_prompt, temperature=0.8):
            calls.append(
                {"system": system_prompt, "user": user_prompt}
            )
            return _make_agent_response("test")

        mock_claude.side_effect = capture_calls

        context = build_shared_context(council_db)
        run_round_1(context, db_path=council_db)

        # The 5th call (index 4) should be the devil's advocate
        assert len(calls) == 5
        da_call = calls[4]
        assert "Devil's Advocate" in da_call["system"]
        assert "ROUND 1 ASSESSMENTS" in da_call["user"]

    @patch("src.council.protocol._call_claude")
    def test_devils_advocate_is_flagged_in_votes(self, mock_claude, council_db):
        """Devil's advocate votes should be marked in the database."""
        from src.council.engine import CouncilEngine

        mock_claude.return_value = _make_agent_response("test")

        engine = CouncilEngine(db_path=council_db)
        result = engine.run_session(session_type="test")

        conn = sqlite3.connect(council_db)
        conn.row_factory = sqlite3.Row
        da_votes = conn.execute(
            "SELECT * FROM council_votes WHERE is_devils_advocate = 1"
        ).fetchall()
        conn.close()

        # Should have one DA vote per round (3 rounds)
        assert len(da_votes) == 3


# ---------------------------------------------------------------------------
# Session storage tests
# ---------------------------------------------------------------------------


class TestSessionStorage:
    @patch("src.council.protocol._call_claude")
    def test_full_session_stores_in_db(self, mock_claude, council_db):
        """A complete session should persist to council_sessions and council_votes."""
        from src.council.engine import CouncilEngine

        mock_claude.return_value = _make_agent_response(
            "test", vote="hold_steady", confidence=8
        )

        engine = CouncilEngine(db_path=council_db)
        result = engine.run_session(session_type="daily")

        assert result["rounds_completed"] == 3
        assert result["session_id"] is not None

        # Check database
        conn = sqlite3.connect(council_db)
        conn.row_factory = sqlite3.Row

        session = conn.execute(
            "SELECT * FROM council_sessions WHERE session_id = ?",
            (result["session_id"],),
        ).fetchone()
        assert session is not None
        assert session["session_type"] == "daily"
        assert session["rounds_completed"] == 3

        votes = conn.execute(
            "SELECT COUNT(*) as n FROM council_votes WHERE session_id = ?",
            (result["session_id"],),
        ).fetchone()
        # 5 agents x 3 rounds = 15 votes
        assert votes["n"] == 15

        conn.close()

    @patch("src.council.protocol._call_claude")
    def test_session_tracks_cost(self, mock_claude, council_db):
        """Session should estimate and record API cost."""
        from src.council.engine import CouncilEngine

        mock_claude.return_value = _make_agent_response("test")

        engine = CouncilEngine(db_path=council_db)
        result = engine.run_session()

        assert result["total_cost"] > 0

        conn = sqlite3.connect(council_db)
        conn.row_factory = sqlite3.Row
        session = conn.execute(
            "SELECT total_cost FROM council_sessions WHERE session_id = ?",
            (result["session_id"],),
        ).fetchone()
        conn.close()

        assert session["total_cost"] > 0

    @patch("src.council.protocol._call_claude")
    def test_get_session_retrieves_data(self, mock_claude, council_db):
        """get_session should return session + votes."""
        from src.council.engine import CouncilEngine

        mock_claude.return_value = _make_agent_response("test")

        engine = CouncilEngine(db_path=council_db)
        result = engine.run_session()

        retrieved = engine.get_session(result["session_id"])
        assert retrieved is not None
        assert "session" in retrieved
        assert "votes" in retrieved
        assert len(retrieved["votes"]) == 15

    @patch("src.council.protocol._call_claude")
    def test_get_recent_sessions(self, mock_claude, council_db):
        """get_recent_sessions should return session list."""
        from src.council.engine import CouncilEngine

        mock_claude.return_value = _make_agent_response("test")

        engine = CouncilEngine(db_path=council_db)
        engine.run_session(session_type="daily")
        engine.run_session(session_type="emergency")

        recent = engine.get_recent_sessions(limit=5)
        assert len(recent) == 2


# ---------------------------------------------------------------------------
# Response parsing edge cases
# ---------------------------------------------------------------------------


class TestResponseParsing:
    def test_parse_valid_json(self):
        from src.council.protocol import _parse_agent_response

        raw = _make_agent_response("risk_officer", confidence=8)
        result = _parse_agent_response(raw, "risk_officer")
        assert result["confidence"] == 8
        assert result["agent"] == "risk_officer"

    def test_parse_json_with_markdown_fences(self):
        from src.council.protocol import _parse_agent_response

        raw = "```json\n" + _make_agent_response("risk_officer") + "\n```"
        result = _parse_agent_response(raw, "risk_officer")
        assert result["agent"] == "risk_officer"

    def test_parse_json_embedded_in_text(self):
        from src.council.protocol import _parse_agent_response

        raw = (
            "Here is my analysis:\n"
            + _make_agent_response("risk_officer")
            + "\nThat concludes my review."
        )
        result = _parse_agent_response(raw, "risk_officer")
        assert result["agent"] == "risk_officer"

    def test_parse_none_returns_default(self):
        from src.council.protocol import _parse_agent_response

        result = _parse_agent_response(None, "risk_officer")
        assert result["agent"] == "risk_officer"
        assert result["confidence"] == 3
        assert result["vote"] == "hold_steady"

    def test_confidence_clamped(self):
        from src.council.protocol import _parse_agent_response

        raw = json.dumps({"confidence": 99, "vote": "hold_steady"})
        result = _parse_agent_response(raw, "test")
        assert result["confidence"] == 10

        raw = json.dumps({"confidence": -5, "vote": "hold_steady"})
        result = _parse_agent_response(raw, "test")
        assert result["confidence"] == 1

    def test_invalid_vote_normalized(self):
        from src.council.protocol import _parse_agent_response

        raw = json.dumps({"vote": "yolo_all_in", "confidence": 5})
        result = _parse_agent_response(raw, "test")
        assert result["vote"] == "hold_steady"

    def test_invalid_position_normalized(self):
        from src.council.protocol import _parse_agent_response

        raw = json.dumps({"position": "extreme_bullish", "confidence": 5})
        result = _parse_agent_response(raw, "test")
        assert result["position"] == "neutral"
