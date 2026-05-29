"""Build SA2-level disruption observation base from parsed trip updates."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.geospatial_utils import aggregate_sa2_disruption, now_utc_iso  # noqa: E402
from ingestion.utils import ensure_dir, load_env, load_settings, save_json_to_file, setup_logging  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Build SA2 disruption base table.")
    parser.add_argument("--trip-updates-root")
    parser.add_argument("--stop-sa2-path", default="data/processed/geospatial/stops_sa2_mapping.csv")
    parser.add_argument("--output-dir")
    return parser.parse_args()


def _read_trip_update_csvs(root: Path) -> pd.DataFrame:
    files = sorted(root.rglob("parsed.csv"))
    if not files:
        raise FileNotFoundError(f"No parsed.csv files found under {root}")
    frames = [pd.read_csv(file) for file in files]
    return pd.concat(frames, ignore_index=True)


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    logger = setup_logging()
    load_env()
    settings = load_settings()
    paths = settings.get("paths", {})
    analytics_settings = settings.get("analytics", {})
    processed_root = Path(os.getenv("PROCESSED_DATA_DIR", paths.get("processed_data_dir", "data/processed")))

    trip_root = Path(args.trip_updates_root or processed_root / "gtfs_realtime" / "feed=trip_updates")
    mapping_path = Path(args.stop_sa2_path)
    output_dir = ensure_dir(Path(args.output_dir or analytics_settings.get("output_dir", "data/processed/analytics")))

    if not mapping_path.exists():
        logger.error("Stop-SA2 mapping file not found: %s", mapping_path)
        return 1
    try:
        updates_df = _read_trip_update_csvs(trip_root)
        mapping_df = pd.read_csv(mapping_path)
        updates_df = updates_df[updates_df["stop_id"].notna()].copy()
        base_df, report = aggregate_sa2_disruption(updates_df, mapping_df)
        output_csv = output_dir / "sa2_disruption_observations_base.csv"
        base_df.to_csv(output_csv, index=False)
        report.update(
            {
                "trip_updates_root": str(trip_root),
                "mapping_file": str(mapping_path),
                "output_file": str(output_csv),
                "rows": int(len(base_df)),
                "created_at": now_utc_iso(),
            }
        )
        save_json_to_file(report, output_dir / "sa2_disruption_observations_report.json")
        logger.info("Wrote SA2 disruption base to %s", output_csv)
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to build SA2 disruption base: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
