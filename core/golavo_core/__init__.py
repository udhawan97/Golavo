"""Golavo core modeling library.

Boundaries (each a submodule):
    ingest     - source adapters + immutable snapshotter
    warehouse  - Parquet match index + side tables (pandas/pyarrow)
    models     - Elo, Dixon-Coles, bivariate Poisson, corners, scorers, calibration
    artifacts  - immutable Phase 0 ForecastArtifact seal/score pipeline
    facts      - deterministic, source-backed fact templates
    identity   - the one team-name fold and fixture key

The engine owns every probability; nothing here performs network I/O outside
`ingest`. Apache-2.0 licensed so the science stays reusable.
"""

__version__ = "0.17.0"
