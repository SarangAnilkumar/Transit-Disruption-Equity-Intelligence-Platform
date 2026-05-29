# Milestone 3 Progress

## GitHub milestone status
- **Milestone 3 — GTFS Static Modelling & Stop-to-SA2 Mapping**: 7 closed / 1 open (blocked)
- Milestones 1 and 2: fully closed on GitHub

## Issue tracker (2026-05-29)
| Issue | Title | Status |
|---|---|---|
| #20 | ABS SA2 boundary data source documentation | Closed |
| #21 | SA2 boundary ingestion script | Closed |
| #22 | Stop-to-SA2 GeoPandas mapping script | Closed |
| #23 | Generate `processed/stop_area_mapping.csv` | **Open / blocked** |
| #24 | Mapping coverage report | Closed |
| #25 | Route-to-SA2 coverage logic | Closed |
| #26 | Tests for mapping output schema | Closed |
| #27 | Geospatial assumptions and limitations docs | Closed |

## Implementation checklist vs original prompt

| Step | Requirement | Status |
|---|---|---|
| 4 | `.env.example` + `settings.example.yml` geospatial/equity/analytics | Done |
| 5 | geopandas/shapely/pyproj/pyogrio/openpyxl in requirements | Done |
| 6 | `build_stop_sa2_mapping.py` | Done |
| 7 | `build_route_sa2_coverage.py` | Done |
| 8 | `prepare_seifa_sa2.py` | Done (not a separate GitHub issue) |
| 9 | `build_sa2_disruption_base.py` | Done (not a separate GitHub issue) |
| 6 extra | `ingest_sa2_boundaries.py` | Done |
| 10 | geospatial/equity/disruption tests | Done (19 pytest total) |
| 11 | `docs/geospatial_mapping.md` + README/docs updates | Done |
| 12 | `.gitignore` raw geospatial/equity | Done |
| 14 | compileall + pytest | 19 passed |

## Pending (data-dependent, not faked)
- Run mapping pipeline after placing ABS SA2 boundaries file and setting `SA2_BOUNDARIES_PATH` in `.env`
- Optional: `SEIFA_SA2_PATH` + `prepare_seifa_sa2.py`
- Run `build_sa2_disruption_base.py` after stop mapping exists (parsed trip updates already present locally)

## Commands once SA2 file is available
```bash
python ingestion/ingest_sa2_boundaries.py
python ingestion/build_stop_sa2_mapping.py
python ingestion/build_route_sa2_coverage.py
python ingestion/build_sa2_disruption_base.py
```

## Local git note
Milestone 3 code/docs/tests are implemented locally but may still be **uncommitted** on `main`. Commit and push when ready.
