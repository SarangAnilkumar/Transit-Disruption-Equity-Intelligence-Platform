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

## Important metric framing
This project derives a **disruption exposure analytical metric** from observed feed snapshots. It is **not** an official government reliability KPI and should be interpreted as a decision-support proxy.

## Future phases
- Geospatial stop-to-SA2 mapping and boundary joins.
- Equity layer integration (SEIFA, population, transport dependence proxies).
- Redshift load scripts and dbt staging/intermediate/marts models.
- Orchestration, data quality checks, and snapshot cadence hardening.

## Known limitations
- GTFS-Realtime snapshots are sampled observations, not complete operational records.
- Feed coverage and schema quality can vary by operator and time.
- Metro trains only in MVP; buses and trams are intentionally deferred.

See `PROJECT_SCOPE.md` and `docs/limitations.md` for full details.
