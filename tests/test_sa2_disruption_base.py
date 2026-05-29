"""Tests for SA2 disruption aggregation logic."""

from __future__ import annotations

import pandas as pd

from ingestion.geospatial_utils import aggregate_sa2_disruption


def test_sa2_disruption_aggregation_metrics() -> None:
    updates = pd.DataFrame(
        [
            {
                "snapshot_timestamp": "2026-05-28T07:54:00+00:00",
                "entity_id": "e1",
                "trip_id": "t1",
                "stop_id": "s1",
                "arrival_delay_seconds": 400,
                "departure_delay_seconds": 200,
            },
            {
                "snapshot_timestamp": "2026-05-28T07:54:00+00:00",
                "entity_id": "e2",
                "trip_id": "t2",
                "stop_id": "s2",
                "arrival_delay_seconds": 10,
                "departure_delay_seconds": 20,
            },
        ]
    )
    mapping = pd.DataFrame(
        [
            {"stop_id": "s1", "sa2_code": "20601", "sa2_name": "Area A", "is_matched": True},
            {"stop_id": "s2", "sa2_code": "20601", "sa2_name": "Area A", "is_matched": True},
        ]
    )

    out, report = aggregate_sa2_disruption(updates, mapping)
    assert len(out) == 1
    row = out.iloc[0]
    assert row["observation_count"] == 2
    assert row["delayed_observation_count"] == 1
    assert row["distinct_stop_count"] == 2
    assert report["total_observations"] == 2


def test_sa2_disruption_unmatched_observations_counted() -> None:
    updates = pd.DataFrame(
        [
            {
                "snapshot_timestamp": "2026-05-28T07:54:00+00:00",
                "entity_id": "e1",
                "trip_id": "t1",
                "stop_id": "missing_stop",
                "arrival_delay_seconds": 0,
                "departure_delay_seconds": 0,
            }
        ]
    )
    mapping = pd.DataFrame(
        [{"stop_id": "s1", "sa2_code": "20601", "sa2_name": "Area A", "is_matched": True}]
    )
    out, report = aggregate_sa2_disruption(updates, mapping)
    assert len(out) == 1
    assert out.iloc[0]["unmatched_stop_observation_count"] == 1
    assert report["unmatched_observations"] == 1
