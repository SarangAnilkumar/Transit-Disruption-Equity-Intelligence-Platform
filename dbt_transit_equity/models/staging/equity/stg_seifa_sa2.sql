select
    sa2_code,
    sa2_name,
    seifa_release_year::integer as seifa_release_year,
    irsd_score::decimal(12, 6) as irsd_score,
    irsd_decile::decimal(8, 2) as irsd_decile,
    irsd_percentile::decimal(8, 2) as irsd_percentile,
    source_file,
    prepared_at::timestamp as prepared_at,
    warehouse_dataset,
    load_batch_id,
    loaded_at::timestamp as loaded_at
from {{ source('raw', 'raw_seifa_sa2') }}
