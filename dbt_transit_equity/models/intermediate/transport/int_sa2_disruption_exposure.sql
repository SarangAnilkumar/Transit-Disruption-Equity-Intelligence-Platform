with trip_delays as (
    select * from {{ ref('int_trip_delay_events') }}
    where sa2_code is not null
),

alert_events as (
    select * from {{ ref('int_service_alert_events') }}
    where sa2_code is not null
),

route_coverage as (
    select
        sa2_code,
        count(distinct route_id) as routes_serving_sa2
    from {{ ref('stg_route_sa2_coverage') }}
    group by 1
),

stop_counts as (
    select
        sa2_code,
        count(distinct stop_id) as stops_in_sa2
    from {{ ref('stg_stops_sa2_mapping') }}
    where is_matched = true
    group by 1
),

trip_exposure as (
    select
        snapshot_date,
        snapshot_hour,
        sa2_code,
        max(sa2_name) as sa2_name,
        count(*) as observation_count,
        count(distinct trip_id) as distinct_trip_count,
        count(distinct stop_id) as distinct_stop_count,
        sum(case when is_delayed_5min then 1 else 0 end) as delayed_observation_count,
        avg(arrival_delay_seconds::decimal(18, 4)) as avg_arrival_delay_seconds,
        avg(departure_delay_seconds::decimal(18, 4)) as avg_departure_delay_seconds,
        max(max_delay_seconds) as max_delay_seconds,
        sum(case when delay_severity_band = 'major_delay' then 1 else 0 end) as major_delay_count
    from trip_delays
    group by 1, 2, 3
),

alert_exposure as (
    select
        snapshot_date,
        snapshot_hour,
        sa2_code,
        count(*) as service_alert_count,
        sum(case when is_disruption_alert then 1 else 0 end) as disruption_alert_count
    from alert_events
    group by 1, 2, 3
),

combined as (
    select
        coalesce(te.snapshot_date, ae.snapshot_date) as snapshot_date,
        coalesce(te.snapshot_hour, ae.snapshot_hour) as snapshot_hour,
        coalesce(te.sa2_code, ae.sa2_code) as sa2_code,
        te.sa2_name,
        coalesce(te.observation_count, 0) as observation_count,
        coalesce(te.distinct_trip_count, 0) as distinct_trip_count,
        coalesce(te.distinct_stop_count, 0) as distinct_stop_count,
        coalesce(te.delayed_observation_count, 0) as delayed_observation_count,
        case
            when coalesce(te.observation_count, 0) = 0 then null
            else te.delayed_observation_count::decimal(18, 6)
                / te.observation_count::decimal(18, 6)
        end as delay_observation_rate,
        te.avg_arrival_delay_seconds,
        te.avg_departure_delay_seconds,
        te.max_delay_seconds,
        coalesce(te.major_delay_count, 0) as major_delay_count,
        coalesce(ae.service_alert_count, 0) as service_alert_count,
        coalesce(ae.disruption_alert_count, 0) as disruption_alert_count
    from trip_exposure as te
    full outer join alert_exposure as ae
        on te.snapshot_date = ae.snapshot_date
        and te.snapshot_hour = ae.snapshot_hour
        and te.sa2_code = ae.sa2_code
)

select
    c.snapshot_date,
    c.snapshot_hour,
    c.sa2_code,
    c.sa2_name,
    c.observation_count,
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
    coalesce(rc.routes_serving_sa2, 0) as routes_serving_sa2,
    coalesce(sc.stops_in_sa2, 0) as stops_in_sa2
from combined as c
left join route_coverage as rc on c.sa2_code = rc.sa2_code
left join stop_counts as sc on c.sa2_code = sc.sa2_code
