"""Load warehouse-ready CSV files from S3 into Redshift raw tables."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.aws_utils import build_s3_key, ensure_s3_prefix_style, validate_s3_config  # noqa: E402
from ingestion.redshift_utils import (  # noqa: E402
    build_copy_sql,
    check_table_row_count,
    copy_csv_from_s3,
    get_redshift_connection_from_env,
    validate_redshift_config,
    write_load_report,
)
from ingestion.utils import ensure_dir, load_env, load_settings, setup_logging  # noqa: E402
from ingestion.warehouse_utils import (  # noqa: E402
    get_dataset_schema,
    load_schema_registry,
    new_load_batch_id,
    now_utc_iso,
    resolve_dataset_names,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="COPY warehouse-ready S3 files into Redshift raw tables.")
    parser.add_argument("--dataset", default="all")
    parser.add_argument("--input-dir", default=None)
    parser.add_argument("--bucket", default=None)
    parser.add_argument("--prefix", default=None)
    parser.add_argument("--schema-path", default="config/warehouse_schemas.yml")
    parser.add_argument("--truncate-before-load", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-dir", default=None)
    return parser.parse_args()


def _warehouse_csv_path(input_dir: Path, schema: dict[str, Any]) -> Path:
    domain = schema.get("domain", "misc")
    return input_dir / domain / f"{schema['dataset_name']}.csv"


def build_load_plans(
    registry: dict[str, Any],
    dataset_group: str,
    input_dir: Path,
    bucket: str,
    prefix: str,
    schema_raw: str,
) -> list[dict[str, Any]]:
    """Build COPY load plans for selected datasets."""
    plans: list[dict[str, Any]] = []
    for dataset_name in resolve_dataset_names(registry, dataset_group):
        schema = get_dataset_schema(registry, dataset_name)
        local_path = _warehouse_csv_path(input_dir, schema)
        if not local_path.exists():
            if schema.get("allow_empty"):
                continue
            plans.append(
                {
                    "dataset_name": dataset_name,
                    "status": "missing_local_file",
                    "local_path": local_path.as_posix(),
                }
            )
            continue
        domain = schema.get("domain", "misc")
        key = build_s3_key(prefix, dataset_name, local_path.name, domain=domain)
        s3_uri = f"s3://{bucket}/{key}"
        table = schema.get("future_redshift_table", dataset_name)
        plans.append(
            {
                "dataset_name": dataset_name,
                "status": "ready",
                "local_path": local_path.as_posix(),
                "s3_uri": s3_uri,
                "schema": schema_raw,
                "table": table,
            }
        )
    return plans


def main() -> int:
    args = parse_args()
    logger = setup_logging()
    load_env()
    settings = load_settings()
    warehouse_settings = settings.get("warehouse", {})
    aws_settings = settings.get("aws", {})

    missing_s3, s3_config = validate_s3_config()
    bucket = args.bucket or s3_config["bucket"]
    prefix = ensure_s3_prefix_style(
        args.prefix or os.getenv("S3_WAREHOUSE_READY_PREFIX") or aws_settings.get(
            "warehouse_ready_prefix", "transit-equity/warehouse_ready"
        )
    )
    if not bucket:
        logger.error(
            "Missing S3 bucket. Set S3_BUCKET_NAME in .env or pass --bucket "
            "(required even for --dry-run COPY planning)."
        )
        return 1

    input_dir = Path(
        args.input_dir
        or warehouse_settings.get("output_dir", "data/processed/warehouse_ready")
    )
    registry = load_schema_registry(Path(args.schema_path))
    _, redshift_config = validate_redshift_config()
    schema_raw = redshift_config.get("schema_raw", "raw")

    plans = build_load_plans(registry, args.dataset, input_dir, bucket, prefix, schema_raw)
    batch_id = new_load_batch_id()
    report_dir = ensure_dir(
        Path(args.report_dir or warehouse_settings.get("output_dir", "data/processed/warehouse_ready"))
        / "quality_reports"
    )
    report_path = report_dir / f"redshift_load_report_{batch_id}.json"

    report: dict[str, Any] = {
        "load_batch_id": batch_id,
        "created_at": now_utc_iso(),
        "dry_run": args.dry_run,
        "truncate_before_load": args.truncate_before_load,
        "entries": [],
        "errors": [],
    }

    if missing_s3 and not args.dry_run:
        report["errors"].append(f"Missing S3 config: {', '.join(missing_s3)}")
        write_load_report(report, report_path)
        logger.error(report["errors"][0])
        return 1

    connection = None
    if not args.dry_run:
        missing_rs, _ = validate_redshift_config()
        if missing_rs:
            report["errors"].append(f"Missing Redshift config: {', '.join(missing_rs)}")
            write_load_report(report, report_path)
            logger.error(report["errors"][0])
            return 1
        connection = get_redshift_connection_from_env()

    try:
        for plan in plans:
            if plan.get("status") != "ready":
                report["errors"].append(f"{plan['dataset_name']}: {plan['status']}")
                report["entries"].append(plan)
                continue

            copy_sql = build_copy_sql(
                plan["schema"],
                plan["table"],
                plan["s3_uri"],
                redshift_config.get("iam_role_arn") or os.getenv("REDSHIFT_IAM_ROLE_ARN", ""),
                truncate=args.truncate_before_load,
            )
            entry = {**plan, "copy_sql": copy_sql}
            if args.dry_run:
                logger.info("[dry-run] COPY %s.%s <= %s", plan["schema"], plan["table"], plan["s3_uri"])
                report["entries"].append(entry)
                continue

            assert connection is not None
            copy_csv_from_s3(
                connection,
                plan["schema"],
                plan["table"],
                plan["s3_uri"],
                redshift_config["iam_role_arn"],
                truncate=args.truncate_before_load,
                dry_run=False,
            )
            row_count = check_table_row_count(connection, plan["schema"], plan["table"])
            entry["row_count_after_load"] = row_count
            report["entries"].append(entry)
            logger.info("Loaded %s.%s (%s rows)", plan["schema"], plan["table"], row_count)
    except Exception as exc:  # noqa: BLE001
        report["errors"].append(str(exc))
        logger.error("Redshift load failed: %s", exc)
    finally:
        if connection is not None:
            connection.close()

    write_load_report(report, report_path)
    logger.info("Wrote Redshift load report to %s", report_path)
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
