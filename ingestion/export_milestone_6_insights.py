"""Export Milestone 6 insight query results from Redshift to docs/insights/."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import UTC, datetime
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.redshift_utils import get_redshift_connection_from_env  # noqa: E402
from ingestion.utils import ensure_dir, load_env, setup_logging  # noqa: E402

QUERIES: dict[str, str] = {
    "top_equity_impact_sa2s.csv": """
        select sa2_code, sa2_name, irsd_decile, equity_impact_score, equity_risk_band,
               observation_count, delayed_observation_count, delay_observation_rate,
               disruption_alert_count
        from marts.mart_transport_disruption_equity_score
        order by equity_impact_score desc nulls last
        limit 25
    """,
    "route_disruption_summary.csv": """
        select route_id, route_short_name, route_long_name,
               sum(observed_trip_update_rows) as total_observations,
               sum(delayed_observation_count) as total_delayed_observations,
               sum(disruption_alert_count) as total_disruption_alerts,
               max(max_delay_seconds) as peak_delay_seconds
        from marts.mart_route_disruption_summary
        group by 1, 2, 3
        order by total_delayed_observations desc nulls last
        limit 25
    """,
    "seifa_vs_disruption_summary.csv": """
        select case
                 when irsd_decile <= 3 then 'most_disadvantaged_deciles_1_3'
                 when irsd_decile <= 7 then 'middle_deciles_4_7'
                 else 'least_disadvantaged_deciles_8_10'
               end as seifa_decile_band,
               count(*) as sa2_hour_rows,
               avg(equity_impact_score) as avg_equity_impact_score,
               avg(disruption_score) as avg_disruption_score,
               avg(delay_observation_rate) as avg_delay_observation_rate
        from marts.mart_transport_disruption_equity_score
        where irsd_decile is not null
        group by 1
        order by avg_equity_impact_score desc
    """,
    "hourly_disruption_pattern.csv": """
        select snapshot_hour,
               count(distinct sa2_code) as sa2_count,
               sum(observation_count) as total_observations,
               avg(equity_impact_score) as avg_equity_impact_score
        from marts.mart_transport_disruption_equity_score
        group by 1
        order by avg_equity_impact_score desc nulls last
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


def write_summary(output_dir: Path, results: dict[str, int]) -> None:
    lines = [
        "# Milestone 6 insight summary",
        "",
        f"Generated at: {datetime.now(UTC).isoformat()}",
        "",
        "## Exported files",
        "",
    ]
    for name, count in results.items():
        lines.append(f"- `{name}`: {count} rows")
    lines.extend(
        [
            "",
            "## Interpretation notes",
            "",
            "- Scores are snapshot-based disruption exposure proxies, not official reliability KPIs.",
            "- SA2 attachment depends on stop-to-SA2 spatial mapping coverage.",
            "- SEIFA is area-level disadvantage context, not individual-level need.",
            "",
        ]
    )
    (output_dir / "milestone_6_insight_summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Milestone 6 insight CSVs from Redshift.")
    parser.add_argument("--output-dir", default="docs/insights")
    args = parser.parse_args()
    logger = setup_logging()
    load_env()
    output_dir = ensure_dir(Path(args.output_dir))
    connection = get_redshift_connection_from_env()
    results: dict[str, int] = {}
    try:
        for filename, sql in QUERIES.items():
            path = output_dir / filename
            row_count = export_query(connection, sql, path)
            results[filename] = row_count
            logger.info("Wrote %s (%s rows)", path, row_count)
    finally:
        connection.close()
    write_summary(output_dir, results)
    logger.info("Wrote summary to %s", output_dir / "milestone_6_insight_summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
