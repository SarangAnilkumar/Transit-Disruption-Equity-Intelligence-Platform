# Tests for S3 upload planning CLI helpers.

from __future__ import annotations

from pathlib import Path

import pytest

from ingestion.aws_utils import plan_warehouse_ready_uploads
from ingestion.upload_warehouse_ready_to_s3 import main


def test_upload_plan_filters_dataset(tmp_path: Path) -> None:
    for domain in ["gtfs_static", "geospatial"]:
        (tmp_path / domain).mkdir(parents=True)
        (tmp_path / domain / f"{'gtfs_stops' if domain == 'gtfs_static' else 'stops_sa2_mapping'}.csv").write_text(
            "x\n1\n", encoding="utf-8"
        )
    plans = plan_warehouse_ready_uploads(tmp_path, "bucket", "prefix", dataset_names=["gtfs_stops"])
    assert len(plans) == 1
    assert plans[0]["dataset_name"] == "gtfs_stops"


def test_upload_cli_dry_run_missing_bucket(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["upload_warehouse_ready_to_s3.py", "--dry-run"])
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    assert main() == 1


def test_upload_cli_dry_run_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    static_dir = tmp_path / "gtfs_static"
    static_dir.mkdir(parents=True)
    (static_dir / "gtfs_stops.csv").write_text("stop_id\n1\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["upload_warehouse_ready_to_s3.py", "--dry-run", "--dataset", "gtfs_stops"])
    monkeypatch.setenv("S3_BUCKET_NAME", "example-bucket")
    monkeypatch.setattr(
        "ingestion.upload_warehouse_ready_to_s3.load_settings",
        lambda: {"warehouse": {"output_dir": str(tmp_path)}},
    )
    assert main() == 0
    manifests = list((tmp_path / "manifests").glob("s3_upload_manifest_*.json"))
    assert manifests
