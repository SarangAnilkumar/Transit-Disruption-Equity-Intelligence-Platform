# Data Model

This document describes the local data layers and how they prepare for warehouse loading.

## Layers

| Layer | Location | Purpose |
|-------|----------|---------|
| Raw | `data/raw/` | Immutable feed snapshots (zip, protobuf, boundaries) |
| Processed | `data/processed/` | Parsed and derived CSV/TXT outputs |
| Warehouse-ready | `data/processed/warehouse_ready/` | Standardised, metadata-enriched load contracts |
| SQL raw DDL | `sql/create_raw_tables.sql` | Redshift raw table definitions (design only in M4) |
| dbt (future) | `dbt/` | Staging, intermediate, and mart models (Milestone 5+) |

## Warehouse-ready datasets

Canonical schemas live in `config/warehouse_schemas.yml`. The builder (`ingestion/build_warehouse_ready_datasets.py`) reads processed outputs and writes domain-organised CSVs:

- **GTFS static**: stops, routes, trips, stop_times
- **GTFS-Realtime**: trip updates, service alerts
- **Geospatial**: stop-to-SA2 mapping, route-to-SA2 coverage
- **Equity**: SEIFA SA2 ready
- **Analytics**: SA2 disruption observations base

Each row includes load metadata: `warehouse_dataset`, `source_file`, `prepared_at`, `load_batch_id`.

## Future dbt layers (planned)

- **Staging**: Typed views over raw tables with consistent naming
- **Intermediate**: Trip delay events, service alert events, route daily disruption
- **Marts**: SA2 disruption exposure, equity-disruption score

See `docs/warehouse_ready_datasets.md` for quality checks, reconciliation, and Milestone 5 COPY assumptions.
