"""Tests for geospatial mapping helper logic."""

from __future__ import annotations

import pandas as pd

from ingestion.geospatial_utils import (
    STOPS_SA2_MAPPING_COLUMNS,
    aggregate_route_sa2,
    detect_sa2_columns,
    validate_stop_columns,
    valid_coordinate_mask,
)


def test_detect_sa2_columns_variants() -> None:
    code_col, name_col = detect_sa2_columns(["SA2_MAIN21", "SA2_NAME21", "geometry"])
    assert code_col == "SA2_MAIN21"
    assert name_col == "SA2_NAME21"


def test_validate_stop_columns_missing() -> None:
    df = pd.DataFrame({"stop_id": ["s1"], "stop_lat": [1.0], "stop_lon": [2.0]})
    try:
        validate_stop_columns(df)
        assert False, "Expected ValueError when stop_name is missing"
    except ValueError as exc:
        assert "stop_name" in str(exc)


def test_valid_coordinate_mask_flags_invalid_rows() -> None:
    df = pd.DataFrame(
        [
            {"stop_id": "s1", "stop_name": "Valid", "stop_lat": -37.8, "stop_lon": 144.9},
            {"stop_id": "s2", "stop_name": "BadLat", "stop_lat": 999, "stop_lon": 144.9},
            {"stop_id": "s3", "stop_name": "BadLon", "stop_lat": -37.8, "stop_lon": "abc"},
        ]
    )
    mask = valid_coordinate_mask(df)
    assert mask.tolist() == [True, False, False]


def test_stops_sa2_mapping_schema_columns_defined() -> None:
    assert "stop_id" in STOPS_SA2_MAPPING_COLUMNS
    assert "is_matched" in STOPS_SA2_MAPPING_COLUMNS
    assert len(STOPS_SA2_MAPPING_COLUMNS) == 11


def test_route_sa2_aggregation_schema_and_counts() -> None:
    routes_df = pd.DataFrame(
        [
            {"route_id": "r1", "route_short_name": "M1", "route_long_name": "Metro 1", "route_type": 2},
        ]
    )
    trips_df = pd.DataFrame([{"trip_id": "t1", "route_id": "r1"}])
    stop_times_df = pd.DataFrame(
        [
            {"trip_id": "t1", "stop_id": "s1", "stop_sequence": 1},
            {"trip_id": "t1", "stop_id": "s2", "stop_sequence": 2},
        ]
    )
    mapping_df = pd.DataFrame(
        [
            {"stop_id": "s1", "sa2_code": "20601", "sa2_name": "Area A", "is_matched": True},
            {"stop_id": "s2", "sa2_code": "20601", "sa2_name": "Area A", "is_matched": True},
        ]
    )
    out = aggregate_route_sa2(routes_df, trips_df, stop_times_df, mapping_df)
    assert list(out.columns) == [
        "route_id",
        "route_short_name",
        "route_long_name",
        "route_type",
        "sa2_code",
        "sa2_name",
        "stop_count_in_sa2",
        "trip_count_serving_sa2",
        "first_stop_sequence",
        "last_stop_sequence",
    ]
    assert len(out) == 1
    assert out.iloc[0]["stop_count_in_sa2"] == 2
