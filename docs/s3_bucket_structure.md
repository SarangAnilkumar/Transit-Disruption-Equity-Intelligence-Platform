# S3 Bucket Structure

This document describes the recommended S3 layout for Milestone 5 loads. **Review bucket name, IAM policies, and lifecycle rules before creating resources.**

## Design principles

- Separate prefixes for warehouse-ready loads, raw archives, and dbt artifacts.
- No secrets or credentials stored in S3.
- Cost control: use one bucket with prefix isolation; add lifecycle expiration for non-production prefixes if desired.
- Region default: `ap-southeast-2` (override via `AWS_REGION`).

## Recommended bucket layout

```
s3://<S3_BUCKET_NAME>/
├── transit-equity/
│   ├── warehouse_ready/
│   │   ├── gtfs_static/
│   │   │   ├── gtfs_stops.csv
│   │   │   ├── gtfs_routes.csv
│   │   │   ├── gtfs_trips.csv
│   │   │   └── gtfs_stop_times.csv
│   │   ├── gtfs_realtime/
│   │   │   ├── gtfs_trip_updates.csv
│   │   │   └── gtfs_service_alerts.csv
│   │   ├── geospatial/
│   │   │   ├── stops_sa2_mapping.csv
│   │   │   └── route_sa2_coverage.csv
│   │   ├── equity/
│   │   │   └── seifa_sa2_ready.csv
│   │   ├── analytics/
│   │   │   └── sa2_disruption_observations_base.csv
│   │   ├── manifests/
│   │   │   ├── warehouse_manifest_<batch>.json
│   │   │   ├── s3_upload_manifest_<batch>.json
│   │   │   └── ingestion_run_<batch>.json
│   │   └── quality_reports/
│   │       └── *.json
│   ├── raw/
│   │   └── (optional future immutable raw archives)
│   └── dbt_artifacts/
│       ├── manifest.json
│       ├── catalog.json
│       └── index.html
```

Environment variables (placeholders in `.env.example`):

- `S3_BUCKET_NAME`
- `S3_WAREHOUSE_READY_PREFIX=transit-equity/warehouse_ready`
- `S3_RAW_PREFIX=transit-equity/raw`
- `S3_DBT_ARTIFACTS_PREFIX=transit-equity/dbt_artifacts`

## IAM expectations

Redshift COPY requires an IAM role (`REDSHIFT_IAM_ROLE_ARN`) trusted by Redshift with read access to `s3://<bucket>/transit-equity/warehouse_ready/*`.

Local upload uses your AWS profile (`AWS_PROFILE`) or default credential chain with `s3:PutObject` on the same prefix.

## Upload script mapping

`ingestion/upload_warehouse_ready_to_s3.py` uploads:

- Warehouse-ready CSVs only (not `data/raw/` files)
- Local manifests and quality reports under the same prefix

Dry-run first:

```bash
python ingestion/upload_warehouse_ready_to_s3.py --dry-run --dataset all
```

## Cost notes

- Do not enable versioning on large prefixes unless required.
- Consider lifecycle rules to expire test uploads after 30–90 days.
- Pause or resize Redshift when not actively loading/testing.
