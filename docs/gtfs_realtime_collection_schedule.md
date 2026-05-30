# GTFS-Realtime collection schedule

## Purpose

Collect enough GTFS-R snapshots over time to support **evidence-grade** analyst reporting (minimum **7 days**, **15-minute** intervals during active windows).

## One-off snapshot

```bash
set -a && source .env && set +a
python ingestion/collect_gtfs_realtime_snapshots.py --once --feed both
python ingestion/parse_gtfs_realtime.py --feed trip_updates --input <path/to/feed.pb>  # optional if using collector
python ingestion/audit_gtfsr_snapshot_coverage.py
```

The collector fetches **and parses** both feeds in one step.

## 8-hour collection (portfolio default)

```bash
python ingestion/collect_gtfs_realtime_snapshots.py --duration-hours 8 --interval-minutes 15 --feed both
```

Covers one weekday with morning + evening peaks if started around 06:30–07:00.

## 24-hour collection

```bash
python ingestion/collect_gtfs_realtime_snapshots.py --duration-hours 24 --interval-minutes 15 --feed both
```

## Multi-day collection (manual)

Run daily for 7–14 days:

```bash
python ingestion/collect_gtfs_realtime_snapshots.py --duration-hours 18 --interval-minutes 15 --feed both
python ingestion/audit_gtfsr_snapshot_coverage.py
```

Repeat each weekday; optionally run shorter windows on weekends.

## macOS cron example

Edit crontab (`crontab -e`):

```cron
# Weekdays 06:30–22:30, 15-min GTFS-R collection (adjust path)
30 6 * * 1-5 cd "/path/to/Transit Disruption Equity Intelligence Platform" && set -a && source .env && set +a && /usr/bin/python ingestion/collect_gtfs_realtime_snapshots.py --duration-hours 16 --interval-minutes 15 --feed both >> logs/gtfsr_collection.log 2>&1
```

Ensure `.env` contains valid `TRANSPORT_API_KEY` and feed URLs.

## Stop a running collection

Press **Ctrl+C** in the terminal. Partial manifest is still useful; re-run audit:

```bash
python ingestion/audit_gtfsr_snapshot_coverage.py
```

## Verify snapshots

```bash
find data/processed/gtfs_realtime -name parsed.csv | wc -l
python ingestion/audit_gtfsr_snapshot_coverage.py
cat docs/insights/gtfsr_snapshot_coverage_report.md
```

## Refresh after collection

Local only (dry-run first):

```bash
python ingestion/refresh_after_gtfsr_collection.py --dry-run
python ingestion/refresh_after_gtfsr_collection.py
```

With cloud + dbt (when ready):

```bash
python ingestion/refresh_after_gtfsr_collection.py --include-s3 --include-redshift --include-dbt --include-analyst-exports
```

## API / cost cautions

- Transport Victoria API keys may have rate limits — **15-minute** intervals are sufficient for this portfolio project.
- Do not run infinite loops; use `--duration-hours` or `--max-cycles`.
- Empty snapshots can occur during quiet periods — logged as warnings, not failures.
- Collection is **local-first**; no AWS required until refresh/upload.

## Why 15-minute intervals?

GTFS-R trip updates capture **observed delay states** at a point in time. Fifteen-minute cadence balances:

- Enough temporal resolution for peak/off-peak comparison
- Reasonable API usage for a portfolio project
- Alignment with common operational monitoring practice (not real-time control)

This is **not** equivalent to official monthly reliability reporting.
