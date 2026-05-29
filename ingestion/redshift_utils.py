"""Redshift connection and COPY helpers."""

from __future__ import annotations

import csv
import os
import re
from pathlib import Path
from typing import Any

from ingestion.utils import save_json_to_file

# Redshift table columns that may be absent from warehouse-ready CSVs.
TABLE_ONLY_OPTIONAL_COLUMNS = frozenset({"loaded_at", "zone_id"})

REQUIRED_REDSHIFT_ENV_KEYS = [
    "REDSHIFT_HOST",
    "REDSHIFT_DATABASE",
    "REDSHIFT_USER",
    "REDSHIFT_PASSWORD",
    "REDSHIFT_IAM_ROLE_ARN",
]


def validate_redshift_config(env: dict[str, str] | None = None) -> tuple[list[str], dict[str, str]]:
    """Return missing required env keys and resolved config."""
    if env is None:
        env = os.environ
    config = {
        "host": env.get("REDSHIFT_HOST", "").strip(),
        "port": env.get("REDSHIFT_PORT", "5439").strip(),
        "database": env.get("REDSHIFT_DATABASE", "").strip(),
        "user": env.get("REDSHIFT_USER", "").strip(),
        "password": env.get("REDSHIFT_PASSWORD", "").strip(),
        "schema_raw": env.get("REDSHIFT_SCHEMA_RAW", "raw_data").strip(),
        "schema_staging": env.get("REDSHIFT_SCHEMA_STAGING", "staging").strip(),
        "iam_role_arn": env.get("REDSHIFT_IAM_ROLE_ARN", "").strip(),
    }
    missing = [key for key in REQUIRED_REDSHIFT_ENV_KEYS if not env.get(key, "").strip()]
    return missing, config


def get_redshift_connection_from_env():
    """Open a Redshift connection using environment variables."""
    missing, config = validate_redshift_config()
    if missing:
        raise EnvironmentError(
            "Missing Redshift configuration. Set: "
            + ", ".join(missing)
            + ". See .env.example and docs/redshift_dbt_foundation.md."
        )
    import psycopg2

    sslmode = os.environ.get("REDSHIFT_SSLMODE", "require").strip() or "require"

    return psycopg2.connect(
        host=config["host"],
        port=config["port"],
        dbname=config["database"],
        user=config["user"],
        password=config["password"],
        sslmode=sslmode,
    )


def split_sql_statements(sql_text: str) -> list[str]:
    """Split SQL file into executable statements."""
    statements: list[str] = []
    buffer: list[str] = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buffer.append(line)
        if stripped.endswith(";"):
            statement = "\n".join(buffer).strip()
            if statement:
                statements.append(statement[:-1].strip() if statement.endswith(";") else statement)
            buffer = []
    trailing = "\n".join(buffer).strip()
    if trailing:
        statements.append(trailing.rstrip(";"))
    return statements


def execute_sql(connection, sql: str) -> None:
    """Execute one SQL statement inside a transaction."""
    with connection.cursor() as cursor:
        cursor.execute(sql)
    connection.commit()


def execute_sql_file(connection, path: str | Path) -> int:
    """Execute all statements in a SQL file. Returns statement count."""
    sql_text = Path(path).read_text(encoding="utf-8")
    statements = split_sql_statements(sql_text)
    for statement in statements:
        execute_sql(connection, statement)
    return len(statements)


def get_target_table_columns(dataset_schema: dict[str, Any], registry: dict[str, Any]) -> set[str]:
    """Return valid Redshift target column names for a dataset."""
    columns = set(dataset_schema.get("column_types", {}))
    columns.update(registry.get("metadata_columns", []))
    columns.update(TABLE_ONLY_OPTIONAL_COLUMNS)
    return columns


def read_csv_header(csv_path: str | Path) -> list[str]:
    """Read the header row from a warehouse-ready CSV file."""
    path = Path(csv_path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
    if not header:
        raise ValueError(f"CSV file has no header row: {path}")
    return [column.strip() for column in header if column.strip()]


def validate_and_resolve_copy_columns(
    csv_columns: list[str],
    table_columns: set[str],
    *,
    dataset_name: str,
) -> list[str]:
    """Validate CSV columns against the target table and preserve CSV column order."""
    if not csv_columns:
        raise ValueError(f"{dataset_name}: CSV header is empty.")
    unknown = [column for column in csv_columns if column not in table_columns]
    if unknown:
        raise ValueError(
            f"{dataset_name}: CSV columns not found in target table schema: {unknown}. "
            f"Allowed columns: {sorted(table_columns)}"
        )
    return list(csv_columns)


def format_copy_column_list(copy_columns: list[str]) -> str:
    """Format COPY column names for SQL."""
    return ",\n    ".join(copy_columns)


def build_copy_sql(
    schema: str,
    table: str,
    s3_uri: str,
    iam_role_arn: str,
    copy_columns: list[str],
    *,
    truncate: bool = False,
) -> str:
    """Build a Redshift COPY statement with an explicit column list."""
    if not copy_columns:
        raise ValueError(f"COPY column list is empty for {schema}.{table}")
    statements: list[str] = []
    qualified = f"{schema}.{table}"
    if truncate:
        statements.append(f"truncate table {qualified};")
    column_sql = format_copy_column_list(copy_columns)
    copy_sql = f"""
copy {qualified} (
    {column_sql}
)
from '{s3_uri}'
iam_role '{iam_role_arn}'
csv
ignoreheader 1
timeformat 'auto'
dateformat 'auto'
acceptinvchars
blanksasnull
emptyasnull
compupdate off
statupdate off
""".strip()
    statements.append(copy_sql)
    return "\n".join(statements)


def copy_csv_from_s3(
    connection,
    schema: str,
    table: str,
    s3_uri: str,
    iam_role_arn: str,
    copy_columns: list[str],
    *,
    truncate: bool = False,
    dry_run: bool = False,
) -> str:
    """Run COPY from S3 into a Redshift table."""
    sql = build_copy_sql(
        schema, table, s3_uri, iam_role_arn, copy_columns, truncate=truncate
    )
    if dry_run:
        return sql
    for statement in split_sql_statements(sql):
        execute_sql(connection, statement)
    return sql


def check_table_row_count(connection, schema: str, table: str) -> int:
    """Return row count for a schema-qualified table."""
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", schema) or not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table):
        raise ValueError(f"Invalid schema/table identifier: {schema}.{table}")
    with connection.cursor() as cursor:
        cursor.execute(f"select count(*) from {schema}.{table}")
        result = cursor.fetchone()
    return int(result[0]) if result else 0


def write_load_report(payload: dict[str, Any], output_path: str | Path) -> Path:
    """Write Redshift load report JSON."""
    return save_json_to_file(payload, output_path)


def fetch_recent_load_errors(
    connection,
    table_name: str,
    *,
    schema_name: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Fetch recent COPY load errors from sys_load_error_detail."""
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name):
        raise ValueError(f"Invalid table name: {table_name}")
    if schema_name is not None and not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", schema_name):
        raise ValueError(f"Invalid schema name: {schema_name}")

    query = """
        select
            "table" as table_name,
            line_number,
            column_name,
            column_type,
            column_length,
            error_code,
            error_message
        from sys_load_error_detail
        where "table" = %s
        order by line_number desc nulls last
        limit %s
    """
    params: list[Any] = [table_name, limit]
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
    return [dict(zip(columns, row, strict=False)) for row in rows]
