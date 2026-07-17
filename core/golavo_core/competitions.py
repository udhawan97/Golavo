"""Stable competition identities and honest feature-capability declarations.

This module is deliberately data-only.  It freezes the identifiers and format-era
boundaries that analytics, refresh adapters, standings and simulations will share,
without claiming those later phases are already available.  A missing capability
is a typed state with a reason, never an empty object that the UI could misread as
zero probability or zero coverage.
"""

from __future__ import annotations

import copy
from typing import Any

CATALOG_SCHEMA_VERSION = "0.1.0"
CATALOG_VERSION = "2026.07.17.2"


def _capability(
    status: str,
    reason: str,
    *source_ids: str,
) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "source_ids": list(source_ids),
    }


def _format(
    format_era_id: str,
    label: str,
    first_cycle: str,
    last_cycle: str | None,
) -> dict[str, Any]:
    return {
        "format_era_id": format_era_id,
        "label": label,
        "first_cycle": first_cycle,
        "last_cycle": last_cycle,
        "rules_status": "declared",
    }


def _base_capabilities() -> dict[str, dict[str, Any]]:
    return {
        "report_cards": _capability(
            "planned", "Phase 1 will add confidence intervals and skill scores."
        ),
        "strength_trends": _capability(
            "planned", "Phase 1 will add cutoff-safe, competition-local trends."
        ),
        "rest_congestion": _capability(
            "planned", "Phase 1 will derive pre-match rest and fixture load."
        ),
        "schedule_difficulty": _capability(
            "blocked", "A complete remaining-fixture list is required."
        ),
        "conditions": _capability(
            "partial",
            "Rest is available when a prior indexed match exists; city, local-time, and "
            "travel context require an exact city-country resolution. Stadium remains unknown.",
            "geonames",
            "natural-earth",
        ),
        "simulation": _capability(
            "blocked", "Verified rules and complete remaining fixtures are required."
        ),
        "research": _capability(
            "unavailable", "No competition-and-era-compatible research pack is installed."
        ),
        "weather_context": _capability(
            "partial",
            "A per-user Open-Meteo forecast can be fetched for an upcoming match and is "
            "shown only when it was captured before kickoff; it is display-only context.",
            "open-meteo",
        ),
    }


def _domestic(
    competition_id: str,
    slug: str,
    display_name: str,
    source_competition: str,
    fixture_source_id: str,
) -> dict[str, Any]:
    capabilities = _base_capabilities()
    capabilities["results"] = _capability(
        "available",
        "Completed results are bundled from the pinned OpenFootball league pack.",
        "openfootball-football-json",
    )
    capabilities["fixtures"] = _capability(
        "available",
        "The complete 2026-27 double round-robin is bundled from the pinned OpenFootball "
        "fixture list and machine-checked against the season certificate.",
        "openfootball-football-json",
        fixture_source_id,
    )
    capabilities["report_cards"] = _capability(
        "available",
        "Three chronological held-out season folds include seeded match-bootstrap skill intervals.",
        "openfootball-football-json",
    )
    capabilities["strength_trends"] = _capability(
        "available",
        "Competition-local, cutoff-safe Poisson strength trends are derived from bundled results.",
        "openfootball-football-json",
    )
    capabilities["rest_congestion"] = _capability(
        "available",
        "Rest and fixture load are derived from matches present in the local index.",
        "openfootball-football-json",
    )
    capabilities["simulation"] = _capability(
        "available",
        "Standings rules are verified and the 2026-27 fixture list certifies complete, so the "
        "seeded outlook runs. It still fails closed per request if that certificate ever fails.",
        "openfootball-football-json",
        fixture_source_id,
    )
    capabilities["research"] = _capability(
        "partial",
        "Pappalardo/Wyscout event research is limited to the 2017/18 season.",
        "pappalardo-wyscout-events",
    )
    return {
        "competition_id": competition_id,
        "slug": slug,
        "display_name": display_name,
        "team_scope": "club",
        "jurisdiction": "domestic",
        "source_competition_names": [source_competition],
        "format_eras": [
            _format(f"{competition_id}-current", "Current domestic league era", "2021/22", None)
        ],
        "capabilities": capabilities,
    }


def _uefa_club(
    competition_id: str,
    slug: str,
    display_name: str,
    *,
    coverage: str,
    began: str = "2021/22",
) -> dict[str, Any]:
    capabilities = _base_capabilities()
    capabilities["results"] = _capability(
        "available",
        f"Completed main-competition results are bundled for {coverage}.",
        "openfootball-champions-league",
    )
    capabilities["fixtures"] = _capability(
        "partial",
        "Historical results are complete for the stated editions; no complete future schedule "
        "is claimed.",
        "openfootball-champions-league",
    )
    capabilities["strength_trends"] = _capability(
        "available",
        "Competition-local, cutoff-safe strength trends are derived from bundled results.",
        "openfootball-champions-league",
    )
    capabilities["rest_congestion"] = _capability(
        "available",
        "Rest and load count only matches present in this competition's local index.",
        "openfootball-champions-league",
    )
    old_label = (
        "Group-stage era"
        if competition_id != "uefa-conference-league"
        else "Inaugural group-stage era"
    )
    return {
        "competition_id": competition_id,
        "slug": slug,
        "display_name": display_name,
        "team_scope": "club",
        "jurisdiction": "uefa-club",
        "source_competition_names": [display_name],
        "format_eras": [
            _format(f"{competition_id}-group-2021", old_label, began, "2023/24"),
            _format(
                f"{competition_id}-league-2024",
                "League-phase era",
                "2024/25",
                None,
            ),
        ],
        "capabilities": capabilities,
    }


def _international(
    competition_id: str,
    slug: str,
    display_name: str,
    source_names: list[str],
    format_eras: list[dict[str, Any]],
    *,
    research: bool = False,
    report_card: bool = False,
    simulation: bool = False,
    jurisdiction: str = "uefa-international",
) -> dict[str, Any]:
    capabilities = _base_capabilities()
    capabilities["results"] = _capability(
        "available",
        "Historical results are present in the pinned martj42 internationals pack.",
        "martj42-international-results",
    )
    capabilities["fixtures"] = _capability(
        "partial",
        "Historical results do not imply a complete future schedule.",
        "martj42-international-results",
    )
    if source_names:
        capabilities["strength_trends"] = _capability(
            "available",
            "Competition-local, cutoff-safe strength trends are derived from bundled results.",
            "martj42-international-results",
        )
        capabilities["rest_congestion"] = _capability(
            "available",
            "Rest and load count matches present in Golavo's international index.",
            "martj42-international-results",
        )
    if report_card:
        capabilities["report_cards"] = _capability(
            "available",
            "A frozen chronological tournament fold includes seeded match-bootstrap "
            "skill intervals.",
            "martj42-international-results",
        )
    if simulation:
        capabilities["simulation"] = _capability(
            "available",
            "The resolved four-team 2026 bracket is exactly enumerated from separate Golavo "
            "model voices; it is not a seal.",
            "martj42-international-results",
            "openfootball-worldcup-json",
        )
    if research:
        covered_era = (
            "World Cup 2018" if competition_id == "fifa-world-cup" else "Euro 2016"
        )
        capabilities["research"] = _capability(
            "partial",
            f"Pappalardo/Wyscout team event research covers {covered_era} only.",
            "pappalardo-wyscout-events",
        )
    return {
        "competition_id": competition_id,
        "slug": slug,
        "display_name": display_name,
        "team_scope": "international",
        "jurisdiction": jurisdiction,
        "source_competition_names": source_names,
        "format_eras": format_eras,
        "capabilities": capabilities,
    }


_COMPETITIONS: tuple[dict[str, Any], ...] = (
    _domestic(
        "england-premier-league",
        "premier-league",
        "Premier League",
        "English Premier League",
        "openfootball-england",
    ),
    _domestic("spain-la-liga", "la-liga", "La Liga", "La Liga", "openfootball-espana"),
    _domestic(
        "germany-bundesliga", "bundesliga", "Bundesliga", "Bundesliga", "openfootball-deutschland"
    ),
    _domestic("italy-serie-a", "serie-a", "Serie A", "Serie A", "openfootball-italy"),
    # France has no repo of its own upstream; Ligue 1 ships in openfootball/europe.
    _domestic("france-ligue-1", "ligue-1", "Ligue 1", "Ligue 1", "openfootball-europe"),
    _uefa_club(
        "uefa-champions-league",
        "champions-league",
        "UEFA Champions League",
        coverage="2020/21 through 2025/26",
        began="2020/21",
    ),
    _uefa_club(
        "uefa-europa-league",
        "europa-league",
        "UEFA Europa League",
        coverage="2020/21 through 2024/25",
        began="2020/21",
    ),
    _uefa_club(
        "uefa-conference-league",
        "conference-league",
        "UEFA Conference League",
        coverage="2021/22 through 2024/25",
    ),
    _international(
        "fifa-world-cup",
        "world-cup-2026",
        "FIFA World Cup",
        ["FIFA World Cup"],
        [_format("fifa-world-cup-2026", "48-team finals era", "2026", None)],
        research=True,
        report_card=True,
        simulation=True,
        jurisdiction="fifa-international",
    ),
    _international(
        "uefa-euro",
        "euro",
        "UEFA European Championship",
        ["UEFA Euro"],
        [
            _format("uefa-euro-finals-2020", "24-team finals era", "2020", "2024"),
        ],
        research=True,
        report_card=True,
    ),
    _international(
        "uefa-euro-qualification",
        "euro-qualification",
        "UEFA Euro qualification",
        ["UEFA Euro qualification"],
        [_format("uefa-euro-qualification-2024", "Euro 2024 qualifying era", "2024", None)],
    ),
    _international(
        "uefa-nations-league",
        "nations-league",
        "UEFA Nations League",
        ["UEFA Nations League"],
        [
            _format("uefa-nations-league-2020", "Pre-quarter-final era", "2020/21", "2022/23"),
            _format("uefa-nations-league-2024", "Quarter-final era", "2024/25", None),
        ],
    ),
    _international(
        "uefa-world-cup-qualification",
        "world-cup-qualification",
        "UEFA World Cup qualification",
        [],
        [
            _format("uefa-world-cup-qualification-2022", "Qatar 2022 cycle", "2022", "2022"),
            _format(
                "uefa-world-cup-qualification-2026",
                "Canada/Mexico/USA 2026 cycle",
                "2026",
                None,
            ),
        ],
    ),
)


def competition_catalog() -> dict[str, Any]:
    """Return a defensive copy of the frozen competition/capability catalog."""
    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "catalog_version": CATALOG_VERSION,
        "scope": {
            "team_category": "mens-senior",
            "club_history": "current-plus-five-completed-seasons",
            "cross_era_default": "strict",
        },
        "refresh_policy": {
            "daily_open_snapshots": "planned",
            "on_demand_open_refresh": "planned",
            "byok_api": "blocked",
            "byok_reason": (
                "football-data.org remains rejected by the verified source registry; "
                "a fresh terms review is required before an adapter can be enabled."
            ),
        },
        "competitions": copy.deepcopy(list(_COMPETITIONS)),
    }


def competition_by_id(competition_id: str) -> dict[str, Any] | None:
    """Return one definition by stable id, or None without fuzzy identity merging."""
    for competition in _COMPETITIONS:
        if competition["competition_id"] == competition_id:
            return copy.deepcopy(competition)
    return None


def competition_id_for_source_name(name: str) -> str | None:
    """Resolve only exact, declared aliases; ambiguous names deliberately return None."""
    for competition in _COMPETITIONS:
        if name in competition["source_competition_names"]:
            return str(competition["competition_id"])
    return None
