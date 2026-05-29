"""Tests for warehouse utility helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ingestion.warehouse_utils import (
    add_load_metadata,
    build_reconciliation_entry,
    calculate_duplicate_counts,
    coerce_column_types,
    get_dataset_schema,
    load_schema_registry,
    resolve_dataset_names,
    run_quality_checks,
    standardize_dataset,
    validate_required_columns,
)


@pytest.fixture
def registry() -> dict:
    return load_schema_registry(Path("config/warehouse_schemas.yml"))


def test_load_schema_registry(registry: dict) -> None:
    assert "datasets" in registry
    assert "gtfs_stops" in registry["datasets"]
    assert registry["metadata_columns"]


def test_resolve_dataset_names(registry: dict) -> None:
    static = resolve_dataset_names(registry, "gtfs_static")
    assert static == ["gtfs_stops", "gtfs_routes", "gtfs_trips", "gtfs_stop_times"]


def test_validate_required_columns_pass() -> None:
    schema = {"required_columns": ["stop_id", "stop_name"]}
    df = pd.DataFrame({"stop_id": ["1"], "stop_name": ["Central"]})
    assert validate_required_columns(df, schema) == []


def test_validate_required_columns_fail() -> None:
    schema = {"required_columns": ["stop_id", "stop_name"]}
    df = pd.DataFrame({"stop_id": ["1"]})
    assert validate_required_columns(df, schema) == ["stop_name"]


def test_coerce_column_types() -> None:
    schema = {
        "column_types": {
            "stop_id": "string",
            "stop_lat": "float",
            "location_type": "integer",
        }
    }
    df = pd.DataFrame({"stop_id": ["101"], "stop_lat": ["-37.8"], "location_type": ["0"]})
    coerced = coerce_column_types(df, schema)
    assert coerced["stop_lat"].iloc[0] == pytest.approx(-37.8)
    assert str(coerced["stop_id"].dtype) == "string"


def test_add_load_metadata() -> None:
    df = pd.DataFrame({"stop_id": ["1"]})
    enriched = add_load_metadata(df, "source.csv", "gtfs_stops", "batch-1", prepared_at="2026-01-01T00:00:00+00:00")
    assert list(enriched.columns) == ["stop_id", "warehouse_dataset", "source_file", "prepared_at", "load_batch_id"]
    assert enriched["warehouse_dataset"].iloc[0] == "gtfs_stops"


def test_calculate_duplicate_counts() -> None:
    df = pd.DataFrame({"stop_id": ["1", "1", "2"], "stop_name": ["A", "A", "B"]})
    assert calculate_duplicate_counts(df, ["stop_id"]) == 2


def test_standardize_dataset(registry: dict) -> None:
    schema = get_dataset_schema(registry, "gtfs_stops")
    df = pd.DataFrame(
        {
            "stop_id": ["101"],
            "stop_name": ["Central"],
            "stop_lat": ["-37.8136"],
            "stop_lon": ["144.9631"],
            "extra_col": ["ignore"],
        }
    )
    out = standardize_dataset(df, schema, "stops.txt", "batch-abc")
    assert "extra_col" not in out.columns
    assert "warehouse_dataset" in out.columns
    assert out["stop_id"].iloc[0] == "101"


def test_run_quality_checks_passes_for_valid_stops(registry: dict) -> None:
    schema = get_dataset_schema(registry, "gtfs_stops")
    df = pd.DataFrame(
        {
            "stop_id": ["101"],
            "stop_name": ["Central"],
            "stop_lat": ["-37.8136"],
            "stop_lon": ["144.9631"],
        }
    )
    checks = run_quality_checks(df, schema)
    assert not checks["errors"]
    assert checks["passed"]


def test_run_quality_checks_errors_on_missing_columns(registry: dict) -> None:
    schema = get_dataset_schema(registry, "gtfs_stops")
    df = pd.DataFrame({"stop_id": ["101"]})
    checks = run_quality_checks(df, schema)
    assert checks["errors"]


def test_build_reconciliation_entry() -> None:
    entry = build_reconciliation_entry("gtfs_stops", 100, 100, ["a.txt"], "b.csv")
    assert entry["status"] == "match"
    assert entry["delta"] == 0
