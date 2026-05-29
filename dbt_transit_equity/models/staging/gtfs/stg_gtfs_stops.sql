select
    stop_id,
    stop_name,
    stop_lat::decimal(10, 7) as stop_lat,
    stop_lon::decimal(10, 7) as stop_lon,
    location_type::integer as location_type,
    parent_station,
    wheelchair_boarding::integer as wheelchair_boarding,
    zone_id,
    warehouse_dataset,
    source_file,
    prepared_at::timestamp as prepared_at,
    load_batch_id,
    loaded_at::timestamp as loaded_at
from {{ source('raw', 'raw_gtfs_stops') }}
