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

# Optional destructive reload (explicit flag only)
python ingestion/load_s3_to_redshift_raw.py --dataset gtfs_stops --truncate-before-load
```

Reports are written under `data/processed/warehouse_ready/quality_reports/`.

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

## Staging models

Views in `staging` schema:

- GTFS static: `stg_gtfs_stops`, `stg_gtfs_routes`, `stg_gtfs_trips`, `stg_gtfs_stop_times`
- GTFS-R: `stg_gtfs_trip_updates`, `stg_gtfs_service_alerts`
- Geospatial: `stg_stops_sa2_mapping`, `stg_route_sa2_coverage`
- Analytics: `stg_sa2_disruption_observations_base`
- Equity: `stg_seifa_sa2`

Sources defined in `dbt_transit_equity/models/sources/sources.yml` (`raw` schema).

## dbt docs and lineage screenshots

After first successful `dbt docs generate`:

1. Open `dbt docs serve` lineage view.
2. Capture screenshots of raw → staging lineage.
3. Optionally commit screenshots under `docs/assets/dbt_lineage/` (not generated automatically in this milestone).

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
