"""Collect GTFS-Realtime snapshots repeatedly over a configured window."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.fetch_gtfs_realtime import (  # noqa: E402
    AuthConfig,
    FeedConfig,
    _build_auth_config,
    _build_metadata,
    build_feed_output_dir,
    build_request_auth,
    fetch_feed,
)
from ingestion.parse_gtfs_realtime import build_output_path, parse_feed  # noqa: E402
from ingestion.utils import (  # noqa: E402
    ensure_dir,
    get_timestamp_parts,
    load_env,
    load_settings,
    resolve_env_or_config,
    save_bytes_to_file,
    save_json_to_file,
    setup_logging,
)


def _feed_configs(settings: dict[str, Any]) -> dict[str, FeedConfig]:
    feed_settings = settings.get("gtfs_realtime", {}).get("feeds", {})
    return {
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


def _resolve_feeds(feed_arg: str) -> list[str]:
    if feed_arg == "both":
        return ["trip_updates", "service_alerts"]
    return [feed_arg]


def _count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def collect_once(
    *,
    feed_names: list[str],
    feed_configs: dict[str, FeedConfig],
    auth: AuthConfig,
    raw_root: Path,
    processed_root: Path,
    timeout_seconds: int,
    user_agent: str | None,
    logger,
) -> dict[str, Any]:
    """Fetch and parse one snapshot cycle for selected feeds."""
    ts = get_timestamp_parts()
    cycle: dict[str, Any] = {
        "timestamp_utc": ts["iso"],
        "feeds": {},
        "errors": [],
        "warnings": [],
    }
    for feed_name in feed_names:
        cfg = feed_configs[feed_name]
        feed_result: dict[str, Any] = {
            "feed_name": feed_name,
            "ok": False,
            "raw_file": None,
            "parsed_file": None,
            "row_count": 0,
        }
        if not cfg.url:
            feed_result["error"] = "Missing feed URL"
            cycle["errors"].append(f"{feed_name}: missing URL")
            cycle["feeds"][feed_name] = feed_result
            continue
        output_dir = ensure_dir(build_feed_output_dir(raw_root, feed_name, ts))
        pb_path = output_dir / "feed.pb"
        metadata_path = output_dir / "metadata.json"
        fetch_result = fetch_feed(
            url=cfg.url,
            auth=auth,
            timeout_seconds=timeout_seconds,
            user_agent=user_agent,
        )
        _, _, auth_mode_used = build_request_auth(auth)
        if not fetch_result.ok:
            feed_result["error"] = fetch_result.error_message
            cycle["errors"].append(f"{feed_name}: {fetch_result.error_message}")
            cycle["feeds"][feed_name] = feed_result
            logger.error("Fetch failed feed=%s error=%s", feed_name, fetch_result.error_message)
            continue
        save_bytes_to_file(fetch_result.payload, pb_path)
        metadata = _build_metadata(
            feed_name=feed_name,
            source_url=cfg.url,
            output_file=pb_path,
            request_timestamp_utc=ts["iso"],
            fetch_result=fetch_result,
            auth_mode_used=auth_mode_used,
            auth=auth,
        )
        save_json_to_file(metadata, metadata_path)
        try:
            parsed_df = parse_feed(feed_name, pb_path)
            parsed_path = build_output_path(processed_root, feed_name, pb_path)
            ensure_dir(parsed_path.parent)
            parsed_df.to_csv(parsed_path, index=False)
            row_count = int(len(parsed_df))
            feed_result.update(
                {
                    "ok": True,
                    "raw_file": str(pb_path),
                    "parsed_file": str(parsed_path),
                    "row_count": row_count,
                }
            )
            if row_count == 0:
                cycle["warnings"].append(f"{feed_name}: parsed zero rows (quiet snapshot)")
            logger.info("Collected feed=%s rows=%s", feed_name, row_count)
        except Exception as exc:  # noqa: BLE001
            feed_result["error"] = str(exc)
            cycle["errors"].append(f"{feed_name}: parse failed: {exc}")
            logger.error("Parse failed feed=%s: %s", feed_name, exc)
        cycle["feeds"][feed_name] = feed_result
    return cycle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect GTFS-R snapshots over time.")
    parser.add_argument("--feed", choices=["trip_updates", "service_alerts", "both"], default="both")
    parser.add_argument("--once", action="store_true", help="Collect a single snapshot cycle and exit.")
    parser.add_argument("--duration-hours", type=float, default=8.0)
    parser.add_argument("--interval-minutes", type=int, default=15)
    parser.add_argument("--max-cycles", type=int, default=0, help="Optional hard cap on collection cycles.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = setup_logging()
    load_env()
    settings = load_settings()
    import os

    paths = settings.get("paths", {})
    realtime_settings = settings.get("gtfs_realtime", {})
    raw_root = Path(os.getenv("RAW_DATA_DIR", paths.get("raw_data_dir", "data/raw")))
    processed_root = Path(
        os.getenv("PROCESSED_DATA_DIR", paths.get("processed_data_dir", "data/processed"))
    )
    feed_names = _resolve_feeds(args.feed)
    feed_configs = _feed_configs(settings)
    auth = _build_auth_config(settings)
    timeout_seconds = int(
        os.getenv("TRANSPORT_TIMEOUT_SECONDS", str(realtime_settings.get("timeout_seconds", 60)))
    )
    user_agent = os.getenv("TRANSPORT_USER_AGENT", realtime_settings.get("user_agent", "")) or None

    start = datetime.now(UTC)
    manifest: dict[str, Any] = {
        "collection_start": start.isoformat(),
        "collection_end": None,
        "interval_minutes": args.interval_minutes,
        "duration_hours": None if args.once else args.duration_hours,
        "feed_names": feed_names,
        "attempted_snapshots": 0,
        "successful_snapshots": 0,
        "failed_snapshots": 0,
        "cycles": [],
        "raw_files": [],
        "parsed_files": [],
        "row_counts": {},
        "errors": [],
        "warnings": [],
    }

    end_time = None if args.once else start.timestamp() + args.duration_hours * 3600
    cycle_index = 0
    while True:
        cycle_index += 1
        if args.max_cycles and cycle_index > args.max_cycles:
            break
        if end_time is not None and time.time() >= end_time:
            break
        manifest["attempted_snapshots"] += 1
        cycle = collect_once(
            feed_names=feed_names,
            feed_configs=feed_configs,
            auth=auth,
            raw_root=raw_root,
            processed_root=processed_root,
            timeout_seconds=timeout_seconds,
            user_agent=user_agent,
            logger=logger,
        )
        manifest["cycles"].append(cycle)
        manifest["errors"].extend(cycle["errors"])
        manifest["warnings"].extend(cycle["warnings"])
        ok_feeds = [name for name, result in cycle["feeds"].items() if result.get("ok")]
        if ok_feeds:
            manifest["successful_snapshots"] += 1
        else:
            manifest["failed_snapshots"] += 1
        for name, result in cycle["feeds"].items():
            if result.get("raw_file"):
                manifest["raw_files"].append(result["raw_file"])
            if result.get("parsed_file"):
                manifest["parsed_files"].append(result["parsed_file"])
                manifest["row_counts"][result["parsed_file"]] = result.get("row_count", 0)

        if args.once:
            break
        if end_time is not None and time.time() + args.interval_minutes * 60 >= end_time:
            break
        logger.info("Sleeping %s minutes before next collection cycle.", args.interval_minutes)
        time.sleep(args.interval_minutes * 60)

    manifest["collection_end"] = datetime.now(UTC).isoformat()
    manifest_dir = ensure_dir(processed_root / "gtfs_realtime" / "collection_manifests")
    stamp = start.strftime("%Y%m%dT%H%M%SZ")
    manifest_path = manifest_dir / f"gtfsr_collection_manifest_{stamp}.json"
    save_json_to_file(manifest, manifest_path)
    logger.info("Wrote collection manifest to %s", manifest_path)
    return 0 if manifest["successful_snapshots"] > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
