"""Prepare SEIFA data to a standard SA2-ready shape."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.geospatial_utils import detect_seifa_columns, now_utc_iso  # noqa: E402
from ingestion.utils import (  # noqa: E402
    ensure_dir,
    load_env,
    load_settings,
    resolve_env_or_config,
    save_json_to_file,
    setup_logging,
)


def parse_args() -> argparse.Namespace:
    """Parse CLI args."""
    parser = argparse.ArgumentParser(description="Prepare SEIFA SA2 data.")
    parser.add_argument("--input")
    parser.add_argument("--output-dir")
    return parser.parse_args()


def _read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported SEIFA file format: {suffix}. Use CSV or XLSX.")


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    logger = setup_logging()
    load_env()
    settings = load_settings()
    equity_settings = settings.get("equity", {})

    source_path = Path(
        args.input
        or resolve_env_or_config("SEIFA_SA2_PATH", equity_settings.get("seifa_sa2_path"))
    )
    output_dir = ensure_dir(Path(args.output_dir or equity_settings.get("output_dir", "data/processed/equity")))
    release_year = int(equity_settings.get("seifa_release_year", 2021))

    if not str(source_path).strip() or "<your_seifa_sa2_file" in str(source_path):
        logger.error("SEIFA source path is not configured. Set SEIFA_SA2_PATH or pass --input.")
        return 1
    if not source_path.exists():
        logger.error("SEIFA source file not found: %s", source_path)
        return 1

    try:
        source_df = _read_table(source_path)
        col_map = detect_seifa_columns(source_df.columns)
        required = ["sa2_code", "sa2_name", "irsd_score"]
        missing = [name for name in required if not col_map.get(name)]
        if missing:
            raise ValueError(
                f"Could not safely detect required SEIFA columns: {missing}. "
                f"Found columns: {list(source_df.columns)}"
            )

        out = pd.DataFrame(
            {
                "sa2_code": source_df[col_map["sa2_code"]].astype("string"),
                "sa2_name": source_df[col_map["sa2_name"]].astype("string"),
                "seifa_release_year": release_year,
                "irsd_score": pd.to_numeric(source_df[col_map["irsd_score"]], errors="coerce"),
                "irsd_decile": pd.to_numeric(source_df[col_map["irsd_decile"]], errors="coerce")
                if col_map["irsd_decile"]
                else pd.NA,
                "irsd_percentile": pd.to_numeric(source_df[col_map["irsd_percentile"]], errors="coerce")
                if col_map["irsd_percentile"]
                else pd.NA,
                "source_file": str(source_path),
                "prepared_at": now_utc_iso(),
            }
        )
        output_csv = output_dir / "seifa_sa2_ready.csv"
        out.to_csv(output_csv, index=False)
        report = {
            "source_file": str(source_path),
            "input_columns": list(source_df.columns),
            "detected_columns": col_map,
            "output_file": str(output_csv),
            "rows": int(len(out)),
            "created_at": now_utc_iso(),
        }
        save_json_to_file(report, output_dir / "seifa_preparation_report.json")
        logger.info("Wrote SEIFA-ready data to %s", output_csv)
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to prepare SEIFA SA2 data: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
