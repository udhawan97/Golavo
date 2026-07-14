# Test fixtures

`martj42-results-subset.csv` is a small CC0-1.0 excerpt from the pinned
`martj42/international_results` sourcepack. It covers completed, neutral,
non-neutral, and scheduled-row parsing without making tests read the full pack.

`sample_artifacts/` contains deterministic **synthetic contract fixtures**. They
are not historical forecasts and must never be presented as model results. The
set exercises sealed, scored, abstained, and voided states for schema, API, and
UI integration tests.

The authoritative vendored source snapshot and license are in
`packs/martj42-internationals/`. This fixture set intentionally has no club,
BYOK, ODbL, or scraped-data dependency.
