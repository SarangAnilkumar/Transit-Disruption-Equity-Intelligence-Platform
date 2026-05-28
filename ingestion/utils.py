"""Shared utility helpers for ingestion scripts."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import yaml


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Create a simple project logger with consistent formatting."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logging.getLogger("transit_ingestion")


def load_env() -> None:
    """Load environment variables from .env if present."""
    load_dotenv(override=False)


def load_settings(settings_path: str | Path = "config/settings.example.yml") -> dict[str, Any]:
    """Load YAML settings file if available, else return empty dict."""
    path = Path(settings_path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    return loaded if isinstance(loaded, dict) else {}


def resolve_env_or_config(env_key: str, config_value: str | None = None) -> str:
    """Resolve value from env first, then config literal/template."""
    env_value = os.getenv(env_key, "").strip()
    if env_value:
        return env_value
    if not config_value:
        return ""
    if config_value.startswith("${") and config_value.endswith("}"):
        nested_env = config_value[2:-1]
        return os.getenv(nested_env, "").strip()
    return config_value


def ensure_dir(path: str | Path) -> Path:
    """Ensure a directory exists and return it as Path."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def get_timestamp_parts(ts: datetime | None = None) -> dict[str, str]:
    """Return UTC timestamp parts for partitioned folder paths."""
    timestamp = ts or datetime.now(timezone.utc)
    return {
        "iso": timestamp.isoformat(),
        "date": timestamp.strftime("%Y-%m-%d"),
        "year": timestamp.strftime("%Y"),
        "month": timestamp.strftime("%m"),
        "day": timestamp.strftime("%d"),
        "hour": timestamp.strftime("%H"),
        "minute": timestamp.strftime("%M"),
    }


def save_bytes_to_file(content: bytes, output_path: str | Path) -> Path:
    """Write bytes content to file, creating parent directories as needed."""
    destination = Path(output_path)
    ensure_dir(destination.parent)
    destination.write_bytes(content)
    return destination


def save_json_to_file(payload: dict[str, Any], output_path: str | Path) -> Path:
    """Write JSON payload to file with stable formatting."""
    destination = Path(output_path)
    ensure_dir(destination.parent)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return destination
