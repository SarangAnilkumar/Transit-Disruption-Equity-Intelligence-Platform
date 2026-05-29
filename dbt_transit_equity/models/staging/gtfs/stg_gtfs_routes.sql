select
    route_id,
    agency_id,
    route_short_name,
    route_long_name,
    route_type::integer as route_type,
    route_color,
    route_text_color,
    warehouse_dataset,
    source_file,
    prepared_at::timestamp as prepared_at,
    load_batch_id,
    loaded_at::timestamp as loaded_at
from {{ source('raw', 'raw_gtfs_routes') }}
