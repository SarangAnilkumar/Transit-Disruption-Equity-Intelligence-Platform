"""Upload warehouse-ready local datasets to S3."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.aws_utils import (  # noqa: E402
    get_boto3_session,
    new_upload_batch_id,
    plan_warehouse_ready_uploads,
    upload_file_to_s3,
    validate_s3_config,
    write_s3_upload_manifest,
)
from ingestion.utils import ensure_dir, load_env, load_settings, setup_logging  # noqa: E402
from ingestion.warehouse_utils import load_schema_registry, resolve_dataset_names  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload warehouse-ready datasets to S3.")
    parser.add_argument("--dataset", default="all")
    parser.add_argument("--input-dir", default=None)
    parser.add_argument("--bucket", default=None)
    parser.add_argument("--prefix", default=None)
    parser.add_argument("--aws-profile", default=None)
    parser.add_argument("--region", default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = setup_logging()
    load_env()
    settings = load_settings()
    warehouse_settings = settings.get("warehouse", {})
    aws_settings = settings.get("aws", {})

    missing, config = validate_s3_config()
    bucket = args.bucket or os.getenv("S3_BUCKET_NAME", "").strip()
    prefix = args.prefix or os.getenv("S3_WAREHOUSE_READY_PREFIX") or aws_settings.get(
        "warehouse_ready_prefix", "transit-equity/warehouse_ready"
    )
    if not bucket:
        missing.append("S3_BUCKET_NAME")
    if missing:
        logger.error(
            "Missing AWS/S3 configuration: %s. Set variables in .env (see .env.example) "
            "or pass --bucket explicitly.",
            ", ".join(sorted(set(missing))),
        )
        return 1

    input_dir = Path(
        args.input_dir
        or warehouse_settings.get("output_dir", "data/processed/warehouse_ready")
    )
    if not input_dir.exists():
        logger.error("Warehouse-ready input directory not found: %s", input_dir)
        return 1

    registry = load_schema_registry(Path(warehouse_settings.get("schema_path", "config/warehouse_schemas.yml")))
    dataset_names = None if args.dataset == "all" else resolve_dataset_names(registry, args.dataset)

    plans = plan_warehouse_ready_uploads(input_dir, bucket, prefix, dataset_names=dataset_names)
    if not plans:
        logger.error("No warehouse-ready files found to upload under %s", input_dir)
        return 1

    batch_id = new_upload_batch_id()
    session = None if args.dry_run else get_boto3_session(args.aws_profile, args.region)
    uploaded: list[dict[str, Any]] = []
    for plan in plans:
        if args.dry_run:
            plan["dry_run"] = True
            uploaded.append(plan)
            logger.info("[dry-run] would upload %s -> s3://%s/%s", plan["local_path"], bucket, plan["key"])
            continue
        uploaded.append(
            upload_file_to_s3(plan["local_path"], bucket, plan["key"], session=session, dry_run=False)
        )
        logger.info("Uploaded %s -> s3://%s/%s", plan["local_path"], bucket, plan["key"])

    manifest = {
        "upload_batch_id": batch_id,
        "dry_run": args.dry_run,
        "bucket": bucket,
        "prefix": prefix,
        "file_count": len(uploaded),
        "uploads": uploaded,
    }
    manifest_dir = ensure_dir(input_dir / "manifests")
    manifest_path = manifest_dir / f"s3_upload_manifest_{batch_id}.json"
    write_s3_upload_manifest(manifest, manifest_path)
    logger.info("Wrote S3 upload manifest to %s", manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
