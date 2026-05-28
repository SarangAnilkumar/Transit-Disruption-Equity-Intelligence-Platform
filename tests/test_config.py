"""Configuration and env loading tests."""

from pathlib import Path

from ingestion.utils import load_env, load_settings, resolve_env_or_config


def test_settings_example_exists() -> None:
    assert Path("config/settings.example.yml").exists()


def test_load_env_no_dotenv_file(monkeypatch) -> None:
    monkeypatch.delenv("GTFS_STATIC_URL", raising=False)
    load_env()
    assert True


def test_config_paths_resolve() -> None:
    settings = load_settings("config/settings.example.yml")
    assert settings.get("paths", {}).get("raw_data_dir") == "data/raw"
    assert settings.get("paths", {}).get("processed_data_dir") == "data/processed"


def test_env_or_config_resolution(monkeypatch) -> None:
    monkeypatch.delenv("SAMPLE_KEY", raising=False)
    assert resolve_env_or_config("SAMPLE_KEY", "fallback") == "fallback"
