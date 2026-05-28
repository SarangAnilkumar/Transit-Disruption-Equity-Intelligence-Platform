"""Fetch and extract GTFS static files into local raw/processed folders."""

from __future__ import annotations

import argparse
import io
import os
import sys
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd
import requests

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.utils import (  # noqa: E402
    ensure_dir,
    get_timestamp_parts,
    load_env,
    load_settings,
    resolve_env_or_config,
    save_bytes_to_file,
    setup_logging,
)

KEY_FILES = [
    "stops.txt",
    "routes.txt",
    "trips.txt",
    "stop_times.txt",
    "calendar.txt",
    "calendar_dates.txt",
]


def _resolve_paths(settings: dict[str, Any]) -> tuple[Path, Path]:
    paths = settings.get("paths", {})
    raw_root = Path(os.getenv("RAW_DATA_DIR", paths.get("raw_data_dir", "data/raw")))
    processed_root = Path(
        os.getenv("PROCESSED_DATA_DIR", paths.get("processed_data_dir", "data/processed"))
    )
    return raw_root, processed_root


def fetch_gtfs_static(url: str, timeout_seconds: int = 60) -> bytes:
    """Download GTFS static zip from URL."""
    response = requests.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    return response.content


def extract_key_files(zip_bytes: bytes, output_dir: Path, logger) -> None:
    """Extract selected GTFS text files and print row counts."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        archive_names = archive.namelist()
        basename_map = {Path(name).name: name for name in archive_names}
        for file_name in KEY_FILES:
            matched_path = basename_map.get(file_name)
            if not matched_path:
                logger.warning("Missing optional/key file in archive: %s", file_name)
                continue
            target_path = output_dir / file_name
            ensure_dir(target_path.parent)
            with archive.open(matched_path) as source, target_path.open("wb") as target:
                target.write(source.read())
            try:
                row_count = len(pd.read_csv(target_path))
                logger.info("Extracted %s with %s rows", file_name, row_count)
            except Exception as exc:  # noqa: BLE001
                logger.error("Could not read %s with pandas: %s", file_name, exc)


def main() -> int:
    """CLI entrypoint for GTFS static fetch."""
    parser = argparse.ArgumentParser(description="Fetch GTFS static zip and extract key files.")
    parser.parse_args()

    logger = setup_logging()
    load_env()
    settings = load_settings()
    gtfs_url = resolve_env_or_config(
        "GTFS_STATIC_URL",
        settings.get("gtfs_static", {}).get("url"),
    )
    if not gtfs_url:
        logger.error(
            "Missing GTFS_STATIC_URL. Add it to .env from .env.example, then rerun this script."
        )
        return 1

    raw_root, processed_root = _resolve_paths(settings)
    ts = get_timestamp_parts()

    raw_dir = ensure_dir(raw_root / "gtfs_static" / f"load_date={ts['date']}")
    processed_dir = ensure_dir(processed_root / "gtfs_static" / f"load_date={ts['date']}")
    raw_zip_path = raw_dir / "gtfs_static.zip"

    logger.info("Downloading GTFS static feed from configured URL")
    try:
        zip_bytes = fetch_gtfs_static(gtfs_url)
        save_bytes_to_file(zip_bytes, raw_zip_path)
        logger.info("Saved raw zip to %s", raw_zip_path)
        extract_key_files(zip_bytes, processed_dir, logger)
    except requests.RequestException as exc:
        logger.error("Network/request error while fetching GTFS static: %s", exc)
        return 2
    except zipfile.BadZipFile as exc:
        logger.error("Downloaded file is not a valid zip archive: %s", exc)
        return 3
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected failure in GTFS static ingestion: %s", exc)
        return 4

    logger.info("GTFS static ingestion completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
