select
    feed_name,
    snapshot_timestamp::timestamp as snapshot_timestamp,
    entity_id,
    cause,
    effect,
    active_period_start::timestamp as active_period_start,
    active_period_end::timestamp as active_period_end,
    informed_route_id,
    informed_stop_id,
    informed_trip_id,
    header_text,
    description_text,
    warehouse_dataset,
    source_file,
    prepared_at::timestamp as prepared_at,
    load_batch_id,
    loaded_at::timestamp as loaded_at
from {{ source('raw', 'raw_gtfs_service_alerts') }}
