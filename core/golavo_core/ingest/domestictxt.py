"""Football.TXT fixture-list loader for the OpenFootball domestic league repos.

football.json (the domestic packs' historical source) stops at 2025-26; the
2026-27 schedules are published only as Football.TXT, in a per-country repo
(``openfootball/england``, ``deutschland``, ``espana``, ``italy``, and
``europe`` for France). This module reads exactly that grammar and emits the
same typed frame ``load_openfootball_table`` produces, so a season's fixtures
join their own league's history rather than arriving as a separate source.

It is deliberately separate from ``footballtxt``: that loader is pinned to the
UEFA club grammar, where every side carries a ``(ENG)`` country suffix and the
file is named ``<season>.<code>.txt``. Domestic files share the surrounding
grammar (title, ``▪`` markers, date lines, kickoff clocks) but not those two
things, so the shared pieces are imported and only the divergent ones redefined.

Two upstream properties are load-bearing and pinned by tests:

* the printed title is upstream's own naming ("Deutsche Bundesliga"), which is
  NOT the label the index carries for that league ("Bundesliga"); the title is
  verified but never becomes the competition identity;
* a kickoff clock is printed once per time group and inherited by the fixtures
  beneath it, and only the first date of a matchday carries its year.

Clocks are venue-local with no timezone token anywhere in the file, so they are
kept as date evidence only — exactly as the football.json loader treats them.
"""

from __future__ import annotations

import re

import pandas as pd

from .footballtxt import _MONTH, _date, _half_time
from .openfootball import LEAGUES, canonical_team

# league code -> the competition title upstream prints in its .txt file. Pinned
# because four of the five differ from LEAGUES' canonical label.
DOMESTIC_TXT_TITLES: dict[str, str] = {
    "en.1": "English Premier League",
    "es.1": "Spain Primera División",
    "de.1": "Deutsche Bundesliga",
    "it.1": "Italian Serie A",
    "fr.1": "French Ligue 1",
}

_TITLE = re.compile(r"^=\s+(?P<title>.+?)\s+(?P<season>\d{4}/\d{2})\s*$")
_MATCHDAY = re.compile(r"^▪\s+Matchday\s+(?P<matchday>\d+)\s*$")
_DATE = re.compile(
    r"^\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
    rf"(?P<month>{'|'.join(_MONTH)})\s+"
    r"(?P<day>\d{1,2})(?:\s+(?P<year>\d{4}))?\s*$"
)
_CLOCK = re.compile(r"^(?P<clock>\d{1,2}:\d{2})\s+(?P<rest>.+)$")
# Domestic sides carry no country suffix, so the result — when present — is
# anchored on the two-or-more spaces that separate it from the away side. Team
# names are single-spaced upstream ("FC Schalke 04"), so a name can never be
# mistaken for a score.
_TEAMS = re.compile(r"^(?P<home>.+?)\s+v\s+(?P<away>.+?)(?:\s{2,}(?P<result>\d.*))?$")
_SCORE = re.compile(r"^(?P<home>\d+)-(?P<away>\d+)(?!\d)")


def _full_time(result: str) -> tuple[int, int] | None:
    match = _SCORE.match(result.strip())
    if match is None:
        return None
    return int(match["home"]), int(match["away"])


def parse_domestic_txt(text: str, *, season: str, league_code: str) -> pd.DataFrame:
    """Parse one pinned domestic Football.TXT season file into typed match rows.

    ``season`` is the pack season ("2026-27"); ``league_code`` is the football.json
    league key ("en.1"), which selects both the expected upstream title and the
    canonical competition label the rows are tagged with.
    """
    try:
        expected_title = DOMESTIC_TXT_TITLES[league_code]
        competition, country = LEAGUES[league_code]
    except KeyError as exc:
        raise ValueError(f"unsupported domestic league code: {league_code!r}") from exc

    rows: list[dict] = []
    current_date: pd.Timestamp | None = None
    current_clock: str | None = None
    current_matchday: int | None = None
    title_seen = False
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        title = _TITLE.match(line)
        if title:
            expected_season = season.replace("-", "/")
            if title["title"] != expected_title or title["season"] != expected_season:
                raise ValueError(
                    f"line {line_number}: domestic Football.TXT title does not match "
                    f"{expected_title} {expected_season}"
                )
            title_seen = True
            continue
        matchday = _MATCHDAY.match(line.strip())
        if matchday:
            current_matchday = int(matchday["matchday"])
            current_date = None
            current_clock = None
            continue
        dated = _DATE.match(line)
        if dated:
            current_date = _date(dated, season)
            current_clock = None
            continue
        if " v " not in line:
            continue
        if current_date is None:
            raise ValueError(f"line {line_number}: match appears before a date header")
        content = line.strip()
        clocked = _CLOCK.match(content)
        if clocked:
            current_clock = clocked["clock"]
            content = clocked["rest"]
        teams = _TEAMS.match(content)
        # A side that parses as a bare score means the real one was dropped
        # upstream; indexing a club called "4-2" would be worse than failing.
        if (
            teams is None
            or not teams["home"].strip()
            or not teams["away"].strip()
            or _SCORE.match(teams["away"].strip())
            or _SCORE.match(teams["home"].strip())
        ):
            raise ValueError(f"line {line_number}: unsupported domestic Football.TXT match syntax")
        result = (teams["result"] or "").strip()
        full_time = _full_time(result)
        half_time = _half_time(result, full_time)
        rows.append(
            {
                "date": current_date,
                "local_time": current_clock,
                "matchday": current_matchday,
                "home_team": canonical_team(teams["home"].strip(), league_code),
                "away_team": canonical_team(teams["away"].strip(), league_code),
                "home_score": full_time[0] if full_time is not None else pd.NA,
                "away_score": full_time[1] if full_time is not None else pd.NA,
                "ht_home_score": half_time[0] if half_time is not None else pd.NA,
                "ht_away_score": half_time[1] if half_time is not None else pd.NA,
                "tournament": competition,
                "city": pd.NA,
                "country": country,
                "neutral": False,
            }
        )
    if not title_seen:
        raise ValueError("domestic Football.TXT file has no competition title")

    frame = pd.DataFrame(
        rows,
        columns=[
            "date",
            "local_time",
            "matchday",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
            "ht_home_score",
            "ht_away_score",
            "tournament",
            "city",
            "country",
            "neutral",
        ],
    )
    frame["home_score"] = frame["home_score"].astype("Int16")
    frame["away_score"] = frame["away_score"].astype("Int16")
    frame["ht_home_score"] = frame["ht_home_score"].astype("Int16")
    frame["ht_away_score"] = frame["ht_away_score"].astype("Int16")
    frame["matchday"] = frame["matchday"].astype("Int16")
    for column in ("local_time", "home_team", "away_team", "tournament", "city", "country"):
        frame[column] = frame[column].astype("string")
    frame["neutral"] = frame["neutral"].astype("boolean")
    frame["is_complete"] = frame[["home_score", "away_score"]].notna().all(axis=1)
    return frame
