-- Which hours show the highest disruption exposure?
select
    snapshot_hour,
    count(distinct sa2_code) as sa2_count,
    sum(observation_count) as total_observations,
    sum(delayed_observation_count) as total_delayed_observations,
    round(avg(equity_impact_score), 2) as avg_equity_impact_score,
    round(avg(delay_observation_rate) * 100, 2) as avg_delay_rate_pct
from {{ ref('mart_transport_disruption_equity_score') }}
group by 1
order by avg_equity_impact_score desc nulls last
