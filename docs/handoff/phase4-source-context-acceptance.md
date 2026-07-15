# Phase 4 source-backed context acceptance

Verified on 2026-07-15 against the arm64 macOS 0.13.0 bundle.

## Shipped boundary

- Context remains display-only. `GeoNames`, `Natural Earth`, and `Wikidata`
  provenance is structurally barred from model, artifact, calibration,
  settlement, and core-index sinks by `scripts/validate_context_pack.py`.
- The installed application performs no GeoNames, Wikidata, map-tile, or
  geocoder request. It reads one immutable bundled generation and fails the
  whole context surface closed if any declared byte or hash disagrees.
- The runtime bundle contains `data/context/manifest.json`, the reviewed venue
  entities and exact scoped assignments, the compact place lookup, and the
  Natural Earth 1:110m basemap. Review queues and raw build snapshots do not
  ship.
- Match-index refresh resets the context caches with the index cache. A sealed
  forecast is neither rewritten nor reinterpreted by context.

## Acceptance evidence

- Context validator: 1,497 resolved places, 16 reviewed venues, and 644
  unresolved/review states; all manifest bytes and hashes verified.
- Python matrix: 642 tests passed, including determinism, sealing, refresh,
  provenance, ODbL isolation, context corruption, and sidecar routes.
- UI matrix: 134 unit tests and 133 browser tests passed; production TypeScript
  and Vite build passed.
- Live source-mode visual check: reviewed World Cup venue, identity conflict,
  calendar-day gaps, great-circle routes, source tags, and expanded formulas
  rendered at desktop and 375 px with no horizontal overflow.
- Frozen sidecar: `--smoke` passed search, notebook, reviewed venue, place,
  source catalog, offline map, and internationals sealing-pack probes.
- `/Applications/Golavo.app`: arm64 shell and bundled sidecar launched; the
  installed sidecar reported 0.13.0 and passed the same expanded smoke test.
  The final installed-WebView screenshot was unavailable because the macOS
  session was locked; the identical production UI bundle was visually checked
  against the live sidecar before packaging.

## Budgets

- Runtime context payload: 2,008,533 declared bytes plus a 2,934-byte manifest;
  budget is 2.5 MB.
- Match-detail production chunk: 81.83 kB uncompressed / 21.49 kB gzip; budget
  is 90 kB / 25 kB.
- Installed application: 315 MB; budget is 330 MB. The context payload adds
  roughly 2 MB and does not justify a higher application budget.
- Map rendering uses one bundled 1:110m SVG path set, no raster tiles, and at
  most two routes.

## Rollback and removal

The context generation is read-only and creates no Application Support
database. Rollback is an application-version rollback: quit Golavo and replace
`/Applications/Golavo.app` with the prior verified bundle. Existing ledger,
picks, refresh generations, and the optional OpenLigaDB overlay remain in
Application Support and must not be deleted as part of a context rollback.

## Non-goals and forbidden claims

- Do not call a city location a stadium, a great-circle line actual team
  travel, or a date-only gap rest.
- Do not claim complete schedules, current club fixtures, live venue data, or
  live weather from this pack.
- Do not feed place, venue, timezone, elevation, distance, or schedule-gap
  fields into forecasts until a separate leakage-safe backtest and model-change
  gate is approved.
- Do not describe model-implied goals as observed xG.
- Do not add fuzzy automatic entity merges, hosted map/geocoder dependencies,
  or a closed-app refresh daemon.
