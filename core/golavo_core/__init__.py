"""Golavo core modeling library.

Boundaries (each a submodule):
    ingest     - source adapters + immutable snapshotter
    warehouse  - Parquet + DuckDB views and schema migrations
    models     - Elo, Dixon-Coles, bivariate Poisson, corners, scorers, calibration
    artifacts  - immutable Phase 0 ForecastArtifact seal/score pipeline
    ledger     - planned hash-chained ledger (ADR-0001, Phase 1)
    facts      - planned deterministic, source-backed fact templates

The engine owns every probability; nothing here performs network I/O outside
`ingest`. Apache-2.0 licensed so the science stays reusable.
"""

__version__ = "0.2.3"
