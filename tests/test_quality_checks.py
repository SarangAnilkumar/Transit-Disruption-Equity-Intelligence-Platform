"""Tests for local quality checks and reconciliation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ingestion.reconcile_processed_outputs import reconcile
from ingestion.run_local_quality_checks import run_checks
from ingestion.warehouse_utils import get_dataset_schema, load_schema_registry, run_quality_checks


def test_quality_checks_trip_update_delay_warning(registry: dict | None = None) -> None:
    registry = registry or load_schema_registry(Path("config/warehouse_schemas.yml"))
    schema = get_dataset_schema(registry, "gtfs_trip_updates")
    schema = dict(schema)
    schema["allow_empty"] = True
    df = pd.DataFrame(
        {
            "feed_name": ["trip_updates"],
            "snapshot_timestamp": ["2026-05-28T07:00:00+00:00"],
            "entity_id": ["e1"],
            "arrival_delay_seconds": ["99999"],
            "departure_delay_seconds": ["0"],
        }
    )
    checks = run_quality_checks(df, schema)
    assert any("outside [-3600, 86400]" in warning for warning in checks["warnings"])


def test_run_checks_summary(tmp_path: Path) -> None:
    input_root = tmp_path / "warehouse_ready"
    (input_root / "gtfs_static").mkdir(parents=True)
    pd.DataFrame(
        {
            "stop_id": ["101"],
            "stop_name": ["Central"],
            "stop_lat": ["-37.8136"],
            "stop_lon": ["144.9631"],
            "warehouse_dataset": ["gtfs_stops"],
            "source_file": ["stops.txt"],
            "prepared_at": ["2026-05-28T00:00:00+00:00"],
            "load_batch_id": ["batch-1"],
        }
    ).to_csv(input_root / "gtfs_static" / "gtfs_stops.csv", index=False)

    summary = run_checks("gtfs_stops", input_root, Path("config/warehouse_schemas.yml"))
    assert "gtfs_stops" in summary["datasets_checked"]
    assert summary["passed"]


def test_reconcile_match(tmp_path: Path) -> None:
    processed_root = tmp_path / "processed"
    warehouse_root = tmp_path / "warehouse_ready"
    static_dir = processed_root / "gtfs_static" / "load_date=2026-05-28"
    static_dir.mkdir(parents=True)
    stops = pd.DataFrame(
        {
            "stop_id": ["101", "102"],
            "stop_name": ["Central", "Flinders"],
            "stop_lat": [-37.8, -37.9],
            "stop_lon": [144.9, 145.0],
        }
    )
    stops.to_csv(static_dir / "stops.txt", index=False)

    wh_dir = warehouse_root / "gtfs_static"
    wh_dir.mkdir(parents=True)
    stops.assign(
        warehouse_dataset="gtfs_stops",
        source_file="stops.txt",
        prepared_at="2026-05-28T00:00:00+00:00",
        load_batch_id="batch-1",
    ).to_csv(wh_dir / "gtfs_stops.csv", index=False)

    report = reconcile("gtfs_stops", processed_root, warehouse_root, Path("config/warehouse_schemas.yml"))
    assert report["matches"] == 1
    assert report["entries"][0]["status"] == "match"


def test_reconcile_mismatch(tmp_path: Path) -> None:
    processed_root = tmp_path / "processed"
    warehouse_root = tmp_path / "warehouse_ready"
    static_dir = processed_root / "gtfs_static" / "load_date=2026-05-28"
    static_dir.mkdir(parents=True)
    pd.DataFrame({"stop_id": ["101"], "stop_name": ["Central"], "stop_lat": [-37.8], "stop_lon": [144.9]}).to_csv(
        static_dir / "stops.txt", index=False
    )

    wh_dir = warehouse_root / "gtfs_static"
    wh_dir.mkdir(parents=True)
    pd.DataFrame({"stop_id": ["101"], "stop_name": ["Central"], "stop_lat": [-37.8], "stop_lon": [144.9]}).to_csv(
        wh_dir / "gtfs_stops.csv", index=False
    )
    # Append an extra row to warehouse file to force mismatch
    extra = pd.read_csv(wh_dir / "gtfs_stops.csv")
    extra = pd.concat([extra, extra], ignore_index=True)
    extra.to_csv(wh_dir / "gtfs_stops.csv", index=False)

    report = reconcile("gtfs_stops", processed_root, warehouse_root, Path("config/warehouse_schemas.yml"))
    assert report["mismatches"] == 1
