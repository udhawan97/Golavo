"""A per-user, on-disk store for fetched weather readings — one file per capture.

Readings live under ``<data_dir>/weather/<match_id>/<fetched_at>.json`` (never in
the bundled index or any CC0/ODbL store): weather is per-user context a user
fetched onto their own machine. ``load_latest`` returns the most recently fetched
capture, which the conditions reader then gates on ``fetched_at < kickoff``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_SAFE_ID = re.compile(r"[^A-Za-z0-9_.-]")


def _match_dir(weather_root: Path, match_id: str) -> Path:
    # match_ids are ``m_<hex>``/``fa_*`` style; sanitize defensively so a crafted
    # id can never escape the weather store into another path.
    safe = _SAFE_ID.sub("_", str(match_id))
    return Path(weather_root) / safe


def save_reading(weather_root: Path, match_id: str, reading: dict[str, Any]) -> Path:
    """Persist one reading, keyed by its ``fetched_at_utc`` so captures accumulate."""
    fetched_at = str(reading["fetched_at_utc"])
    directory = _match_dir(weather_root, match_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{_SAFE_ID.sub('_', fetched_at)}.json"
    path.write_text(json.dumps(reading, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_latest(weather_root: Path, match_id: str) -> dict[str, Any] | None:
    """The most recently fetched reading for a match, or None if none are stored."""
    directory = _match_dir(weather_root, match_id)
    if not directory.is_dir():
        return None
    latest: dict[str, Any] | None = None
    for path in directory.glob("*.json"):
        try:
            reading = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(reading, dict) or "fetched_at_utc" not in reading:
            continue
        if latest is None or str(reading["fetched_at_utc"]) > str(latest["fetched_at_utc"]):
            latest = reading
    return latest
