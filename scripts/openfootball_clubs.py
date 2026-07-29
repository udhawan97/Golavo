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


def _strip_comment(line: str) -> str:
    return line.split("#", 1)[0]


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
