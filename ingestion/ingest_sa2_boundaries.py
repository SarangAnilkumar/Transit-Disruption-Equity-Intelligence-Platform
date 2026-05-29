"""Validate and register local ABS SA2 boundary source files."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.geospatial_utils import detect_sa2_columns, now_utc_iso  # noqa: E402
from ingestion.utils import (  # noqa: E402
    ensure_dir,
    load_env,
    load_settings,
    resolve_env_or_config,
    save_json_to_file,
    setup_logging,
)

try:
    import geopandas as gpd
except ModuleNotFoundError:  # pragma: no cover
    gpd = None


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Validate ABS SA2 boundary source file.")
    parser.add_argument("--input")
    parser.add_argument("--layer")
    parser.add_argument("--output-dir", default="data/raw/geospatial/sa2_boundaries")
    return parser.parse_args()


def main() -> int:
    """Validate SA2 boundary file and write ingestion manifest."""
    args = parse_args()
    logger = setup_logging()
    load_env()
    settings = load_settings()
    geospatial = settings.get("geospatial", {})

    if gpd is None:
        logger.error("geopandas is required. Install with: pip install -r requirements.txt")
        return 2

    source_path = Path(
        args.input
        or resolve_env_or_config("SA2_BOUNDARIES_PATH", geospatial.get("sa2_boundaries_path"))
    )
    layer = args.layer or os.getenv("SA2_BOUNDARY_LAYER", geospatial.get("sa2_boundary_layer")) or None
    output_dir = ensure_dir(args.output_dir)

    if not str(source_path).strip() or "<your_sa2_boundary_file" in str(source_path):
        logger.error(
            "SA2 boundary path is not configured. Set SA2_BOUNDARIES_PATH in .env or pass --input."
        )
        return 1
    if not source_path.exists():
        logger.error("SA2 boundary file not found: %s", source_path)
        return 1

    try:
        sa2_gdf = gpd.read_file(source_path, layer=layer) if layer else gpd.read_file(source_path)
        code_col, name_col = detect_sa2_columns(sa2_gdf.columns)
        manifest = {
            "source_file": str(source_path.resolve()),
            "sa2_layer": layer,
            "feature_count": int(len(sa2_gdf)),
            "crs": str(sa2_gdf.crs) if sa2_gdf.crs else None,
            "detected_sa2_code_column": code_col,
            "detected_sa2_name_column": name_col,
            "columns": list(sa2_gdf.columns),
            "validated_at": now_utc_iso(),
            "status": "validated",
        }
        manifest_path = output_dir / "sa2_boundaries_manifest.json"
        save_json_to_file(manifest, manifest_path)
        logger.info("Validated SA2 boundaries: %s features from %s", len(sa2_gdf), source_path)
        logger.info("Wrote manifest to %s", manifest_path)
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to validate SA2 boundaries: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
