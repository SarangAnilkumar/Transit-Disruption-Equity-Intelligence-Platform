# Warehouse-Ready Datasets

## Purpose

The warehouse-ready layer sits between local processed outputs and future Redshift raw loads. It standardises column names and types, adds load metadata, and produces manifests and quality reports that support Milestone 5 COPY workflows without requiring AWS in Milestone 4.

## Folder structure

```
data/processed/warehouse_ready/
├── gtfs_static/
│   ├── gtfs_stops.csv
│   ├── gtfs_routes.csv
│   ├── gtfs_trips.csv
│   └── gtfs_stop_times.csv
├── gtfs_realtime/
│   ├── gtfs_trip_updates.csv
│   └── gtfs_service_alerts.csv
├── geospatial/
│   ├── stops_sa2_mapping.csv
│   └── route_sa2_coverage.csv
├── equity/
│   └── seifa_sa2_ready.csv
├── analytics/
│   └── sa2_disruption_observations_base.csv
├── manifests/
│   ├── warehouse_manifest_<batch_id>.json
│   └── ingestion_run_<batch_id>.json
└── quality_reports/
    ├── <dataset>_quality_report.json
    ├── local_quality_summary_<batch_id>.json
    └── reconciliation_report_<batch_id>.json
```

Generated outputs live under `data/processed/` and are gitignored. Rebuild locally with the commands below.

## Dataset list

| Dataset | Domain | Grain | Future Redshift table |
|---------|--------|-------|------------------------|
| gtfs_stops | gtfs_static | stop | raw_gtfs_stops |
| gtfs_routes | gtfs_static | route | raw_gtfs_routes |
| gtfs_trips | gtfs_static | trip | raw_gtfs_trips |
| gtfs_stop_times | gtfs_static | trip × stop sequence | raw_gtfs_stop_times |
| gtfs_trip_updates | gtfs_realtime | trip update observation | raw_gtfs_trip_updates |
| gtfs_service_alerts | gtfs_realtime | alert entity | raw_gtfs_service_alerts |
| stops_sa2_mapping | geospatial | stop | raw_stops_sa2_mapping |
| route_sa2_coverage | geospatial | route × SA2 | raw_route_sa2_coverage |
| seifa_sa2_ready | equity | SA2 | raw_seifa_sa2 |
| sa2_disruption_observations_base | analytics | SA2 × date × hour | raw_sa2_disruption_observations_base |

Canonical contracts are defined in `config/warehouse_schemas.yml`.

## Schema registry

`config/warehouse_schemas.yml` defines for each dataset:

- `grain` and `natural_key`
- `required_columns` and `nullable_columns`
- `column_types` (string, integer, float, boolean, timestamp)
- `timestamp_columns`
- `source_files` (processed input patterns)
- `future_redshift_table`
- `allow_empty` for optional feeds (realtime snapshots, SEIFA)

The builder selects schema columns, coerces types, and appends metadata.

## Metadata columns

Every warehouse-ready dataset includes:

| Column | Description |
|--------|-------------|
| `warehouse_dataset` | Canonical dataset name |
| `source_file` | Processed source path or summary label |
| `prepared_at` | UTC ISO timestamp when the row was prepared |
| `load_batch_id` | Unique batch ID for the build run |

`row_hash` is intentionally omitted. Row-level hashing across wide GTFS tables adds complexity without clear benefit at this stage; natural keys and reconciliation reports provide sufficient load traceability for Milestone 4.

## Commands

```bash
python ingestion/build_warehouse_ready_datasets.py --dataset all
python ingestion/run_local_quality_checks.py --dataset all
python ingestion/reconcile_processed_outputs.py
pytest -q
```

Optional flags:

- `--dataset gtfs_static|gtfs_realtime|geospatial|equity|analytics|all`
- `--output-dir` / `--processed-dir` / `--input-dir`

## Quality checks

`ingestion/run_local_quality_checks.py` validates warehouse-ready files:

- Required columns present
- Non-null key fields
- Duplicate natural keys (warning)
- Timestamp parseability
- Numeric delay ranges (-3600 to 86400 seconds)
- Lat/lon ranges for stop data
- SA2 code present for matched stops
- Row count > 0 unless `allow_empty`

Results are split into **errors**, **warnings**, and **passed** checks. Warnings do not fail the overall project run.

## Row-count reconciliation

`ingestion/reconcile_processed_outputs.py` compares processed source row counts with warehouse-ready outputs. Mismatches usually indicate a build error or schema selection issue. Realtime feeds concatenated from multiple snapshots should match the sum of parsed CSV rows.

## Ingestion run metadata

Each build run writes:

- `warehouse_manifest_<batch_id>.json` — datasets, row counts, quality report paths, warnings/errors
- `ingestion_run_<batch_id>.json` — run record aligned with `raw_ingestion_runs` DDL

## Redshift preparation (Milestone 5)

Milestone 4 delivers:

1. Stable local CSV contracts matching `sql/create_raw_tables.sql`
2. Manifests and quality reports for audit
3. Reconciliation evidence before COPY

Milestone 5 will add S3 upload, Redshift COPY, dbt sources, and staging models. No COPY or cloud infrastructure runs in Milestone 4.

## Known limitations

- Warehouse-ready files are regenerated locally; they are not committed to git.
- GTFS-R datasets may be empty if no snapshots exist; this is allowed but logged.
- SEIFA is optional until `seifa_sa2_ready.csv` exists.
- Type coercion uses pandas best-effort parsing; Redshift COPY may need explicit NULL handling for edge cases.
- Calendar tables are not yet in the warehouse-ready scope (can be added in a later milestone if needed).
