-- Which routes show the highest delay/disruption exposure?
select
    route_id,
    route_short_name,
    route_long_name,
    sum(observed_trip_update_rows) as total_observations,
    sum(delayed_observation_count) as total_delayed_observations,
    round(
        sum(delayed_observation_count)::decimal(18, 6)
        / nullif(sum(observed_trip_update_rows), 0)::decimal(18, 6) * 100,
        2
    ) as delay_rate_pct,
    sum(disruption_alert_count) as total_disruption_alerts,
    max(max_delay_seconds) as peak_delay_seconds
from {{ ref('mart_route_disruption_summary') }}
group by 1, 2, 3
order by total_delayed_observations desc nulls last
limit 25
