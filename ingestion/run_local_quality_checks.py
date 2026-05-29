"""Run local data quality checks against warehouse-ready datasets."""

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
    get_dataset_schema,
    load_schema_registry,
    new_load_batch_id,
    now_utc_iso,
    resolve_dataset_names,
    run_quality_checks,
    write_quality_report,
)


def parse_args() -> argparse.Namespace:
    """Parse CLI args."""
    parser = argparse.ArgumentParser(description="Run local quality checks on warehouse-ready datasets.")
    parser.add_argument("--dataset", default="all")
    parser.add_argument("--input-dir", default=None)
    parser.add_argument("--schema-path", default="config/warehouse_schemas.yml")
    return parser.parse_args()


def _find_warehouse_file(input_root: Path, schema: dict[str, Any]) -> Path | None:
    domain = schema.get("domain", "misc")
    candidate = input_root / domain / f"{schema['dataset_name']}.csv"
    return candidate if candidate.exists() else None


def run_checks(
    dataset_group: str,
    input_root: Path,
    schema_path: Path,
) -> dict[str, Any]:
    """Run quality checks and return summary payload."""
    registry = load_schema_registry(schema_path)
    dataset_names = resolve_dataset_names(registry, dataset_group)
    batch_id = new_load_batch_id()
    created_at = now_utc_iso()

    summary: dict[str, Any] = {
        "load_batch_id": batch_id,
        "created_at": created_at,
        "input_dir": input_root.as_posix(),
        "datasets_checked": [],
        "errors": [],
        "warnings": [],
        "passed": [],
        "dataset_results": {},
    }

    for dataset_name in dataset_names:
        schema = get_dataset_schema(registry, dataset_name)
        warehouse_file = _find_warehouse_file(input_root, schema)
        if warehouse_file is None:
            message = f"{dataset_name}: warehouse-ready file not found"
            if schema.get("allow_empty"):
                summary["warnings"].append(message)
                continue
            summary["errors"].append(message)
            continue

        df = pd.read_csv(warehouse_file, dtype=str, keep_default_na=False)
        checks = run_quality_checks(df, schema)
        summary["datasets_checked"].append(dataset_name)
        summary["errors"].extend(checks["errors"])
        summary["warnings"].extend(checks["warnings"])
        summary["passed"].extend(checks["passed"])
        summary["dataset_results"][dataset_name] = {
            "warehouse_file": warehouse_file.as_posix(),
            "row_count": int(len(df)),
            **checks,
        }

    return summary


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    logger = setup_logging()
    load_env()
    settings = load_settings()
    paths = settings.get("paths", {})

    processed_root = Path(os.getenv("PROCESSED_DATA_DIR") or paths.get("processed_data_dir", "data/processed"))
    input_root = Path(args.input_dir or processed_root / "warehouse_ready")
    quality_dir = ensure_dir(input_root / "quality_reports")

    summary = run_checks(args.dataset, input_root, Path(args.schema_path))
    output_path = quality_dir / f"local_quality_summary_{summary['load_batch_id']}.json"
    write_quality_report(summary, output_path)

    logger.info("Wrote local quality summary to %s", output_path)
    logger.info("Passed checks: %s", len(summary["passed"]))
    logger.info("Warnings: %s", len(summary["warnings"]))
    logger.info("Errors: %s", len(summary["errors"]))

    return 1 if summary["errors"] and not summary["datasets_checked"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
