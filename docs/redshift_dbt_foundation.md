# Redshift + dbt Foundation (Milestone 5)

## Purpose

Milestone 5 connects local warehouse-ready CSVs to Amazon Redshift and dbt staging models. It does **not** include final disruption scoring, equity marts, or dashboards (Milestone 6).

## Prerequisites

1. Milestone 4 warehouse-ready files built locally.
2. AWS account with S3 bucket and Redshift cluster (cost-controlled; pause when idle).
3. Redshift IAM role with S3 read access for warehouse-ready prefix.
4. Local `.env` populated from `.env.example` (never commit `.env`).

## Environment variables

See `.env.example` for placeholders:

- AWS: `AWS_PROFILE`, `AWS_REGION`, `S3_BUCKET_NAME`, S3 prefixes
- Redshift: host, port, database, user, password, schema names, IAM role ARN
- dbt: `DBT_PROFILES_DIR`, `DBT_TARGET`

### Redshift schema naming

The physical Redshift schema for loaded tables is **`raw_data`** (not `raw`), because `RAW` is a reserved word in Amazon Redshift. Set `REDSHIFT_SCHEMA_RAW=raw_data` in `.env`.

dbt still uses source name `raw` in `source('raw', 'raw_gtfs_stops')`; the source definition maps that logical name to the `raw_data` schema via `REDSHIFT_SCHEMA_RAW`.

Copy dbt profile locally:

```bash
cp dbt_transit_equity/profiles.yml.example dbt_transit_equity/profiles.yml
```

Never commit `dbt_transit_equity/profiles.yml`.

## Dry-run workflow (safe, no cloud writes)

```bash
python ingestion/upload_warehouse_ready_to_s3.py --dry-run --dataset all
python ingestion/init_redshift_raw_schema.py --dry-run
python ingestion/load_s3_to_redshift_raw.py --dry-run --dataset all
```

Dry-runs validate paths, SQL statement counts, and COPY statement generation.

## Live execution workflow

Review `docs/s3_bucket_structure.md` and IAM policies first.

```bash
# 1) Upload warehouse-ready files
python ingestion/upload_warehouse_ready_to_s3.py --dataset all

# 2) Create schemas/tables
python ingestion/init_redshift_raw_schema.py

# 3) COPY into raw tables (append by default)
python ingestion/load_s3_to_redshift_raw.py --dataset all

# Clean dev reload: truncate each target table before COPY (explicit flag only)
python ingestion/load_s3_to_redshift_raw.py --dataset all --truncate-before-load
```

### Append vs truncate

- **Default:** `COPY` **appends** rows. Re-running a load without truncation doubles row counts (for example `raw_gtfs_stops` at ~3007 source rows can show ~6014 after two loads).
- **`--truncate-before-load`:** runs `TRUNCATE TABLE schema.table;` immediately before each selected table’s `COPY`. Use for clean dev reloads after fixing upstream CSVs or re-uploading S3 objects.
- **Dry-run:** with `--truncate-before-load`, logs include planned `TRUNCATE` statements before `COPY` SQL.
- **Production:** prefer append with batch keys / dedupe in staging, or controlled truncate only when you intend to replace a full snapshot.

Failed loads write `redshift_load_report_*.json` including the latest rows from `sys_load_error_detail` (line, column, error code/message) when the cluster allows that query.

Reports are written under `data/processed/warehouse_ready/quality_reports/`.

### SEIFA validation (equity → warehouse-ready → raw)

`ingestion/prepare_seifa_sa2.py` filters ABS Excel footers and bad rows before `seifa_sa2_ready.csv`:

- `sa2_code`: non-null string, trimmed, must match `^\d{9}$` (Australian SA2 code).
- `sa2_name`: non-null; rows with ABS footer/title strings (for example `© Commonwealth of Australia`) are dropped.
- `irsd_score`: required numeric; `irsd_decile` / `irsd_percentile` numeric or null when present.

`ingestion/run_local_quality_checks.py --dataset seifa_sa2_ready` errors if any row has `sa2_code` longer than 32 characters, non-numeric `sa2_code`, or missing/non-numeric `irsd_score`.

After changing SEIFA prep, rebuild equity warehouse-ready, re-upload S3, then reload with truncate:

```bash
python ingestion/prepare_seifa_sa2.py
python ingestion/build_warehouse_ready_datasets.py --dataset equity
python ingestion/upload_warehouse_ready_to_s3.py --dataset seifa_sa2_ready
python ingestion/load_s3_to_redshift_raw.py --dataset seifa_sa2_ready --truncate-before-load
```

## dbt setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Validate project parsing (no Redshift connection required):

```bash
dbt parse --project-dir dbt_transit_equity --profiles-dir dbt_transit_equity
```

When Redshift env vars are set:

```bash
dbt debug --project-dir dbt_transit_equity --profiles-dir dbt_transit_equity
dbt run --project-dir dbt_transit_equity --profiles-dir dbt_transit_equity
dbt test --project-dir dbt_transit_equity --profiles-dir dbt_transit_equity
dbt docs generate --project-dir dbt_transit_equity --profiles-dir dbt_transit_equity
dbt docs serve --project-dir dbt_transit_equity --profiles-dir dbt_transit_equity
```

## Schema naming (`generate_schema_name`)

dbt uses `macros/generate_schema_name.sql` so custom schemas resolve to clean names:

- `staging` (not `staging_staging`)
- `intermediate`
- `marts`

Legacy views under `staging_staging` from earlier runs are not dropped automatically. New `dbt run` builds into the clean schemas above.

Views in `staging` schema:

- GTFS static: `stg_gtfs_stops`, `stg_gtfs_routes`, `stg_gtfs_trips`, `stg_gtfs_stop_times`
- GTFS-R: `stg_gtfs_trip_updates`, `stg_gtfs_service_alerts`
- Geospatial: `stg_stops_sa2_mapping`, `stg_route_sa2_coverage`
- Analytics: `stg_sa2_disruption_observations_base`
- Equity: `stg_seifa_sa2`

Sources defined in `dbt_transit_equity/models/sources/sources.yml` (dbt source name `raw`, Redshift schema `raw_data`).

## dbt docs and lineage screenshots

After first successful `dbt docs generate`:

1. Open `dbt docs serve` lineage view.
2. Capture screenshots of raw → staging lineage.
3. Capture lineage screenshots under `docs/assets/dbt_lineage/` (see `01_`–`06_` PNGs for Milestone 5 evidence).

## Milestone 5 evidence

Live Redshift + dbt validation screenshots are stored in [`docs/assets/dbt_lineage/`](assets/dbt_lineage/):

- `01_dbt_lineage_raw_to_staging.png` — full lineage DAG (`raw` → staging)
- `02_dbt_docs_database_sidebar.png` — dbt docs Database / project sidebar
- `03_staging_model_detail.png` — staging model detail (e.g. `stg_sa2_disruption_observations_base`)
- `04_dbt_column_tests.png` — column tests on a staging model
- `05_dbt_run_test_success.png` — `dbt run` / `dbt test` / `dbt docs generate` success output
- `06_dbt_project_overview.png` — project overview (optional)

## Safety notes

- Do not commit AWS credentials, `.env`, or `profiles.yml`.
- Do not leave Redshift running unnecessarily.
- Generated dbt `target/`, `logs/`, and `dbt_packages/` are gitignored.
- Warehouse-ready and load reports under `data/processed/` are gitignored.

## Known limitations

- Live COPY requires uploaded S3 files and configured `REDSHIFT_IAM_ROLE_ARN`.
- `dbt debug` / `dbt run` fail without reachable Redshift — expected during local-only development.
- GTFS-R raw tables may contain duplicate natural keys across snapshots; staging preserves raw grain.
- `raw_seifa_sa2` and `stg_seifa_sa2` are optional until SEIFA warehouse-ready file exists.

## Related docs

- `docs/warehouse_ready_datasets.md` — local warehouse-ready contracts
- `docs/s3_bucket_structure.md` — S3 prefix layout
- `config/warehouse_schemas.yml` — dataset to raw table mapping
