# Final project story

## Problem

Public transport disruptions in Melbourne are not experienced equally. Some SA2 areas combine higher observed delay and alert exposure with greater socio-economic disadvantage and different network coverage. Planners need **reproducible, transparent evidence** — not opaque scores.

## Solution

The **Transit Disruption Equity Intelligence Platform** ingests Transport Victoria GTFS static and GTFS-Realtime feeds, maps stops to ABS SA2 geography, joins SEIFA 2021 disadvantage indicators, and builds dbt marts that rank SA2-level **disruption equity impact** using documented formulas.

## Architecture

```text
Transport Victoria APIs
  → Python ingestion (local + S3)
  → Redshift raw_data (COPY)
  → dbt staging / intermediate / marts
  → Insight queries + portfolio docs
```

Key AWS components: S3 (warehouse-ready CSVs), Redshift Serverless (raw + transformed views), IAM role for COPY.

## Pipeline stages

1. **Ingestion:** GTFS static, GTFS-R trip updates & service alerts
2. **Geospatial:** Stop-to-SA2 mapping, route-to-SA2 coverage
3. **Equity prep:** SEIFA SA2 validation and warehouse-ready outputs
4. **Warehouse-ready:** Standardised CSV contracts + quality checks
5. **Cloud load:** S3 upload → Redshift raw tables
6. **dbt:** Staging → intermediate event/exposure models → equity scoring marts
7. **Insights:** Analysis SQL + exported summaries for portfolio

## Final marts

- `mart_transport_disruption_equity_score` — primary SA2/date/hour equity impact mart
- `mart_route_disruption_summary` — route daily disruption summary
- `mart_disruption_hotspots` — reporting layer for top-impact SA2 snapshots
- `mart_sa2_daily_equity_summary` — daily SA2 rollup

## Scoring (v1)

Transparent weighted proxy documented in `docs/transport_disruption_equity_scoring.md`. Disruption exposure is primary; disadvantage weight amplifies priority for lower SEIFA decile areas.

## Evidence

- Milestone 5 dbt lineage: `docs/assets/dbt_lineage/`
- Milestone 6 final lineage & insights: `docs/assets/milestone_6/`

## Limitations

See scoring doc and `docs/limitations.md`. This is analytical decision support from sampled GTFS-R snapshots — not an official KPI.

## Status

Milestones 1–6 complete. Live Redshift validation: 10 staging models, 31+ dbt tests (M5), extended intermediate/mart layer (M6).

## Reproduce

See README sections for Milestones 4–6 and `docs/redshift_dbt_foundation.md`.
