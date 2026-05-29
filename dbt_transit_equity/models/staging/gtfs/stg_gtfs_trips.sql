select
    trip_id,
    route_id,
    service_id,
    trip_headsign,
    direction_id::integer as direction_id,
    shape_id,
    block_id,
    wheelchair_accessible::integer as wheelchair_accessible,
    bikes_allowed::integer as bikes_allowed,
    warehouse_dataset,
    source_file,
    prepared_at::timestamp as prepared_at,
    load_batch_id,
    loaded_at::timestamp as loaded_at
from {{ source('raw', 'raw_gtfs_trips') }}
