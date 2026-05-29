# Tests for Redshift utilities.

from __future__ import annotations

from unittest.mock import patch

import pytest

from ingestion.redshift_utils import (
    build_copy_sql,
    get_redshift_connection_from_env,
    split_sql_statements,
    validate_redshift_config,
)


def _set_required_redshift_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDSHIFT_HOST", "example.redshift.amazonaws.com")
    monkeypatch.setenv("REDSHIFT_DATABASE", "dev")
    monkeypatch.setenv("REDSHIFT_USER", "admin")
    monkeypatch.setenv("REDSHIFT_PASSWORD", "secret")
    monkeypatch.setenv("REDSHIFT_IAM_ROLE_ARN", "arn:aws:iam::123456789012:role/RedshiftLoadRole")


def test_split_sql_statements() -> None:
    sql = """
-- comment
create schema if not exists raw_data;
create table if not exists raw_data.raw_gtfs_stops (
    stop_id varchar(64)
);
"""
    statements = split_sql_statements(sql)
    assert len(statements) == 2
    assert statements[0].lower().startswith("create schema")


def test_build_copy_sql() -> None:
    columns = ["stop_id", "stop_name", "load_batch_id"]
    sql = build_copy_sql(
        "raw_data",
        "raw_gtfs_stops",
        "s3://example-bucket/transit-equity/warehouse_ready/gtfs_static/gtfs_stops.csv",
        "arn:aws:iam::123456789012:role/RedshiftLoadRole",
        columns,
    )
    assert "copy raw_data.raw_gtfs_stops (" in sql.lower()
    assert "stop_id,\n    stop_name,\n    load_batch_id" in sql
    assert "ignoreheader 1" in sql.lower()
    assert "truncate table" not in sql.lower()


def test_build_copy_sql_with_truncate() -> None:
    sql = build_copy_sql(
        "raw_data",
        "raw_gtfs_stops",
        "s3://example-bucket/file.csv",
        "arn:aws:iam::123456789012:role/RedshiftLoadRole",
        ["stop_id"],
        truncate=True,
    )
    assert "truncate table raw_data.raw_gtfs_stops" in sql.lower()


def test_validate_redshift_config_missing() -> None:
    missing, _ = validate_redshift_config({})
    assert "REDSHIFT_HOST" in missing
    assert "REDSHIFT_IAM_ROLE_ARN" in missing


@patch("psycopg2.connect")
def test_get_redshift_connection_sslmode_defaults_to_require(
    mock_connect, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_required_redshift_env(monkeypatch)
    monkeypatch.delenv("REDSHIFT_SSLMODE", raising=False)
    get_redshift_connection_from_env()
    assert mock_connect.call_args.kwargs["sslmode"] == "require"


@patch("psycopg2.connect")
def test_get_redshift_connection_sslmode_from_env(
    mock_connect, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_required_redshift_env(monkeypatch)
    monkeypatch.setenv("REDSHIFT_SSLMODE", "verify-full")
    get_redshift_connection_from_env()
    assert mock_connect.call_args.kwargs["sslmode"] == "verify-full"
