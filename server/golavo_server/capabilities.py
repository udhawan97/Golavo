"""Read-only API projection of the frozen competition capability catalog."""

from __future__ import annotations

from typing import Any

from golavo_core.competitions import competition_catalog


def get_capabilities() -> dict[str, Any]:
    return competition_catalog()
