# Project Scope

## Final analytical question
"Which Melbourne SA2 areas experience the highest public transport disruption exposure when combined with socio-economic disadvantage and transport dependence?"

## In scope (MVP)
- Local-first project scaffold and reproducible repository structure.
- GTFS static ingestion, storage, extraction, and basic row-count checks.
- GTFS-Realtime ingestion for:
  - Trip Updates
  - Service Alerts
- GTFS-R protobuf parsing into analysis-friendly CSVs.
- Raw/processed data zone partitioning conventions.
- Initial SQL DDL scaffold for future Redshift raw layer.
- dbt project skeleton and source definitions only.
- Basic tests for path/config/environment behavior.

## Out of scope (MVP)
- AWS infrastructure provisioning (S3, IAM, Redshift clusters).
- Full dbt transformation layer implementation.
- Dashboarding or BI productization.
- ML forecasting or predictive modelling.
- Buses and trams ingestion/analysis.
- Publishing official reliability metrics.

## MVP success criteria
- Can download and parse GTFS static data locally.
- Can fetch at least one GTFS-R feed snapshot (Trip Updates or Service Alerts).
- Can parse GTFS-R protobuf snapshots into clean CSV outputs.
- Scripts fail clearly with setup guidance when env values are missing.
- Tests run without requiring secrets or live API responses.
- Documentation explains assumptions, scope, and limitations from day one.

## Future extensions
- Geospatial preprocessing: stop-to-SA2 mapping.
- SA2 equity enrichment: ABS SEIFA, population, car ownership/proxy measures.
- Redshift `COPY` ingestion and dbt layered models.
- Data quality expectations and freshness monitoring.
- Orchestration (e.g., cron/Airflow/Prefect) and CI checks.
