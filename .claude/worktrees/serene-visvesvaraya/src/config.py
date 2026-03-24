"""Centralized config loader for the AI Research Desk."""

import sys
from pathlib import Path

import yaml


def load_config() -> dict:
    """Load settings from config/settings.local.yaml, falling back to settings.example.yaml."""
    base_dir = Path(__file__).resolve().parent.parent / "config"
    local_path = base_dir / "settings.local.yaml"
    example_path = base_dir / "settings.example.yaml"

    if local_path.exists():
        config_path = local_path
    elif example_path.exists():
        print(
            "WARNING: config/settings.local.yaml not found, using settings.example.yaml. "
            "Copy it and fill in your credentials.",
            file=sys.stderr,
        )
        config_path = example_path
    else:
        print("ERROR: No config file found in config/", file=sys.stderr)
        return {}

    with open(config_path, "r") as f:
        return yaml.safe_load(f) or {}
