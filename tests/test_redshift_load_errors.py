"""Tests for Redshift load error diagnostics."""

from __future__ import annotations

from unittest.mock import MagicMock

from ingestion.redshift_utils import fetch_recent_load_errors


def test_fetch_recent_load_errors_returns_rows() -> None:
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.description = [
        ("table_name",),
        ("line_number",),
        ("column_name",),
        ("column_type",),
        ("column_length",),
        ("error_code",),
        ("error_message",),
    ]
    cursor.fetchall.return_value = [
        ("raw_seifa_sa2", 2355, "sa2_code", "varchar", 32, 1204, "String length exceeds DDL length"),
    ]

    rows = fetch_recent_load_errors(connection, "raw_seifa_sa2", limit=5)
    assert len(rows) == 1
    assert rows[0]["column_name"] == "sa2_code"
    assert rows[0]["error_code"] == 1204
