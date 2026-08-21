"""Read club → home ground → city out of the openfootball/clubs text files (CC0).

This is the only pinned CC0 source in the repo that names a club's ground, which
is why the venue lane can reach club fixtures at all. It is also the loosest
grammar any pinned source uses, so the reader is deliberately conservative:

* the ground is OPTIONAL and usually absent — 89 of England's 203 clubs carry
  one, 19 of Germany's 208, and Spain and Italy none at all. A club with no
  ``@`` marker yields nothing rather than a guess;
* the fields are positional but ragged across countries (``name, founded,
  @ ground, city`` in England against ``name, city`` in Spain), so the ground is
  located by its marker and never by index;
* only a flush-left line is a club. Alias lines (``|``), postal addresses and
  reserve teams (``ii)``) are indented or prefixed;
* ``#``/``##`` comments can contain commas, so they are stripped before the
  split — otherwise "## Greater London" becomes a field.

Club names are canonicalized through the same ``canonical_team`` the index uses,
so a parsed row keys directly against indexed match rows instead of needing a
second name-fold that could drift from it.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "core"))

from golavo_core.ingest.openfootball import canonical_team  # noqa: E402

# A city may carry a district in parentheses ("London (Fulham)") or a region
# after '›'/'>' ("Paris › Île-de-France"); neither is part of the city name.
_CITY_QUALIFIER = re.compile(r"\s*(?:\(|›|>).*$")


@dataclass(frozen=True)
class ClubGround:
    """One club's pinned home ground, as openfootball prints it."""

    name: str
    team: str
    ground: str
    city: str


@dataclass(frozen=True)
class ClubCity:
    """One club's pinned home city, with the alias names upstream gives it.

    A ground is optional upstream and Spain and Italy state none at all, so the
    ground-bearing reader sees no Spanish or Italian club. A city, though, is
    stated for every club in every one of these files — which is why the city is
    worth reading on its own rather than only as a field beside a ground.
    """

    name: str
    team: str
    city: str
    alias_teams: tuple[str, ...]


def _strip_comment(line: str) -> str:
    return line.split("#", 1)[0]


def _is_club_line(raw_line: str) -> bool:
    """Only a flush-left, non-reserve line introduces a club."""
    return bool(raw_line) and raw_line[0] not in " \t=|" and not raw_line.startswith("ii)")


def _city_from_fields(fields: list[str]) -> str:
    """The city these comma-separated fields state, or "" if they state none.

    Two shapes occur and neither is positional: with a ground marker the city
    follows the ground ("name, 1886, @ ground, city"), and without one the city
    is simply the last field ("name, city" in Spain, "name, 1919, city" in
    France). A bare founding year is the one field that can trail a club line
    without being a city, so a digits-only tail is read as "no city stated"
    rather than as a place called 1919.
    """
    for index, field in enumerate(fields[1:], start=1):
        if field.startswith("@"):
            return fields[index + 1].strip() if index + 1 < len(fields) else ""
    if len(fields) < 2:
        return ""
    tail = fields[-1].strip()
    return "" if not tail or tail.isdigit() else tail


def parse_club_cities(text: str, *, league_code: str) -> list[ClubCity]:
    """Every club in ``text`` that states a home city, in file order.

    Each club's indented ``|`` alias lines are collected with it, because the
    index's canonical name for a club is often one of those aliases rather than
    the headline name upstream prints — "Atalanta" against "Atalanta Bergamo".
    A reserve-team (``ii)``) line ends the current club so its aliases are never
    read as the senior side's.
    """
    clubs: list[ClubCity] = []
    pending: list[str] = []
    current: dict[str, str] | None = None

    def flush() -> None:
        if current is None:
            return
        aliases = tuple(
            dict.fromkeys(
                canonical_team(alias, league_code) for alias in pending if alias
            )
        )
        clubs.append(
            ClubCity(
                name=current["name"],
                team=current["team"],
                city=current["city"],
                alias_teams=aliases,
            )
        )

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if raw_line.startswith("ii)"):
            flush()
            current, pending = None, []
            continue
        if stripped.startswith("|"):
            if current is not None:
                pending.extend(
                    part.strip()
                    for part in _strip_comment(stripped).lstrip("|").split("|")
                    if part.strip()
                )
            continue
        if not _is_club_line(raw_line):
            continue
        line = _strip_comment(raw_line).strip()
        if not line:
            continue
        fields = [field.strip() for field in line.split(",")]
        city = _CITY_QUALIFIER.sub("", _city_from_fields(fields)).strip()
        if not fields[0] or not city:
            flush()
            current, pending = None, []
            continue
        flush()
        current = {
            "name": fields[0],
            "team": canonical_team(fields[0], league_code),
            "city": city,
        }
        pending = []
    flush()
    return clubs


def parse_clubs_txt(text: str, *, league_code: str) -> list[ClubGround]:
    """Every club in ``text`` that declares a home ground, in file order."""
    clubs: list[ClubGround] = []
    for raw_line in text.splitlines():
        if not raw_line or raw_line[0] in " \t=|" or raw_line.startswith("ii)"):
            continue
        line = _strip_comment(raw_line).strip()
        if not line or "@" not in line:
            continue
        fields = [field.strip() for field in line.split(",")]
        name = fields[0]
        ground = ""
        city = ""
        for index, field in enumerate(fields[1:], start=1):
            if field.startswith("@"):
                ground = field[1:].strip()
                city = fields[index + 1].strip() if index + 1 < len(fields) else ""
                break
        if not name or not ground or not city:
            continue
        clubs.append(
            ClubGround(
                name=name,
                team=canonical_team(name, league_code),
                ground=ground,
                city=_CITY_QUALIFIER.sub("", city).strip(),
            )
        )
    return clubs
