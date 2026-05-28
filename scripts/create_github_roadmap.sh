#!/usr/bin/env bash

set -euo pipefail

# Create GitHub labels, milestones, and issues for the Transit Disruption Equity Intelligence Platform.
# Safe to run multiple times: it checks for existing entities before creating new ones.

REPO_SLUG=""

log() {
  printf '[roadmap] %s\n' "$1"
}

warn() {
  printf '[roadmap][warn] %s\n' "$1" >&2
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    warn "Missing required command: $1"
    exit 1
  fi
}

detect_repo_slug() {
  if ! REPO_SLUG="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)"; then
    warn "Unable to detect GitHub repository from current directory."
    warn "Run this script from a git repo connected to GitHub and with gh authenticated."
    exit 1
  fi
}

ensure_gh_auth() {
  if ! gh auth status >/dev/null 2>&1; then
    warn "GitHub CLI is not authenticated. Run: gh auth login -h github.com"
    exit 1
  fi
}

label_exists() {
  local name="$1"
  local existing
  existing="$(gh label list --limit 500 --json name --jq ".[] | select(.name == \"$name\") | .name" || true)"
  [ -n "$existing" ]
}

create_label_if_missing() {
  local name="$1"
  local color="$2"
  local description="$3"
  if label_exists "$name"; then
    log "Label exists: $name"
    return 0
  fi
  gh label create "$name" --color "$color" --description "$description"
  log "Created label: $name"
}

milestone_number_by_title() {
  local title="$1"
  gh api "repos/$REPO_SLUG/milestones?state=all&per_page=100" \
    --jq ".[] | select(.title == \"$title\") | .number" | head -n 1
}

create_milestone_if_missing() {
  local title="$1"
  local description="$2"
  local number
  number="$(milestone_number_by_title "$title" || true)"
  if [ -n "$number" ]; then
    log "Milestone exists: $title (#$number)"
    return 0
  fi
  gh api "repos/$REPO_SLUG/milestones" \
    --method POST \
    -f title="$title" \
    -f description="$description" >/dev/null
  log "Created milestone: $title"
}

issue_exists_by_title() {
  local title="$1"
  local existing
  existing="$(gh issue list --state all --limit 200 --search "\"$title\" in:title" --json title \
    --jq ".[] | select(.title == \"$title\") | .title" || true)"
  [ -n "$existing" ]
}

issue_body() {
  local goal="$1"
  local notes="$2"
  local m1_status="$3"
  cat <<EOF
## Goal

$goal

## Tasks

* [ ] Review current project state and identify required updates.
* [ ] Implement or refine code/docs/tests needed for this outcome.
* [ ] Validate outputs and document any follow-up actions.

## Acceptance Criteria

* [ ] Clear measurable output produced and saved in-repo where relevant.
* [ ] Tests/docs updated where relevant.
* [ ] No secrets or raw data committed.

## Notes

$notes
EOF
  if [ "$m1_status" = "yes" ]; then
    cat <<EOF

Current status: likely completed; verify and close after review.
EOF
  fi
}

create_issue_if_missing() {
  local milestone_title="$1"
  local title="$2"
  local labels_csv="$3"
  local goal="$4"
  local notes="$5"
  local m1_status="$6"

  if issue_exists_by_title "$title"; then
    log "Issue exists: $title"
    return 0
  fi

  local body
  body="$(issue_body "$goal" "$notes" "$m1_status")"

  gh issue create \
    --title "$title" \
    --milestone "$milestone_title" \
    --label "$labels_csv" \
    --body "$body" >/dev/null

  log "Created issue: $title"
}

main() {
  require_cmd gh
  ensure_gh_auth
  detect_repo_slug
  log "Using repository: $REPO_SLUG"

  # name|color|description
  LABELS=$(cat <<'EOF'
type: ingestion|0E8A16|Data ingestion pipelines and connectors
type: dbt|5319E7|dbt models, tests, and documentation
type: docs|0052CC|Documentation and project communication
type: data-quality|1D76DB|Validation, reconciliation, and quality checks
type: geospatial|006B75|Geospatial processing and mapping work
type: aws|D97706|AWS, S3, and Redshift related work
type: analytics|1F883D|Analytical modelling and insights
type: testing|B60205|Automated and manual testing work
type: config|6E7781|Configuration and project setup
type: portfolio|7A3E9D|Portfolio polish and recruiter-facing assets
priority: high|B60205|High-priority work
priority: medium|D97706|Medium-priority work
priority: low|0E8A16|Low-priority work
status: blocked|8B1A10|Blocked by dependency or external factor
status: needs-review|FBCA04|Requires review before completion
status: ready|0E8A16|Ready to start
milestone: m1|C2E0C6|Tracks Milestone 1 issues
milestone: m2|C5DEF5|Tracks Milestone 2 issues
milestone: m3|D8C2F2|Tracks Milestone 3 issues
milestone: m4|F8D2C4|Tracks Milestone 4 issues
milestone: m5|FCE8B2|Tracks Milestone 5 issues
milestone: m6|F9E2D2|Tracks Milestone 6 issues
EOF
)

  while IFS='|' read -r name color description; do
    [ -z "$name" ] && continue
    create_label_if_missing "$name" "$color" "$description"
  done <<EOF
$LABELS
EOF

  # key|title|description
  MILESTONES=$(cat <<'EOF'
m1|Milestone 1 — Local Project Scaffold & Data Feasibility Foundation|Create the local-first project structure and prove the repo can support ingestion, parsing, tests, documentation, SQL scaffolding, and dbt scaffolding. Scripts should fail gracefully when URLs or API keys are missing. No real cloud infrastructure is required in this milestone.
m2|Milestone 2 — Validate Real Transport Victoria Feeds|Prove that real GTFS static and GTFS-Realtime metro train data can be accessed, saved, parsed, and validated locally. Harden authentication handling, generate validation reports, and confirm raw protobuf files and parsed CSV outputs are produced successfully.
m3|Milestone 3 — GTFS Static Modelling & Stop-to-SA2 Mapping|Use GTFS static stop coordinates and ABS SA2 boundary data to create a reliable stop-to-SA2 lookup table. This milestone creates the bridge between transport data and equity/geographic analysis.
m4|Milestone 4 — Local Warehouse-Ready Datasets & Raw Load Design|Standardise processed GTFS static, GTFS-Realtime, service alert, and stop-to-SA2 outputs into stable warehouse-loadable datasets. Align processed schemas with raw Redshift table definitions and add row-count/data-quality reconciliation.
m5|Milestone 5 — Redshift + dbt Foundation|Set up the minimum cloud warehouse workflow: S3 raw/processed storage, Redshift raw schemas, COPY loading, dbt source definitions, staging models, dbt tests, and dbt documentation.
m6|Milestone 6 — Disruption Exposure, Equity Scoring & Portfolio Delivery|Create final analytics models combining transport disruption observations with geographic and equity context. Build the final disruption equity score, insight queries, dashboard/reporting screenshots, polished README, architecture docs, and resume-ready project story.
EOF
)

  while IFS='|' read -r _key title description; do
    [ -z "$title" ] && continue
    create_milestone_if_missing "$title" "$description"
  done <<EOF
$MILESTONES
EOF

  # milestone_key|title|labels_csv|goal|notes|m1_status
  ISSUES=$(cat <<'EOF'
m1|Set up local-first repository structure|type: config,type: docs,priority: high,milestone: m1|Establish a reliable local-first project scaffold for ingestion, transformation, testing, and documentation workflows.|Focus on folder conventions, script entry points, and setup instructions so contributors can run locally with minimal friction.|yes
m1|Add README and project scope documentation|type: docs,priority: high,milestone: m1|Document project scope, architecture intent, and execution flow in a recruiter-friendly format.|Ensure README and scope docs reflect actual implemented components and constraints.|yes
m1|Create .env.example and settings config|type: config,priority: high,milestone: m1|Provide a safe, reproducible configuration baseline for local runs without exposing secrets.|Document required variables, defaults, and failure behavior when credentials are absent.|yes
m1|Build GTFS static ingestion script|type: ingestion,priority: high,milestone: m1|Implement ingestion workflow for GTFS static feed retrieval and local persistence.|Include graceful handling for missing URLs or inaccessible sources.|yes
m1|Build GTFS-Realtime fetch script|type: ingestion,priority: high,milestone: m1|Implement GTFS-Realtime snapshot retrieval process for local raw data capture.|Capture outputs in a consistent folder structure to support downstream parsing.|yes
m1|Build GTFS-Realtime parser script|type: ingestion,priority: high,milestone: m1|Parse GTFS-Realtime protobuf snapshots into structured outputs for analytics preparation.|Handle common missing/optional fields robustly and document assumptions.|yes
m1|Add SQL raw table scaffold|type: aws,type: analytics,priority: medium,milestone: m1|Add initial SQL scaffold for raw-layer tables aligned with ingestion outputs.|Keep definitions warehouse-ready without requiring active cloud infrastructure.|yes
m1|Add dbt project skeleton|type: dbt,priority: medium,milestone: m1|Bootstrap dbt project structure to support future source/staging/mart modelling.|Include baseline project files and folder conventions.|yes
m1|Add basic pytest coverage|type: testing,priority: medium,milestone: m1|Add foundational test coverage for critical scripts and expected output contracts.|Prioritize smoke tests that improve confidence in local workflows.|yes
m1|Review and patch reliability issues in Milestone 1 scaffold|type: testing,type: config,status: needs-review,priority: medium,milestone: m1|Assess Milestone 1 artifacts for reliability gaps and patch any fragile behavior.|Focus on error handling, configuration defaults, and repeatability.|yes
m2|Add real Transport Victoria GTFS static and GTFS-R URLs to config|type: config,type: ingestion,priority: high,milestone: m2|Configure real Transport Victoria feed endpoints for static and realtime ingestion workflows.|Keep secrets externalized and avoid committing sensitive tokens.|no
m2|Support configurable API authentication modes|type: ingestion,type: config,priority: high,milestone: m2|Implement flexible auth handling for feeds requiring none, header-based, or key-based auth.|Document auth strategy and configuration switches clearly.|no
m2|Improve HTTP diagnostics for realtime feed failures|type: ingestion,type: testing,priority: high,milestone: m2|Improve visibility into realtime fetch failures through actionable HTTP diagnostics.|Capture status codes, retry context, and failure reason details.|no
m2|Add metadata sidecar files for downloaded GTFS-R snapshots|type: ingestion,type: data-quality,priority: medium,milestone: m2|Record metadata alongside each snapshot to improve traceability and auditability.|Include fetch timestamp, source URL identifier, and response summary fields.|no
m2|Build validate_transport_feeds.py smoke test script|type: ingestion,type: testing,priority: high,milestone: m2|Create a smoke-test script validating accessibility and parse readiness of configured feeds.|Script should be easy to run locally and produce clear pass/fail reporting.|no
m2|Improve parser handling for missing and empty GTFS-R fields|type: ingestion,type: data-quality,priority: high,milestone: m2|Harden parser behavior for sparse GTFS-R payloads without losing integrity.|Ensure outputs remain schema-consistent even with partial source records.|no
m2|Add tests for auth construction and metadata output|type: testing,type: config,priority: medium,milestone: m2|Add tests for authentication request construction and metadata sidecar generation.|Cover edge cases for missing configuration and optional auth fields.|no
m2|Document Transport Victoria feed access notes|type: docs,priority: medium,milestone: m2|Document practical access notes for Transport Victoria feeds and local setup expectations.|Include known limitations and troubleshooting guidance for contributors.|no
m2|Run and document first successful local feed validation|type: docs,type: data-quality,status: ready,priority: high,milestone: m2|Run feed validation end-to-end and document the first successful local execution evidence.|Store validation outputs and summarize what was proven locally.|no
m3|Add ABS SA2 boundary data source documentation|type: docs,type: geospatial,priority: high,milestone: m3|Document authoritative ABS SA2 boundary sources, licensing, and download instructions.|Clarify versioning and geography assumptions used in the project.|no
m3|Create SA2 boundary ingestion script|type: ingestion,type: geospatial,priority: high,milestone: m3|Implement ingestion flow for SA2 boundary data suitable for geospatial joins.|Ensure reproducible local download and extraction behavior.|no
m3|Build stop-to-SA2 GeoPandas mapping script|type: geospatial,type: analytics,priority: high,milestone: m3|Create geospatial mapping from GTFS stops to SA2 regions using GeoPandas.|Handle coordinate reference systems and edge cases explicitly.|no
m3|Generate processed/stop_area_mapping.csv|type: geospatial,type: data-quality,priority: high,milestone: m3|Produce the canonical stop-to-SA2 mapping output for downstream analytics.|Validate schema, uniqueness, and coverage before publishing output.|no
m3|Add mapping coverage report|type: geospatial,type: data-quality,priority: medium,milestone: m3|Create coverage reporting for successful and unmatched stop mappings.|Surface data quality insights for iterative geospatial refinement.|no
m3|Create route-to-SA2 coverage logic from stops and trips|type: analytics,type: geospatial,priority: high,milestone: m3|Derive route-level SA2 coverage logic using stop and trip relationships.|Support later disruption exposure calculations by geography.|no
m3|Add tests for mapping output schema|type: testing,type: geospatial,priority: medium,milestone: m3|Add automated tests validating stop-to-SA2 output schema and key constraints.|Ensure required columns and types remain stable across runs.|no
m3|Document geospatial assumptions and limitations|type: docs,type: geospatial,priority: medium,milestone: m3|Document modelling assumptions, spatial limitations, and potential bias risks.|Provide transparency for interpretation and future enhancements.|no
m4|Standardise processed GTFS static output schemas|type: ingestion,type: data-quality,priority: high,milestone: m4|Standardise GTFS static processed outputs into stable, warehouse-ready schemas.|Capture schema definitions and compatibility expectations.|no
m4|Standardise parsed Trip Updates output schema|type: ingestion,type: data-quality,priority: high,milestone: m4|Stabilize parsed Trip Updates output structure for consistent downstream loads.|Address nullability and field naming consistency.|no
m4|Standardise parsed Service Alerts output schema|type: ingestion,type: data-quality,priority: high,milestone: m4|Stabilize parsed Service Alerts output structure for consistent downstream loads.|Define required vs optional fields and serialization approach.|no
m4|Add ingestion run metadata tracking|type: ingestion,type: data-quality,priority: high,milestone: m4|Track run metadata for ingestion jobs to support observability and auditing.|Include run IDs, timestamps, source metadata, and status outcomes.|no
m4|Add row-count reconciliation checks|type: data-quality,type: testing,priority: medium,milestone: m4|Implement row-count reconciliation across pipeline stages to detect anomalies.|Report mismatches clearly with actionable diagnostics.|no
m4|Update Redshift raw DDLs for final processed schemas|type: aws,type: analytics,priority: medium,milestone: m4|Align raw-layer Redshift DDLs with finalized processed schema contracts.|Ensure load compatibility with local-to-warehouse pipeline expectations.|no
m4|Add local data quality checks for parsed outputs|type: data-quality,type: testing,priority: high,milestone: m4|Add local data quality checks that validate parsed output integrity before loading.|Include threshold-based checks where practical.|no
m4|Document local-to-warehouse load assumptions|type: docs,type: aws,priority: medium,milestone: m4|Document assumptions and constraints between local outputs and warehouse ingestion design.|Clarify contracts to reduce integration ambiguity.|no
m5|Create S3 bucket structure documentation|type: docs,type: aws,priority: medium,milestone: m5|Document S3 folder conventions for raw, processed, and metadata datasets.|Ensure naming standards are consistent and maintainable.|no
m5|Create Redshift schemas and raw tables|type: aws,type: analytics,priority: high,milestone: m5|Create baseline Redshift schemas and raw tables aligned to ingestion outputs.|Ensure structures support COPY loading and downstream modelling.|no
m5|Build local-to-S3 upload script|type: ingestion,type: aws,priority: high,milestone: m5|Build script to upload validated local artifacts to S3 in expected folder layout.|Include safe retries and clear logging for failures.|no
m5|Build Redshift COPY load script|type: ingestion,type: aws,priority: high,milestone: m5|Automate Redshift COPY loading from S3 into raw tables.|Ensure robust handling for load errors and schema mismatches.|no
m5|Configure dbt-redshift profile|type: dbt,type: aws,priority: high,milestone: m5|Configure dbt profile for Redshift execution with environment-based credentials.|Keep secrets externalized and profile setup documented.|no
m5|Create dbt source definitions|type: dbt,priority: high,milestone: m5|Define dbt sources for raw ingestion tables with freshness/testing hooks.|Ensure source naming is consistent and traceable.|no
m5|Build staging models for GTFS static tables|type: dbt,type: analytics,priority: high,milestone: m5|Build dbt staging models for GTFS static entities with clean typing and naming.|Prepare data for downstream disruption analytics models.|no
m5|Build staging models for GTFS-R trip updates and service alerts|type: dbt,type: analytics,priority: high,milestone: m5|Build dbt staging models for GTFS-R trip updates and service alert entities.|Standardize timestamps, keys, and event semantics.|no
m5|Add dbt generic tests|type: dbt,type: testing,priority: medium,milestone: m5|Add dbt generic tests for key constraints and basic data quality guarantees.|Prioritize uniqueness, not-null, and accepted-value checks.|no
m5|Generate first dbt docs and lineage screenshots|type: dbt,type: docs,type: portfolio,priority: medium,milestone: m5|Generate first dbt docs site and lineage screenshots for portfolio evidence.|Capture artifacts clearly for README and recruiter review.|no
m6|Build intermediate trip delay event model|type: dbt,type: analytics,priority: high,milestone: m6|Create intermediate model representing trip delay events from GTFS-R signals.|Normalize event granularity for consistent downstream aggregation.|no
m6|Build intermediate service alert event model|type: dbt,type: analytics,priority: high,milestone: m6|Create intermediate model representing service alert events for analysis readiness.|Standardize alert status and affected service dimensions.|no
m6|Build route daily disruption model|type: dbt,type: analytics,priority: high,milestone: m6|Build route-level daily disruption model combining delay and alert signals.|Support trend and comparative analysis over time.|no
m6|Build SA2 disruption exposure model|type: dbt,type: analytics,type: geospatial,priority: high,milestone: m6|Build SA2-level disruption exposure model linked to mapped stops/routes.|Enable geography-based equity analysis.|no
m6|Integrate SEIFA/equity dataset|type: ingestion,type: analytics,priority: high,milestone: m6|Integrate equity context dataset (e.g., SEIFA) into modelling pipeline.|Document source lineage, licensing, and transformation logic.|no
m6|Define transparent disruption equity scoring formula|type: analytics,type: docs,priority: high,milestone: m6|Define a transparent, explainable scoring formula for disruption equity outcomes.|Document weighting rationale and interpretation guardrails.|no
m6|Build final mart_transport_disruption_equity_score|type: dbt,type: analytics,priority: high,milestone: m6|Build final mart model publishing disruption equity score outputs.|Ensure model is reproducible, documented, and query-ready.|no
m6|Add dbt tests for final marts|type: dbt,type: testing,priority: medium,milestone: m6|Add tests covering final marts to enforce quality and contract stability.|Include tests for keys, ranges, and nullability as appropriate.|no
m6|Create insight SQL queries|type: analytics,type: portfolio,priority: medium,milestone: m6|Create curated SQL queries demonstrating key project insights for stakeholders.|Queries should be readable, reproducible, and interview-ready.|no
m6|Build dashboard or reporting screenshots|type: analytics,type: portfolio,priority: medium,milestone: m6|Create dashboard/reporting screenshots that communicate disruption equity findings.|Produce polished visuals suitable for portfolio presentation.|no
m6|Write final README project story|type: docs,type: portfolio,priority: high,milestone: m6|Write final README narrative that explains scope, methods, outputs, and impact.|Ensure story is clear, credible, and recruiter-friendly.|no
m6|Add architecture and dbt lineage screenshots|type: docs,type: portfolio,priority: medium,milestone: m6|Add architecture and dbt lineage visuals to support technical communication.|Ensure artifacts are current and referenced from docs.|no
m6|Write resume bullets and interview explanation|type: docs,type: portfolio,priority: medium,milestone: m6|Draft resume bullets and interview talking points grounded in real project outputs.|Keep claims factual and aligned with repository evidence.|no
EOF
)

  while IFS='|' read -r milestone_key title labels goal notes m1_status; do
    [ -z "$title" ] && continue
    milestone_title="$(printf '%s\n' "$MILESTONES" | awk -F'|' -v key="$milestone_key" '$1 == key { print $2; exit }')"
    create_issue_if_missing "$milestone_title" "$title" "$labels" "$goal" "$notes" "$m1_status"
  done <<EOF
$ISSUES
EOF

  log "Roadmap creation finished."
  log "Note: duplicate checks are best-effort exact-title checks."
}

main "$@"
