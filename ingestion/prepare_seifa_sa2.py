"""Prepare SEIFA data to a standard SA2-ready shape."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.geospatial_utils import now_utc_iso  # noqa: E402
from ingestion.seifa_excel import (  # noqa: E402
    discover_best_seifa_table,
    read_seifa_file,
    scan_excel_workbook,
)
from ingestion.seifa_validation import clean_seifa_sa2_dataframe  # noqa: E402
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


def _write_report(output_dir: Path, report: dict[str, Any]) -> None:
    save_json_to_file(report, output_dir / "seifa_preparation_report.json")


def _build_success_report(
    source_path: Path,
    read_result,
    output_csv: Path,
    cleaning_stats: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": "success",
        "input_file": str(source_path),
        "available_sheets": list(pd.ExcelFile(source_path).sheet_names)
        if source_path.suffix.lower() in {".xlsx", ".xls"}
        else ["csv"],
        "selected_sheet": read_result.sheet_name,
        "detected_header_row": read_result.header_row,
        "detected_columns": read_result.detected_columns,
        "original_columns": read_result.original_columns,
        "output_file": str(output_csv),
        "rows": cleaning_stats.get("valid_sa2_rows", 0),
        "input_rows": cleaning_stats.get("input_rows", 0),
        "valid_sa2_rows": cleaning_stats.get("valid_sa2_rows", 0),
        "dropped_invalid_sa2_code_rows": cleaning_stats.get("dropped_invalid_sa2_code_rows", 0),
        "dropped_invalid_sa2_name_rows": cleaning_stats.get("dropped_invalid_sa2_name_rows", 0),
        "dropped_missing_score_rows": cleaning_stats.get("dropped_missing_score_rows", 0),
        "suspicious_rows_sample": cleaning_stats.get("suspicious_rows_sample", []),
        "created_at": now_utc_iso(),
    }


def _build_failure_report(
    source_path: Path,
    error_message: str,
    scanned_sheets: list[dict[str, Any]] | None = None,
    detected_columns: dict[str, str | None] | None = None,
    missing_required_fields: list[str] | None = None,
    selected_sheet: str | None = None,
    detected_header_row: int | None = None,
) -> dict[str, Any]:
    available_sheets: list[str] = []
    if source_path.exists() and source_path.suffix.lower() in {".xlsx", ".xls"}:
        available_sheets = list(pd.ExcelFile(source_path).sheet_names)
    return {
        "status": "failed",
        "input_file": str(source_path),
        "available_sheets": available_sheets,
        "scanned_sheets": scanned_sheets or [],
        "selected_sheet": selected_sheet,
        "detected_header_row": detected_header_row,
        "detected_columns": detected_columns or {},
        "missing_required_fields": missing_required_fields or [],
        "error_message": error_message,
        "next_recommended_action": (
            "Confirm the workbook contains an SA2-level IRSD table (prefer Table 2) with "
            "SA2 code, SA2 name, and Score columns. If columns use non-standard names, "
            "provide a CSV export or update column detection rules."
        ),
        "created_at": now_utc_iso(),
    }


def _prepare_output(
    source_df: pd.DataFrame,
    col_map: dict[str, str | None],
    source_path: Path,
    release_year: int,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sa2_code": source_df[col_map["sa2_code"]].astype("string"),
            "sa2_name": source_df[col_map["sa2_name"]].astype("string"),
            "seifa_release_year": release_year,
            "irsd_score": pd.to_numeric(source_df[col_map["irsd_score"]], errors="coerce"),
            "irsd_decile": pd.to_numeric(source_df[col_map["irsd_decile"]], errors="coerce")
            if col_map.get("irsd_decile")
            else pd.NA,
            "irsd_percentile": pd.to_numeric(source_df[col_map["irsd_percentile"]], errors="coerce")
            if col_map.get("irsd_percentile")
            else pd.NA,
            "source_file": str(source_path),
            "prepared_at": now_utc_iso(),
        }
    )


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
        report = _build_failure_report(
            source_path=source_path,
            error_message="SEIFA source path is not configured. Set SEIFA_SA2_PATH or pass --input.",
        )
        _write_report(output_dir, report)
        logger.error(report["error_message"])
        return 1
    if not source_path.exists():
        report = _build_failure_report(
            source_path=source_path,
            error_message=f"SEIFA source file not found: {source_path}",
        )
        _write_report(output_dir, report)
        logger.error(report["error_message"])
        return 1

    scanned_sheets: list[dict[str, Any]] = []
    if source_path.suffix.lower() in {".xlsx", ".xls"}:
        scanned_sheets = [
            {
                "sheet_name": candidate.sheet_name,
                "header_row": candidate.header_row,
                "header_score": candidate.header_score,
                "sheet_bonus": candidate.sheet_bonus,
                "total_score": candidate.total_score,
                "title_hint": candidate.title_hint,
            }
            for candidate in scan_excel_workbook(source_path)
        ]

    try:
        read_result = read_seifa_file(source_path)
        col_map = read_result.detected_columns
        required = ["sa2_code", "sa2_name", "irsd_score"]
        missing = [name for name in required if not col_map.get(name)]
        if missing:
            report = _build_failure_report(
                source_path=source_path,
                error_message=(
                    f"Could not safely detect required SEIFA columns: {missing}. "
                    f"Found columns: {list(read_result.dataframe.columns)}"
                ),
                scanned_sheets=scanned_sheets,
                detected_columns=col_map,
                missing_required_fields=missing,
                selected_sheet=read_result.sheet_name,
                detected_header_row=read_result.header_row,
            )
            _write_report(output_dir, report)
            logger.error(report["error_message"])
            return 1

        prepared = _prepare_output(read_result.dataframe, col_map, source_path, release_year)
        out, cleaning_stats = clean_seifa_sa2_dataframe(prepared)
        if cleaning_stats["valid_sa2_rows"] == 0:
            report = _build_failure_report(
                source_path=source_path,
                error_message="No valid SA2 rows remained after SEIFA validation filtering.",
                scanned_sheets=scanned_sheets,
                detected_columns=col_map,
                missing_required_fields=["sa2_code", "irsd_score"],
                selected_sheet=read_result.sheet_name,
                detected_header_row=read_result.header_row,
            )
            report.update(cleaning_stats)
            _write_report(output_dir, report)
            logger.error(report["error_message"])
            return 1

        output_csv = output_dir / "seifa_sa2_ready.csv"
        out.to_csv(output_csv, index=False)
        report = _build_success_report(source_path, read_result, output_csv, cleaning_stats)
        _write_report(output_dir, report)
        logger.info(
            "Wrote SEIFA-ready data to %s using sheet=%s header_row=%s",
            output_csv,
            read_result.sheet_name,
            read_result.header_row,
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        selected = discover_best_seifa_table(source_path) if source_path.suffix.lower() in {".xlsx", ".xls"} else None
        report = _build_failure_report(
            source_path=source_path,
            error_message=str(exc),
            scanned_sheets=scanned_sheets,
            selected_sheet=selected.sheet_name if selected else None,
            detected_header_row=selected.header_row if selected else None,
        )
        _write_report(output_dir, report)
        logger.error("Failed to prepare SEIFA SA2 data: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
