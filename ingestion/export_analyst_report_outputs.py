"""Export analyst report query outputs from Redshift."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import UTC, datetime
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.audit_gtfsr_snapshot_coverage import build_coverage_report  # noqa: E402
from ingestion.redshift_utils import get_redshift_connection_from_env  # noqa: E402
from ingestion.utils import ensure_dir, load_env, setup_logging  # noqa: E402

QUERIES: dict[str, str] = {
    "top_recurring_high_impact_sa2s.csv": """
        select sa2_code, sa2_name, irsd_decile, days_observed,
               avg_equity_impact_score, max_equity_impact_score,
               high_or_above_snapshot_rate, avg_delay_observation_rate,
               peak_equity_risk_band
        from marts.mart_sa2_multi_day_equity_summary
        order by avg_equity_impact_score desc nulls last
        limit 25
    """,
    "seifa_decile_vs_disruption.csv": """
        select irsd_decile, sa2_count, avg_equity_impact_score,
               avg_disruption_score, avg_delay_observation_rate,
               total_observations, total_delayed_observations
        from marts.mart_seifa_disruption_comparison
        order by irsd_decile
    """,
    "route_contribution_to_high_impact_areas.csv": """
        with high_impact_sa2 as (
            select sa2_code
            from marts.mart_sa2_multi_day_equity_summary
            where peak_equity_risk_band in ('moderate', 'high', 'very_high')
               or avg_equity_impact_score >= 35
        )
        select d.route_id,
               count(*) as delayed_observations_in_high_impact_sa2,
               count(distinct d.sa2_code) as high_impact_sa2_count,
               count(distinct d.trip_id) as distinct_trip_count,
               avg(d.max_delay_seconds) as avg_max_delay_seconds
        from intermediate.int_trip_delay_events d
        inner join high_impact_sa2 h on d.sa2_code = h.sa2_code
        where d.is_delayed_5min = true and d.route_id is not null
        group by 1
        order by delayed_observations_in_high_impact_sa2 desc nulls last
        limit 25
    """,
    "hourly_disruption_pattern.csv": """
        select snapshot_hour, peak_period_flag, observed_sa2_count,
               avg_delay_observation_rate, avg_equity_impact_score,
               total_delayed_observations
        from marts.mart_hourly_disruption_pattern
        order by snapshot_hour
    """,
    "data_sufficiency_summary.csv": """
        select count(distinct snapshot_date) as days_in_mart,
               count(distinct snapshot_hour) as hours_in_mart,
               count(*) as sa2_hour_rows,
               count(distinct sa2_code) as sa2_count,
               sum(observation_count) as total_observations
        from marts.mart_transport_disruption_equity_score
    """,
}


def export_query(connection, sql: str, output_path: Path) -> int:
    with connection.cursor() as cursor:
        cursor.execute(sql)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(rows)
    return len(rows)


def write_summary(output_dir: Path, results: dict[str, int], rating: str) -> None:
    lines = [
        "# Analyst report export summary",
        "",
        f"Generated at: {datetime.now(UTC).isoformat()}",
        f"Data sufficiency rating (local GTFS-R audit): **{rating}**",
        "",
        "## Files",
        "",
    ]
    for name, count in results.items():
        lines.append(f"- `{name}`: {count} rows")
    lines.extend(
        [
            "",
            "## Status",
            "",
            "Exploratory" if rating in {"insufficient", "exploratory"} else "Evidence-ready minimum met",
            "",
        ]
    )
    (output_dir / "analyst_report_summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export analyst report CSVs from Redshift.")
    parser.add_argument("--output-dir", default="docs/analyst_report/data")
    args = parser.parse_args()
    logger = setup_logging()
    load_env()
    output_dir = ensure_dir(Path(args.output_dir))
    coverage = build_coverage_report(Path("data/processed"))
    rating = coverage["data_sufficiency_rating"]
    connection = get_redshift_connection_from_env()
    results: dict[str, int] = {}
    try:
        for filename, sql in QUERIES.items():
            path = output_dir / filename
            count = export_query(connection, sql, path)
            results[filename] = count
            logger.info("Wrote %s (%s rows)", path, count)
    finally:
        connection.close()
    write_summary(output_dir, results, rating)
    logger.info("Analyst export complete (rating=%s)", rating)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
