-- Redshift schema and raw layer DDL aligned with warehouse-ready local schemas.
-- Physical schema is raw_data because RAW is a reserved word in Amazon Redshift.
-- Execute via: python ingestion/init_redshift_raw_schema.py
-- COPY execution via: python ingestion/load_s3_to_redshift_raw.py

create schema if not exists raw_data;
create schema if not exists staging;
create schema if not exists audit;

create table if not exists raw_data.raw_gtfs_stops (
    stop_id varchar(64),
    stop_name varchar(512),
    stop_lat numeric(10, 7),
    stop_lon numeric(10, 7),
    location_type integer,
    parent_station varchar(64),
    wheelchair_boarding integer,
    zone_id varchar(64),
    warehouse_dataset varchar(128),
    source_file varchar(1024),
    prepared_at timestamp,
    load_batch_id varchar(64),
    loaded_at timestamp default current_timestamp
);

create table if not exists raw_data.raw_gtfs_routes (
    route_id varchar(64),
    agency_id varchar(64),
    route_short_name varchar(128),
    route_long_name varchar(512),
    route_type integer,
    route_color varchar(16),
    route_text_color varchar(16),
    warehouse_dataset varchar(128),
    source_file varchar(1024),
    prepared_at timestamp,
    load_batch_id varchar(64),
    loaded_at timestamp default current_timestamp
);

create table if not exists raw_data.raw_gtfs_trips (
    trip_id varchar(128),
    route_id varchar(64),
    service_id varchar(64),
    trip_headsign varchar(512),
    direction_id integer,
    shape_id varchar(128),
    block_id varchar(64),
    wheelchair_accessible integer,
    bikes_allowed integer,
    warehouse_dataset varchar(128),
    source_file varchar(1024),
    prepared_at timestamp,
    load_batch_id varchar(64),
    loaded_at timestamp default current_timestamp
);

create table if not exists raw_data.raw_gtfs_stop_times (
    trip_id varchar(128),
    stop_id varchar(64),
    stop_sequence integer,
    arrival_time varchar(16),
    departure_time varchar(16),
    pickup_type integer,
    drop_off_type integer,
    stop_headsign varchar(512),
    shape_dist_traveled numeric(12, 4),
    warehouse_dataset varchar(128),
    source_file varchar(1024),
    prepared_at timestamp,
    load_batch_id varchar(64),
    loaded_at timestamp default current_timestamp
);

create table if not exists raw_data.raw_gtfs_trip_updates (
    feed_name varchar(64),
    snapshot_timestamp timestamp,
    entity_id varchar(128),
    trip_id varchar(128),
    route_id varchar(64),
    start_time varchar(16),
    start_date varchar(16),
    schedule_relationship varchar(64),
    stop_sequence integer,
    stop_id varchar(64),
    arrival_delay_seconds integer,
    arrival_time timestamp,
    departure_delay_seconds integer,
    departure_time timestamp,
    warehouse_dataset varchar(128),
    source_file varchar(1024),
    prepared_at timestamp,
    load_batch_id varchar(64),
    loaded_at timestamp default current_timestamp
);

create table if not exists raw_data.raw_gtfs_service_alerts (
    feed_name varchar(64),
    snapshot_timestamp timestamp,
    entity_id varchar(128),
    cause varchar(128),
    effect varchar(128),
    active_period_start timestamp,
    active_period_end timestamp,
    informed_route_id varchar(64),
    informed_stop_id varchar(64),
    informed_trip_id varchar(128),
    header_text varchar(2000),
    description_text varchar(4000),
    warehouse_dataset varchar(128),
    source_file varchar(1024),
    prepared_at timestamp,
    load_batch_id varchar(64),
    loaded_at timestamp default current_timestamp
);

create table if not exists raw_data.raw_stops_sa2_mapping (
    stop_id varchar(64),
    stop_name varchar(512),
    stop_lat numeric(10, 7),
    stop_lon numeric(10, 7),
    sa2_code varchar(32),
    sa2_name varchar(512),
    mapping_method varchar(64),
    is_matched boolean,
    mapping_created_at timestamp,
    source_stops_path varchar(1024),
    source_sa2_path varchar(1024),
    warehouse_dataset varchar(128),
    source_file varchar(1024),
    prepared_at timestamp,
    load_batch_id varchar(64),
    loaded_at timestamp default current_timestamp
);

create table if not exists raw_data.raw_route_sa2_coverage (
    route_id varchar(64),
    route_short_name varchar(128),
    route_long_name varchar(512),
    route_type integer,
    sa2_code varchar(32),
    sa2_name varchar(512),
    stop_count_in_sa2 integer,
    trip_count_serving_sa2 integer,
    first_stop_sequence integer,
    last_stop_sequence integer,
    coverage_created_at timestamp,
    warehouse_dataset varchar(128),
    source_file varchar(1024),
    prepared_at timestamp,
    load_batch_id varchar(64),
    loaded_at timestamp default current_timestamp
);

create table if not exists raw_data.raw_sa2_disruption_observations_base (
    snapshot_date varchar(16),
    snapshot_hour integer,
    sa2_code varchar(32),
    sa2_name varchar(512),
    observation_count integer,
    distinct_trip_count integer,
    distinct_stop_count integer,
    delayed_observation_count integer,
    avg_arrival_delay_seconds numeric(12, 4),
    avg_departure_delay_seconds numeric(12, 4),
    max_arrival_delay_seconds numeric(12, 4),
    max_departure_delay_seconds numeric(12, 4),
    unmatched_stop_observation_count integer,
    warehouse_dataset varchar(128),
    source_file varchar(1024),
    prepared_at timestamp,
    load_batch_id varchar(64),
    loaded_at timestamp default current_timestamp
);

create table if not exists raw_data.raw_seifa_sa2 (
    sa2_code varchar(32),
    sa2_name varchar(512),
    seifa_release_year integer,
    irsd_score numeric(12, 6),
    irsd_decile numeric(8, 2),
    irsd_percentile numeric(8, 2),
    source_file varchar(1024),
    prepared_at timestamp,
    warehouse_dataset varchar(128),
    load_batch_id varchar(64),
    loaded_at timestamp default current_timestamp
);

create table if not exists audit.ingestion_runs (
    run_id varchar(64),
    feed_name varchar(64),
    started_at timestamp,
    finished_at timestamp,
    status varchar(32),
    records_loaded integer,
    source_file varchar(1024),
    loaded_at timestamp default current_timestamp
);

create table if not exists audit.source_files (
    source_file_id varchar(64),
    dataset_name varchar(128),
    source_path varchar(1024),
    file_size_bytes bigint,
    row_count integer,
    checksum varchar(128),
    discovered_at timestamp,
    load_batch_id varchar(64),
    loaded_at timestamp default current_timestamp
);

create table if not exists audit.load_quality_reports (
    report_id varchar(64),
    dataset_name varchar(128),
    load_batch_id varchar(64),
    report_path varchar(1024),
    error_count integer,
    warning_count integer,
    passed_count integer,
    created_at timestamp,
    loaded_at timestamp default current_timestamp
);
