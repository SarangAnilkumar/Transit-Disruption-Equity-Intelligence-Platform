-- Analytical question: Are disruption patterns concentrated in particular hours?
-- Source mart: mart_hourly_disruption_pattern
-- Hypothesis H4: peak periods show higher exposure than off-peak.
select
    snapshot_hour,
    peak_period_flag,
    observed_sa2_count,
    avg_delay_observation_rate,
    avg_equity_impact_score,
    total_delayed_observations
from {{ ref('mart_hourly_disruption_pattern') }}
order by snapshot_hour
