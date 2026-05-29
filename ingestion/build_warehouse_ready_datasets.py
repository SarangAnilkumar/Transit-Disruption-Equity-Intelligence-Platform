"""Build local warehouse-ready CSV datasets from processed outputs."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.utils import ensure_dir, load_env, load_settings, setup_logging  # noqa: E402
from ingestion.warehouse_utils import (  # noqa: E402
    build_dataset_quality_report,
    get_dataset_schema,
    load_schema_registry,
    new_load_batch_id,
    now_utc_iso,
    read_csv_sources,
    resolve_dataset_names,
    resolve_dataset_source_paths,
    run_quality_checks,
    safe_write_csv,
    standardize_dataset,
    write_manifest,
    write_quality_report,
)


def parse_args() -> argparse.Namespace:
    """Parse CLI args."""
    parser = argparse.ArgumentParser(description="Build warehouse-ready local datasets.")
    parser.add_argument("--dataset", default="all", help="Dataset group or dataset name.")
    parser.add_argument("--output-dir", default=None, help="Warehouse-ready output root.")
    parser.add_argument("--processed-dir", default=None, help="Processed data root to read from.")
    parser.add_argument("--schema-path", default="config/warehouse_schemas.yml")
    parser.add_argument("--write-manifest", action="store_true", default=True)
    return parser.parse_args()


def _warehouse_output_path(output_root: Path, schema: dict[str, Any]) -> Path:
    domain = schema.get("domain", "misc")
    return output_root / domain / f"{schema['dataset_name']}.csv"


def _quality_report_path(output_root: Path, dataset_name: str) -> Path:
    return output_root / "quality_reports" / f"{dataset_name}_quality_report.json"


def build_datasets(
    dataset_group: str,
    processed_root: Path,
    output_root: Path,
    schema_path: Path,
    write_manifest_flag: bool = True,
) -> dict[str, Any]:
    """Build warehouse-ready datasets and return run summary."""
    registry = load_schema_registry(schema_path)
    dataset_names = resolve_dataset_names(registry, dataset_group)
    load_batch_id = new_load_batch_id()
    created_at = now_utc_iso()

    ensure_dir(output_root / "manifests")
    ensure_dir(output_root / "quality_reports")

    summary: dict[str, Any] = {
        "load_batch_id": load_batch_id,
        "created_at": created_at,
        "datasets_processed": [],
        "source_files": {},
        "output_files": {},
        "row_counts": {},
        "quality_report_files": {},
        "warnings": [],
        "errors": [],
    }

    for dataset_name in dataset_names:
        schema = get_dataset_schema(registry, dataset_name)
        source_paths = resolve_dataset_source_paths(dataset_name, processed_root)
        if not source_paths:
            message = f"{dataset_name}: no source files found under {processed_root}"
            if schema.get("allow_empty"):
                summary["warnings"].append(message)
                continue
            summary["errors"].append(message)
            continue

        try:
            raw_df, source_label = read_csv_sources(source_paths)
            if raw_df.empty and not schema.get("allow_empty"):
                summary["errors"].append(f"{dataset_name}: source files exist but produced zero rows")
                continue

            standardized = standardize_dataset(raw_df, schema, source_label, load_batch_id)
            output_path = _warehouse_output_path(output_root, schema)
            safe_write_csv(standardized, output_path)

            quality_report = build_dataset_quality_report(standardized, schema, source_label)
            checks = run_quality_checks(standardized, schema)
            quality_report["checks"] = checks
            quality_path = _quality_report_path(output_root, dataset_name)
            write_quality_report(quality_report, quality_path)

            summary["datasets_processed"].append(dataset_name)
            summary["source_files"][dataset_name] = [path.as_posix() for path in source_paths]
            summary["output_files"][dataset_name] = output_path.as_posix()
            summary["row_counts"][dataset_name] = int(len(standardized))
            summary["quality_report_files"][dataset_name] = quality_path.as_posix()
            summary["warnings"].extend(checks["warnings"])
            summary["errors"].extend(checks["errors"])
        except Exception as exc:  # noqa: BLE001
            summary["errors"].append(f"{dataset_name}: {exc}")

    if write_manifest_flag:
        manifest_path = output_root / "manifests" / f"warehouse_manifest_{load_batch_id}.json"
        write_manifest(summary, manifest_path)
        summary["manifest_file"] = manifest_path.as_posix()

        ingestion_run = {
            "run_id": load_batch_id,
            "feed_name": "warehouse_ready_builder",
            "started_at": created_at,
            "finished_at": now_utc_iso(),
            "status": "success" if not summary["errors"] else "completed_with_errors",
            "records_loaded": sum(summary["row_counts"].values()),
            "source_file": processed_root.as_posix(),
            "datasets_processed": summary["datasets_processed"],
        }
        write_manifest(ingestion_run, output_root / "manifests" / f"ingestion_run_{load_batch_id}.json")

    return summary


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
    output_root = ensure_dir(
        Path(args.output_dir or processed_root / "warehouse_ready")
    )

    summary = build_datasets(
        dataset_group=args.dataset,
        processed_root=processed_root,
        output_root=output_root,
        schema_path=Path(args.schema_path),
        write_manifest_flag=args.write_manifest,
    )

    if summary["datasets_processed"]:
        logger.info(
            "Built %s warehouse-ready dataset(s): %s",
            len(summary["datasets_processed"]),
            ", ".join(summary["datasets_processed"]),
        )
    for warning in summary["warnings"]:
        logger.warning(warning)
    for error in summary["errors"]:
        logger.error(error)

    return 1 if summary["errors"] and not summary["datasets_processed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
