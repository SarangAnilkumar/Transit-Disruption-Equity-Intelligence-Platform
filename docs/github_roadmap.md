# GitHub Roadmap Setup

This repository uses **GitHub Issues + Milestones** as the current project management approach (instead of a full GitHub Projects board for now).

## Purpose

- Keep the repository structured and recruiter-ready.
- Track roadmap delivery in a transparent, milestone-driven way.
- Preserve factual project status (no fake completed work).

## Milestones

### Milestone 1 — Local Project Scaffold & Data Feasibility Foundation

Create the local-first project structure and prove the repo can support ingestion, parsing, tests, documentation, SQL scaffolding, and dbt scaffolding. Scripts should fail gracefully when URLs or API keys are missing. No real cloud infrastructure is required in this milestone.

### Milestone 2 — Validate Real Transport Victoria Feeds

Prove that real GTFS static and GTFS-Realtime metro train data can be accessed, saved, parsed, and validated locally. Harden authentication handling, generate validation reports, and confirm raw protobuf files and parsed CSV outputs are produced successfully.

### Milestone 3 — GTFS Static Modelling & Stop-to-SA2 Mapping

Use GTFS static stop coordinates and ABS SA2 boundary data to create a reliable stop-to-SA2 lookup table. This milestone creates the bridge between transport data and equity/geographic analysis.

### Milestone 4 — Local Warehouse-Ready Datasets & Raw Load Design

Standardise processed GTFS static, GTFS-Realtime, service alert, and stop-to-SA2 outputs into stable warehouse-loadable datasets. Align processed schemas with raw Redshift table definitions and add row-count/data-quality reconciliation.

### Milestone 5 — Redshift + dbt Foundation

Set up the minimum cloud warehouse workflow: S3 raw/processed storage, Redshift raw schemas, COPY loading, dbt source definitions, staging models, dbt tests, and dbt documentation.

### Milestone 6 — Disruption Exposure, Equity Scoring & Portfolio Delivery

Create final analytics models combining transport disruption observations with geographic and equity context. Build the final disruption equity score, insight queries, dashboard/reporting screenshots, polished README, architecture docs, and resume-ready project story.

## Label Taxonomy

### Work Type

- `type: ingestion`
- `type: dbt`
- `type: docs`
- `type: data-quality`
- `type: geospatial`
- `type: aws`
- `type: analytics`
- `type: testing`
- `type: config`
- `type: portfolio`

### Priority

- `priority: high`
- `priority: medium`
- `priority: low`

### Status

- `status: blocked`
- `status: needs-review`
- `status: ready`

### Milestone Tracking Labels

- `milestone: m1`
- `milestone: m2`
- `milestone: m3`
- `milestone: m4`
- `milestone: m5`
- `milestone: m6`

## Issues by Milestone

### Milestone 1

- Set up local-first repository structure
- Add README and project scope documentation
- Create `.env.example` and settings config
- Build GTFS static ingestion script
- Build GTFS-Realtime fetch script
- Build GTFS-Realtime parser script
- Add SQL raw table scaffold
- Add dbt project skeleton
- Add basic pytest coverage
- Review and patch reliability issues in Milestone 1 scaffold

> Milestone 1 issues include: `Current status: likely completed; verify and close after review.`

### Milestone 2

- Add real Transport Victoria GTFS static and GTFS-R URLs to config
- Support configurable API authentication modes
- Improve HTTP diagnostics for realtime feed failures
- Add metadata sidecar files for downloaded GTFS-R snapshots
- Build `validate_transport_feeds.py` smoke test script
- Improve parser handling for missing and empty GTFS-R fields
- Add tests for auth construction and metadata output
- Document Transport Victoria feed access notes
- Run and document first successful local feed validation

### Milestone 3

- Add ABS SA2 boundary data source documentation
- Create SA2 boundary ingestion script
- Build stop-to-SA2 GeoPandas mapping script
- Generate `processed/stop_area_mapping.csv`
- Add mapping coverage report
- Create route-to-SA2 coverage logic from stops and trips
- Add tests for mapping output schema
- Document geospatial assumptions and limitations

### Milestone 4

- Standardise processed GTFS static output schemas
- Standardise parsed Trip Updates output schema
- Standardise parsed Service Alerts output schema
- Add ingestion run metadata tracking
- Add row-count reconciliation checks
- Update Redshift raw DDLs for final processed schemas
- Add local data quality checks for parsed outputs
- Document local-to-warehouse load assumptions

### Milestone 5

- Create S3 bucket structure documentation
- Create Redshift schemas and raw tables
- Build local-to-S3 upload script
- Build Redshift COPY load script
- Configure dbt-redshift profile
- Create dbt source definitions
- Build staging models for GTFS static tables
- Build staging models for GTFS-R trip updates and service alerts
- Add dbt generic tests
- Generate first dbt docs and lineage screenshots

### Milestone 6

- Build intermediate trip delay event model
- Build intermediate service alert event model
- Build route daily disruption model
- Build SA2 disruption exposure model
- Integrate SEIFA/equity dataset
- Define transparent disruption equity scoring formula
- Build final `mart_transport_disruption_equity_score`
- Add dbt tests for final marts
- Create insight SQL queries
- Build dashboard or reporting screenshots
- Write final README project story
- Add architecture and dbt lineage screenshots
- Write resume bullets and interview explanation

## Scripted Setup

Run from repo root:

```bash
bash scripts/create_github_roadmap.sh
```

The script:

- checks `gh` installation and authentication
- creates labels if missing
- creates milestones if missing
- creates issues with milestone assignment and labels
- performs a best-effort duplicate check by exact issue title

## Closing Milestone 1 Issues After Verification

1. Review each Milestone 1 issue against actual repository state.
2. Confirm output exists and is usable (code/docs/tests).
3. Add verification comments/evidence links in each issue.
4. Close only verified issues; keep any gaps open with follow-up tasks.

## Notes and Limitations

- Duplicate prevention is best-effort based on exact issue title matching.
- If titles are changed manually, rerunning the script may create similarly scoped duplicates.
- Keep all roadmap changes auditable via issue history and milestone progress.
