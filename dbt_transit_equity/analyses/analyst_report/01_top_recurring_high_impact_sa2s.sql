-- Analytical question: Which SA2 areas repeatedly rank highest on equity impact?
-- Source mart: mart_sa2_multi_day_equity_summary
-- Limitation: Requires multi-day snapshots; single-day data is exploratory only.
select
    sa2_code,
    sa2_name,
    irsd_decile,
    days_observed,
    avg_equity_impact_score,
    max_equity_impact_score,
    high_or_above_snapshot_rate,
    avg_delay_observation_rate,
    peak_equity_risk_band
from {{ ref('mart_sa2_multi_day_equity_summary') }}
order by avg_equity_impact_score desc nulls last, max_equity_impact_score desc nulls last
limit 25
