# Transport Disruption Equity Scoring (v1)

## Objective

Combine observed public transport disruption exposure (GTFS-Realtime trip delays and service alerts), SA2 geography, and SEIFA 2021 disadvantage into a **transparent analytical proxy** for portfolio and planning discussions.

This is **not** an official government reliability or equity metric.

## Grain

Final mart `mart_transport_disruption_equity_score`:

- `snapshot_date`
- `snapshot_hour`
- `sa2_code`

## Data sources

| Layer | Models |
|-------|--------|
| Raw | `raw_data.raw_gtfs_trip_updates`, `raw_gtfs_service_alerts`, `raw_stops_sa2_mapping`, `raw_route_sa2_coverage`, `raw_seifa_sa2` |
| Staging | `stg_gtfs_*`, `stg_stops_sa2_mapping`, `stg_route_sa2_coverage`, `stg_seifa_sa2` |
| Intermediate | `int_trip_delay_events`, `int_service_alert_events`, `int_sa2_disruption_exposure`, `int_sa2_equity_context`, `int_transport_equity_score_components` |
| Marts | `mart_transport_disruption_equity_score` |

## Delay logic (`int_trip_delay_events`)

- **Delayed (5 min):** `arrival_delay_seconds > 300` OR `departure_delay_seconds > 300`
- Missing delay values are **not** treated as delayed
- **Severity bands** (based on max of arrival/departure delay):
  - `early_or_on_time`: ≤ 300 seconds or null
  - `minor_delay`: > 300 and ≤ 600
  - `moderate_delay`: > 600 and ≤ 1200
  - `major_delay`: > 1200

## Service alert logic (`int_service_alert_events`)

`is_disruption_alert = true` when `effect` is one of:

`NO_SERVICE`, `REDUCED_SERVICE`, `SIGNIFICANT_DELAYS`, `DETOUR`, `MODIFIED_SERVICE`, `STOP_MOVED`, `OTHER_EFFECT`

## Disadvantage weight (`int_sa2_equity_context`)

1. If `irsd_decile` present: `(11 - irsd_decile) / 10` (lower decile → higher weight)
2. Else if `irsd_percentile` present: `(100 - irsd_percentile) / 100`
3. Else if `irsd_score` present: `1 - PERCENT_RANK()` over ascending score
4. Else: `0.5` (documented limitation)

## Component scores (0–100, min-max scaled within snapshot dataset)

| Component | Definition |
|-----------|------------|
| `delay_frequency_score` | Scaled `delay_observation_rate` |
| `delay_severity_score` | Scaled blend of avg and max delay seconds |
| `alert_exposure_score` | Scaled disruption alert count |
| `disruption_score` | `0.5 × delay_frequency + 0.3 × delay_severity + 0.2 × alert_exposure` |
| `disadvantage_score` | `disadvantage_weight × 100` |
| `network_exposure_score` | Min-max scaled route + stop count proxy |

## Final equity impact score

```
equity_impact_score = disruption_score × (0.6 + 0.4 × disadvantage_weight)
```

- `score_formula_version = 'v1_transparent_weighted_proxy'`

## Risk bands

| Band | Score |
|------|-------|
| `very_high` | ≥ 80 |
| `high` | ≥ 60 |
| `moderate` | ≥ 40 |
| `low` | ≥ 20 |
| `minimal` | < 20 |

## Known limitations

- GTFS-R rows are **snapshot observations**, not complete operational history
- Snapshot cadence affects observed counts
- Stop-to-SA2 mapping is spatial exposure, not ridership or trip purpose
- SEIFA is area-level; does not measure individual transport dependency
- Route/stop counts proxy network access, not actual usage
- Scoring weights are explicit but subjective — intended for transparent discussion, not policy certification

## Interpretation guidance

Use results to **prioritise SA2 areas for further investigation**, not to assert official service failure. Compare relative rankings within the loaded snapshot window and document snapshot timestamps when presenting findings.
