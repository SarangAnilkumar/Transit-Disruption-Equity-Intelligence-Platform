"""Initialise Redshift raw/staging/audit schemas and tables."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.redshift_utils import (  # noqa: E402
    execute_sql_file,
    get_redshift_connection_from_env,
    split_sql_statements,
    validate_redshift_config,
    write_load_report,
)
from ingestion.utils import ensure_dir, load_env, load_settings, setup_logging  # noqa: E402
from ingestion.warehouse_utils import new_load_batch_id, now_utc_iso  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialise Redshift schemas and raw tables.")
    parser.add_argument("--sql-file", default="sql/create_raw_tables.sql")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-dir", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = setup_logging()
    load_env()
    settings = load_settings()
    warehouse_settings = settings.get("warehouse", {})

    sql_path = Path(args.sql_file)
    if not sql_path.exists():
        logger.error("SQL file not found: %s", sql_path)
        return 1

    sql_text = sql_path.read_text(encoding="utf-8")
    statements = split_sql_statements(sql_text)
    batch_id = new_load_batch_id()
    report_dir = ensure_dir(
        Path(args.report_dir or warehouse_settings.get("output_dir", "data/processed/warehouse_ready"))
        / "quality_reports"
    )
    report_path = report_dir / f"redshift_schema_init_report_{batch_id}.json"

    if args.dry_run:
        logger.info("[dry-run] SQL file: %s", sql_path.as_posix())
        logger.info("[dry-run] statement count: %s", len(statements))
        write_load_report(
            {
                "status": "dry_run",
                "sql_file": sql_path.as_posix(),
                "statement_count": len(statements),
                "created_at": now_utc_iso(),
            },
            report_path,
        )
        logger.info("Wrote schema init dry-run report to %s", report_path)
        return 0

    missing, _ = validate_redshift_config()
    if missing:
        logger.error(
            "Missing Redshift configuration: %s. Set .env values before running without --dry-run.",
            ", ".join(missing),
        )
        return 1

    connection = get_redshift_connection_from_env()
    try:
        executed = execute_sql_file(connection, sql_path)
        write_load_report(
            {
                "status": "success",
                "sql_file": sql_path.as_posix(),
                "statement_count": executed,
                "created_at": now_utc_iso(),
            },
            report_path,
        )
        logger.info("Executed %s SQL statements from %s", executed, sql_path)
        logger.info("Wrote schema init report to %s", report_path)
        return 0
    except Exception as exc:  # noqa: BLE001
        write_load_report(
            {
                "status": "failed",
                "sql_file": sql_path.as_posix(),
                "error_message": str(exc),
                "created_at": now_utc_iso(),
            },
            report_path,
        )
        logger.error("Redshift schema init failed: %s", exc)
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
