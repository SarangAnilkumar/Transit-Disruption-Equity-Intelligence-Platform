# Milestone 6 insights

Insight SQL lives in `dbt_transit_equity/analyses/`. Export small summary CSVs with:

```bash
set -a && source .env && set +a
python ingestion/export_milestone_6_insights.py
```

Outputs under `docs/insights/`:

| File | Question |
|------|----------|
| `top_equity_impact_sa2s.csv` | Which SA2 areas rank highest on equity impact? |
| `route_disruption_summary.csv` | Which routes show highest delay/alert exposure? |
| `seifa_vs_disruption_summary.csv` | How does SEIFA disadvantage overlap with disruption scores? |
| `hourly_disruption_pattern.csv` | Which hours show highest exposure? |
| `milestone_6_insight_summary.md` | Export metadata and interpretation notes |

Scoring methodology: `docs/transport_disruption_equity_scoring.md`.

Evidence screenshots: `docs/assets/milestone_6/`.

## Key insights (loaded snapshot window)

From exported CSVs (see `milestone_6_insight_summary.md` for timestamp):

- Highest equity-impact SA2s in the loaded GTFS-R window include Bayswater, Ferntree Gully North, and St Albans North/South — all **moderate** risk band in v1; no SA2 reached `very_high` in this single-snapshot dataset.
- SEIFA deciles 1–3 show higher average equity impact than deciles 8–10 in the loaded window (`seifa_vs_disruption_summary.csv`).
- Hourly pattern export has one snapshot hour — multi-hour ingestion would strengthen temporal analysis.

Scores are transparent proxies from sampled GTFS-R observations, not official KPIs.
