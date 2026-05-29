"""Helpers for reading ABS-style SEIFA Excel workbooks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from ingestion.geospatial_utils import detect_seifa_columns, normalize_name

HEADER_SCAN_ROWS = 50

SA2_CODE_HINTS = ("sa2_code_2021", "sa2_maincode_2021", "sa2_code21", "9-digit code", "sa2 code")
SA2_NAME_HINTS = ("sa2_name_2021", "sa2_name21", "sa2 name", "sa2) name")
IRSD_HINTS = (
    "index of relative socio-economic disadvantage",
    "index of relative socio economic disadvantage",
    "irsd",
)
IRSAD_HINTS = ("advantage and disadvantage", "irsad")
SCORE_HINTS = ("score",)
DECILE_HINTS = ("decile",)
PERCENTILE_HINTS = ("percentile",)


def normalize_column_label(text: str) -> str:
    """Normalize a column label for matching: strip, lowercase, collapse whitespace."""
    return re.sub(r"\s+", " ", str(text).strip().lower())


@dataclass(frozen=True)
class SeifaSheetCandidate:
    """Best header candidate for one worksheet."""

    sheet_name: str
    header_row: int
    header_score: int
    sheet_bonus: int
    title_hint: str | None

    @property
    def total_score(self) -> int:
        return self.header_score + self.sheet_bonus


@dataclass(frozen=True)
class SeifaTableReadResult:
    """Result of reading a SEIFA table from Excel."""

    dataframe: pd.DataFrame
    sheet_name: str
    header_row: int
    original_columns: list[str]
    detected_columns: dict[str, str | None]


def _cell_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return normalize_column_label(str(value))


def _row_texts(row: pd.Series) -> list[str]:
    return [_cell_text(value) for value in row.tolist() if _cell_text(value)]


def _contains_any(text: str, hints: tuple[str, ...]) -> bool:
    return any(hint in text for hint in hints)


def _sheet_title_bonus(preview: pd.DataFrame) -> tuple[int, str | None]:
    """Score worksheet title area for IRSD preference over IRSAD/IER/IEO."""
    title_cells: list[str] = []
    for _, row in preview.head(6).iterrows():
        title_cells.extend(_row_texts(row))
    joined = " | ".join(title_cells)
    bonus = 0
    hint: str | None = None

    if "table 2" in joined:
        bonus += 8
        hint = "table_2_irsd"
    if _contains_any(joined, IRSD_HINTS) and not _contains_any(joined, IRSAD_HINTS):
        bonus += 10
        hint = hint or "irsd"
    if _contains_any(joined, IRSAD_HINTS):
        bonus -= 8
    if "economic resources" in joined:
        bonus -= 8
    if "education and occupation" in joined:
        bonus -= 8
    if "excluded areas" in joined:
        bonus -= 20
    if joined.startswith("contents") or "explanatory notes" in joined:
        bonus -= 20
    return bonus, hint


def _score_header_row(row_texts: list[str], previous_row_texts: list[str] | None = None) -> int:
    """Score a candidate header row based on SA2 and SEIFA-related terms."""
    joined = " | ".join(row_texts)
    prev_joined = " | ".join(previous_row_texts or [])
    score = 0
    has_sa2_code = _contains_any(joined, SA2_CODE_HINTS) or ("sa2" in joined and "code" in joined)
    has_sa2_name = _contains_any(joined, SA2_NAME_HINTS) or ("sa2" in joined and "name" in joined)

    if has_sa2_code:
        score += 4
    if has_sa2_name:
        score += 4
    if _contains_any(joined, SCORE_HINTS):
        score += 3
    if _contains_any(joined, DECILE_HINTS):
        score += 2
    if _contains_any(joined, PERCENTILE_HINTS):
        score += 2
    if _contains_any(prev_joined, IRSD_HINTS) and not _contains_any(prev_joined, IRSAD_HINTS):
        score += 3
    if _contains_any(joined, IRSD_HINTS) and not _contains_any(joined, IRSAD_HINTS):
        score += 2
    if _contains_any(joined, IRSAD_HINTS):
        score -= 4

    # Penalize title-only rows.
    if "australian bureau of statistics" in joined and "sa2" not in joined:
        score -= 5

    if not (has_sa2_code and has_sa2_name):
        return 0
    return score


def scan_excel_workbook(path: Path, max_scan_rows: int = HEADER_SCAN_ROWS) -> list[SeifaSheetCandidate]:
    """Inspect all sheets and return ranked header candidates."""
    workbook = pd.ExcelFile(path)
    candidates: list[SeifaSheetCandidate] = []

    for sheet_name in workbook.sheet_names:
        preview = pd.read_excel(path, sheet_name=sheet_name, header=None, nrows=max_scan_rows)
        sheet_bonus, title_hint = _sheet_title_bonus(preview)
        best_header_row = -1
        best_header_score = -1

        for row_idx in range(min(max_scan_rows, len(preview))):
            row_texts = _row_texts(preview.iloc[row_idx])
            if not row_texts:
                continue
            prev_texts = _row_texts(preview.iloc[row_idx - 1]) if row_idx > 0 else None
            header_score = _score_header_row(row_texts, prev_texts)
            if header_score > best_header_score:
                best_header_score = header_score
                best_header_row = row_idx

        if best_header_row >= 0 and best_header_score > 0:
            candidates.append(
                SeifaSheetCandidate(
                    sheet_name=sheet_name,
                    header_row=best_header_row,
                    header_score=best_header_score,
                    sheet_bonus=sheet_bonus,
                    title_hint=title_hint,
                )
            )

    return sorted(candidates, key=lambda item: item.total_score, reverse=True)


def discover_best_seifa_table(path: Path) -> SeifaSheetCandidate | None:
    """Return the highest-scoring SEIFA worksheet/header combination."""
    candidates = scan_excel_workbook(path)
    if not candidates:
        return None
    return candidates[0]


def _clean_table(df: pd.DataFrame) -> pd.DataFrame:
    """Drop fully empty rows/columns and reset index."""
    cleaned = df.dropna(how="all").dropna(axis=1, how="all")
    return cleaned.reset_index(drop=True)


def detect_seifa_columns_robust(columns: list[str]) -> dict[str, str | None]:
    """Detect SEIFA columns with ABS-friendly partial matching."""
    base = detect_seifa_columns(columns)
    normalized_pairs = [(normalize_column_label(col), col) for col in columns]

    def find_substring(*substrings: str, exclude: tuple[str, ...] = ()) -> str | None:
        for norm, original in normalized_pairs:
            if any(ex in norm for ex in exclude):
                continue
            if all(part in norm for part in substrings):
                return original
        return None

    if not base["sa2_code"]:
        base["sa2_code"] = find_substring("9-digit", "code") or find_substring("sa2", "code")
    if not base["sa2_name"]:
        base["sa2_name"] = find_substring("sa2", "name")
    if not base["irsd_score"]:
        for norm, original in normalized_pairs:
            if norm == "score":
                base["irsd_score"] = original
                break
        if not base["irsd_score"]:
            base["irsd_score"] = find_substring("score", exclude=("irsad", "advantage and disadvantage"))
    if not base["irsd_decile"]:
        for norm, original in normalized_pairs:
            if norm == "decile":
                base["irsd_decile"] = original
                break
    if not base["irsd_percentile"]:
        for norm, original in normalized_pairs:
            if norm == "percentile":
                base["irsd_percentile"] = original
                break
    return base


def read_seifa_excel_table(path: Path, candidate: SeifaSheetCandidate) -> SeifaTableReadResult:
    """Read a SEIFA table using discovered sheet/header metadata."""
    raw_df = pd.read_excel(path, sheet_name=candidate.sheet_name, header=candidate.header_row)
    original_columns = [str(col) for col in raw_df.columns]
    cleaned = _clean_table(raw_df)
    detected = detect_seifa_columns_robust([str(col) for col in cleaned.columns])
    return SeifaTableReadResult(
        dataframe=cleaned,
        sheet_name=candidate.sheet_name,
        header_row=candidate.header_row,
        original_columns=original_columns,
        detected_columns=detected,
    )


def read_seifa_file(path: Path) -> SeifaTableReadResult:
    """Read SEIFA data from CSV or ABS-style Excel workbook."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = _clean_table(pd.read_csv(path))
        detected = detect_seifa_columns_robust([str(col) for col in df.columns])
        return SeifaTableReadResult(
            dataframe=df,
            sheet_name="csv",
            header_row=0,
            original_columns=[str(col) for col in df.columns],
            detected_columns=detected,
        )
    if suffix not in {".xlsx", ".xls"}:
        raise ValueError(f"Unsupported SEIFA file format: {suffix}. Use CSV or XLSX.")

    candidate = discover_best_seifa_table(path)
    if not candidate:
        raise ValueError("Could not detect a SEIFA header row in any worksheet.")
    return read_seifa_excel_table(path, candidate)
