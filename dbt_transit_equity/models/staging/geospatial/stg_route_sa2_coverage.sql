select
    route_id,
    route_short_name,
    route_long_name,
    route_type::integer as route_type,
    sa2_code,
    sa2_name,
    stop_count_in_sa2::integer as stop_count_in_sa2,
    trip_count_serving_sa2::integer as trip_count_serving_sa2,
    first_stop_sequence::integer as first_stop_sequence,
    last_stop_sequence::integer as last_stop_sequence,
    coverage_created_at::timestamp as coverage_created_at,
    warehouse_dataset,
    source_file,
    prepared_at::timestamp as prepared_at,
    load_batch_id,
    loaded_at::timestamp as loaded_at
from {{ source('raw', 'raw_route_sa2_coverage') }}
