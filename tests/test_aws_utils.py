# Tests for AWS/S3 utilities.

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ingestion.aws_utils import (
    build_s3_key,
    ensure_s3_prefix_style,
    plan_warehouse_ready_uploads,
    upload_file_to_s3,
    validate_s3_config,
    write_s3_upload_manifest,
)


def test_ensure_s3_prefix_style() -> None:
    assert ensure_s3_prefix_style("/transit-equity/warehouse_ready/") == "transit-equity/warehouse_ready"


def test_build_s3_key_with_domain() -> None:
    key = build_s3_key("transit-equity/warehouse_ready", "gtfs_stops", "gtfs_stops.csv", domain="gtfs_static")
    assert key == "transit-equity/warehouse_ready/gtfs_static/gtfs_stops.csv"


def test_validate_s3_config_missing_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    missing, config = validate_s3_config({})
    assert "S3_BUCKET_NAME" in missing


def test_plan_warehouse_ready_uploads(tmp_path: Path) -> None:
    static_dir = tmp_path / "gtfs_static"
    static_dir.mkdir(parents=True)
    csv_path = static_dir / "gtfs_stops.csv"
    csv_path.write_text("stop_id\n1\n", encoding="utf-8")
    plans = plan_warehouse_ready_uploads(tmp_path, "my-bucket", "transit-equity/warehouse_ready")
    assert len(plans) == 1
    assert plans[0]["s3_uri"].startswith("s3://my-bucket/")


def test_upload_file_to_s3_dry_run(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.csv"
    file_path.write_text("a\n1\n", encoding="utf-8")
    result = upload_file_to_s3(file_path, "bucket", "prefix/sample.csv", dry_run=True)
    assert result["dry_run"] is True


@patch("ingestion.aws_utils.get_boto3_session")
def test_upload_file_to_s3_live(mock_session: MagicMock, tmp_path: Path) -> None:
    file_path = tmp_path / "sample.csv"
    file_path.write_text("a\n1\n", encoding="utf-8")
    client = MagicMock()
    mock_session.return_value.client.return_value = client
    result = upload_file_to_s3(file_path, "bucket", "prefix/sample.csv", session=mock_session.return_value)
    assert result["uploaded"] is True
    client.upload_file.assert_called_once()


def test_write_s3_upload_manifest(tmp_path: Path) -> None:
    path = write_s3_upload_manifest({"file_count": 1}, tmp_path / "manifest.json")
    assert path.exists()
