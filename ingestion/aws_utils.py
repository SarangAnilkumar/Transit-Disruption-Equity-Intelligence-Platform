"""AWS/S3 helpers for warehouse-ready uploads."""

from __future__ import annotations

import fnmatch
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ingestion.utils import ensure_dir, save_json_to_file

REQUIRED_S3_ENV_KEYS = ["S3_BUCKET_NAME"]
OPTIONAL_S3_ENV_KEYS = ["AWS_PROFILE", "AWS_REGION", "S3_WAREHOUSE_READY_PREFIX"]


def validate_s3_config(env: dict[str, str] | None = None) -> tuple[list[str], dict[str, str]]:
    """Return missing required env keys and resolved config dict."""
    env = env or os.environ
    config = {
        "aws_profile": env.get("AWS_PROFILE", "").strip(),
        "aws_region": env.get("AWS_REGION", "ap-southeast-2").strip(),
        "bucket": env.get("S3_BUCKET_NAME", "").strip(),
        "warehouse_ready_prefix": ensure_s3_prefix_style(
            env.get("S3_WAREHOUSE_READY_PREFIX", "transit-equity/warehouse_ready")
        ),
    }
    missing = [key for key in REQUIRED_S3_ENV_KEYS if not env.get(key, "").strip()]
    return missing, config


def get_boto3_session(profile_name: str | None = None, region_name: str | None = None):
    """Create a boto3 session using optional profile and region."""
    import boto3

    session_kwargs: dict[str, str] = {}
    profile = profile_name or os.getenv("AWS_PROFILE", "").strip()
    region = region_name or os.getenv("AWS_REGION", "ap-southeast-2").strip()
    if profile:
        session_kwargs["profile_name"] = profile
    if region:
        session_kwargs["region_name"] = region
    return boto3.Session(**session_kwargs)


def ensure_s3_prefix_style(path_or_prefix: str) -> str:
    """Normalize S3 prefix without leading slash and with no trailing slash."""
    normalized = path_or_prefix.strip().replace("\\", "/").lstrip("/")
    return normalized.rstrip("/")


def build_s3_key(prefix: str, dataset_name: str, file_name: str, domain: str | None = None) -> str:
    """Build an S3 object key for a warehouse-ready artifact."""
    clean_prefix = ensure_s3_prefix_style(prefix)
    if domain:
        return f"{clean_prefix}/{domain}/{file_name}"
    return f"{clean_prefix}/{dataset_name}/{file_name}"


def upload_file_to_s3(
    local_path: str | Path,
    bucket: str,
    key: str,
    session=None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Upload one local file to S3 or return a dry-run plan entry."""
    path = Path(local_path)
    if not path.exists():
        raise FileNotFoundError(f"Local file not found: {path}")
    entry = {
        "local_path": path.as_posix(),
        "bucket": bucket,
        "key": ensure_s3_prefix_style(key) if "/" in key else key,
        "size_bytes": path.stat().st_size,
        "dry_run": dry_run,
    }
    if dry_run:
        return entry
    active_session = session or get_boto3_session()
    client = active_session.client("s3")
    client.upload_file(str(path), bucket, key)
    entry["uploaded"] = True
    return entry


def _match_patterns(name: str, include_patterns: list[str] | None, exclude_patterns: list[str] | None) -> bool:
    if exclude_patterns and any(fnmatch.fnmatch(name, pattern) for pattern in exclude_patterns):
        return False
    if not include_patterns:
        return True
    return any(fnmatch.fnmatch(name, pattern) for pattern in include_patterns)


def upload_directory_to_s3(
    local_dir: str | Path,
    bucket: str,
    prefix: str,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    session=None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Upload files under a directory tree to S3 preserving relative paths."""
    root = Path(local_dir)
    if not root.exists():
        raise FileNotFoundError(f"Local directory not found: {root}")
    clean_prefix = ensure_s3_prefix_style(prefix)
    uploads: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if not _match_patterns(path.name, include_patterns, exclude_patterns):
            continue
        relative = path.relative_to(root).as_posix()
        key = f"{clean_prefix}/{relative}"
        uploads.append(upload_file_to_s3(path, bucket, key, session=session, dry_run=dry_run))
    return uploads


def write_s3_upload_manifest(payload: dict[str, Any], output_path: str | Path) -> Path:
    """Write S3 upload manifest JSON."""
    return save_json_to_file(payload, output_path)


def plan_warehouse_ready_uploads(
    input_dir: Path,
    bucket: str,
    prefix: str,
    dataset_names: list[str] | None = None,
    include_manifests: bool = True,
    include_quality_reports: bool = True,
) -> list[dict[str, Any]]:
    """Build upload plan entries for warehouse-ready CSV and sidecar files."""
    plans: list[dict[str, Any]] = []
    domain_dirs = ["gtfs_static", "gtfs_realtime", "geospatial", "equity", "analytics"]
    for domain in domain_dirs:
        domain_path = input_dir / domain
        if not domain_path.exists():
            continue
        for csv_path in sorted(domain_path.glob("*.csv")):
            dataset_name = csv_path.stem
            if dataset_names and dataset_name not in dataset_names:
                continue
            key = build_s3_key(prefix, dataset_name, csv_path.name, domain=domain)
            plans.append(
                {
                    "dataset_name": dataset_name,
                    "domain": domain,
                    "local_path": csv_path.as_posix(),
                    "bucket": bucket,
                    "key": key,
                    "s3_uri": f"s3://{bucket}/{key}",
                    "size_bytes": csv_path.stat().st_size,
                }
            )

    if include_manifests:
        manifest_dir = input_dir / "manifests"
        if manifest_dir.exists():
            for path in sorted(manifest_dir.glob("*.json")):
                key = build_s3_key(prefix, "manifests", path.name, domain="manifests")
                plans.append(
                    {
                        "artifact_type": "manifest",
                        "local_path": path.as_posix(),
                        "bucket": bucket,
                        "key": key,
                        "s3_uri": f"s3://{bucket}/{key}",
                        "size_bytes": path.stat().st_size,
                    }
                )

    if include_quality_reports:
        report_dir = input_dir / "quality_reports"
        if report_dir.exists():
            for path in sorted(report_dir.glob("*.json")):
                key = build_s3_key(prefix, "quality_reports", path.name, domain="quality_reports")
                plans.append(
                    {
                        "artifact_type": "quality_report",
                        "local_path": path.as_posix(),
                        "bucket": bucket,
                        "key": key,
                        "s3_uri": f"s3://{bucket}/{key}",
                        "size_bytes": path.stat().st_size,
                    }
                )
    return plans


def new_upload_batch_id() -> str:
    """Return upload batch identifier."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
