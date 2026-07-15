"""Resource path resolution for source checkouts and PyInstaller bundles.

Golavo reads a handful of read-only resources at runtime — the ForecastArtifact
JSON schema, the vendored evaluation summaries, and (optionally) a bundled
ledger. In a normal source checkout these live under the repository root. When
the FastAPI server is frozen into a single-file PyInstaller binary, the same
files are unpacked into a temporary directory exposed as ``sys._MEIPASS``.

This module hides that difference behind one resolver so callers never have to
branch on ``sys.frozen`` themselves. Paths are always resolved lazily (never
cached at import) so a test or the sidecar can set ``GOLAVO_DATA_DIR`` and have
it honoured.
"""

from __future__ import annotations

import sys
from pathlib import Path

# In a source checkout this file is core/golavo_core/resources.py, so parents[2]
# is the repository root. In a frozen build __file__ points inside the unpacked
# bundle instead and this value is never used (see ``resource_root``).
_SOURCE_ROOT = Path(__file__).resolve().parents[2]


def is_frozen() -> bool:
    """True when running inside a PyInstaller (or similar) frozen bundle."""
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """Root directory that bundled read-only resources are resolved against.

    Frozen builds unpack ``datas`` under ``sys._MEIPASS`` (onefile) or the
    executable's directory (onedir); either way PyInstaller sets ``_MEIPASS``.
    Source checkouts resolve against the repository root.
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", _SOURCE_ROOT))
    return _SOURCE_ROOT


def resource(*parts: str) -> Path:
    """Resolve a bundled resource by its repo-relative path components."""
    return resource_root().joinpath(*parts)


def schema_path() -> Path:
    """Absolute path to the canonical ForecastArtifact JSON schema."""
    return resource("docs", "contracts", "forecast_artifact.schema.json")


def user_pick_schema_path() -> Path:
    """Absolute path to the user-pick ledger and API-view schema."""
    return resource("docs", "contracts", "user_pick.schema.json")


def evidence_bundle_schema_path() -> Path:
    """Absolute path to the MatchEvidenceBundle JSON schema (Phase 5, additive)."""
    return resource("docs", "contracts", "evidence_bundle.schema.json")


def narration_schema_path() -> Path:
    """Absolute path to the AiNarration JSON schema (Phase 5, additive)."""
    return resource("docs", "contracts", "ai_narration.schema.json")


def facts_schema_path() -> Path:
    """Absolute path to the CommentatorsNotebook JSON schema (Phase 7, additive)."""
    return resource("docs", "contracts", "facts.schema.json")


def competition_catalog_schema_path() -> Path:
    """Absolute path to the competition identity/capability contract."""
    return resource("docs", "contracts", "competition_catalog.schema.json")


def conditions_snapshot_schema_path() -> Path:
    """Absolute path to the display-only Conditions Snapshot contract."""
    return resource("docs", "contracts", "conditions_snapshot.schema.json")


def match_index_path() -> Path:
    """Absolute path to the committed, frozen match search index (Parquet)."""
    return resource("data", "index", "matches_index.parquet")


def match_index_meta_path() -> Path:
    """Absolute path to the match index's schema/row-count/digest sidecar."""
    return resource("data", "index", "matches_index.meta.json")


def match_index_goalscorers_path() -> Path:
    """Absolute path to the internationals goalscorers side table (Parquet)."""
    return resource("data", "index", "goalscorers.parquet")


def match_index_shootouts_path() -> Path:
    """Absolute path to the internationals shootouts side table (Parquet)."""
    return resource("data", "index", "shootouts.parquet")


def match_index_aliases_path() -> Path:
    """Absolute path to the former-name search alias map (JSON)."""
    return resource("data", "index", "aliases.json")


def geonames_places_path() -> Path:
    """Compact, pinned city-country lookup derived from the GeoNames pack."""
    return resource("data", "enrichment", "places.json")


def natural_earth_world_path() -> Path:
    """Pinned Natural Earth 1:110m country basemap for offline route maps."""
    return resource("data", "enrichment", "world_110m.geojson")
