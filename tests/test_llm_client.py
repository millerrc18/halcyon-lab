"""Tests for the LLM client module."""

from unittest.mock import patch, MagicMock

from src.llm.client import is_llm_available, generate, _strip_think_blocks


class TestIsLlmAvailable:
    def test_returns_true_when_reachable(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("src.llm.client.requests.get", return_value=mock_resp):
            assert is_llm_available() is True

    def test_returns_false_when_unreachable(self):
        with patch("src.llm.client.requests.get", side_effect=ConnectionError):
            assert is_llm_available() is False

    def test_returns_boolean(self):
        with patch("src.llm.client.requests.get", side_effect=Exception("any error")):
            result = is_llm_available()
            assert isinstance(result, bool)
            assert result is False


class TestGenerate:
    def test_returns_none_when_unreachable(self):
        with patch("src.llm.client.requests.post", side_effect=ConnectionError):
            result = generate("hello", "system prompt")
            assert result is None

    def test_returns_content_on_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Hello world"}}]
        }
        mock_resp.raise_for_status = MagicMock()
        with patch("src.llm.client.requests.post", return_value=mock_resp):
            result = generate("hello", "system prompt")
            assert result == "Hello world"

    def test_strips_think_blocks(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "<think>internal reasoning</think>Clean output"}}]
        }
        mock_resp.raise_for_status = MagicMock()
        with patch("src.llm.client.requests.post", return_value=mock_resp):
            result = generate("hello", "system prompt")
            assert result == "Clean output"
            assert "<think>" not in result


class TestStripThinkBlocks:
    def test_strips_single_block(self):
        text = "<think>some reasoning here</think>The actual response."
        assert _strip_think_blocks(text) == "The actual response."

    def test_strips_multiple_blocks(self):
        text = "<think>block1</think>Hello <think>block2</think>world"
        assert _strip_think_blocks(text) == "Hello world"

    def test_strips_multiline_block(self):
        text = "<think>\nline1\nline2\n</think>Clean output"
        assert _strip_think_blocks(text) == "Clean output"

    def test_no_think_blocks(self):
        text = "Just normal text"
        assert _strip_think_blocks(text) == "Just normal text"
