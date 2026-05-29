"""Reconcile row counts between processed sources and warehouse-ready outputs."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.utils import ensure_dir, load_env, load_settings, setup_logging  # noqa: E402
from ingestion.warehouse_utils import (  # noqa: E402
    build_reconciliation_entry,
    get_dataset_schema,
    load_schema_registry,
    new_load_batch_id,
    now_utc_iso,
    read_csv_sources,
    resolve_dataset_names,
    resolve_dataset_source_paths,
    write_quality_report,
)


def parse_args() -> argparse.Namespace:
    """Parse CLI args."""
    parser = argparse.ArgumentParser(description="Reconcile processed vs warehouse-ready row counts.")
    parser.add_argument("--dataset", default="all")
    parser.add_argument("--processed-dir", default=None)
    parser.add_argument("--warehouse-dir", default=None)
    parser.add_argument("--schema-path", default="config/warehouse_schemas.yml")
    return parser.parse_args()


def _find_warehouse_file(warehouse_root: Path, schema: dict[str, Any]) -> Path | None:
    domain = schema.get("domain", "misc")
    candidate = warehouse_root / domain / f"{schema['dataset_name']}.csv"
    return candidate if candidate.exists() else None


def reconcile(
    dataset_group: str,
    processed_root: Path,
    warehouse_root: Path,
    schema_path: Path,
) -> dict[str, Any]:
    """Compare source and warehouse row counts."""
    registry = load_schema_registry(schema_path)
    dataset_names = resolve_dataset_names(registry, dataset_group)
    batch_id = new_load_batch_id()

    report: dict[str, Any] = {
        "load_batch_id": batch_id,
        "created_at": now_utc_iso(),
        "processed_dir": processed_root.as_posix(),
        "warehouse_dir": warehouse_root.as_posix(),
        "entries": [],
        "matches": 0,
        "mismatches": 0,
        "missing_warehouse_files": 0,
        "missing_source_files": 0,
    }

    for dataset_name in dataset_names:
        schema = get_dataset_schema(registry, dataset_name)
        source_paths = resolve_dataset_source_paths(dataset_name, processed_root)
        warehouse_file = _find_warehouse_file(warehouse_root, schema)

        if not source_paths:
            report["missing_source_files"] += 1
            report["entries"].append(
                build_reconciliation_entry(dataset_name, 0, 0, [], warehouse_file.as_posix() if warehouse_file else None)
                | {"note": "source files missing"}
            )
            continue

        source_df, _ = read_csv_sources(source_paths)
        source_count = int(len(source_df))
        warehouse_count = 0
        if warehouse_file and warehouse_file.exists():
            warehouse_count = int(len(pd.read_csv(warehouse_file, dtype=str, keep_default_na=False)))
        else:
            report["missing_warehouse_files"] += 1

        entry = build_reconciliation_entry(
            dataset_name,
            source_count,
            warehouse_count,
            [path.as_posix() for path in source_paths],
            warehouse_file.as_posix() if warehouse_file else None,
        )
        report["entries"].append(entry)
        if entry["status"] == "match":
            report["matches"] += 1
        elif entry["status"] == "mismatch":
            report["mismatches"] += 1

    return report


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    logger = setup_logging()
    load_env()
    settings = load_settings()
    paths = settings.get("paths", {})

    processed_root = Path(
        args.processed_dir
        or os.getenv("PROCESSED_DATA_DIR")
        or paths.get("processed_data_dir", "data/processed")
    )
    warehouse_root = Path(args.warehouse_dir or processed_root / "warehouse_ready")
    quality_dir = ensure_dir(warehouse_root / "quality_reports")

    report = reconcile(args.dataset, processed_root, warehouse_root, Path(args.schema_path))
    output_path = quality_dir / f"reconciliation_report_{report['load_batch_id']}.json"
    write_quality_report(report, output_path)

    logger.info("Wrote reconciliation report to %s", output_path)
    logger.info(
        "Matches=%s mismatches=%s missing_warehouse=%s missing_source=%s",
        report["matches"],
        report["mismatches"],
        report["missing_warehouse_files"],
        report["missing_source_files"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
