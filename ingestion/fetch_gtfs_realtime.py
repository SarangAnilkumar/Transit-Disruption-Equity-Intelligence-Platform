"""Fetch GTFS-Realtime protobuf snapshots for configured feeds."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import requests

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.utils import (
    ensure_dir,
    get_timestamp_parts,
    load_env,
    load_settings,
    resolve_env_or_config,
    save_bytes_to_file,
    save_json_to_file,
    setup_logging,
)


@dataclass(frozen=True)
class FeedConfig:
    """Configuration for one GTFS-R feed endpoint."""

    name: str
    url: str


def build_headers(api_key: str | None, auth_style: str = "x-api-key") -> Mapping[str, str]:
    """Build headers for future-pluggable auth strategies."""
    if not api_key:
        return {}
    if auth_style.lower() == "authorization-bearer":
        return {"Authorization": f"Bearer {api_key}"}
    return {"x-api-key": api_key}


def fetch_feed_bytes(url: str, headers: Mapping[str, str], timeout_seconds: int = 60) -> bytes:
    """Fetch one GTFS-R protobuf payload."""
    response = requests.get(url, headers=dict(headers), timeout=timeout_seconds)
    response.raise_for_status()
    return response.content


def build_feed_output_dir(raw_data_dir: Path, feed_name: str, ts: dict[str, str]) -> Path:
    """Build partitioned output directory for raw GTFS-R snapshots."""
    return (
        raw_data_dir
        / "gtfs_realtime"
        / f"feed={feed_name}"
        / f"year={ts['year']}"
        / f"month={ts['month']}"
        / f"day={ts['day']}"
        / f"hour={ts['hour']}"
        / f"minute={ts['minute']}"
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Fetch GTFS-Realtime protobuf feed snapshots.")
    parser.add_argument(
        "--feed",
        choices=["trip_updates", "service_alerts", "both"],
        default="both",
        help="Which feed(s) to fetch",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint for GTFS-R fetch."""
    args = parse_args()
    logger = setup_logging()
    load_env()
    settings = load_settings()
    path_settings = settings.get("paths", {})
    feed_settings = settings.get("gtfs_realtime", {}).get("feeds", {})

    feed_configs = {
        "trip_updates": FeedConfig(
            name="trip_updates",
            url=resolve_env_or_config(
                "GTFS_REALTIME_TRIP_UPDATES_URL",
                feed_settings.get("trip_updates", {}).get("url"),
            ),
        ),
        "service_alerts": FeedConfig(
            name="service_alerts",
            url=resolve_env_or_config(
                "GTFS_REALTIME_SERVICE_ALERTS_URL",
                feed_settings.get("service_alerts", {}).get("url"),
            ),
        ),
    }

    requested_feeds = (
        ["trip_updates", "service_alerts"] if args.feed == "both" else [args.feed]
    )

    missing_urls = [f for f in requested_feeds if not feed_configs[f].url]
    if missing_urls:
        logger.error(
            "Missing URL(s) for %s. Add required GTFS_REALTIME_*_URL values to .env.",
            ", ".join(missing_urls),
        )
        return 1

    api_key = os.getenv("TRANSPORT_API_KEY", "").strip() or None
    headers = build_headers(api_key=api_key, auth_style=os.getenv("GTFS_AUTH_STYLE", "x-api-key"))
    raw_root = Path(os.getenv("RAW_DATA_DIR", path_settings.get("raw_data_dir", "data/raw")))
    ts = get_timestamp_parts()

    failures = 0
    for feed_name in requested_feeds:
        cfg = feed_configs[feed_name]
        output_dir = ensure_dir(build_feed_output_dir(raw_root, feed_name, ts))
        pb_path = output_dir / "feed.pb"
        metadata_path = output_dir / "metadata.json"
        logger.info("Fetching feed=%s", feed_name)
        try:
            payload = fetch_feed_bytes(cfg.url, headers=headers)
            save_bytes_to_file(payload, pb_path)
            save_json_to_file(
                {
                    "feed_name": feed_name,
                    "request_timestamp_utc": ts["iso"],
                    "source_url": cfg.url,
                    "output_file": str(pb_path),
                },
                metadata_path,
            )
            logger.info("Saved %s and %s", pb_path, metadata_path)
        except requests.RequestException as exc:
            failures += 1
            logger.error("Failed to fetch feed=%s: %s", feed_name, exc)

    if failures:
        logger.error("Completed with %s failed feed fetches.", failures)
        return 2

    logger.info("GTFS-Realtime fetch completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
