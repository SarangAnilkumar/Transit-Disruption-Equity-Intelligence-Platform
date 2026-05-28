"""Fetch GTFS-Realtime protobuf snapshots for configured feeds."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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


@dataclass(frozen=True)
class AuthConfig:
    """Authentication behavior for feed requests."""

    api_key: str | None
    auth_mode: str
    header_name: str
    query_param_name: str


@dataclass(frozen=True)
class FetchResult:
    """Result of one feed fetch including diagnostics."""

    ok: bool
    status_code: int | None
    content_type: str | None
    content_length: int
    response_preview: str | None
    payload: bytes
    url_called: str
    error_message: str | None


def build_request_auth(auth: AuthConfig) -> tuple[dict[str, str], dict[str, str], str]:
    """Build request headers/params and report effective auth mode."""
    if not auth.api_key:
        return {}, {}, "none"
    if auth.auth_mode == "query":
        return {}, {auth.query_param_name: auth.api_key}, "query"
    return {auth.header_name: auth.api_key}, {}, "header"


def _sanitize_url_for_logs(url: str, query_param_name: str, query_value_used: bool) -> str:
    """Return URL safe for logs without leaking API key value."""
    if not query_value_used:
        return url
    parts = urlsplit(url)
    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    query_pairs.append((query_param_name, "***redacted***"))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query_pairs), parts.fragment))


def _response_preview(response: requests.Response, max_chars: int = 500) -> str | None:
    """Get short text preview if response appears textual."""
    content_type = response.headers.get("Content-Type", "")
    if any(text_hint in content_type.lower() for text_hint in ["text", "json", "xml", "html"]):
        return response.text[:max_chars]
    return None


def fetch_feed(
    url: str,
    auth: AuthConfig,
    timeout_seconds: int = 60,
    user_agent: str | None = None,
) -> FetchResult:
    """Fetch one GTFS-R protobuf payload with HTTP diagnostics."""
    headers, params, mode_used = build_request_auth(auth)
    if user_agent:
        headers["User-Agent"] = user_agent
    safe_url = _sanitize_url_for_logs(url, auth.query_param_name, mode_used == "query")
    try:
        response = requests.get(url, headers=headers, params=params, timeout=timeout_seconds)
    except requests.RequestException as exc:
        return FetchResult(
            ok=False,
            status_code=None,
            content_type=None,
            content_length=0,
            response_preview=None,
            payload=b"",
            url_called=safe_url,
            error_message=str(exc),
        )

    payload = response.content or b""
    preview = _response_preview(response)
    status_code = response.status_code
    content_type = response.headers.get("Content-Type")
    ok = response.ok and len(payload) > 0
    error_message = None
    if not response.ok:
        error_message = f"HTTP {status_code}"
    elif len(payload) == 0:
        error_message = "Response payload was empty."
    return FetchResult(
        ok=ok,
        status_code=status_code,
        content_type=content_type,
        content_length=len(payload),
        response_preview=preview,
        payload=payload,
        url_called=safe_url,
        error_message=error_message,
    )


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


def _build_auth_config(settings: dict[str, Any]) -> AuthConfig:
    auth_settings = settings.get("gtfs_realtime", {}).get("auth", {})
    api_key_env = auth_settings.get("api_key_env_var", "TRANSPORT_API_KEY")
    api_key = os.getenv(api_key_env, "").strip() or None
    auth_mode = os.getenv(
        "TRANSPORT_API_AUTH_MODE", auth_settings.get("auth_mode", "header")
    ).strip().lower()
    header_name = os.getenv(
        "TRANSPORT_API_HEADER_NAME", auth_settings.get("header_name", "Ocp-Apim-Subscription-Key")
    ).strip()
    query_param_name = os.getenv(
        "TRANSPORT_API_QUERY_PARAM_NAME", auth_settings.get("query_param_name", "subscription-key")
    ).strip()
    return AuthConfig(
        api_key=api_key,
        auth_mode="query" if auth_mode == "query" else "header",
        header_name=header_name or "Ocp-Apim-Subscription-Key",
        query_param_name=query_param_name or "subscription-key",
    )


def _build_metadata(
    feed_name: str,
    source_url: str,
    output_file: Path,
    request_timestamp_utc: str,
    fetch_result: FetchResult,
    auth_mode_used: str,
    auth: AuthConfig,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "source_url": source_url,
        "feed_name": feed_name,
        "request_timestamp_utc": request_timestamp_utc,
        "http_status_code": fetch_result.status_code,
        "content_type": fetch_result.content_type,
        "content_length": fetch_result.content_length,
        "auth_mode_used": auth_mode_used,
        "output_file": str(output_file),
    }
    if auth_mode_used == "header":
        metadata["api_header_name_used"] = auth.header_name
    if auth_mode_used == "query":
        metadata["api_query_param_name_used"] = auth.query_param_name
    return metadata


def main() -> int:
    """CLI entrypoint for GTFS-R fetch."""
    args = parse_args()
    logger = setup_logging()
    load_env()
    settings = load_settings()
    path_settings = settings.get("paths", {})
    realtime_settings = settings.get("gtfs_realtime", {})
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

    auth = _build_auth_config(settings)
    if not auth.api_key:
        logger.warning(
            "TRANSPORT_API_KEY is empty; requesting feeds without auth. "
            "If calls fail, set key and try header Ocp-Apim-Subscription-Key, then KeyID, "
            "or query param subscription-key."
        )
    timeout_seconds = int(os.getenv("TRANSPORT_TIMEOUT_SECONDS", str(realtime_settings.get("timeout_seconds", 60))))
    user_agent = os.getenv("TRANSPORT_USER_AGENT", realtime_settings.get("user_agent", ""))
    raw_root = Path(os.getenv("RAW_DATA_DIR", path_settings.get("raw_data_dir", "data/raw")))
    ts = get_timestamp_parts()

    failures = 0
    for feed_name in requested_feeds:
        cfg = feed_configs[feed_name]
        output_dir = ensure_dir(build_feed_output_dir(raw_root, feed_name, ts))
        pb_path = output_dir / "feed.pb"
        metadata_path = output_dir / "metadata.json"
        logger.info("Fetching feed=%s", feed_name)
        fetch_result = fetch_feed(
            url=cfg.url,
            auth=auth,
            timeout_seconds=timeout_seconds,
            user_agent=user_agent or None,
        )
        _, _, auth_mode_used = build_request_auth(auth)
        if not fetch_result.ok:
            failures += 1
            logger.error(
                "Failed feed=%s | status=%s | content_type=%s | url=%s | error=%s",
                feed_name,
                fetch_result.status_code,
                fetch_result.content_type,
                fetch_result.url_called,
                fetch_result.error_message,
            )
            if fetch_result.response_preview:
                logger.error("Response preview (first 500 chars): %s", fetch_result.response_preview)
            logger.error(
                "If auth is failing, try TRANSPORT_API_HEADER_NAME=KeyID or "
                "TRANSPORT_API_AUTH_MODE=query with TRANSPORT_API_QUERY_PARAM_NAME=subscription-key."
            )
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
        logger.info("Saved %s and %s", pb_path, metadata_path)

    if failures:
        logger.error("Completed with %s failed feed fetches.", failures)
        return 2

    logger.info("GTFS-Realtime fetch completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
