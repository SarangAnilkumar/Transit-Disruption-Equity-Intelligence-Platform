# Tests for Redshift utilities.

from __future__ import annotations

from ingestion.redshift_utils import (
    build_copy_sql,
    split_sql_statements,
    validate_redshift_config,
)


def test_split_sql_statements() -> None:
    sql = """
-- comment
create schema if not exists raw;
create table if not exists raw.raw_gtfs_stops (
    stop_id varchar(64)
);
"""
    statements = split_sql_statements(sql)
    assert len(statements) == 2
    assert statements[0].lower().startswith("create schema")


def test_build_copy_sql() -> None:
    sql = build_copy_sql(
        "raw",
        "raw_gtfs_stops",
        "s3://example-bucket/transit-equity/warehouse_ready/gtfs_static/gtfs_stops.csv",
        "arn:aws:iam::123456789012:role/RedshiftLoadRole",
    )
    assert "copy raw.raw_gtfs_stops" in sql.lower()
    assert "ignoreheader 1" in sql.lower()
    assert "truncate table" not in sql.lower()


def test_build_copy_sql_with_truncate() -> None:
    sql = build_copy_sql(
        "raw",
        "raw_gtfs_stops",
        "s3://example-bucket/file.csv",
        "arn:aws:iam::123456789012:role/RedshiftLoadRole",
        truncate=True,
    )
    assert "truncate table raw.raw_gtfs_stops" in sql.lower()


def test_validate_redshift_config_missing() -> None:
    missing, _ = validate_redshift_config({})
    assert "REDSHIFT_HOST" in missing
    assert "REDSHIFT_IAM_ROLE_ARN" in missing
