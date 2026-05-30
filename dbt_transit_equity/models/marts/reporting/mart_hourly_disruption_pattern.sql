select
    snapshot_hour,
    count(distinct sa2_code) as observed_sa2_count,
    avg(delay_observation_rate) as avg_delay_observation_rate,
    avg(equity_impact_score) as avg_equity_impact_score,
    sum(delayed_observation_count) as total_delayed_observations,
    case
        when snapshot_hour between 7 and 9 then 'morning_peak'
        when snapshot_hour between 16 and 18 then 'evening_peak'
        when snapshot_hour between 10 and 15 then 'midday'
        else 'off_peak'
    end as peak_period_flag
from {{ ref('mart_transport_disruption_equity_score') }}
group by 1
