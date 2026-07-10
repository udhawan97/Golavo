# golavo-core

The Golavo modeling library. **Apache-2.0** licensed so the science stays reusable,
independent of the AGPL-3.0 application.

## Boundaries

| Module | Responsibility |
|---|---|
| `ingest` | source adapters + the immutable, content-addressed snapshotter |
| `warehouse` | Parquet + DuckDB views and schema migrations |
| `models` | Elo, time-decayed Dixon-Coles, bivariate Poisson, corners, scorers, calibration |
| `ledger` | the immutable, hash-chained forecast ledger |
| `facts` | deterministic, source-backed fact & coincidence templates |

`core` never performs network I/O outside `ingest`. It is pure computation over
cached snapshots, which is what makes forecasts replayable and deterministic.

See the [methodology docs](https://udhawan97.github.io/Golavo/methodology/prediction/).
