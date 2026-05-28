"""Tests for realtime auth helpers and parser edge cases."""

from __future__ import annotations

from pathlib import Path

import pytest

from ingestion.fetch_gtfs_realtime import (
    AuthConfig,
    FetchResult,
    _build_metadata,
    build_request_auth,
)
from ingestion.parse_gtfs_realtime import parse_feed_message

gtfs_pb2 = pytest.importorskip("google.transit.gtfs_realtime_pb2")


def test_build_request_auth_header_mode() -> None:
    auth = AuthConfig(
        api_key="secret",
        auth_mode="header",
        header_name="Ocp-Apim-Subscription-Key",
        query_param_name="subscription-key",
    )
    headers, params, mode = build_request_auth(auth)
    assert mode == "header"
    assert headers == {"Ocp-Apim-Subscription-Key": "secret"}
    assert params == {}


def test_build_request_auth_query_mode() -> None:
    auth = AuthConfig(
        api_key="secret",
        auth_mode="query",
        header_name="KeyID",
        query_param_name="subscription-key",
    )
    headers, params, mode = build_request_auth(auth)
    assert mode == "query"
    assert headers == {}
    assert params == {"subscription-key": "secret"}


def test_build_metadata_structure() -> None:
    auth = AuthConfig(
        api_key="secret",
        auth_mode="query",
        header_name="KeyID",
        query_param_name="subscription-key",
    )
    fetch_result = FetchResult(
        ok=True,
        status_code=200,
        content_type="application/x-protobuf",
        content_length=123,
        response_preview=None,
        payload=b"abc",
        url_called="https://example.com/feed",
        error_message=None,
    )
    metadata = _build_metadata(
        feed_name="trip_updates",
        source_url="https://example.com/feed",
        output_file=Path("data/raw/feed.pb"),
        request_timestamp_utc="2026-01-01T00:00:00+00:00",
        fetch_result=fetch_result,
        auth_mode_used="query",
        auth=auth,
    )
    assert metadata["feed_name"] == "trip_updates"
    assert metadata["http_status_code"] == 200
    assert metadata["content_type"] == "application/x-protobuf"
    assert metadata["content_length"] == 123
    assert metadata["api_query_param_name_used"] == "subscription-key"
    assert "output_file" in metadata


def test_parse_trip_updates_with_and_without_stop_time_updates() -> None:
    message = gtfs_pb2.FeedMessage()
    message.header.gtfs_realtime_version = "2.0"
    message.header.timestamp = 1700000000

    entity_with_stops = message.entity.add()
    entity_with_stops.id = "e1"
    trip_update = entity_with_stops.trip_update
    trip_update.trip.trip_id = "t1"
    trip_update.trip.route_id = "r1"
    stu = trip_update.stop_time_update.add()
    stu.stop_sequence = 1
    stu.stop_id = "s1"
    stu.arrival.delay = 120

    entity_without_stops = message.entity.add()
    entity_without_stops.id = "e2"
    entity_without_stops.trip_update.trip.trip_id = "t2"

    df = parse_feed_message("trip_updates", message)
    assert len(df) == 2
    assert set(df["entity_id"]) == {"e1", "e2"}
    row_no_stops = df[df["entity_id"] == "e2"].iloc[0]
    assert row_no_stops["stop_id"] is None


def test_parse_service_alerts_handles_missing_informed_entities() -> None:
    message = gtfs_pb2.FeedMessage()
    message.header.gtfs_realtime_version = "2.0"

    alert_entity = message.entity.add()
    alert_entity.id = "a1"
    alert = alert_entity.alert
    alert.header_text.translation.add(text="Minor delay")
    alert.description_text.translation.add(text="Platform update")

    df = parse_feed_message("service_alerts", message)
    assert len(df) == 1
    assert df.iloc[0]["entity_id"] == "a1"
    assert df.iloc[0]["header_text"] == "Minor delay"
    assert df.iloc[0]["informed_route_id"] is None
