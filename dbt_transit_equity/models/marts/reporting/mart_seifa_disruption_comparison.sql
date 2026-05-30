select
    irsd_decile,
    count(distinct sa2_code) as sa2_count,
    avg(equity_impact_score) as avg_equity_impact_score,
    avg(disruption_score) as avg_disruption_score,
    avg(delay_observation_rate) as avg_delay_observation_rate,
    sum(observation_count) as total_observations,
    sum(delayed_observation_count) as total_delayed_observations
from {{ ref('mart_transport_disruption_equity_score') }}
where irsd_decile is not null
group by 1
order by 1
