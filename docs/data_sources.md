# Data Sources

## GTFS Static
- **Purpose**: Baseline schedule and network reference (stops, routes, trips, stop times, service calendars).
- **Expected grain**: File-specific; typically one row per stop/route/trip/stop-event.
- **Refresh frequency**: Periodic feed updates (operator dependent, often daily/weekly).
- **Expected format**: ZIP containing CSV text files per GTFS spec.
- **Current status**: In MVP ingestion scope and implemented for local fetch/extract.
- **Known risks**: Feed schema variations, missing optional files, schedule not equal to actual operations.

## GTFS-Realtime Trip Updates
- **Purpose**: Observed operational delay/change snapshots by trip and stop sequence.
- **Expected grain**: Snapshot -> entity -> trip update -> stop time update.
- **Refresh frequency**: Near-real-time (often every 10-60 seconds by provider).
- **Expected format**: Protocol Buffers (GTFS-R).
- **Current status**: In MVP ingestion scope and parser implemented.
- **Known risks**: Snapshot incompleteness, transient feed outages, varying field population.

## GTFS-Realtime Service Alerts
- **Purpose**: Incident and disruption advisories affecting routes/stops/trips.
- **Expected grain**: Snapshot -> entity -> alert -> informed entity period.
- **Refresh frequency**: Event-driven near-real-time.
- **Expected format**: Protocol Buffers (GTFS-R).
- **Current status**: In MVP ingestion scope and parser implemented.
- **Known risks**: Inconsistent text quality, missing informed entities, changing cause/effect usage.

## ABS SEIFA (future)
- **Purpose**: Socio-economic disadvantage context for equity lens.
- **Expected grain**: SA2 (or available statistical area level).
- **Refresh frequency**: Census/release cycle.
- **Expected format**: CSV/XLSX and metadata documentation.
- **Current status**: Planned; not yet ingested in MVP.
- **Known risks**: Time lag versus live transport data, index interpretation caveats.

## SA2 Boundaries (future)
- **Purpose**: Spatial joins between transport features and socio-economic geography.
- **Expected grain**: Polygon geometry by SA2.
- **Refresh frequency**: ABS boundary release cycle.
- **Expected format**: GeoPackage/Shapefile/GeoJSON.
- **Current status**: Milestone 3 local preprocessing scripts implemented; awaiting/using user-provided ABS raw file.
- **Known risks**: Coordinate reference mismatches, boundary updates across years.

## ABS SEIFA SA2 (Milestone 3/next)
- **Purpose**: Equity context through socio-economic disadvantage indicators at SA2 level.
- **Expected grain**: SA2.
- **Refresh frequency**: Census/release cycle.
- **Expected format**: CSV/XLSX.
- **Current status**: Preparation script implemented; depends on user-provided source file.
- **Known risks**: Column naming variation and release-year comparability.

## Population / Car Ownership Proxies (future)
- **Purpose**: Estimate transport dependence and contextualize disruption burden.
- **Expected grain**: SA2 or finer where available.
- **Refresh frequency**: Annual/census dependent.
- **Expected format**: CSV/XLSX.
- **Current status**: Optional future enrichment.
- **Known risks**: Different vintages and definitions across datasets.
