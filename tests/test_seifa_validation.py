"""Tests for SEIFA SA2 validation helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ingestion.seifa_validation import (
    clean_seifa_sa2_dataframe,
    is_valid_sa2_code,
    is_valid_sa2_name,
    validate_seifa_sa2_quality,
)
from ingestion.warehouse_utils import run_quality_checks


def test_is_valid_sa2_code() -> None:
    assert is_valid_sa2_code("206011097")
    assert not is_valid_sa2_code("© Commonwealth of Australia 2023")
    assert not is_valid_sa2_code("12345")
    assert not is_valid_sa2_code(None)


def test_footer_row_is_dropped() -> None:
    df = pd.DataFrame(
        {
            "sa2_code": ["206011097", "© Commonwealth of Australia 2023"],
            "sa2_name": ["Melbourne", None],
            "seifa_release_year": [2021, 2021],
            "irsd_score": [980.1, None],
            "irsd_decile": [4.0, None],
            "irsd_percentile": [40.0, None],
            "source_file": ["x.xlsx", "x.xlsx"],
            "prepared_at": ["2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"],
        }
    )
    cleaned, stats = clean_seifa_sa2_dataframe(df)
    assert len(cleaned) == 1
    assert stats["dropped_invalid_sa2_code_rows"] == 1
    assert cleaned.iloc[0]["sa2_code"] == "206011097"


def test_non_numeric_irsd_score_rows_are_dropped() -> None:
    df = pd.DataFrame(
        {
            "sa2_code": ["206011097", "206011098"],
            "sa2_name": ["Melbourne", "Carlton"],
            "seifa_release_year": [2021, 2021],
            "irsd_score": [980.1, "not-a-number"],
            "source_file": ["x.xlsx", "x.xlsx"],
            "prepared_at": ["2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"],
        }
    )
    cleaned, stats = clean_seifa_sa2_dataframe(df)
    assert len(cleaned) == 1
    assert stats["dropped_missing_score_rows"] == 1


def test_validate_seifa_sa2_quality_flags_invalid_rows() -> None:
    df = pd.DataFrame(
        {
            "sa2_code": ["206011097", "© Commonwealth of Australia 2023"],
            "sa2_name": ["Melbourne", "Footer"],
            "irsd_score": [980.1, None],
        }
    )
    errors = validate_seifa_sa2_quality(df)
    assert errors
    assert any("9-digit" in message for message in errors)


def test_warehouse_quality_checks_fail_on_invalid_seifa(tmp_path: Path) -> None:
    from ingestion.warehouse_utils import get_dataset_schema, load_schema_registry

    registry = load_schema_registry()
    schema = get_dataset_schema(registry, "seifa_sa2_ready")
    df = pd.DataFrame(
        {
            "sa2_code": ["206011097", "© Commonwealth of Australia 2023"],
            "sa2_name": ["Melbourne", "Footer"],
            "seifa_release_year": [2021, 2021],
            "irsd_score": [980.1, None],
            "irsd_decile": [4.0, None],
            "irsd_percentile": [40.0, None],
            "warehouse_dataset": ["seifa_sa2_ready", "seifa_sa2_ready"],
            "source_file": ["a.csv", "a.csv"],
            "prepared_at": ["2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"],
            "load_batch_id": ["batch-1", "batch-1"],
        }
    )
    checks = run_quality_checks(df, schema)
    assert checks["errors"]
