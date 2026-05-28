-- Redshift-compatible raw layer DDL scaffold

create table if not exists raw_gtfs_stops (
    stop_id varchar(64),
    stop_name varchar(512),
    stop_lat numeric(10, 7),
    stop_lon numeric(10, 7),
    zone_id varchar(64),
    location_type integer,
    parent_station varchar(64),
    source_file varchar(1024),
    loaded_at timestamp default current_timestamp
);

create table if not exists raw_gtfs_routes (
    route_id varchar(64),
    agency_id varchar(64),
    route_short_name varchar(128),
    route_long_name varchar(512),
    route_type integer,
    source_file varchar(1024),
    loaded_at timestamp default current_timestamp
);

create table if not exists raw_gtfs_trips (
    trip_id varchar(128),
    route_id varchar(64),
    service_id varchar(64),
    trip_headsign varchar(512),
    direction_id integer,
    shape_id varchar(128),
    source_file varchar(1024),
    loaded_at timestamp default current_timestamp
);

create table if not exists raw_gtfs_stop_times (
    trip_id varchar(128),
    arrival_time varchar(16),
    departure_time varchar(16),
    stop_id varchar(64),
    stop_sequence integer,
    pickup_type integer,
    drop_off_type integer,
    source_file varchar(1024),
    loaded_at timestamp default current_timestamp
);

create table if not exists raw_gtfs_trip_updates (
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
    source_file varchar(1024),
    loaded_at timestamp default current_timestamp
);

create table if not exists raw_gtfs_service_alerts (
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
    source_file varchar(1024),
    loaded_at timestamp default current_timestamp
);

create table if not exists raw_ingestion_runs (
    run_id varchar(64),
    feed_name varchar(64),
    started_at timestamp,
    finished_at timestamp,
    status varchar(32),
    records_loaded integer,
    source_file varchar(1024),
    loaded_at timestamp default current_timestamp
);
