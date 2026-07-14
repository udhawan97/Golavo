# golavo-core

The Golavo modeling library. **Apache-2.0** licensed so the science stays reusable,
independent of any application that uses it.

## Boundaries

| Module | Responsibility |
|---|---|
| `ingest` | source adapters + the immutable, content-addressed snapshotter |
| `warehouse` | Parquet + DuckDB views and schema migrations |
| `models` | Elo, time-decayed Dixon-Coles, bivariate Poisson, corners, scorers, calibration |
| `artifacts` | immutable ForecastArtifact seal/score pipeline |
| `ledger` | forecast ledger; hash chaining remains planned (ADR-0001) |
| `facts` | deterministic, source-backed fact & coincidence templates |

`core` never performs network I/O outside `ingest`. It is pure computation over
cached snapshots, which is what makes forecasts replayable and deterministic.

See the [methodology docs](https://udhawan97.github.io/Golavo/methodology/prediction/).
