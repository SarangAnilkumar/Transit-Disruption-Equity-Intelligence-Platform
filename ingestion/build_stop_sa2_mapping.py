"""Build stop-to-SA2 mapping from GTFS stops and ABS boundaries."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.geospatial_utils import (  # noqa: E402
    detect_sa2_columns,
    latest_partition_file,
    now_utc_iso,
    validate_stop_columns,
    valid_coordinate_mask,
)
from ingestion.utils import (  # noqa: E402
    ensure_dir,
    load_env,
    load_settings,
    resolve_env_or_config,
    save_json_to_file,
    setup_logging,
)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Build stop-to-SA2 mapping.")
    parser.add_argument("--stops-path")
    parser.add_argument("--sa2-boundaries-path")
    parser.add_argument("--sa2-layer")
    parser.add_argument("--output-dir")
    parser.add_argument("--write-parquet", action="store_true")
    return parser.parse_args()


def _resolve_paths(args: argparse.Namespace, settings: dict) -> tuple[Path, Path, str | None]:
    paths = settings.get("paths", {})
    geospatial = settings.get("geospatial", {})
    processed_root = Path(os.getenv("PROCESSED_DATA_DIR", paths.get("processed_data_dir", "data/processed")))
    default_stops = latest_partition_file(processed_root / "gtfs_static", "stops.txt")
    stops_path = Path(args.stops_path) if args.stops_path else default_stops
    sa2_path = Path(
        args.sa2_boundaries_path
        or resolve_env_or_config("SA2_BOUNDARIES_PATH", geospatial.get("sa2_boundaries_path"))
    )
    if not str(sa2_path).strip():
        raise ValueError("Missing SA2 boundaries path. Set SA2_BOUNDARIES_PATH or pass --sa2-boundaries-path.")
    output_dir = Path(args.output_dir or geospatial.get("output_dir", processed_root / "geospatial"))
    layer = args.sa2_layer or os.getenv("SA2_BOUNDARY_LAYER", geospatial.get("sa2_boundary_layer"))
    return stops_path, sa2_path, layer or None


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    logger = setup_logging()
    load_env()
    settings = load_settings()

    warnings: list[str] = []
    errors: list[str] = []
    try:
        stops_path, sa2_path, sa2_layer = _resolve_paths(args, settings)
        output_dir = ensure_dir(Path(args.output_dir or settings.get("geospatial", {}).get("output_dir", "data/processed/geospatial")))
        stops_df = pd.read_csv(stops_path)
        validate_stop_columns(stops_df)
        stops_df["stop_lat"] = pd.to_numeric(stops_df["stop_lat"], errors="coerce")
        stops_df["stop_lon"] = pd.to_numeric(stops_df["stop_lon"], errors="coerce")
        valid_mask = valid_coordinate_mask(stops_df)
        invalid_coordinate_stops = int((~valid_mask).sum())
        valid_stops = stops_df[valid_mask].copy()
        stops_gdf = gpd.GeoDataFrame(
            valid_stops,
            geometry=gpd.points_from_xy(valid_stops["stop_lon"], valid_stops["stop_lat"]),
            crs="EPSG:4326",
        )

        if not sa2_path.exists():
            raise FileNotFoundError(f"SA2 boundaries file not found: {sa2_path}")
        sa2_gdf = gpd.read_file(sa2_path, layer=sa2_layer) if sa2_layer else gpd.read_file(sa2_path)
        sa2_code_col, sa2_name_col = detect_sa2_columns(sa2_gdf.columns)
        if sa2_gdf.crs is None:
            warnings.append("SA2 boundaries CRS was missing; assuming EPSG:4326.")
            sa2_gdf = sa2_gdf.set_crs("EPSG:4326")
        sa2_gdf = sa2_gdf.to_crs(stops_gdf.crs)
        sa2_subset = sa2_gdf[[sa2_code_col, sa2_name_col, "geometry"]].rename(
            columns={sa2_code_col: "sa2_code", sa2_name_col: "sa2_name"}
        )

        joined = gpd.sjoin(stops_gdf, sa2_subset, how="left", predicate="within")
        mapping = joined[
            ["stop_id", "stop_name", "stop_lat", "stop_lon", "sa2_code", "sa2_name"]
        ].copy()
        mapping["mapping_method"] = "within"
        mapping["is_matched"] = mapping["sa2_code"].notna()
        mapping["mapping_created_at"] = now_utc_iso()
        mapping["source_stops_path"] = str(stops_path)
        mapping["source_sa2_path"] = str(sa2_path)

        unmatched_raw = stops_df[~valid_mask][["stop_id", "stop_name", "stop_lat", "stop_lon"]].copy()
        if not unmatched_raw.empty:
            unmatched_raw["sa2_code"] = None
            unmatched_raw["sa2_name"] = None
            unmatched_raw["mapping_method"] = "invalid_coordinates"
            unmatched_raw["is_matched"] = False
            unmatched_raw["mapping_created_at"] = now_utc_iso()
            unmatched_raw["source_stops_path"] = str(stops_path)
            unmatched_raw["source_sa2_path"] = str(sa2_path)
            mapping = pd.concat([mapping, unmatched_raw], ignore_index=True)

        mapping = mapping.sort_values("stop_id").reset_index(drop=True)
        mapping_path = output_dir / "stops_sa2_mapping.csv"
        mapping.to_csv(mapping_path, index=False)
        # Roadmap alias filename for Milestone 3 issue compatibility.
        mapping.to_csv(output_dir / "stop_area_mapping.csv", index=False)
        if args.write_parquet:
            mapping.to_parquet(output_dir / "stops_sa2_mapping.parquet", index=False)

        total_stops = int(len(stops_df))
        matched = int(mapping["is_matched"].sum())
        unmatched = int(total_stops - matched)
        match_rate = matched / total_stops if total_stops else 0.0
        if match_rate < 0.9:
            warnings.append(f"Match rate below 90% ({match_rate:.2%}).")
            logger.warning("Stop-to-SA2 match rate below 90%%: %.2f%%", match_rate * 100)

        report = {
            "total_stops": total_stops,
            "valid_coordinate_stops": int(valid_mask.sum()),
            "invalid_coordinate_stops": invalid_coordinate_stops,
            "matched_stops": matched,
            "unmatched_stops": unmatched,
            "match_rate": round(match_rate, 6),
            "sa2_boundary_file": str(sa2_path),
            "sa2_layer": sa2_layer,
            "stops_file": str(stops_path),
            "created_at": now_utc_iso(),
            "warnings": warnings,
            "errors": errors,
        }
        save_json_to_file(report, output_dir / "geospatial_mapping_report.json")
        logger.info("Wrote stop-SA2 mapping to %s", mapping_path)
        logger.info("Matched %s/%s stops (%.2f%%)", matched, total_stops, match_rate * 100)
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to build stop-SA2 mapping: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
