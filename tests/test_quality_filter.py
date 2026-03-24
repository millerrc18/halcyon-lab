"""Tests for LLM-as-judge quality filtering."""

import pytest
from unittest.mock import patch
import json


def test_quality_judge_prompt_format():
    from src.training.quality_filter import QUALITY_JUDGE_PROMPT
    assert "thesis_clarity" in QUALITY_JUDGE_PROMPT
    assert "evidence_quality" in QUALITY_JUDGE_PROMPT
    assert "risk_assessment" in QUALITY_JUDGE_PROMPT
    assert "technical_accuracy" in QUALITY_JUDGE_PROMPT
    assert "calibration" in QUALITY_JUDGE_PROMPT
    assert "actionability" in QUALITY_JUDGE_PROMPT


@patch("src.training.claude_client.generate_training_example")
def test_score_training_example_valid(mock_generate):
    from src.training.quality_filter import score_training_example

    mock_generate.return_value = json.dumps({
        "thesis_clarity": 4, "evidence_quality": 3, "risk_assessment": 4,
        "technical_accuracy": 5, "calibration": 3, "actionability": 4,
        "overall": 3.8, "issues": "Minor calibration gap"
    })

    result = score_training_example("input text", "output text")
    assert result is not None
    assert result["overall"] == 3.8
    assert result["thesis_clarity"] == 4


@patch("src.training.claude_client.generate_training_example")
def test_score_training_example_no_overall(mock_generate):
    from src.training.quality_filter import score_training_example

    mock_generate.return_value = json.dumps({
        "thesis_clarity": 4, "evidence_quality": 3, "risk_assessment": 4,
        "technical_accuracy": 5, "calibration": 3, "actionability": 4,
    })

    result = score_training_example("input", "output")
    assert result is not None
    assert "overall" in result
    assert abs(result["overall"] - 3.8) < 0.1


@patch("src.training.claude_client.generate_training_example")
def test_score_training_example_failure(mock_generate):
    from src.training.quality_filter import score_training_example

    mock_generate.return_value = None
    result = score_training_example("input", "output")
    assert result is None


@patch("src.training.claude_client.generate_training_example")
def test_score_training_example_invalid_json(mock_generate):
    from src.training.quality_filter import score_training_example

    mock_generate.return_value = "This is not JSON at all."
    result = score_training_example("input", "output")
    assert result is None
