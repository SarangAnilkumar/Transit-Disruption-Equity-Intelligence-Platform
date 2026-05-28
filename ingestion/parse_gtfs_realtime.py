"""Parse GTFS-Realtime protobuf files into normalized CSV outputs."""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.utils import ensure_dir, get_timestamp_parts, load_env, load_settings, setup_logging

try:
    from google.transit import gtfs_realtime_pb2
except ModuleNotFoundError:  # pragma: no cover - runtime dependency guard
    gtfs_realtime_pb2 = None

TRIP_UPDATE_COLUMNS = [
    "feed_name",
    "snapshot_timestamp",
    "entity_id",
    "trip_id",
    "route_id",
    "start_time",
    "start_date",
    "schedule_relationship",
    "stop_sequence",
    "stop_id",
    "arrival_delay_seconds",
    "arrival_time",
    "departure_delay_seconds",
    "departure_time",
]

SERVICE_ALERT_COLUMNS = [
    "feed_name",
    "snapshot_timestamp",
    "entity_id",
    "cause",
    "effect",
    "active_period_start",
    "active_period_end",
    "informed_route_id",
    "informed_stop_id",
    "informed_trip_id",
    "header_text",
    "description_text",
]


def _safe_get(obj: Any, attr: str) -> Any:
    """Return attribute value if present, else None."""
    return getattr(obj, attr) if hasattr(obj, attr) else None


def _extract_ts_from_feed(feed_message: gtfs_realtime_pb2.FeedMessage) -> str:
    """Extract snapshot timestamp in ISO8601 from GTFS-R header if available."""
    feed_ts = _safe_get(feed_message.header, "timestamp")
    if feed_ts:
        return datetime.fromtimestamp(feed_ts, tz=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def parse_trip_updates(feed_message: gtfs_realtime_pb2.FeedMessage, snapshot_ts: str) -> list[dict[str, Any]]:
    """Parse trip update entities into flat row records."""
    rows: list[dict[str, Any]] = []
    for entity in feed_message.entity:
        if not entity.HasField("trip_update"):
            continue
        trip_update = entity.trip_update
        trip = trip_update.trip
        trip_base = {
            "feed_name": "trip_updates",
            "snapshot_timestamp": snapshot_ts,
            "entity_id": entity.id or None,
            "trip_id": trip.trip_id or None,
            "route_id": trip.route_id or None,
            "start_time": trip.start_time or None,
            "start_date": trip.start_date or None,
            "schedule_relationship": str(trip.schedule_relationship)
            if hasattr(trip, "schedule_relationship")
            else None,
        }
        if not trip_update.stop_time_update:
            rows.append(
                {
                    **trip_base,
                    "stop_sequence": None,
                    "stop_id": None,
                    "arrival_delay_seconds": None,
                    "arrival_time": None,
                    "departure_delay_seconds": None,
                    "departure_time": None,
                }
            )
            continue
        for stu in trip_update.stop_time_update:
            rows.append(
                {
                    **trip_base,
                    "stop_sequence": stu.stop_sequence if stu.HasField("stop_sequence") else None,
                    "stop_id": stu.stop_id if stu.stop_id else None,
                    "arrival_delay_seconds": stu.arrival.delay
                    if stu.HasField("arrival") and stu.arrival.HasField("delay")
                    else None,
                    "arrival_time": datetime.fromtimestamp(stu.arrival.time, tz=timezone.utc).isoformat()
                    if stu.HasField("arrival") and stu.arrival.HasField("time")
                    else None,
                    "departure_delay_seconds": stu.departure.delay
                    if stu.HasField("departure") and stu.departure.HasField("delay")
                    else None,
                    "departure_time": datetime.fromtimestamp(
                        stu.departure.time, tz=timezone.utc
                    ).isoformat()
                    if stu.HasField("departure") and stu.departure.HasField("time")
                    else None,
                }
            )
    return rows


def _extract_translation_text(translation_field: Any) -> str | None:
    """Extract first translation text value if present."""
    if not translation_field or not translation_field.translation:
        return None
    return translation_field.translation[0].text if translation_field.translation[0].text else None


def parse_service_alerts(feed_message: gtfs_realtime_pb2.FeedMessage, snapshot_ts: str) -> list[dict[str, Any]]:
    """Parse service alert entities into flat row records."""
    rows: list[dict[str, Any]] = []
    for entity in feed_message.entity:
        if not entity.HasField("alert"):
            continue
        alert = entity.alert
        periods = list(alert.active_period) or [None]
        informed_entities = list(alert.informed_entity) or [None]
        for period in periods:
            for informed in informed_entities:
                rows.append(
                    {
                        "feed_name": "service_alerts",
                        "snapshot_timestamp": snapshot_ts,
                        "entity_id": entity.id or None,
                        "cause": str(alert.cause) if hasattr(alert, "cause") else None,
                        "effect": str(alert.effect) if hasattr(alert, "effect") else None,
                        "active_period_start": datetime.fromtimestamp(period.start, tz=timezone.utc).isoformat()
                        if period and period.HasField("start")
                        else None,
                        "active_period_end": datetime.fromtimestamp(period.end, tz=timezone.utc).isoformat()
                        if period and period.HasField("end")
                        else None,
                        "informed_route_id": informed.route_id if informed and informed.route_id else None,
                        "informed_stop_id": informed.stop_id if informed and informed.stop_id else None,
                        "informed_trip_id": informed.trip.trip_id
                        if informed and informed.HasField("trip") and informed.trip.trip_id
                        else None,
                        "header_text": _extract_translation_text(alert.header_text),
                        "description_text": _extract_translation_text(alert.description_text),
                    }
                )
    return rows


def parse_feed(feed_name: str, pb_path: Path) -> pd.DataFrame:
    """Parse a protobuf file path into a pandas DataFrame."""
    feed_message = gtfs_realtime_pb2.FeedMessage()
    feed_message.ParseFromString(pb_path.read_bytes())
    snapshot_ts = _extract_ts_from_feed(feed_message)

    if feed_name == "trip_updates":
        rows = parse_trip_updates(feed_message, snapshot_ts)
        return pd.DataFrame(rows, columns=TRIP_UPDATE_COLUMNS)
    rows = parse_service_alerts(feed_message, snapshot_ts)
    return pd.DataFrame(rows, columns=SERVICE_ALERT_COLUMNS)


def _extract_path_part(pattern: str, file_path: str, fallback: str) -> str:
    """Extract partition values from input path when possible."""
    match = re.search(pattern, file_path)
    return match.group(1) if match else fallback


def build_output_path(processed_root: Path, feed_name: str, input_path: Path) -> Path:
    """Build processed output path aligned to partition convention."""
    input_text = str(input_path)
    ts = get_timestamp_parts()
    parts = {
        "year": _extract_path_part(r"year=(\d{4})", input_text, ts["year"]),
        "month": _extract_path_part(r"month=(\d{2})", input_text, ts["month"]),
        "day": _extract_path_part(r"day=(\d{2})", input_text, ts["day"]),
        "hour": _extract_path_part(r"hour=(\d{2})", input_text, ts["hour"]),
        "minute": _extract_path_part(r"minute=(\d{2})", input_text, ts["minute"]),
    }
    return (
        processed_root
        / "gtfs_realtime"
        / f"feed={feed_name}"
        / f"year={parts['year']}"
        / f"month={parts['month']}"
        / f"day={parts['day']}"
        / f"hour={parts['hour']}"
        / f"minute={parts['minute']}"
        / "parsed.csv"
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Parse GTFS-Realtime protobuf files to CSV.")
    parser.add_argument("--feed", choices=["trip_updates", "service_alerts"], required=True)
    parser.add_argument("--input", required=True, help="Path to feed protobuf file (.pb)")
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint for GTFS-R parsing."""
    args = parse_args()
    logger = setup_logging()
    load_env()
    settings = load_settings()

    if gtfs_realtime_pb2 is None:
        logger.error(
            "Missing dependency: gtfs-realtime-bindings. Install requirements with "
            "'pip install -r requirements.txt'."
        )
        return 3

    pb_path = Path(args.input)
    if not pb_path.exists():
        logger.error("Input file does not exist: %s", pb_path)
        return 1

    processed_root = Path(
        os.getenv("PROCESSED_DATA_DIR", settings.get("paths", {}).get("processed_data_dir", "data/processed"))
    )
    try:
        parsed_df = parse_feed(args.feed, pb_path)
        output_path = build_output_path(processed_root, args.feed, pb_path)
        ensure_dir(output_path.parent)
        parsed_df.to_csv(output_path, index=False)
        logger.info("Parsed rows for %s: %s", args.feed, len(parsed_df))
        logger.info("Wrote parsed CSV to %s", output_path)
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to parse feed %s from %s: %s", args.feed, pb_path, exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
