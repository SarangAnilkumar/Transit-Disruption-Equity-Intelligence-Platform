with trip_delays as (
    select * from {{ ref('int_trip_delay_events') }}
),

alert_events as (
    select * from {{ ref('int_service_alert_events') }}
),

routes as (
    select * from {{ ref('stg_gtfs_routes') }}
),

trip_daily as (
    select
        snapshot_date as service_date,
        route_id,
        count(*) as observed_trip_update_rows,
        count(distinct trip_id) as distinct_trip_count,
        count(distinct stop_id) as distinct_stop_count,
        sum(case when is_delayed_5min then 1 else 0 end) as delayed_observation_count,
        avg(arrival_delay_seconds::decimal(18, 4)) as avg_arrival_delay_seconds,
        avg(departure_delay_seconds::decimal(18, 4)) as avg_departure_delay_seconds,
        max(max_delay_seconds) as max_delay_seconds,
        sum(case when delay_severity_band = 'major_delay' then 1 else 0 end) as major_delay_count
    from trip_delays
    where route_id is not null
    group by 1, 2
),

alert_daily as (
    select
        snapshot_date as service_date,
        informed_route_id as route_id,
        count(*) as service_alert_count,
        sum(case when is_disruption_alert then 1 else 0 end) as disruption_alert_count
    from alert_events
    where informed_route_id is not null
    group by 1, 2
),

combined as (
    select
        coalesce(td.service_date, ad.service_date) as service_date,
        coalesce(td.route_id, ad.route_id) as route_id,
        coalesce(td.observed_trip_update_rows, 0) as observed_trip_update_rows,
        coalesce(td.distinct_trip_count, 0) as distinct_trip_count,
        coalesce(td.distinct_stop_count, 0) as distinct_stop_count,
        coalesce(td.delayed_observation_count, 0) as delayed_observation_count,
        case
            when coalesce(td.observed_trip_update_rows, 0) = 0 then null
            else td.delayed_observation_count::decimal(18, 6)
                / td.observed_trip_update_rows::decimal(18, 6)
        end as delay_observation_rate,
        td.avg_arrival_delay_seconds,
        td.avg_departure_delay_seconds,
        td.max_delay_seconds,
        coalesce(td.major_delay_count, 0) as major_delay_count,
        coalesce(ad.service_alert_count, 0) as service_alert_count,
        coalesce(ad.disruption_alert_count, 0) as disruption_alert_count
    from trip_daily as td
    full outer join alert_daily as ad
        on td.service_date = ad.service_date
        and td.route_id = ad.route_id
)

select
    c.service_date,
    c.route_id,
    c.observed_trip_update_rows,
    c.distinct_trip_count,
    c.distinct_stop_count,
    c.delayed_observation_count,
    c.delay_observation_rate,
    c.avg_arrival_delay_seconds,
    c.avg_departure_delay_seconds,
    c.max_delay_seconds,
    c.major_delay_count,
    c.service_alert_count,
    c.disruption_alert_count,
    r.route_short_name,
    r.route_long_name,
    r.route_type
from combined as c
left join routes as r on c.route_id = r.route_id
