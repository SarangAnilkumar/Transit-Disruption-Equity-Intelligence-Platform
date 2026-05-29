"""Validation helpers for SEIFA SA2-ready outputs."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

SA2_CODE_PATTERN = re.compile(r"^\d{9}$")
SA2_CODE_MAX_LENGTH = 32
FOOTER_NAME_MARKERS = (
    "commonwealth of australia",
    "australian bureau of statistics",
    "socio-economic indexes for australia",
)


def normalize_sa2_code(value: Any) -> str | None:
    """Normalize SA2 code to stripped string or None."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def is_valid_sa2_code(value: Any) -> bool:
    """Return True when value is a 9-digit SA2 code."""
    text = normalize_sa2_code(value)
    if text is None:
        return False
    return bool(SA2_CODE_PATTERN.match(text))


def is_valid_sa2_name(value: Any) -> bool:
    """Return True when SA2 name is present and not an ABS footer/title string."""
    if pd.isna(value):
        return False
    text = str(value).strip()
    if not text:
        return False
    if text.startswith("©"):
        return False
    lowered = text.lower()
    return not any(marker in lowered for marker in FOOTER_NAME_MARKERS)


def clean_seifa_sa2_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Filter SEIFA rows to valid SA2 records and return cleaning statistics."""
    input_rows = int(len(df))
    suspicious_rows_sample: list[dict[str, Any]] = []

    working = df.copy()
    working["sa2_code"] = working["sa2_code"].map(normalize_sa2_code).astype("string")
    working["sa2_name"] = working["sa2_name"].astype("string").str.strip()

    invalid_code_mask = ~working["sa2_code"].map(is_valid_sa2_code)
    dropped_invalid_sa2_code_rows = int(invalid_code_mask.sum())
    if dropped_invalid_sa2_code_rows:
        suspicious_rows_sample.extend(
            _sample_rows(working.loc[invalid_code_mask], "invalid_sa2_code")
        )
    working = working.loc[~invalid_code_mask].copy()

    invalid_name_mask = ~working["sa2_name"].map(is_valid_sa2_name)
    dropped_invalid_sa2_name_rows = int(invalid_name_mask.sum())
    if dropped_invalid_sa2_name_rows:
        suspicious_rows_sample.extend(
            _sample_rows(working.loc[invalid_name_mask], "invalid_sa2_name")
        )
    working = working.loc[~invalid_name_mask].copy()

    working["irsd_score"] = pd.to_numeric(working["irsd_score"], errors="coerce")
    missing_score_mask = working["irsd_score"].isna()
    dropped_missing_score_rows = int(missing_score_mask.sum())
    if dropped_missing_score_rows:
        suspicious_rows_sample.extend(
            _sample_rows(working.loc[missing_score_mask], "missing_irsd_score")
        )
    working = working.loc[~missing_score_mask].copy()

    if "irsd_decile" in working.columns:
        working["irsd_decile"] = pd.to_numeric(working["irsd_decile"], errors="coerce")
    if "irsd_percentile" in working.columns:
        working["irsd_percentile"] = pd.to_numeric(working["irsd_percentile"], errors="coerce")

    stats = {
        "input_rows": input_rows,
        "valid_sa2_rows": int(len(working)),
        "dropped_invalid_sa2_code_rows": dropped_invalid_sa2_code_rows,
        "dropped_invalid_sa2_name_rows": dropped_invalid_sa2_name_rows,
        "dropped_missing_score_rows": dropped_missing_score_rows,
        "suspicious_rows_sample": suspicious_rows_sample[:10],
    }
    return working, stats


def _sample_rows(frame: pd.DataFrame, reason: str, limit: int = 3) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for _, row in frame.head(limit).iterrows():
        sample = {column: _json_safe_value(row[column]) for column in row.index}
        sample["validation_reason"] = reason
        samples.append(sample)
    return samples


def _json_safe_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def validate_seifa_sa2_quality(df: pd.DataFrame, dataset_name: str = "seifa_sa2_ready") -> list[str]:
    """Return quality check error messages for SEIFA warehouse-ready data."""
    errors: list[str] = []
    if "sa2_code" not in df.columns:
        return [f"{dataset_name}: missing sa2_code column"]

    codes = df["sa2_code"].astype("string").str.strip()
    long_codes = codes.notna() & (codes.str.len() > SA2_CODE_MAX_LENGTH)
    if int(long_codes.sum()) > 0:
        errors.append(f"{dataset_name}: {int(long_codes.sum())} sa2_code values exceed {SA2_CODE_MAX_LENGTH} characters")

    non_numeric_codes = codes.notna() & ~codes.map(is_valid_sa2_code)
    if int(non_numeric_codes.sum()) > 0:
        errors.append(f"{dataset_name}: {int(non_numeric_codes.sum())} sa2_code values are not valid 9-digit codes")

    if "irsd_score" not in df.columns:
        errors.append(f"{dataset_name}: missing irsd_score column")
    else:
        scores = pd.to_numeric(df["irsd_score"], errors="coerce")
        if scores.isna().any():
            errors.append(f"{dataset_name}: {int(scores.isna().sum())} rows have missing or non-numeric irsd_score")

    return errors
