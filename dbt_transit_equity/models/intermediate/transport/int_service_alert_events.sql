with service_alerts as (
    select * from {{ ref('stg_gtfs_service_alerts') }}
),

stop_mapping as (
    select
        stop_id,
        sa2_code,
        sa2_name
    from {{ ref('stg_stops_sa2_mapping') }}
    where is_matched = true
),

enriched as (
    select
        sa.snapshot_timestamp,
        cast(sa.snapshot_timestamp as date) as snapshot_date,
        extract(hour from sa.snapshot_timestamp)::integer as snapshot_hour,
        sa.entity_id,
        sa.cause,
        sa.effect,
        sa.informed_route_id,
        sa.informed_stop_id,
        sa.informed_trip_id,
        sm.sa2_code,
        sm.sa2_name,
        sa.active_period_start,
        sa.active_period_end,
        sa.header_text,
        sa.description_text,
        upper(coalesce(sa.effect, '')) in (
            'NO_SERVICE',
            'REDUCED_SERVICE',
            'SIGNIFICANT_DELAYS',
            'DETOUR',
            'MODIFIED_SERVICE',
            'STOP_MOVED',
            'OTHER_EFFECT'
        ) as is_disruption_alert,
        sa.warehouse_dataset,
        sa.source_file,
        sa.prepared_at
    from service_alerts as sa
    left join stop_mapping as sm on sa.informed_stop_id = sm.stop_id
)

select
    snapshot_timestamp,
    snapshot_date,
    snapshot_hour,
    entity_id,
    cause,
    effect,
    informed_route_id,
    informed_stop_id,
    informed_trip_id,
    sa2_code,
    sa2_name,
    active_period_start,
    active_period_end,
    header_text,
    description_text,
    is_disruption_alert,
    case
        when upper(coalesce(effect, '')) = 'NO_SERVICE' then 'critical'
        when upper(coalesce(effect, '')) in ('REDUCED_SERVICE', 'SIGNIFICANT_DELAYS') then 'high'
        when upper(coalesce(effect, '')) in ('DETOUR', 'MODIFIED_SERVICE', 'STOP_MOVED') then 'moderate'
        when upper(coalesce(effect, '')) = 'OTHER_EFFECT' then 'unknown'
        else 'informational'
    end as alert_severity_band,
    warehouse_dataset,
    source_file,
    prepared_at
from enriched
