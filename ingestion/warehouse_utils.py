"""Reusable helpers for warehouse-ready dataset preparation and quality checks."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from ingestion.seifa_validation import validate_seifa_sa2_quality
from ingestion.utils import ensure_dir, save_json_to_file

DEFAULT_SCHEMA_PATH = Path("config/warehouse_schemas.yml")
METADATA_COLUMNS = ["warehouse_dataset", "source_file", "prepared_at", "load_batch_id"]

TYPE_COERCERS: dict[str, Any] = {
    "string": lambda s: s.astype("string"),
    "integer": lambda s: pd.to_numeric(s, errors="coerce").astype("Int64"),
    "float": lambda s: pd.to_numeric(s, errors="coerce"),
    "boolean": lambda s: s.map(lambda value: str(value).strip().lower() in {"true", "1", "yes"}).astype("boolean"),
    "timestamp": lambda s: pd.to_datetime(s, errors="coerce", utc=True),
}


def now_utc_iso() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def new_load_batch_id() -> str:
    """Generate a unique load batch identifier."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]


def load_schema_registry(schema_path: str | Path = DEFAULT_SCHEMA_PATH) -> dict[str, Any]:
    """Load warehouse schema registry YAML."""
    path = Path(schema_path)
    if not path.exists():
        raise FileNotFoundError(f"Schema registry not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict) or "datasets" not in loaded:
        raise ValueError(f"Invalid schema registry format in {path}")
    return loaded


def get_dataset_schema(registry: dict[str, Any], dataset_name: str) -> dict[str, Any]:
    """Return schema definition for one dataset."""
    datasets = registry.get("datasets", {})
    if dataset_name not in datasets:
        raise KeyError(f"Unknown dataset: {dataset_name}")
    return datasets[dataset_name]


def resolve_dataset_names(registry: dict[str, Any], dataset_group: str) -> list[str]:
    """Resolve CLI dataset group to list of dataset names."""
    groups = registry.get("dataset_groups", {})
    if dataset_group == "all":
        return list(groups.get("all", []))
    if dataset_group in groups:
        return list(groups[dataset_group])
    if dataset_group in registry.get("datasets", {}):
        return [dataset_group]
    raise ValueError(f"Unknown dataset group or dataset: {dataset_group}")


def validate_required_columns(df: pd.DataFrame, schema: dict[str, Any]) -> list[str]:
    """Return missing required column names."""
    required = schema.get("required_columns", [])
    return [col for col in required if col not in df.columns]


def select_schema_columns(df: pd.DataFrame, schema: dict[str, Any]) -> pd.DataFrame:
    """Keep schema-defined business columns that exist in the source frame."""
    column_types = schema.get("column_types", {})
    keep = [col for col in column_types if col in df.columns]
    if not keep:
        keep = [col for col in schema.get("required_columns", []) if col in df.columns]
    return df[keep].copy()


def coerce_column_types(df: pd.DataFrame, schema: dict[str, Any]) -> pd.DataFrame:
    """Coerce dataframe columns to schema logical types."""
    coerced = df.copy()
    column_types = schema.get("column_types", {})
    for column, logical_type in column_types.items():
        if column not in coerced.columns:
            continue
        coercer = TYPE_COERCERS.get(logical_type)
        if coercer is None:
            continue
        coerced[column] = coercer(coerced[column])
    return coerced


def add_load_metadata(
    df: pd.DataFrame,
    source_file: str,
    dataset_name: str,
    load_batch_id: str,
    prepared_at: str | None = None,
) -> pd.DataFrame:
    """Append standard warehouse load metadata columns."""
    enriched = df.copy()
    enriched["warehouse_dataset"] = dataset_name
    enriched["source_file"] = source_file
    enriched["prepared_at"] = prepared_at or now_utc_iso()
    enriched["load_batch_id"] = load_batch_id
    return enriched


def calculate_row_count(df: pd.DataFrame) -> int:
    """Return dataframe row count."""
    return int(len(df))


def calculate_null_counts(df: pd.DataFrame, columns: list[str] | None = None) -> dict[str, int]:
    """Return null counts for selected columns."""
    target_cols = columns or list(df.columns)
    return {col: int(df[col].isna().sum()) for col in target_cols if col in df.columns}


def calculate_duplicate_counts(df: pd.DataFrame, natural_key: list[str]) -> int:
    """Return duplicate row count for a natural key."""
    if not natural_key or not all(col in df.columns for col in natural_key):
        return 0
    return int(df.duplicated(subset=natural_key, keep=False).sum())


def build_dataset_quality_report(
    df: pd.DataFrame,
    schema: dict[str, Any],
    source_file: str,
) -> dict[str, Any]:
    """Build a per-dataset quality report snapshot."""
    natural_key = schema.get("natural_key", [])
    required = schema.get("required_columns", [])
    missing_required = validate_required_columns(df, schema)
    return {
        "dataset_name": schema.get("dataset_name"),
        "source_file": source_file,
        "row_count": calculate_row_count(df),
        "missing_required_columns": missing_required,
        "null_counts": calculate_null_counts(df, required),
        "duplicate_natural_key_count": calculate_duplicate_counts(df, natural_key),
        "natural_key": natural_key,
        "created_at": now_utc_iso(),
    }


def write_manifest(payload: dict[str, Any], output_path: str | Path) -> Path:
    """Write warehouse manifest JSON."""
    return save_json_to_file(payload, output_path)


def write_quality_report(payload: dict[str, Any], output_path: str | Path) -> Path:
    """Write dataset quality report JSON."""
    return save_json_to_file(payload, output_path)


def safe_write_csv(df: pd.DataFrame, output_path: str | Path) -> Path:
    """Write CSV with parent directory creation."""
    destination = Path(output_path)
    ensure_dir(destination.parent)
    df.to_csv(destination, index=False)
    return destination


def resolve_glob_paths(pattern: str, base_dir: Path | None = None) -> list[Path]:
    """Resolve glob patterns relative to repo root or base_dir."""
    root = base_dir or Path(".")
    if pattern.startswith("data/"):
        matches = sorted(Path(".").glob(pattern))
    else:
        matches = sorted(root.glob(pattern))
    return [Path(match) for match in matches]


def find_latest_static_file(processed_root: Path, filename: str) -> Path | None:
    """Find latest GTFS static processed file by load_date partition."""
    matches = sorted((processed_root / "gtfs_static").rglob(filename))
    return matches[-1] if matches else None


def find_realtime_parsed_files(processed_root: Path, feed_name: str) -> list[Path]:
    """Find all parsed GTFS-R CSV files for a feed."""
    feed_dir = processed_root / "gtfs_realtime" / f"feed={feed_name}"
    if not feed_dir.exists():
        return []
    return sorted(feed_dir.rglob("parsed.csv"))


def read_csv_sources(source_paths: list[Path]) -> tuple[pd.DataFrame, str]:
    """Read and concatenate one or more CSV/TXT sources."""
    if not source_paths:
        return pd.DataFrame(), ""
    frames = [pd.read_csv(path, dtype=str, keep_default_na=False) for path in source_paths]
    combined = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    source_label = source_paths[0].as_posix() if len(source_paths) == 1 else f"{len(source_paths)} files under {source_paths[0].parent.as_posix()}"
    return combined, source_label


def resolve_dataset_source_paths(dataset_name: str, processed_root: Path) -> list[Path]:
    """Resolve concrete source paths for a dataset from processed data layout."""
    static_map = {
        "gtfs_stops": "stops.txt",
        "gtfs_routes": "routes.txt",
        "gtfs_trips": "trips.txt",
        "gtfs_stop_times": "stop_times.txt",
    }
    if dataset_name in static_map:
        latest = find_latest_static_file(processed_root, static_map[dataset_name])
        return [latest] if latest else []

    if dataset_name == "gtfs_trip_updates":
        return find_realtime_parsed_files(processed_root, "trip_updates")
    if dataset_name == "gtfs_service_alerts":
        return find_realtime_parsed_files(processed_root, "service_alerts")

    direct_files = {
        "stops_sa2_mapping": processed_root / "geospatial" / "stops_sa2_mapping.csv",
        "route_sa2_coverage": processed_root / "geospatial" / "route_sa2_coverage.csv",
        "sa2_disruption_observations_base": processed_root / "analytics" / "sa2_disruption_observations_base.csv",
        "seifa_sa2_ready": processed_root / "equity" / "seifa_sa2_ready.csv",
    }
    if dataset_name in direct_files:
        path = direct_files[dataset_name]
        return [path] if path.exists() else []
    return []


def standardize_dataset(
    df: pd.DataFrame,
    schema: dict[str, Any],
    source_file: str,
    load_batch_id: str,
) -> pd.DataFrame:
    """Select, coerce, and annotate one dataset."""
    selected = select_schema_columns(df, schema)
    coerced = coerce_column_types(selected, schema)
    return add_load_metadata(
        coerced,
        source_file=source_file,
        dataset_name=schema["dataset_name"],
        load_batch_id=load_batch_id,
    )


def run_quality_checks(df: pd.DataFrame, schema: dict[str, Any]) -> dict[str, list[str]]:
    """Run local quality checks; return errors, warnings, and passed messages."""
    errors: list[str] = []
    warnings: list[str] = []
    passed: list[str] = []
    dataset_name = schema.get("dataset_name", "unknown")
    allow_empty = bool(schema.get("allow_empty", False))

    missing_required = validate_required_columns(df, schema)
    if missing_required:
        errors.append(f"{dataset_name}: missing required columns: {missing_required}")
    else:
        passed.append(f"{dataset_name}: all required columns present")

    row_count = calculate_row_count(df)
    if row_count == 0 and not allow_empty:
        errors.append(f"{dataset_name}: row count is zero")
    elif row_count == 0:
        warnings.append(f"{dataset_name}: row count is zero (allowed for this dataset)")
    else:
        passed.append(f"{dataset_name}: row count = {row_count}")

    for column in schema.get("required_columns", []):
        if column in df.columns and df[column].isna().all():
            errors.append(f"{dataset_name}: required column '{column}' is entirely null")

    natural_key = schema.get("natural_key", [])
    dup_count = calculate_duplicate_counts(df, natural_key)
    if dup_count > 0:
        warnings.append(f"{dataset_name}: {dup_count} duplicate rows on natural key {natural_key}")
    elif natural_key:
        passed.append(f"{dataset_name}: no duplicate natural keys")

    for column in schema.get("timestamp_columns", []):
        if column not in df.columns:
            continue
        parsed = pd.to_datetime(df[column], errors="coerce", utc=True)
        invalid = int(parsed.isna().sum() - df[column].isna().sum())
        if invalid > 0:
            warnings.append(f"{dataset_name}: {invalid} non-null values in '{column}' failed timestamp parsing")
        else:
            passed.append(f"{dataset_name}: timestamp column '{column}' parseable")

    if "stop_lat" in df.columns and "stop_lon" in df.columns:
        lat = pd.to_numeric(df["stop_lat"], errors="coerce")
        lon = pd.to_numeric(df["stop_lon"], errors="coerce")
        invalid_coords = int((~lat.between(-90, 90, inclusive="both") | ~lon.between(-180, 180, inclusive="both")).sum())
        if invalid_coords > 0:
            warnings.append(f"{dataset_name}: {invalid_coords} rows with out-of-range lat/lon")
        else:
            passed.append(f"{dataset_name}: lat/lon within valid ranges")

    if dataset_name in {"gtfs_trip_updates", "sa2_disruption_observations_base"}:
        for delay_col in ("arrival_delay_seconds", "departure_delay_seconds", "max_arrival_delay_seconds", "max_departure_delay_seconds"):
            if delay_col not in df.columns:
                continue
            delays = pd.to_numeric(df[delay_col], errors="coerce")
            out_of_range = delays.notna() & ((delays < -3600) | (delays > 86400))
            count = int(out_of_range.sum())
            if count > 0:
                warnings.append(f"{dataset_name}: {count} rows in '{delay_col}' outside [-3600, 86400]")
            else:
                passed.append(f"{dataset_name}: '{delay_col}' within expected range")

    if dataset_name == "stops_sa2_mapping" and "is_matched" in df.columns and "sa2_code" in df.columns:
        matched = df["is_matched"].astype(str).str.lower().isin({"true", "1", "yes"})
        missing_sa2 = matched & df["sa2_code"].isna()
        count = int(missing_sa2.sum())
        if count > 0:
            errors.append(f"{dataset_name}: {count} matched stops missing sa2_code")
        else:
            passed.append(f"{dataset_name}: matched stops have sa2_code")

    if dataset_name == "seifa_sa2_ready":
        seifa_errors = validate_seifa_sa2_quality(df, dataset_name=dataset_name)
        if seifa_errors:
            errors.extend(seifa_errors)
        else:
            passed.append(f"{dataset_name}: SA2 code and IRSD score validation passed")

    return {"errors": errors, "warnings": warnings, "passed": passed}


def build_reconciliation_entry(
    dataset_name: str,
    source_row_count: int,
    warehouse_row_count: int,
    source_files: list[str],
    warehouse_file: str | None,
) -> dict[str, Any]:
    """Build one reconciliation report entry."""
    delta = warehouse_row_count - source_row_count
    status = "match"
    if warehouse_row_count == 0 and source_row_count == 0:
        status = "both_empty"
    elif delta != 0:
        status = "mismatch"
    return {
        "dataset_name": dataset_name,
        "source_row_count": source_row_count,
        "warehouse_row_count": warehouse_row_count,
        "delta": delta,
        "status": status,
        "source_files": source_files,
        "warehouse_file": warehouse_file,
    }
