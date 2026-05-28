"""Validate Transport Victoria GTFS feed access and local parsing."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.fetch_gtfs_realtime import (  # noqa: E402
    AuthConfig,
    FeedConfig,
    FetchResult,
    _build_auth_config,
    build_feed_output_dir,
    build_request_auth,
    fetch_feed,
)
from ingestion.fetch_gtfs_static import fetch_gtfs_static  # noqa: E402
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


def parse_args() -> argparse.Namespace:
    """Parse validator CLI args."""
    parser = argparse.ArgumentParser(description="Validate GTFS static and realtime feed access.")
    parser.add_argument("--feed", choices=["trip_updates", "service_alerts", "both"], default="both")
    parser.add_argument("--include-static", action="store_true")
    return parser.parse_args()


def _init_report(auth: AuthConfig, feed_choice: str, include_static: bool) -> dict[str, Any]:
    """Build default report shape."""
    return {
        "feed_choice": feed_choice,
        "include_static": include_static,
        "gtfs_static_url_present": False,
        "trip_updates_url_present": False,
        "service_alerts_url_present": False,
        "api_key_present": bool(auth.api_key),
        "auth_mode": auth.auth_mode if auth.api_key else "none",
        "trip_updates_fetch_status": "not_requested",
        "trip_updates_raw_file": None,
        "trip_updates_parsed_file": None,
        "trip_updates_parsed_rows": None,
        "service_alerts_fetch_status": "not_requested",
        "service_alerts_raw_file": None,
        "service_alerts_parsed_file": None,
        "service_alerts_parsed_rows": None,
        "errors": [],
        "warnings": [],
        "next_recommended_action": "",
    }


def _fetch_and_parse_feed(
    feed_name: str,
    feed_cfg: FeedConfig,
    auth: AuthConfig,
    raw_root: Path,
    processed_root: Path,
    ts: dict[str, str],
    timeout_seconds: int,
    user_agent: str,
    logger,
) -> tuple[FetchResult, Path | None, Path | None, int | None]:
    """Fetch one feed, write raw/parsed artifacts, and return details."""
    output_dir = ensure_dir(build_feed_output_dir(raw_root, feed_name, ts))
    raw_pb_path = output_dir / "feed.pb"
    fetch_result = fetch_feed(
        url=feed_cfg.url,
        auth=auth,
        timeout_seconds=timeout_seconds,
        user_agent=user_agent or None,
    )
    if not fetch_result.ok:
        logger.error(
            "Validation fetch failed for %s (status=%s, content_type=%s, url=%s)",
            feed_name,
            fetch_result.status_code,
            fetch_result.content_type,
            fetch_result.url_called,
        )
        return fetch_result, None, None, None

    save_bytes_to_file(fetch_result.payload, raw_pb_path)
    parsed_output_path = build_output_path(processed_root, feed_name, raw_pb_path)
    parsed_df = parse_feed(feed_name, raw_pb_path)
    ensure_dir(parsed_output_path.parent)
    parsed_df.to_csv(parsed_output_path, index=False)
    return fetch_result, raw_pb_path, parsed_output_path, len(parsed_df)


def main() -> int:
    """Run end-to-end local validation and emit report JSON."""
    args = parse_args()
    logger = setup_logging()
    load_env()
    settings = load_settings()

    paths = settings.get("paths", {})
    realtime_settings = settings.get("gtfs_realtime", {})
    feed_settings = realtime_settings.get("feeds", {})
    auth = _build_auth_config(settings)
    timeout_seconds = int(
        os.getenv("TRANSPORT_TIMEOUT_SECONDS", str(realtime_settings.get("timeout_seconds", 60)))
    )
    user_agent = os.getenv("TRANSPORT_USER_AGENT", realtime_settings.get("user_agent", ""))
    ts = get_timestamp_parts()

    raw_root = Path(os.getenv("RAW_DATA_DIR", paths.get("raw_data_dir", "data/raw")))
    processed_root = Path(
        os.getenv("PROCESSED_DATA_DIR", paths.get("processed_data_dir", "data/processed"))
    )
    samples_dir = ensure_dir(Path("data/samples"))

    static_url = resolve_env_or_config("GTFS_STATIC_URL", settings.get("gtfs_static", {}).get("url"))
    trip_url = resolve_env_or_config(
        "GTFS_REALTIME_TRIP_UPDATES_URL", feed_settings.get("trip_updates", {}).get("url")
    )
    alerts_url = resolve_env_or_config(
        "GTFS_REALTIME_SERVICE_ALERTS_URL", feed_settings.get("service_alerts", {}).get("url")
    )

    report = _init_report(auth=auth, feed_choice=args.feed, include_static=args.include_static)
    report["gtfs_static_url_present"] = bool(static_url)
    report["trip_updates_url_present"] = bool(trip_url)
    report["service_alerts_url_present"] = bool(alerts_url)

    if not auth.api_key:
        report["warnings"].append(
            "No API key detected. If requests fail, try Ocp-Apim-Subscription-Key, then KeyID, "
            "or query mode with subscription-key."
        )

    if args.include_static:
        if not static_url:
            report["errors"].append("GTFS_STATIC_URL missing.")
        else:
            try:
                static_bytes = fetch_gtfs_static(static_url, timeout_seconds=timeout_seconds)
                static_raw = ensure_dir(raw_root / "gtfs_static" / f"load_date={ts['date']}") / "gtfs_static.zip"
                save_bytes_to_file(static_bytes, static_raw)
            except Exception as exc:  # noqa: BLE001
                report["errors"].append(f"GTFS static fetch failed: {exc}")

    requested_feeds = ["trip_updates", "service_alerts"] if args.feed == "both" else [args.feed]
    configured_feeds = {
        "trip_updates": FeedConfig("trip_updates", trip_url),
        "service_alerts": FeedConfig("service_alerts", alerts_url),
    }
    _, _, auth_mode_used = build_request_auth(auth)

    for feed_name in requested_feeds:
        feed_cfg = configured_feeds[feed_name]
        if not feed_cfg.url:
            report["errors"].append(f"Missing URL for {feed_name}.")
            report[f"{feed_name}_fetch_status"] = "missing_url"
            continue
        fetch_result, raw_file, parsed_file, parsed_rows = _fetch_and_parse_feed(
            feed_name=feed_name,
            feed_cfg=feed_cfg,
            auth=auth,
            raw_root=raw_root,
            processed_root=processed_root,
            ts=ts,
            timeout_seconds=timeout_seconds,
            user_agent=user_agent,
            logger=logger,
        )
        if not fetch_result.ok:
            report[f"{feed_name}_fetch_status"] = "failed"
            report["errors"].append(
                f"{feed_name} failed (status={fetch_result.status_code}, content_type={fetch_result.content_type})."
            )
            if fetch_result.response_preview:
                report["warnings"].append(
                    f"{feed_name} response preview: {fetch_result.response_preview[:180]}"
                )
            continue
        report[f"{feed_name}_fetch_status"] = "success"
        report[f"{feed_name}_raw_file"] = str(raw_file) if raw_file else None
        report[f"{feed_name}_parsed_file"] = str(parsed_file) if parsed_file else None
        report[f"{feed_name}_parsed_rows"] = parsed_rows

    if report["errors"]:
        report["next_recommended_action"] = (
            f"Review errors, then retry with auth_mode={auth_mode_used}. "
            "If unauthorized, try header Ocp-Apim-Subscription-Key, then KeyID, then query subscription-key."
        )
        exit_code = 1
    elif any((report["trip_updates_parsed_rows"] == 0, report["service_alerts_parsed_rows"] == 0)):
        report["next_recommended_action"] = (
            "Feeds were reachable. Zero rows can occur at snapshot time; collect additional snapshots and re-validate."
        )
        exit_code = 0
    else:
        report["next_recommended_action"] = (
            "Validation passed. Proceed to Milestone 2 (SA2/geospatial preprocessing)."
        )
        exit_code = 0

    report_path = samples_dir / f"feed_validation_report_{ts['year']}{ts['month']}{ts['day']}_{ts['hour']}{ts['minute']}.json"
    save_json_to_file(report, report_path)
    logger.info("Validation report written to %s", report_path)
    logger.info("Validation summary errors=%s warnings=%s", len(report["errors"]), len(report["warnings"]))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
