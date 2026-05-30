"""Orchestrate refresh steps after new GTFS-R snapshot collection."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.utils import setup_logging  # noqa: E402

LOCAL_STEPS = [
    ["python", "ingestion/audit_gtfsr_snapshot_coverage.py"],
    ["python", "ingestion/build_sa2_disruption_base.py"],
    ["python", "ingestion/build_warehouse_ready_datasets.py", "--dataset", "gtfs_realtime"],
    ["python", "ingestion/build_warehouse_ready_datasets.py", "--dataset", "analytics"],
    ["python", "ingestion/run_local_quality_checks.py", "--dataset", "all"],
    ["python", "ingestion/reconcile_processed_outputs.py"],
]

S3_STEPS = [
    ["python", "ingestion/upload_warehouse_ready_to_s3.py", "--dataset", "gtfs_trip_updates"],
    ["python", "ingestion/upload_warehouse_ready_to_s3.py", "--dataset", "gtfs_service_alerts"],
    [
        "python",
        "ingestion/upload_warehouse_ready_to_s3.py",
        "--dataset",
        "sa2_disruption_observations_base",
    ],
]

REDSHIFT_STEPS = [
    [
        "python",
        "ingestion/load_s3_to_redshift_raw.py",
        "--dataset",
        "gtfs_trip_updates",
        "--truncate-before-load",
    ],
    [
        "python",
        "ingestion/load_s3_to_redshift_raw.py",
        "--dataset",
        "gtfs_service_alerts",
        "--truncate-before-load",
    ],
    [
        "python",
        "ingestion/load_s3_to_redshift_raw.py",
        "--dataset",
        "sa2_disruption_observations_base",
        "--truncate-before-load",
    ],
]

DBT_STEPS = [
    ["dbt", "run", "--project-dir", "dbt_transit_equity", "--profiles-dir", "dbt_transit_equity"],
    ["dbt", "test", "--project-dir", "dbt_transit_equity", "--profiles-dir", "dbt_transit_equity"],
    ["dbt", "docs", "generate", "--project-dir", "dbt_transit_equity", "--profiles-dir", "dbt_transit_equity"],
]

ANALYST_STEPS = [
    ["python", "ingestion/export_analyst_report_outputs.py"],
    ["python", "ingestion/create_analyst_report_visuals.py"],
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh pipeline after GTFS-R collection.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--include-s3", action="store_true")
    parser.add_argument("--include-redshift", action="store_true")
    parser.add_argument("--include-dbt", action="store_true")
    parser.add_argument("--include-analyst-exports", action="store_true")
    return parser.parse_args()


def _run_step(step: list[str], dry_run: bool, logger) -> int:
    cmd = " ".join(step)
    if dry_run:
        logger.info("[dry-run] %s", cmd)
        return 0
    logger.info("Running: %s", cmd)
    result = subprocess.run(step, check=False)
    return int(result.returncode)


def main() -> int:
    args = parse_args()
    logger = setup_logging()
    repo_root = Path(__file__).resolve().parents[1]
    steps = list(LOCAL_STEPS)
    if args.include_s3:
        steps.extend(S3_STEPS)
    if args.include_redshift:
        steps.extend(REDSHIFT_STEPS)
    if args.include_dbt:
        steps.extend(DBT_STEPS)
    if args.include_analyst_exports:
        steps.extend(ANALYST_STEPS)

    failures = 0
    for step in steps:
        code = _run_step(step, args.dry_run, logger)
        if code != 0:
            failures += 1
            logger.error("Step failed (%s): %s", code, " ".join(step))
            break
    if failures:
        return 1
    logger.info("Refresh sequence completed (%s steps).", len(steps))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
