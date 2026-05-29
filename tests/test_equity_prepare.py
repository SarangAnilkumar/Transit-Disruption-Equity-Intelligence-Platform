"""Tests for SEIFA preparation and ABS Excel detection."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from ingestion.geospatial_utils import detect_seifa_columns
from ingestion.seifa_excel import (
    detect_seifa_columns_robust,
    discover_best_seifa_table,
    read_seifa_file,
    scan_excel_workbook,
)
from ingestion.prepare_seifa_sa2 import _build_failure_report, main


def test_detect_seifa_columns_success() -> None:
    columns = ["SA2_CODE21", "SA2_NAME21", "IRSD score", "IRSD decile", "IRSD percentile"]
    detected = detect_seifa_columns(columns)
    assert detected["sa2_code"] == "SA2_CODE21"
    assert detected["sa2_name"] == "SA2_NAME21"
    assert detected["irsd_score"] == "IRSD score"
    assert detected["irsd_decile"] == "IRSD decile"
    assert detected["irsd_percentile"] == "IRSD percentile"


def test_detect_seifa_columns_missing_required_score() -> None:
    columns = ["SA2_CODE21", "SA2_NAME21", "Some Other Field"]
    detected = detect_seifa_columns(columns)
    assert detected["sa2_code"] == "SA2_CODE21"
    assert detected["sa2_name"] == "SA2_NAME21"
    assert detected["irsd_score"] is None


def test_detect_seifa_columns_robust_abs_headers() -> None:
    columns = [
        "2021 Statistical Area Level 2  (SA2) 9-Digit Code",
        "2021 Statistical Area Level 2 (SA2) Name ",
        "Score",
        "Decile",
        "Percentile",
    ]
    detected = detect_seifa_columns_robust(columns)
    assert detected["sa2_code"] is not None
    assert detected["sa2_name"] is not None
    assert detected["irsd_score"] == "Score"
    assert detected["irsd_decile"] == "Decile"
    assert detected["irsd_percentile"] == "Percentile"


def _write_abs_style_workbook(path: Path, include_sa2_sheet: bool = True) -> None:
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(
            {
                0: ["Australian Bureau of Statistics", "SEIFA Contents"],
                1: ["", "Contents"],
            }
        ).to_excel(writer, sheet_name="Contents", index=False, header=False)
        pd.DataFrame(
            {
                0: ["Australian Bureau of Statistics", "Table 4 IER"],
                1: ["", "Score"],
            }
        ).to_excel(writer, sheet_name="Table 4", index=False, header=False)
        if include_sa2_sheet:
            rows = [
                ["Australian Bureau of Statistics", "", "", "", "", "", ""],
                ["Socio-Economic Indexes for Australia (SEIFA), 2021", "", "", "", "", "", ""],
                ["Released at 11.30am (Canberra time) 27 April 2023", "", "", "", "", "", ""],
                [
                    "Table 2 Statistical Area Level 2 (SA2) Index of Relative Socio-economic Disadvantage",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                ],
                ["", "", "", "", "", "Ranking within Australia", ""],
                [
                    "2021 Statistical Area Level 2  (SA2) 9-Digit Code",
                    "2021 Statistical Area Level 2 (SA2) Name ",
                    "Usual Resident Population",
                    "Score",
                    "",
                    "Rank",
                    "Decile",
                    "Percentile",
                ],
                ["206011097", "Melbourne", "12000", "980.1", "", "900", "4", "40"],
                ["206011098", "Carlton", "8000", "1020.5", "", "1300", "6", "55"],
            ]
            pd.DataFrame(rows).to_excel(writer, sheet_name="Table 2", index=False, header=False)


def test_scan_excel_workbook_prefers_irsd_table(tmp_path: Path) -> None:
    workbook = tmp_path / "seifa_sample.xlsx"
    _write_abs_style_workbook(workbook)
    candidates = scan_excel_workbook(workbook)
    assert candidates
    assert candidates[0].sheet_name == "Table 2"
    assert candidates[0].header_row == 5


def test_read_seifa_file_from_abs_style_excel(tmp_path: Path) -> None:
    workbook = tmp_path / "seifa_sample.xlsx"
    _write_abs_style_workbook(workbook)
    result = read_seifa_file(workbook)
    assert result.sheet_name == "Table 2"
    assert len(result.dataframe) == 2
    assert result.detected_columns["irsd_score"] == "Score"
    assert result.detected_columns["irsd_decile"] == "Decile"
    assert result.detected_columns["irsd_percentile"] == "Percentile"


def test_discover_best_seifa_table_skips_non_sa2_sheet(tmp_path: Path) -> None:
    workbook = tmp_path / "seifa_no_sa2.xlsx"
    _write_abs_style_workbook(workbook, include_sa2_sheet=False)
    assert discover_best_seifa_table(workbook) is None


def test_prepare_seifa_cli_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workbook = tmp_path / "seifa_sample.xlsx"
    output_dir = tmp_path / "processed" / "equity"
    _write_abs_style_workbook(workbook)
    monkeypatch.setattr("sys.argv", ["prepare_seifa_sa2.py"])
    monkeypatch.setattr(
        "ingestion.prepare_seifa_sa2.resolve_env_or_config",
        lambda _key, _default: str(workbook),
    )
    monkeypatch.setattr(
        "ingestion.prepare_seifa_sa2.load_settings",
        lambda: {"equity": {"output_dir": str(output_dir), "seifa_release_year": 2021}},
    )
    exit_code = main()
    assert exit_code == 0
    assert (output_dir / "seifa_sa2_ready.csv").exists()
    assert (output_dir / "seifa_preparation_report.json").exists()


def test_prepare_seifa_cli_failure_writes_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workbook = tmp_path / "seifa_bad.xlsx"
    output_dir = tmp_path / "processed" / "equity"
    output_dir.mkdir(parents=True)
    with pd.ExcelWriter(workbook) as writer:
        pd.DataFrame({"A": ["Australian Bureau of Statistics"], "B": ["No SA2 table here"]}).to_excel(
            writer, sheet_name="Contents", index=False, header=False
        )
    monkeypatch.setattr("sys.argv", ["prepare_seifa_sa2.py"])
    monkeypatch.setattr(
        "ingestion.prepare_seifa_sa2.resolve_env_or_config",
        lambda _key, _default: str(workbook),
    )
    monkeypatch.setattr(
        "ingestion.prepare_seifa_sa2.load_settings",
        lambda: {"equity": {"output_dir": str(output_dir), "seifa_release_year": 2021}},
    )
    exit_code = main()
    assert exit_code == 1
    report_path = output_dir / "seifa_preparation_report.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text())
    assert report["status"] == "failed"
    assert "available_sheets" in report
    assert report["error_message"]


def test_failure_report_structure() -> None:
    report = _build_failure_report(
        source_path=Path("data/raw/equity/seifa/sample.xlsx"),
        error_message="missing columns",
        missing_required_fields=["irsd_score"],
    )
    assert report["status"] == "failed"
    assert report["missing_required_fields"] == ["irsd_score"]
    assert report["next_recommended_action"]
