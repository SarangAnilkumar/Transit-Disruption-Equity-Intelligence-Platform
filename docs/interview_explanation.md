# Interview explanation

## Elevator pitch (30 seconds)

I built a data platform that connects Melbourne metro train GTFS-Realtime snapshots to ABS SA2 geography and SEIFA disadvantage data, then scores which areas show the highest **disruption equity impact** in a transparent, documented way — as a portfolio analytics engineering project, not an official government KPI.

## Problem

Disruption averages hide geographic and equity unevenness. I wanted a reproducible pipeline that planners could audit: what data, what grain, what formula, what limitations.

## Architecture

- **Ingestion (Python):** Fetch and parse GTFS static and GTFS-R; prepare warehouse-ready CSVs with batch metadata.
- **Storage:** S3 prefixes for warehouse-ready files; Redshift `raw_data` loaded via COPY with explicit column lists.
- **Transform (dbt):** Staging views on raw tables → intermediate event models (delays, alerts) → SA2 exposure → equity context → scoring components → final marts.
- **Quality:** pytest for ingestion; dbt tests for keys, relationships, accepted values, score ranges.
- **Docs:** Scoring formula, limitations, lineage screenshots, insight exports.

## Data modelling choices

- **Event grain first:** One row per trip update observation before aggregating — preserves auditability.
- **SA2 attachment via stop mapping:** Realistic for exposure proxy; documented that unmatched stops reduce SA2 coverage.
- **SEIFA at SA2 grain:** Matches ABS release; not individual-level disadvantage.
- **Min-max scaling within loaded snapshot:** Keeps scores comparable within the analysed window; documented as limitation for cross-period comparison.

## Scoring trade-offs

- Chose explicit weights (0.5 / 0.3 / 0.2 for disruption components; 0.6 + 0.4 × disadvantage multiplier) instead of ML — interviewers can challenge and adjust weights.
- `equity_impact_score` prioritises disruption but elevates disadvantaged SA2s — reflects policy interest without claiming causal impact.

## Data quality

- SEIFA footer rows filtered before warehouse load (invalid SA2 codes).
- COPY uses explicit column lists to avoid positional misalignment.
- `--truncate-before-load` for clean dev reloads; append-by-default documented.
- dbt tests on route/trip/stop relationships for static GTFS integrity.

## What I would improve next

- Scheduled GTFS-R ingestion for multi-day trend analysis
- Materialise heavy intermediate models as tables with sort keys on `sa2_code`, `snapshot_date`
- Ridership or patronage proxy if data becomes available
- Sensitivity analysis on scoring weights
- Fix `staging_staging` legacy schema or migrate views after `generate_schema_name` macro
- Source freshness monitoring in production orchestration

## Honest limitations to mention proactively

- Snapshot frequency drives observed disruption counts
- Not official PTV reliability reporting
- Spatial mapping ≠ who actually travels from an SA2
- SEIFA decile is area context, not individual need

## Questions I hope this project answers

1. Which SA2 areas combine high observed disruption with higher disadvantage?
2. Which routes drive delay/alert exposure in the loaded window?
3. Are there hours with disproportionate disruption patterns?

See `docs/transport_disruption_equity_scoring.md` and `dbt_transit_equity/analyses/` for query examples.
