# Tests for Redshift COPY generation and load planning.

from __future__ import annotations

from pathlib import Path

import pytest

from ingestion.load_s3_to_redshift_raw import build_load_plans, main
from ingestion.redshift_utils import build_copy_sql
from ingestion.warehouse_utils import load_schema_registry


def test_build_load_plans(tmp_path: Path) -> None:
    registry = load_schema_registry(Path("config/warehouse_schemas.yml"))
    static_dir = tmp_path / "gtfs_static"
    static_dir.mkdir(parents=True)
    (static_dir / "gtfs_stops.csv").write_text("stop_id\n1\n", encoding="utf-8")
    plans = build_load_plans(registry, "gtfs_stops", tmp_path, "bucket", "prefix", "raw")
    assert len(plans) == 1
    assert plans[0]["status"] == "ready"
    assert plans[0]["table"] == "raw_gtfs_stops"


def test_copy_sql_contains_required_options() -> None:
    sql = build_copy_sql("raw", "raw_gtfs_trips", "s3://bucket/key.csv", "arn:aws:iam::123:role/r")
    for token in ["csv", "ignoreheader 1", "blanksasnull", "emptyasnull"]:
        assert token in sql.lower()


def test_load_cli_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    static_dir = tmp_path / "gtfs_static"
    static_dir.mkdir(parents=True)
    (static_dir / "gtfs_stops.csv").write_text("stop_id\n1\n", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        ["load_s3_to_redshift_raw.py", "--dry-run", "--dataset", "gtfs_stops", "--input-dir", str(tmp_path)],
    )
    monkeypatch.setenv("S3_BUCKET_NAME", "example-bucket")
    monkeypatch.setenv("REDSHIFT_IAM_ROLE_ARN", "arn:aws:iam::123456789012:role/RedshiftLoadRole")
    assert main() == 0
