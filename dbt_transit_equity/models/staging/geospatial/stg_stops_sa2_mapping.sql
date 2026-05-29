select
    stop_id,
    stop_name,
    stop_lat::decimal(10, 7) as stop_lat,
    stop_lon::decimal(10, 7) as stop_lon,
    sa2_code,
    sa2_name,
    mapping_method,
    is_matched::boolean as is_matched,
    mapping_created_at::timestamp as mapping_created_at,
    source_stops_path,
    source_sa2_path,
    warehouse_dataset,
    source_file,
    prepared_at::timestamp as prepared_at,
    load_batch_id,
    loaded_at::timestamp as loaded_at
from {{ source('raw', 'raw_stops_sa2_mapping') }}
