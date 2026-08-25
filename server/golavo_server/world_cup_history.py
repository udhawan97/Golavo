"""Read-only archive over the isolated, hash-verified World Cup history pack."""

from __future__ import annotations

from typing import Any

from golavo_core.facts import WorldCupHistory, load_wc_history

HISTORY_SCHEMA_VERSION = "0.1.0"
_CATEGORY_LABELS = {
    "men": "Men's World Cup",
    "women": "Women's World Cup",
}


def _team_pedigree(history: WorldCupHistory) -> list[dict[str, Any]]:
    standings = history.standings
    appearances = history.appearances.drop_duplicates(["tournament_id", "team_id"])
    rows: list[dict[str, Any]] = []
    for team_id, team_appearances in appearances.groupby("team_id", sort=False):
        name = str(team_appearances.iloc[0]["team_name"])
        code = str(team_appearances.iloc[0]["team_code"])
        finishes = standings.loc[standings["team_id"].eq(team_id)]
        titles = finishes.loc[finishes["position"].eq(1)]
        best_finish = int(finishes["position"].min()) if not finishes.empty else None
        rows.append(
            {
                "team_id": str(team_id),
                "team_name": name,
                "team_code": code,
                "appearances": int(team_appearances["tournament_id"].nunique()),
                "titles": int(len(titles)),
                "title_years": sorted(int(year) for year in titles["year"]),
                "finals": int(finishes["position"].isin([1, 2]).sum()),
                "best_finish": best_finish,
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            -row["titles"],
            -row["finals"],
            -row["appearances"],
            row["team_name"],
        ),
    )


def _tournaments(history: WorldCupHistory) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tournament_id, standings in history.standings.groupby("tournament_id", sort=False):
        standings = standings.sort_values("position", kind="mergesort")
        first = standings.iloc[0]
        awards = history.awards.loc[history.awards["tournament_id"].eq(tournament_id)]
        rows.append(
            {
                "tournament_id": str(tournament_id),
                "tournament_name": str(first["tournament_name"]),
                "year": int(first["year"]),
                "ended_on": first["end_date"].date().isoformat(),
                "standings": [
                    {
                        "position": int(row.position),
                        "team_id": str(row.team_id),
                        "team_name": str(row.team_name),
                        "team_code": str(row.team_code),
                    }
                    for row in standings.itertuples()
                ],
                "awards": [
                    {
                        "award": str(row.award_name),
                        "player": str(row.player),
                        "team_name": str(row.team_name),
                        "team_code": str(row.team_code),
                    }
                    for row in awards.itertuples()
                ],
            }
        )
    return sorted(rows, key=lambda row: row["year"], reverse=True)


def build() -> dict[str, Any]:
    """Return both history lanes without merging them into forecast data."""
    histories = [load_wc_history(category=category) for category in ("women", "men")]
    if any(history is None for history in histories):
        raise FileNotFoundError("the bundled World Cup history pack is unavailable")
    present = [history for history in histories if history is not None]
    first = present[0]
    categories: list[dict[str, Any]] = []
    for history in present:
        tournaments = _tournaments(history)
        categories.append(
            {
                "id": history.category,
                "label": _CATEGORY_LABELS[history.category],
                "tournament_count": len(tournaments),
                "first_year": min(row["year"] for row in tournaments),
                "last_year": max(row["year"] for row in tournaments),
                "pedigree": _team_pedigree(history),
                "tournaments": tournaments,
            }
        )
    return {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "source": {
            "source_id": first.source_id,
            "name": "The Fjelstul World Cup Database",
            "creator": "Joshua C. Fjelstul, Ph.D.",
            "copyright_notice": "© 2022 Joshua C. Fjelstul, Ph.D.",
            "license": first.license,
            "license_url": "https://creativecommons.org/licenses/by-sa/4.0/legalcode",
            "url": first.source_url,
            "upstream_ref": first.upstream_ref,
            "retrieved_at_utc": first.retrieved_at_utc,
            "modification_note": (
                "Golavo selects and summarizes pinned tournament, standings, "
                "appearance, and award rows."
            ),
        },
        "categories": categories,
    }
