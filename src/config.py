"""Configuration loader for the AI Research Desk.

Loads settings from config/settings.local.yaml, falling back to
config/settings.example.yaml if the local file does not exist.
"""

import sys
from pathlib import Path

import yaml


def load_config() -> dict:
    """Load and return the application configuration dict."""
    config_dir = Path(__file__).resolve().parent.parent / "config"
    local_path = config_dir / "settings.local.yaml"
    example_path = config_dir / "settings.example.yaml"

    if local_path.exists():
        config_path = local_path
    elif example_path.exists():
        print(
            "WARNING: config/settings.local.yaml not found, "
            "falling back to config/settings.example.yaml",
            file=sys.stderr,
        )
        config_path = example_path
    else:
        print("ERROR: No configuration file found.", file=sys.stderr)
        return {}

    with open(config_path, "r") as f:
        return yaml.safe_load(f) or {}
