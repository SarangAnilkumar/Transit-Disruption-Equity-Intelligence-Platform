select
    trip_id,
    stop_id,
    stop_sequence::integer as stop_sequence,
    arrival_time,
    departure_time,
    pickup_type::integer as pickup_type,
    drop_off_type::integer as drop_off_type,
    stop_headsign,
    shape_dist_traveled::decimal(12, 4) as shape_dist_traveled,
    warehouse_dataset,
    source_file,
    prepared_at::timestamp as prepared_at,
    load_batch_id,
    loaded_at::timestamp as loaded_at
from {{ source('raw', 'raw_gtfs_stop_times') }}
