"""Audit GTFS-R snapshot coverage and rate data sufficiency for analyst reporting."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingestion.utils import ensure_dir, load_env, load_settings, save_json_to_file, setup_logging  # noqa: E402

PARSED_PATTERN = re.compile(
    r"feed=(?P<feed>[^/]+)/year=(?P<year>\d{4})/month=(?P<month>\d{2})/day=(?P<day>\d{2})/hour=(?P<hour>\d{2})/minute=(?P<minute>\d{2})"
)


def _parse_snapshot_path(path: Path) -> dict[str, Any] | None:
    match = PARSED_PATTERN.search(str(path))
    if not match:
        return None
    parts = match.groupdict()
    ts = datetime(
        int(parts["year"]),
        int(parts["month"]),
        int(parts["day"]),
        int(parts["hour"]),
        int(parts["minute"]),
        tzinfo=UTC,
    )
    return {
        "feed": parts["feed"],
        "timestamp": ts,
        "date": ts.date().isoformat(),
        "hour": int(parts["hour"]),
        "weekday": ts.weekday(),
    }


def _count_csv_rows(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def _sufficiency_rating(days_covered: int) -> str:
    if days_covered < 1:
        return "insufficient"
    if days_covered <= 6:
        return "exploratory"
    if days_covered <= 13:
        return "analyst-ready"
    return "strong"


def _recommended_action(rating: str) -> str:
    return {
        "insufficient": "Collect at least 7 days of 15-minute GTFS-R snapshots before evidence-grade reporting.",
        "exploratory": "Continue collection toward 7+ days; label all outputs as exploratory only.",
        "analyst-ready": "Minimum threshold met; proceed with cautious analyst report and note snapshot limitations.",
        "strong": "Strong coverage; suitable for robust multi-day comparisons and portfolio evidence.",
    }[rating]


def build_coverage_report(processed_root: Path) -> dict[str, Any]:
    parsed_files = sorted((processed_root / "gtfs_realtime").rglob("parsed.csv"))
    snapshots: list[dict[str, Any]] = []
    for path in parsed_files:
        meta = _parse_snapshot_path(path)
        if meta is None:
            continue
        snapshots.append(
            {
                **meta,
                "path": str(path),
                "row_count": _count_csv_rows(path),
            }
        )

    dates = sorted({item["date"] for item in snapshots})
    days_covered = len(dates)
    by_feed = Counter(item["feed"] for item in snapshots)
    by_hour = Counter(item["hour"] for item in snapshots)
    by_date = Counter(item["date"] for item in snapshots)
    weekday_dates = {item["date"] for item in snapshots if item["weekday"] < 5}
    weekend_dates = {item["date"] for item in snapshots if item["weekday"] >= 5}

    morning = sum(1 for item in snapshots if 7 <= item["hour"] <= 9)
    evening = sum(1 for item in snapshots if 16 <= item["hour"] <= 18)
    trip_rows = sum(item["row_count"] for item in snapshots if item["feed"] == "trip_updates")
    alert_rows = sum(item["row_count"] for item in snapshots if item["feed"] == "service_alerts")

    rating = _sufficiency_rating(days_covered)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_snapshots": len(snapshots),
        "date_range": {"start": dates[0] if dates else None, "end": dates[-1] if dates else None},
        "days_covered": days_covered,
        "snapshots_per_day": dict(by_date),
        "snapshots_by_feed": dict(by_feed),
        "snapshots_by_hour": {str(k): v for k, v in sorted(by_hour.items())},
        "trip_update_row_count": trip_rows,
        "service_alert_row_count": alert_rows,
        "morning_peak_snapshots": morning,
        "evening_peak_snapshots": evening,
        "weekday_days_covered": len(weekday_dates),
        "weekend_days_covered": len(weekend_dates),
        "data_sufficiency_rating": rating,
        "recommended_next_action": _recommended_action(rating),
        "caveat": "Snapshot observations are not official government reliability records.",
        "snapshots": snapshots,
    }


def write_markdown(report: dict[str, Any], output_path: Path) -> None:
    lines = [
        "# GTFS-R snapshot coverage report",
        "",
        f"Generated: {report['generated_at']}",
        "",
        f"**Data sufficiency rating:** `{report['data_sufficiency_rating']}`",
        "",
        "## Summary",
        "",
        f"- Total snapshots: **{report['total_snapshots']}**",
        f"- Days covered: **{report['days_covered']}**",
        f"- Date range: **{report['date_range']['start']}** → **{report['date_range']['end']}**",
        f"- Trip update rows: **{report['trip_update_row_count']:,}**",
        f"- Service alert rows: **{report['service_alert_row_count']:,}**",
        f"- Morning peak snapshots (07–09): **{report['morning_peak_snapshots']}**",
        f"- Evening peak snapshots (16–18): **{report['evening_peak_snapshots']}**",
        f"- Weekday days: **{report['weekday_days_covered']}** | Weekend days: **{report['weekend_days_covered']}**",
        "",
        "## Recommended next action",
        "",
        report["recommended_next_action"],
        "",
        "## Caveat",
        "",
        report["caveat"],
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit GTFS-R snapshot coverage.")
    parser.add_argument("--processed-root", default="data/processed")
    parser.add_argument("--markdown-out", default="docs/insights/gtfsr_snapshot_coverage_report.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = setup_logging()
    load_env()
    processed_root = Path(args.processed_root)
    report = build_coverage_report(processed_root)
    json_dir = ensure_dir(processed_root / "gtfs_realtime" / "coverage_reports")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = json_dir / f"gtfsr_snapshot_coverage_report_{stamp}.json"
    public_report = {k: v for k, v in report.items() if k != "snapshots"}
    save_json_to_file(public_report, json_path)
    md_path = Path(args.markdown_out)
    ensure_dir(md_path.parent)
    write_markdown(public_report, md_path)
    logger.info("Coverage rating: %s", report["data_sufficiency_rating"])
    logger.info("Wrote %s and %s", json_path, md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
