# Feed Access Notes (Milestone 1.5)

## Transport Victoria URLs
- GTFS static:
  - `https://opendata.transport.vic.gov.au/dataset/3f4e292e-7f8a-4ffe-831f-1953be0fe448/resource/fb152201-859f-4882-9206-b768060b50ad/download/gtfs.zip`
- GTFS-R metro trip updates:
  - `https://api.opendata.transport.vic.gov.au/opendata/public-transport/gtfs/realtime/v1/metro/trip-updates`
- GTFS-R metro service alerts:
  - `https://api.opendata.transport.vic.gov.au/opendata/public-transport/gtfs/realtime/v1/metro/service-alerts`

## Supported auth modes
- `header` mode (default):
  - Header name configurable via `TRANSPORT_API_HEADER_NAME`
  - Start with `Ocp-Apim-Subscription-Key`
  - If needed, retry with `KeyID`
- `query` mode:
  - Parameter name configurable via `TRANSPORT_API_QUERY_PARAM_NAME`
  - Use `subscription-key` when required by endpoint/OpenAPI behavior

## Known auth uncertainty
Transport Victoria documentation and specs may reference different key mechanisms (`KeyID`, `Ocp-Apim-Subscription-Key`, or `subscription-key`). This project keeps auth mode and names configurable to avoid hardcoded assumptions.

## Rate-limit-safe MVP cadence
For MVP feasibility, avoid aggressive polling. A 15-minute snapshot interval is sufficient to prove data access and parsing viability.

## Analytical limitation reminder
GTFS-Realtime snapshots are sampled operational observations, not a complete official reliability record.
