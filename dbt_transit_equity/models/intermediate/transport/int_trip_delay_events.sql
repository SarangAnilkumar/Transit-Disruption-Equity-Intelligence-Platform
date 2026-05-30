with trip_updates as (
    select * from {{ ref('stg_gtfs_trip_updates') }}
),

stop_mapping as (
    select
        stop_id,
        stop_name,
        sa2_code,
        sa2_name
    from {{ ref('stg_stops_sa2_mapping') }}
    where is_matched = true
),

stops as (
    select
        stop_id,
        stop_name
    from {{ ref('stg_gtfs_stops') }}
),

enriched as (
    select
        tu.snapshot_timestamp,
        cast(tu.snapshot_timestamp as date) as snapshot_date,
        extract(hour from tu.snapshot_timestamp)::integer as snapshot_hour,
        tu.route_id,
        tu.trip_id,
        tu.stop_id,
        coalesce(sm.stop_name, s.stop_name) as stop_name,
        sm.sa2_code,
        sm.sa2_name,
        tu.arrival_delay_seconds,
        tu.departure_delay_seconds,
        case
            when tu.arrival_delay_seconds is null and tu.departure_delay_seconds is null then null
            else greatest(
                coalesce(tu.arrival_delay_seconds, tu.departure_delay_seconds),
                coalesce(tu.departure_delay_seconds, tu.arrival_delay_seconds)
            )
        end as max_delay_seconds,
        tu.warehouse_dataset,
        tu.source_file,
        tu.prepared_at
    from trip_updates as tu
    left join stop_mapping as sm on tu.stop_id = sm.stop_id
    left join stops as s on tu.stop_id = s.stop_id
)

select
    snapshot_timestamp,
    snapshot_date,
    snapshot_hour,
    route_id,
    trip_id,
    stop_id,
    stop_name,
    sa2_code,
    sa2_name,
    arrival_delay_seconds,
    departure_delay_seconds,
    max_delay_seconds,
    case
        when arrival_delay_seconds is not null and arrival_delay_seconds > 300 then true
        else false
    end as is_arrival_delayed_5min,
    case
        when departure_delay_seconds is not null and departure_delay_seconds > 300 then true
        else false
    end as is_departure_delayed_5min,
    case
        when arrival_delay_seconds is null and departure_delay_seconds is null then false
        when coalesce(arrival_delay_seconds, 0) > 300
            or coalesce(departure_delay_seconds, 0) > 300 then true
        else false
    end as is_delayed_5min,
    case
        when max_delay_seconds is null or max_delay_seconds <= 300 then 'early_or_on_time'
        when max_delay_seconds <= 600 then 'minor_delay'
        when max_delay_seconds <= 1200 then 'moderate_delay'
        else 'major_delay'
    end as delay_severity_band,
    warehouse_dataset,
    source_file,
    prepared_at
from enriched
