"""Build route-to-SA2 coverage bridge from GTFS static and stop mapping."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.geospatial_utils import aggregate_route_sa2, latest_partition_file, now_utc_iso  # noqa: E402
from ingestion.utils import ensure_dir, load_env, load_settings, save_json_to_file, setup_logging  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Build route-to-SA2 coverage dataset.")
    parser.add_argument("--routes-path")
    parser.add_argument("--trips-path")
    parser.add_argument("--stop-times-path")
    parser.add_argument("--stop-sa2-path", default="data/processed/geospatial/stops_sa2_mapping.csv")
    parser.add_argument("--output-dir")
    return parser.parse_args()


def _resolve_static_paths(args: argparse.Namespace, processed_root: Path) -> tuple[Path, Path, Path]:
    routes_path = Path(args.routes_path) if args.routes_path else latest_partition_file(
        processed_root / "gtfs_static", "routes.txt"
    )
    trips_path = Path(args.trips_path) if args.trips_path else latest_partition_file(
        processed_root / "gtfs_static", "trips.txt"
    )
    stop_times_path = (
        Path(args.stop_times_path)
        if args.stop_times_path
        else latest_partition_file(processed_root / "gtfs_static", "stop_times.txt")
    )
    return routes_path, trips_path, stop_times_path


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    logger = setup_logging()
    load_env()
    settings = load_settings()
    paths = settings.get("paths", {})
    geospatial = settings.get("geospatial", {})
    processed_root = Path(os.getenv("PROCESSED_DATA_DIR", paths.get("processed_data_dir", "data/processed")))
    output_dir = ensure_dir(Path(args.output_dir or geospatial.get("output_dir", processed_root / "geospatial")))

    try:
        routes_path, trips_path, stop_times_path = _resolve_static_paths(args, processed_root)
        mapping_path = Path(args.stop_sa2_path)
        if not mapping_path.exists():
            raise FileNotFoundError(
                f"Missing stop-SA2 mapping: {mapping_path}. Run ingestion/build_stop_sa2_mapping.py first."
            )
        routes_df = pd.read_csv(routes_path)
        trips_df = pd.read_csv(trips_path)
        stop_times_df = pd.read_csv(stop_times_path)
        mapping_df = pd.read_csv(mapping_path)

        coverage = aggregate_route_sa2(routes_df, trips_df, stop_times_df, mapping_df)
        coverage["coverage_created_at"] = now_utc_iso()
        output_csv = output_dir / "route_sa2_coverage.csv"
        coverage.to_csv(output_csv, index=False)

        report = {
            "routes_file": str(routes_path),
            "trips_file": str(trips_path),
            "stop_times_file": str(stop_times_path),
            "stop_sa2_mapping_file": str(mapping_path),
            "coverage_rows": int(len(coverage)),
            "distinct_routes": int(coverage["route_id"].nunique() if not coverage.empty else 0),
            "distinct_sa2": int(coverage["sa2_code"].nunique() if not coverage.empty else 0),
            "created_at": now_utc_iso(),
        }
        save_json_to_file(report, output_dir / "route_sa2_coverage_report.json")
        logger.info("Wrote route-SA2 coverage to %s", output_csv)
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to build route-SA2 coverage: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
