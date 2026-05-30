# Transit Disruption Equity Intelligence Platform

## Problem statement
Public transport disruptions are not experienced equally across a city. This project builds a data platform to identify where disruption exposure may overlap with socio-economic disadvantage and transport dependence, starting with Melbourne metro trains.

## Why this matters
- Disruption burden can compound existing inequities in access to jobs, education, and services.
- Transport planning decisions benefit from place-based evidence, not only network-wide averages.
- A reproducible data pipeline enables transparent, auditable, and extensible analysis.

## MVP scope (Milestone 1: Data feasibility)
- Geography: Victoria data inputs, with analysis focus on Melbourne metro trains.
- Modes: Metro trains only.
- Build local-first ingestion and parsing for GTFS static and GTFS-Realtime feeds.
- Prepare folder conventions and scaffolding for future S3, Redshift, and dbt integration.
- Validate feasibility with basic tests and clear documentation.

## Planned architecture (phased)
1. **Ingestion (local-first)**: Python scripts fetch GTFS static zips and GTFS-R protobuf snapshots.
2. **Raw zone**: Immutable files under partitioned folders by date/time.
3. **Processed zone**: Parsed CSV tables for downstream modelling.
4. **Warehouse (future)**: Load raw/processed data into Amazon Redshift raw/staging layers.
5. **Transform (future)**: dbt models for disruption exposure, equity joins, and final marts.
6. **Analytics (future)**: Scoring and prioritization outputs for SA2-level insights.

## Data sources
- GTFS static schedule feed (routes, trips, stop_times, stops, calendar).
- GTFS-Realtime Trip Updates feed.
- GTFS-Realtime Service Alerts feed.
- ABS SEIFA and SA2 boundaries (future phase).

Detailed source documentation: `docs/data_sources.md`.

## Current status
- Local scaffold created for ingestion, processing, SQL, dbt, docs, and tests.
- GTFS static fetch/extract script implemented.
- GTFS-R fetch script implemented for trip updates and service alerts.
- GTFS-R parser implemented to normalized CSV outputs.
- Basic pytest coverage included for path/config/env behavior.

## Quick start (feasibility run)
1. Install dependencies:
   - `pip install -r requirements.txt`
2. Configure `.env` from `.env.example` with:
   - `GTFS_STATIC_URL`
   - `GTFS_REALTIME_TRIP_UPDATES_URL`
   - `GTFS_REALTIME_SERVICE_ALERTS_URL`
3. Run scripts:
   - `python ingestion/fetch_gtfs_static.py`
   - `python ingestion/fetch_gtfs_realtime.py --feed trip_updates`
   - `python ingestion/parse_gtfs_realtime.py --feed trip_updates --input <path_to_feed.pb>`
4. Run tests:
   - `pytest`

If required URLs are missing, scripts intentionally return clear setup errors rather than failing silently.

## Milestone 1.5 - Validate real Transport Victoria feeds
1. Copy env template and set credentials:
   - `cp .env.example .env`
   - Paste your real key into `TRANSPORT_API_KEY` (never commit this file).
2. Start with header auth:
   - `TRANSPORT_API_AUTH_MODE=header`
   - `TRANSPORT_API_HEADER_NAME=Ocp-Apim-Subscription-Key`
3. If auth fails:
   - Try `TRANSPORT_API_HEADER_NAME=KeyID`
   - If still failing, switch to query auth:
     - `TRANSPORT_API_AUTH_MODE=query`
     - `TRANSPORT_API_QUERY_PARAM_NAME=subscription-key`
4. Run validation commands:
   - `python ingestion/fetch_gtfs_static.py`
   - `python ingestion/fetch_gtfs_realtime.py --feed trip_updates`
   - `python ingestion/fetch_gtfs_realtime.py --feed service_alerts`
   - `python ingestion/validate_transport_feeds.py --feed both`

Expected output locations:
- Static raw zip: `data/raw/gtfs_static/load_date=YYYY-MM-DD/gtfs_static.zip`
- Realtime raw protobuf: `data/raw/gtfs_realtime/feed=<feed_name>/year=YYYY/month=MM/day=DD/hour=HH/minute=mm/feed.pb`
- Realtime parsed CSV: `data/processed/gtfs_realtime/feed=<feed_name>/year=YYYY/month=MM/day=DD/hour=HH/minute=mm/parsed.csv`
- Validation report: `data/samples/feed_validation_report_<timestamp>.json`

Interpretation notes:
- **Request failed** (HTTP/auth error): fix URL/auth mode/header/parameter configuration.
- **Request succeeded but parsed rows = 0**: this can be a valid quiet snapshot; collect more snapshots before concluding feed issues.

## Important metric framing
This project derives a **disruption exposure analytical metric** from observed feed snapshots. It is **not** an official government reliability KPI and should be interpreted as a decision-support proxy.

## Future phases
- Geospatial stop-to-SA2 mapping and boundary joins.
- Equity layer integration (SEIFA, population, transport dependence proxies).
- Redshift load scripts and dbt staging/intermediate/marts models.
- Orchestration, data quality checks, and snapshot cadence hardening.

## Milestone 3 - Stop-to-SA2 geospatial mapping
This milestone builds local geospatial/equity readiness artifacts before any AWS or warehouse orchestration.

Commands:
- `python ingestion/ingest_sa2_boundaries.py`
- `python ingestion/build_stop_sa2_mapping.py`
- `python ingestion/build_route_sa2_coverage.py`
- `python ingestion/prepare_seifa_sa2.py`
- `python ingestion/build_sa2_disruption_base.py`
- `pytest -q`

Primary outputs:
- `data/processed/geospatial/stops_sa2_mapping.csv`
- `data/processed/geospatial/route_sa2_coverage.csv`
- `data/processed/geospatial/geospatial_mapping_report.json`
- `data/processed/equity/seifa_sa2_ready.csv` (if SEIFA source file is supplied)
- `data/processed/analytics/sa2_disruption_observations_base.csv` (if parsed trip updates exist)

## Milestone 4 - Local warehouse-ready datasets
Standardise processed outputs into load-ready CSV contracts aligned with Redshift raw DDL. No AWS, S3, or COPY execution in this milestone.

Commands:
- `python ingestion/build_warehouse_ready_datasets.py --dataset all`
- `python ingestion/run_local_quality_checks.py --dataset all`
- `python ingestion/reconcile_processed_outputs.py`
- `pytest -q`

Primary outputs (local, gitignored):
- `data/processed/warehouse_ready/<domain>/<dataset>.csv`
- `data/processed/warehouse_ready/manifests/warehouse_manifest_<batch_id>.json`
- `data/processed/warehouse_ready/quality_reports/local_quality_summary_<batch_id>.json`
- `data/processed/warehouse_ready/quality_reports/reconciliation_report_<batch_id>.json`

Documentation: `docs/warehouse_ready_datasets.md` and `config/warehouse_schemas.yml`.

## Milestone 5 - Redshift + dbt foundation
Connect warehouse-ready local CSVs to S3, Redshift `raw_data` tables (schema name avoids Redshift reserved word `RAW`), and dbt staging views. No final scoring or dashboards in this milestone.

Commands (dry-run first):
- `python ingestion/upload_warehouse_ready_to_s3.py --dry-run --dataset all`
- `python ingestion/init_redshift_raw_schema.py --dry-run`
- `python ingestion/load_s3_to_redshift_raw.py --dry-run --dataset all`
- `dbt parse --project-dir dbt_transit_equity --profiles-dir dbt_transit_equity`

Documentation: `docs/redshift_dbt_foundation.md`, `docs/s3_bucket_structure.md`.

Milestone 5 evidence screenshots: [`docs/assets/dbt_lineage/`](docs/assets/dbt_lineage/).

Copy `dbt_transit_equity/profiles.yml.example` to `profiles.yml` locally only. Never commit credentials.

## Milestone 6 - Disruption exposure, equity scoring & portfolio delivery

Builds the analytical value layer: intermediate dbt models, transparent disruption-equity scoring marts, insight queries, and portfolio documentation.

Commands:
```bash
set -a && source .env && set +a
dbt run --project-dir dbt_transit_equity --profiles-dir dbt_transit_equity
dbt test --project-dir dbt_transit_equity --profiles-dir dbt_transit_equity
dbt docs generate --project-dir dbt_transit_equity --profiles-dir dbt_transit_equity
python ingestion/export_milestone_6_insights.py
```

Key outputs:
- **Marts:** `marts.mart_transport_disruption_equity_score`, `mart_route_disruption_summary`, `mart_disruption_hotspots`, `mart_sa2_daily_equity_summary`
- **Scoring doc:** `docs/transport_disruption_equity_scoring.md`
- **Insights:** `docs/insights/` (exported CSVs + summary)
- **Portfolio story:** `docs/final_project_story.md`, `docs/resume_bullets.md`, `docs/interview_explanation.md`
- **Evidence:** `docs/assets/milestone_6/`

Schema note: `macros/generate_schema_name.sql` builds into clean `staging`, `intermediate`, and `marts` schemas (legacy `staging_staging` views may remain until dropped manually).

## Milestone 7 — Evidence-grade analyst insight layer

Collect multi-day GTFS-R snapshots, audit coverage sufficiency, refresh marts, and produce an analyst report with honest exploratory/evidence-ready labelling.

Commands:
```bash
python ingestion/collect_gtfs_realtime_snapshots.py --duration-hours 8 --interval-minutes 15 --feed both
python ingestion/audit_gtfsr_snapshot_coverage.py
python ingestion/refresh_after_gtfsr_collection.py --dry-run
python ingestion/export_analyst_report_outputs.py
python ingestion/create_analyst_report_visuals.py
```

Documentation: `docs/analyst_research_plan.md`, `docs/gtfs_realtime_collection_schedule.md`, `docs/analyst_report/public_transport_disruption_equity_report.md`.

## Portfolio positioning

### A. Data Engineering value

- Python ingestion for GTFS static and GTFS-Realtime (Transport Victoria)
- Warehouse-ready CSV contracts, local quality checks, reconciliation
- S3 upload and Redshift COPY with explicit column lists and truncate-before-load
- dbt staging → intermediate → marts with tests and lineage docs
- Transparent scoring logic (`v1_transparent_weighted_proxy`), not black-box ML

### B. Data Analyst value

- Research questions and hypotheses (`docs/analyst_research_plan.md`)
- Disruption equity score with SEIFA decile comparison
- Route, SA2, and hourly insight queries + exported CSVs
- Snapshot sufficiency audit (exploratory vs analyst-ready vs strong)
- Visual report artifacts and professional write-up with limitations
- Resume bullets for both DE and DA roles

**Important:** Analyst conclusions are **evidence-grade only after ≥7 days** of GTFS-R collection at 15-minute intervals. Below that threshold, outputs are labelled **exploratory**.

## Project status

**Milestones 1–6 complete.** Live Redshift validation: raw tables loaded, dbt staging/intermediate/marts built, tests passing, docs and lineage screenshots captured.

## Known limitations
- GTFS-Realtime snapshots are sampled observations, not complete operational records.
- Feed coverage and schema quality can vary by operator and time.
- Metro trains only in MVP; buses and trams are intentionally deferred.

See `PROJECT_SCOPE.md` and `docs/limitations.md` for full details.
