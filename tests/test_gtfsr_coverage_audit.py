"""Tests for GTFS-R snapshot coverage audit."""

from __future__ import annotations

from pathlib import Path

from ingestion.audit_gtfsr_snapshot_coverage import _sufficiency_rating, build_coverage_report


def test_sufficiency_rating_thresholds() -> None:
    assert _sufficiency_rating(0) == "insufficient"
    assert _sufficiency_rating(1) == "exploratory"
    assert _sufficiency_rating(7) == "analyst-ready"
    assert _sufficiency_rating(14) == "strong"


def test_build_coverage_report_empty(tmp_path: Path) -> None:
    report = build_coverage_report(tmp_path)
    assert report["total_snapshots"] == 0
    assert report["data_sufficiency_rating"] == "insufficient"
