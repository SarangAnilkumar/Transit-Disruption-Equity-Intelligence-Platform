select
    service_date,
    route_id,
    observed_trip_update_rows,
    distinct_trip_count,
    distinct_stop_count,
    delayed_observation_count,
    delay_observation_rate,
    avg_arrival_delay_seconds,
    avg_departure_delay_seconds,
    max_delay_seconds,
    major_delay_count,
    service_alert_count,
    disruption_alert_count,
    route_short_name,
    route_long_name,
    route_type
from {{ ref('int_route_daily_disruption') }}
