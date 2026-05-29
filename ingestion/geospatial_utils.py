"""Shared helpers for Milestone 3 geospatial and equity preprocessing."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

SA2_CODE_CANDIDATES = [
    "SA2_CODE21",
    "SA2_MAIN21",
    "SA2_MAINCODE_2021",
    "SA2_CODE_2021",
    "SA2_MAINCODE",
    "sa2_code",
]
STOPS_SA2_MAPPING_COLUMNS = [
    "stop_id",
    "stop_name",
    "stop_lat",
    "stop_lon",
    "sa2_code",
    "sa2_name",
    "mapping_method",
    "is_matched",
    "mapping_created_at",
    "source_stops_path",
    "source_sa2_path",
]

SA2_NAME_CANDIDATES = [
    "SA2_NAME21",
    "SA2_NAME_2021",
    "SA2_NAME",
    "sa2_name",
]
SEIFA_SCORE_CANDIDATES = [
    "irsd_score",
    "index_of_relative_socioeconomic_disadvantage",
    "index_of_relative_socio-economic_disadvantage",
    "irsd",
    "irsd score",
]
SEIFA_DECILE_CANDIDATES = ["irsd_decile", "decile", "irsd decile"]
SEIFA_PERCENTILE_CANDIDATES = ["irsd_percentile", "percentile", "irsd percentile"]


def now_utc_iso() -> str:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def normalize_name(text: str) -> str:
    """Normalize column names for robust matching."""
    return text.strip().lower().replace("-", "_").replace(" ", "_")


def detect_column(columns: Iterable[str], candidates: list[str]) -> str | None:
    """Return the first matching column based on normalized names."""
    normalized_map = {normalize_name(col): col for col in columns}
    for candidate in candidates:
        found = normalized_map.get(normalize_name(candidate))
        if found:
            return found
    return None


def detect_sa2_columns(columns: Iterable[str]) -> tuple[str, str]:
    """Detect SA2 code and name columns or raise a clear error."""
    code_col = detect_column(columns, SA2_CODE_CANDIDATES)
    name_col = detect_column(columns, SA2_NAME_CANDIDATES)
    if not code_col or not name_col:
        raise ValueError(
            "Could not detect SA2 code/name columns. "
            f"Found columns: {list(columns)}. Expected code candidates: {SA2_CODE_CANDIDATES}; "
            f"name candidates: {SA2_NAME_CANDIDATES}"
        )
    return code_col, name_col


def detect_seifa_columns(columns: Iterable[str]) -> dict[str, str | None]:
    """Detect SEIFA columns and return mapping."""
    return {
        "sa2_code": detect_column(columns, SA2_CODE_CANDIDATES),
        "sa2_name": detect_column(columns, SA2_NAME_CANDIDATES),
        "irsd_score": detect_column(columns, SEIFA_SCORE_CANDIDATES),
        "irsd_decile": detect_column(columns, SEIFA_DECILE_CANDIDATES),
        "irsd_percentile": detect_column(columns, SEIFA_PERCENTILE_CANDIDATES),
    }


def validate_stop_columns(df: pd.DataFrame) -> None:
    """Validate required GTFS stops columns."""
    required = {"stop_id", "stop_name", "stop_lat", "stop_lon"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"stops.txt is missing required columns: {sorted(missing)}")


def valid_coordinate_mask(stops_df: pd.DataFrame) -> pd.Series:
    """Return boolean mask for rows with valid lat/lon coordinates."""
    lat = pd.to_numeric(stops_df["stop_lat"], errors="coerce")
    lon = pd.to_numeric(stops_df["stop_lon"], errors="coerce")
    return lat.between(-90, 90, inclusive="both") & lon.between(-180, 180, inclusive="both")


def latest_partition_file(base_dir: Path, suffix: str) -> Path:
    """Return latest file matching suffix beneath partitioned directories."""
    matches = sorted(base_dir.rglob(suffix))
    if not matches:
        raise FileNotFoundError(f"No file found for pattern '{suffix}' under '{base_dir}'.")
    return matches[-1]


def latest_partition_dir(base_dir: Path) -> Path:
    """Return latest partition directory under a base directory."""
    dirs = sorted([p for p in base_dir.rglob("*") if p.is_dir()])
    if not dirs:
        raise FileNotFoundError(f"No directories found under '{base_dir}'.")
    return dirs[-1]


def aggregate_route_sa2(
    routes_df: pd.DataFrame,
    trips_df: pd.DataFrame,
    stop_times_df: pd.DataFrame,
    mapping_df: pd.DataFrame,
) -> pd.DataFrame:
    """Build route-to-SA2 coverage aggregation."""
    stop_times = stop_times_df.copy()
    stop_times["stop_sequence"] = pd.to_numeric(stop_times["stop_sequence"], errors="coerce")
    joined = (
        stop_times.merge(trips_df[["trip_id", "route_id"]], on="trip_id", how="left")
        .merge(mapping_df[["stop_id", "sa2_code", "sa2_name", "is_matched"]], on="stop_id", how="left")
        .merge(
            routes_df[["route_id", "route_short_name", "route_long_name", "route_type"]],
            on="route_id",
            how="left",
        )
    )
    joined = joined[joined["is_matched"] == True]  # noqa: E712
    grouped = (
        joined.groupby(
            ["route_id", "route_short_name", "route_long_name", "route_type", "sa2_code", "sa2_name"],
            dropna=False,
        )
        .agg(
            stop_count_in_sa2=("stop_id", "nunique"),
            trip_count_serving_sa2=("trip_id", "nunique"),
            first_stop_sequence=("stop_sequence", "min"),
            last_stop_sequence=("stop_sequence", "max"),
        )
        .reset_index()
    )
    return grouped


def aggregate_sa2_disruption(
    trip_updates_df: pd.DataFrame,
    mapping_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Aggregate parsed trip updates to SA2 snapshot-date/hour grain."""
    updates = trip_updates_df.copy()
    updates["snapshot_timestamp"] = pd.to_datetime(updates["snapshot_timestamp"], errors="coerce", utc=True)
    updates["arrival_delay_seconds"] = pd.to_numeric(updates["arrival_delay_seconds"], errors="coerce")
    updates["departure_delay_seconds"] = pd.to_numeric(updates["departure_delay_seconds"], errors="coerce")
    updates["snapshot_date"] = updates["snapshot_timestamp"].dt.date.astype("string")
    updates["snapshot_hour"] = updates["snapshot_timestamp"].dt.hour
    enriched = updates.merge(
        mapping_df[["stop_id", "sa2_code", "sa2_name", "is_matched"]],
        on="stop_id",
        how="left",
    )
    enriched["is_matched"] = enriched["is_matched"].astype("boolean").fillna(False).astype(bool)
    enriched["is_delayed"] = (
        (enriched["arrival_delay_seconds"] > 300) | (enriched["departure_delay_seconds"] > 300)
    )

    base = (
        enriched.groupby(["snapshot_date", "snapshot_hour", "sa2_code", "sa2_name"], dropna=False)
        .agg(
            observation_count=("entity_id", "count"),
            distinct_trip_count=("trip_id", "nunique"),
            distinct_stop_count=("stop_id", "nunique"),
            delayed_observation_count=("is_delayed", "sum"),
            avg_arrival_delay_seconds=("arrival_delay_seconds", "mean"),
            avg_departure_delay_seconds=("departure_delay_seconds", "mean"),
            max_arrival_delay_seconds=("arrival_delay_seconds", "max"),
            max_departure_delay_seconds=("departure_delay_seconds", "max"),
            unmatched_stop_observation_count=("is_matched", lambda x: int((~x).sum())),
        )
        .reset_index()
    )

    report = {
        "total_observations": int(len(enriched)),
        "matched_observations": int(enriched["is_matched"].sum()),
        "unmatched_observations": int((~enriched["is_matched"]).sum()),
        "created_at": now_utc_iso(),
    }
    return base, report
