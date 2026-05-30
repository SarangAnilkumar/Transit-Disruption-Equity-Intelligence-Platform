# Public transport disruption equity — analyst report

**Report status:** EXPLORATORY (limited GTFS-R snapshot coverage)

> See `docs/insights/gtfsr_snapshot_coverage_report.md` for current sufficiency rating. This report uses transparent v1 scoring on **observed GTFS-R snapshots**, not official PTV reliability statistics.

## 1. Executive summary

This analysis combines Transport Victoria GTFS-Realtime trip update observations, service alerts, ABS SA2 geography, and SEIFA 2021 disadvantage indicators to identify SA2 areas where **observed disruption exposure** overlaps with **relative socio-economic disadvantage**.

With the current snapshot window, findings are **directional and exploratory**. They support **monitoring prioritisation hypotheses**, not operational or policy conclusions.

## 2. Problem statement

Disruption burden is unlikely to be uniform across Melbourne. Areas with higher disadvantage may face compounding access constraints when observed delays and alerts cluster on routes serving those SA2s. Stakeholders need auditable, place-based metrics — not network-wide averages alone.

## 3. Data coverage

| Item | Current state |
|------|----------------|
| GTFS-R snapshots | See coverage report |
| Sufficiency rating | `exploratory` or below until ≥7 days collected |
| Trip updates + alerts | Both feeds required |
| SEIFA | SA2-level IRSD decile |
| Geography | Stop-to-SA2 spatial mapping |

**Minimum for evidence-grade reporting:** 7+ days, 15-minute cadence, peak windows covered.

## 4. Methodology

1. Collect GTFS-R snapshots locally (`collect_gtfs_realtime_snapshots.py`)
2. Map stops to SA2; join SEIFA context
3. Build dbt intermediate event models (delays, alerts)
4. Aggregate to SA2/date/hour exposure
5. Apply transparent v1 equity impact score
6. Compare across SEIFA deciles, routes, and hours

Full formula: `docs/transport_disruption_equity_scoring.md`

## 5. Metrics and scoring formula

- **Delay flag:** arrival or departure delay > 300 seconds
- **Disruption score:** weighted blend of delay frequency, severity, alert exposure
- **Equity impact score:** `disruption_score × (0.6 + 0.4 × disadvantage_weight)`
- **Risk bands:** very_high / high / moderate / low / minimal

## 6. Key findings (current loaded window)

Refer to exported data in `docs/analyst_report/data/` and figures in `docs/analyst_report/figures/`.

**H1 (recurring high-impact SA2s):** In the current window, certain outer-east and western SA2s rank highest on average equity impact — treat as **candidate monitoring areas**, not confirmed chronic hotspots.

**H2 (SEIFA overlap):** Lower IRSD deciles tend to show higher average equity impact in the loaded snapshot; effect size should be re-tested with ≥7 days.

**H3 (route concentration):** A subset of routes accounts for a large share of delayed observations in high-impact SA2s — route-level follow-up warranted.

**H4 (hourly pattern):** With only one snapshot hour in the current load, peak/off-peak comparison is **not yet valid**. Multi-day collection required.

## 7. Visual evidence

| Figure | Description |
|--------|-------------|
| `01_top_recurring_high_impact_sa2s.png` | Top SA2s by average equity impact |
| `02_seifa_decile_vs_disruption.png` | IRSD decile vs impact and delay rate |
| `03_hourly_disruption_pattern.png` | Hourly pattern (limited until multi-hour data) |
| `04_route_contribution_to_high_impact_areas.png` | Routes in high-impact SA2s |

## 8. Recommendations

1. **Continue GTFS-R collection** for at least 7 weekdays at 15-minute intervals.
2. **Prioritise monitoring** (not intervention) for recurring high-impact SA2 candidates.
3. **Investigate contributing routes** in high-impact areas before service planning conclusions.
4. **Compare against official PTV reliability reports** when extending beyond portfolio scope.
5. **Re-run marts and this report** after sufficiency reaches `analyst-ready`.

## 9. Limitations

- Snapshot observations ≠ complete operational history
- Spatial mapping ≠ ridership or dependency
- SEIFA is area-level
- Scoring weights are explicit but subjective
- Single-mode metro trains MVP

## 10. Future work

- 14–30 day collection window
- Peak/off-peak validation (H4)
- Sensitivity analysis on scoring weights
- Optional SA2 choropleth map when multi-day data is strong
- Comparison to official monthly reliability benchmarks
