# Tests for Redshift COPY generation and load planning.

from __future__ import annotations

from pathlib import Path

import pytest

from ingestion.load_s3_to_redshift_raw import build_load_plans, main
from ingestion.redshift_utils import (
    TABLE_ONLY_OPTIONAL_COLUMNS,
    build_copy_sql,
    get_target_table_columns,
    read_csv_header,
    validate_and_resolve_copy_columns,
)
from ingestion.warehouse_utils import load_schema_registry

GTFS_STOPS_HEADER = (
    "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station,"
    "wheelchair_boarding,warehouse_dataset,source_file,prepared_at,load_batch_id"
)


def test_build_load_plans_includes_copy_columns(tmp_path: Path) -> None:
    registry = load_schema_registry(Path("config/warehouse_schemas.yml"))
    static_dir = tmp_path / "gtfs_static"
    static_dir.mkdir(parents=True)
    (static_dir / "gtfs_stops.csv").write_text(f"{GTFS_STOPS_HEADER}\n1\n", encoding="utf-8")
    plans = build_load_plans(registry, "gtfs_stops", tmp_path, "bucket", "prefix", "raw_data")
    assert len(plans) == 1
    assert plans[0]["status"] == "ready"
    assert plans[0]["copy_columns"][0] == "stop_id"
    assert plans[0]["copy_columns"][-1] == "load_batch_id"
    assert "zone_id" not in plans[0]["copy_columns"]
    assert "loaded_at" not in plans[0]["copy_columns"]


def test_build_copy_sql_without_truncate_by_default() -> None:
    sql = build_copy_sql(
        "raw_data",
        "raw_gtfs_stops",
        "s3://bucket/key.csv",
        "arn:aws:iam::123:role/RedshiftLoadRole",
        ["stop_id"],
        truncate=False,
    )
    assert "truncate table" not in sql.lower()


def test_build_copy_sql_includes_truncate_when_flag_set() -> None:
    sql = build_copy_sql(
        "raw_data",
        "raw_gtfs_stops",
        "s3://bucket/key.csv",
        "arn:aws:iam::123:role/RedshiftLoadRole",
        ["stop_id"],
        truncate=True,
    )
    assert "truncate table raw_data.raw_gtfs_stops" in sql.lower()


def test_copy_sql_includes_explicit_column_list() -> None:
    columns = [
        "stop_id",
        "stop_name",
        "stop_lat",
        "stop_lon",
        "location_type",
        "parent_station",
        "wheelchair_boarding",
        "warehouse_dataset",
        "source_file",
        "prepared_at",
        "load_batch_id",
    ]
    sql = build_copy_sql(
        "raw_data",
        "raw_gtfs_stops",
        "s3://bucket/transit-equity/warehouse_ready/gtfs_static/gtfs_stops.csv",
        "arn:aws:iam::123:role/RedshiftLoadRole",
        columns,
    )
    assert "copy raw_data.raw_gtfs_stops (" in sql.lower()
    assert "stop_id,\n    stop_name" in sql
    assert "load_batch_id" in sql
    assert "from 's3://bucket" in sql.lower()
    for token in ["csv", "ignoreheader 1", "blanksasnull", "emptyasnull"]:
        assert token in sql.lower()


def test_optional_table_columns_do_not_appear_in_copy_list(tmp_path: Path) -> None:
    registry = load_schema_registry(Path("config/warehouse_schemas.yml"))
    schema = registry["datasets"]["gtfs_stops"]
    table_columns = get_target_table_columns(schema, registry)
    assert TABLE_ONLY_OPTIONAL_COLUMNS.issubset(table_columns)
    csv_path = tmp_path / "gtfs_stops.csv"
    csv_path.write_text(f"{GTFS_STOPS_HEADER}\n", encoding="utf-8")
    copy_columns = validate_and_resolve_copy_columns(
        read_csv_header(csv_path),
        table_columns,
        dataset_name="gtfs_stops",
    )
    assert "zone_id" not in copy_columns
    assert "loaded_at" not in copy_columns


def test_csv_header_order_preserved_in_copy_sql(tmp_path: Path) -> None:
    csv_path = tmp_path / "gtfs_stops.csv"
    csv_path.write_text(
        "load_batch_id,prepared_at,source_file,warehouse_dataset,wheelchair_boarding,"
        "parent_station,location_type,stop_lon,stop_lat,stop_name,stop_id\n",
        encoding="utf-8",
    )
    registry = load_schema_registry(Path("config/warehouse_schemas.yml"))
    schema = registry["datasets"]["gtfs_stops"]
    copy_columns = validate_and_resolve_copy_columns(
        read_csv_header(csv_path),
        get_target_table_columns(schema, registry),
        dataset_name="gtfs_stops",
    )
    sql = build_copy_sql("raw_data", "raw_gtfs_stops", "s3://bucket/key.csv", "arn:aws:iam::123:role/r", copy_columns)
    copy_block = sql.lower().split("from ")[0]
    first_index = copy_block.find("load_batch_id")
    last_index = copy_block.find("stop_id")
    assert first_index != -1 and last_index != -1
    assert first_index < last_index


def test_unknown_csv_column_fails_clearly(tmp_path: Path) -> None:
    registry = load_schema_registry(Path("config/warehouse_schemas.yml"))
    schema = registry["datasets"]["gtfs_stops"]
    with pytest.raises(ValueError, match="not found in target table schema"):
        validate_and_resolve_copy_columns(
            ["stop_id", "not_a_real_column"],
            get_target_table_columns(schema, registry),
            dataset_name="gtfs_stops",
        )


def test_load_cli_dry_run_with_truncate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    static_dir = tmp_path / "gtfs_static"
    static_dir.mkdir(parents=True)
    (static_dir / "gtfs_stops.csv").write_text(f"{GTFS_STOPS_HEADER}\n1\n", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "load_s3_to_redshift_raw.py",
            "--dry-run",
            "--dataset",
            "gtfs_stops",
            "--input-dir",
            str(tmp_path),
            "--truncate-before-load",
        ],
    )
    monkeypatch.setenv("S3_BUCKET_NAME", "example-bucket")
    monkeypatch.setenv("REDSHIFT_IAM_ROLE_ARN", "arn:aws:iam::123456789012:role/RedshiftLoadRole")
    assert main() == 0


def test_load_cli_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    static_dir = tmp_path / "gtfs_static"
    static_dir.mkdir(parents=True)
    (static_dir / "gtfs_stops.csv").write_text(f"{GTFS_STOPS_HEADER}\n1\n", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        ["load_s3_to_redshift_raw.py", "--dry-run", "--dataset", "gtfs_stops", "--input-dir", str(tmp_path)],
    )
    monkeypatch.setenv("S3_BUCKET_NAME", "example-bucket")
    monkeypatch.setenv("REDSHIFT_IAM_ROLE_ARN", "arn:aws:iam::123456789012:role/RedshiftLoadRole")
    assert main() == 0
