"""Tests for SEIFA detection helpers."""

from __future__ import annotations

from ingestion.geospatial_utils import detect_seifa_columns


def test_detect_seifa_columns_success() -> None:
    columns = ["SA2_CODE21", "SA2_NAME21", "IRSD score", "IRSD decile", "IRSD percentile"]
    detected = detect_seifa_columns(columns)
    assert detected["sa2_code"] == "SA2_CODE21"
    assert detected["sa2_name"] == "SA2_NAME21"
    assert detected["irsd_score"] == "IRSD score"
    assert detected["irsd_decile"] == "IRSD decile"
    assert detected["irsd_percentile"] == "IRSD percentile"


def test_detect_seifa_columns_missing_required_score() -> None:
    columns = ["SA2_CODE21", "SA2_NAME21", "Some Other Field"]
    detected = detect_seifa_columns(columns)
    assert detected["sa2_code"] == "SA2_CODE21"
    assert detected["sa2_name"] == "SA2_NAME21"
    assert detected["irsd_score"] is None
