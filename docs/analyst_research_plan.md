# Analyst research plan — Milestone 7

## Business / public policy problem

Melbourne metro train passengers do not experience service disruption equally. Some SA2 areas may combine higher **observed** delay and alert exposure with greater socio-economic disadvantage and different network coverage. Transport agencies and community stakeholders need **transparent, place-based evidence** to prioritise monitoring — not opaque scores or single-snapshot anecdotes.

## Target audience

- Transport planners and analysts evaluating disruption patterns
- Portfolio reviewers (Data Engineer / Data Analyst roles)
- Community advocates seeking auditable equity framing

## Decision questions

1. Which SA2 areas should be **prioritised for monitoring** based on repeated disruption-equity impact?
2. Does **SEIFA disadvantage** overlap with higher disruption exposure in observed GTFS-R data?
3. Which **routes** contribute most to high-impact SA2 exposure?
4. Are disruption patterns **concentrated in particular hours** (peak vs off-peak)?
5. Is the current **data coverage sufficient** for evidence-grade conclusions?

## Research questions

1. Which Melbourne SA2 areas repeatedly experience the highest transport disruption equity impact?
2. Do more disadvantaged SA2 areas show higher disruption exposure than less disadvantaged areas?
3. Which routes contribute most to high-impact SA2 areas?
4. Are disruption patterns concentrated in particular hours of the day?
5. Which areas should be prioritised for monitoring based on observed disruption exposure and SEIFA disadvantage?

## Hypotheses

| ID | Hypothesis |
|----|------------|
| H1 | Some SA2s repeatedly appear in high-impact rankings across multiple snapshots. |
| H2 | Lower SEIFA deciles show higher average equity impact than higher SEIFA deciles. |
| H3 | A small number of routes contribute disproportionately to high-impact SA2 exposure. |
| H4 | Peak periods have higher disruption exposure than off-peak periods. |

## Required data coverage

| Threshold | Days | Rating | Use |
|-----------|------|--------|-----|
| Minimum useful | 7 | analyst-ready | Cautious portfolio conclusions |
| Better | 14 | strong (entry) | Multi-day pattern comparison |
| Strong | 30 | strong | Robust temporal claims |

**Collection frequency:** every **15 minutes** during active collection windows.

**Peak coverage:** at least **morning (07:00–09:59)** and **evening (16:00–18:59)** windows represented across weekdays.

## Metrics

- `equity_impact_score` (v1 transparent weighted proxy)
- `delay_observation_rate`, `disruption_score`, `disadvantage_weight`
- Recurrence: `high_or_above_snapshot_rate` across days
- Route contribution counts to high-impact SA2s
- Hourly average equity impact and delay rate

Full formula: `docs/transport_disruption_equity_scoring.md`.

## Definition of “enough data”

Analyst report may be labelled **evidence-ready** only when:

- ≥ **7 distinct calendar days** of GTFS-R snapshots
- ≥ **4 snapshots per day** on average (15-minute cadence over a meaningful window)
- Both **trip_updates** and **service_alerts** feeds represented
- Morning and evening peak hours observed on ≥ **3 weekdays**

Below this threshold, outputs are **exploratory only** — charts and report must state limited coverage explicitly.

## Limitations (always apply)

- GTFS-R snapshots are **observations**, not official PTV reliability records
- Snapshot frequency and API availability affect observed counts
- Stop-to-SA2 mapping is spatial exposure, not ridership
- SEIFA is area-level, not individual-level disadvantage
- Scoring weights are transparent but subjective
- Single-operator metro trains MVP; not full multimodal network

## Analytical workflow

1. Collect multi-day GTFS-R snapshots (`collect_gtfs_realtime_snapshots.py`)
2. Audit coverage (`audit_gtfsr_snapshot_coverage.py`)
3. Refresh warehouse-ready + optional Redshift + dbt
4. Export analyst queries + visuals + report
5. Label conclusions by sufficiency rating
