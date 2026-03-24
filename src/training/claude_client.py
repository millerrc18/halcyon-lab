"""Claude API client for generating training data."""

import logging

from src.config import load_config

logger = logging.getLogger(__name__)


def generate_training_example(system_prompt: str, user_prompt: str) -> str | None:
    """Generate a training example using the Anthropic Claude API.

    Args:
        system_prompt: System prompt for the generation.
        user_prompt: User prompt with feature/outcome data.

    Returns:
        Generated text, or None on failure.
    """
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic package not installed. Run: pip install anthropic")
        return None

    config = load_config()
    training_cfg = config.get("training", {})
    api_key = training_cfg.get("anthropic_api_key", "")

    if not api_key or api_key == "your-anthropic-api-key-here":
        logger.warning("Anthropic API key not configured")
        return None

    model = training_cfg.get("claude_model", "claude-haiku-4-5-20251001")

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model,
            max_tokens=1500,
            temperature=0.5,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text
    except Exception as e:
        logger.warning("Claude API call failed: %s", e)
        return None
