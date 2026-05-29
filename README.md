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

## Known limitations
- GTFS-Realtime snapshots are sampled observations, not complete operational records.
- Feed coverage and schema quality can vary by operator and time.
- Metro trains only in MVP; buses and trams are intentionally deferred.

See `PROJECT_SCOPE.md` and `docs/limitations.md` for full details.
