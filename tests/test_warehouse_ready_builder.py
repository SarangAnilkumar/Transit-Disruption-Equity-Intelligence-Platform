"""Tests for warehouse-ready dataset builder."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from ingestion.build_warehouse_ready_datasets import build_datasets


def _write_processed_fixture(processed_root: Path) -> None:
    static_dir = processed_root / "gtfs_static" / "load_date=2026-05-28"
    static_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "stop_id": ["101"],
            "stop_name": ["Central"],
            "stop_lat": [-37.8136],
            "stop_lon": [144.9631],
            "location_type": [0],
            "parent_station": [""],
            "wheelchair_boarding": [0],
        }
    ).to_csv(static_dir / "stops.txt", index=False)
    pd.DataFrame(
        {
            "route_id": ["R1"],
            "route_short_name": ["CEN"],
            "route_long_name": ["City Loop"],
            "route_type": [2],
            "agency_id": ["1"],
        }
    ).to_csv(static_dir / "routes.txt", index=False)
    pd.DataFrame(
        {
            "trip_id": ["T1"],
            "route_id": ["R1"],
            "service_id": ["S1"],
            "trip_headsign": ["City"],
            "direction_id": [0],
            "shape_id": ["SH1"],
        }
    ).to_csv(static_dir / "trips.txt", index=False)
    pd.DataFrame(
        {
            "trip_id": ["T1"],
            "stop_id": ["101"],
            "stop_sequence": [1],
            "arrival_time": ["08:00:00"],
            "departure_time": ["08:01:00"],
        }
    ).to_csv(static_dir / "stop_times.txt", index=False)

    geo_dir = processed_root / "geospatial"
    geo_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "stop_id": ["101"],
            "stop_name": ["Central"],
            "stop_lat": [-37.8136],
            "stop_lon": [144.9631],
            "sa2_code": ["206011097"],
            "sa2_name": ["Melbourne"],
            "mapping_method": ["within"],
            "is_matched": [True],
            "mapping_created_at": ["2026-05-28T00:00:00+00:00"],
            "source_stops_path": ["stops.txt"],
            "source_sa2_path": ["sa2.gpkg"],
        }
    ).to_csv(geo_dir / "stops_sa2_mapping.csv", index=False)


def test_build_datasets_writes_manifest_and_outputs(tmp_path: Path) -> None:
    processed_root = tmp_path / "processed"
    output_root = tmp_path / "warehouse_ready"
    _write_processed_fixture(processed_root)

    summary = build_datasets(
        dataset_group="gtfs_static",
        processed_root=processed_root,
        output_root=output_root,
        schema_path=Path("config/warehouse_schemas.yml"),
    )

    assert "gtfs_stops" in summary["datasets_processed"]
    assert (output_root / "gtfs_static" / "gtfs_stops.csv").exists()
    assert summary["manifest_file"]
    manifest = json.loads(Path(summary["manifest_file"]).read_text())
    assert manifest["load_batch_id"]
    assert manifest["row_counts"]["gtfs_stops"] == 1


def test_build_datasets_geospatial(tmp_path: Path) -> None:
    processed_root = tmp_path / "processed"
    output_root = tmp_path / "warehouse_ready"
    _write_processed_fixture(processed_root)

    summary = build_datasets(
        dataset_group="geospatial",
        processed_root=processed_root,
        output_root=output_root,
        schema_path=Path("config/warehouse_schemas.yml"),
    )

    assert "stops_sa2_mapping" in summary["datasets_processed"]
    assert (output_root / "quality_reports" / "stops_sa2_mapping_quality_report.json").exists()
