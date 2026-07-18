"""openfootball/worldcup.json parsing: exact kickoff times + a fail-closed cross-check.

worldcup.json (CC0) carries what martj42's date-only internationals feed lacks: an
exact kickoff time with an explicit UTC offset, plus venue and round context. Golavo
does NOT model from this source — martj42 remains the sole training truth. This module
extracts two things:

* an **exact-kickoff overlay** (date, teams, tournament -> precise UTC instant) that
  ``ingest.load_matches`` splices onto the matching internationals rows, so a World Cup
  seal's window closes at the real kickoff instead of the conservative 00:00 UTC proxy;
* a **cross-check** of every completed World Cup result against a reference (martj42)
  frame — any disagreement is returned to the caller, which fails the build closed.

Knockout fixtures whose participants are unresolved appear as ``W101``/``L102``
placeholders; those rows are rejected until the bracket resolves. martj42 records the
result after extra time but before penalties, so the cross-check compares worldcup.json's
``et`` when present and ``ft`` otherwise (never the shootout score).
"""

from __future__ import annotations

import re
from datetime import timedelta, timezone

import pandas as pd

from ..identity import fixture_key_strings

TOURNAMENT = "FIFA World Cup"

# "13:00 UTC-6" -> hour, minute, offset-hours. The offset is the venue's UTC offset.
_TIME_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})\s+UTC([+-]\d{1,2})\s*$")
# An unresolved knockout slot: 'W101' (winner of match 101), 'L102' (loser of 102).
_PLACEHOLDER_RE = re.compile(r"^[WL]\d+$")


def is_placeholder(team: str) -> bool:
    """True for an unresolved knockout participant token (``W101``/``L102``)."""
    return bool(_PLACEHOLDER_RE.match(str(team).strip()))


def parse_kickoff(date_str: str, time_str: str | None) -> pd.Timestamp | None:
    """Parse a local ``date`` + ``"HH:MM UTC±O"`` into a precise UTC instant.

    Returns ``None`` when the time is missing or malformed, so a fixture with no
    usable clock is simply not overlaid (it keeps the date-only proxy).
    """
    if not isinstance(time_str, str):
        return None
    match = _TIME_RE.match(time_str)
    if match is None:
        return None
    hour, minute, offset = int(match[1]), int(match[2]), int(match[3])
    local = pd.Timestamp(f"{date_str}T{hour:02d}:{minute:02d}:00")
    aware = local.tz_localize(timezone(timedelta(hours=offset)))
    return aware.tz_convert("UTC")


def final_score(score: object) -> tuple[int, int] | None:
    """The regulation/extra-time result (never penalties), or None if not final.

    Prefers ``et`` (a match decided in extra time) over ``ft`` (decided in 90'),
    matching what martj42 records so the cross-check compares like with like.
    """
    if not isinstance(score, dict):
        return None
    for key in ("et", "ft"):
        value = score.get(key)
        if isinstance(value, list) and len(value) == 2 and all(isinstance(x, int) for x in value):
            return int(value[0]), int(value[1])
    return None


def parse_worldcup(data: dict) -> pd.DataFrame:
    """Parse a worldcup.json document into a typed fixture frame.

    Columns: date, home_team, away_team, tournament, city, kickoff_utc,
    home_score, away_score, is_complete. Placeholder (unresolved) knockout rows
    are dropped; rows without a parseable kickoff are dropped (they cannot enrich
    anything). Deterministic order: by kickoff, then teams.
    """
    rows: list[dict] = []
    for match in data.get("matches", []):
        home, away = match.get("team1"), match.get("team2")
        if home is None or away is None or is_placeholder(home) or is_placeholder(away):
            continue
        date_str = match.get("date")
        kickoff = parse_kickoff(date_str, match.get("time"))
        if date_str is None or kickoff is None:
            continue
        score = final_score(match.get("score"))
        rows.append(
            {
                "date": pd.Timestamp(date_str),
                "home_team": str(home),
                "away_team": str(away),
                "tournament": TOURNAMENT,
                "city": match.get("ground"),
                "kickoff_utc": kickoff,
                "home_score": pd.NA if score is None else score[0],
                "away_score": pd.NA if score is None else score[1],
                "is_complete": score is not None,
            }
        )
    frame = pd.DataFrame(
        rows,
        columns=[
            "date", "home_team", "away_team", "tournament", "city",
            "kickoff_utc", "home_score", "away_score", "is_complete",
        ],
    )
    if frame.empty:
        return frame
    frame["home_score"] = frame["home_score"].astype("Int16")
    frame["away_score"] = frame["away_score"].astype("Int16")
    frame["kickoff_utc"] = pd.to_datetime(frame["kickoff_utc"], utc=True)
    return frame.sort_values(
        ["kickoff_utc", "home_team", "away_team"], kind="mergesort"
    ).reset_index(drop=True)


def kickoff_overlay(parsed: pd.DataFrame) -> pd.DataFrame:
    """The (date, teams, tournament -> kickoff_utc) table written as a pack's kickoffs.csv."""
    if parsed.empty:
        return pd.DataFrame(columns=["date", "home_team", "away_team", "tournament", "kickoff_utc"])
    overlay = parsed[["date", "home_team", "away_team", "tournament", "kickoff_utc"]].copy()
    return overlay.sort_values(
        ["kickoff_utc", "home_team", "away_team"], kind="mergesort"
    ).reset_index(drop=True)


def _match_key(frame: pd.DataFrame) -> pd.Series:
    return fixture_key_strings(frame)


def missing_fixtures(
    parsed: pd.DataFrame, reference: pd.DataFrame, city_country: dict[str, str]
) -> pd.DataFrame:
    """Scheduled World Cup fixtures present in worldcup.json but absent from the reference.

    Returns rows shaped like martj42's results.csv (scores blank) so they can be appended
    to an internationals pack: the fixture and its venue come from worldcup.json (CC0),
    while training still draws only on the pack's real results. Only fixtures whose city
    resolves to a country (via ``city_country``, built from worldcup's stadiums file) are
    emitted — a missing mapping fails closed rather than writing a null-country row. World
    Cup knockout venues are neutral for both sides.
    """
    columns = [
        "date", "home_team", "away_team", "home_score", "away_score",
        "tournament", "city", "country", "neutral",
    ]
    if parsed.empty:
        return pd.DataFrame(columns=columns)
    scheduled = parsed[~parsed["is_complete"]]
    if scheduled.empty:
        return pd.DataFrame(columns=columns)
    have = set(_match_key(reference)) if not reference.empty else set()
    rows: list[dict] = []
    for key, row in zip(_match_key(scheduled), scheduled.itertuples(index=False), strict=True):
        if key in have:
            continue
        city = None if row.city is None else str(row.city)
        country = city_country.get(city or "")
        if not country:
            raise ValueError(
                f"no country mapping for World Cup venue {city!r} "
                f"({row.home_team} v {row.away_team}); refusing to write a null-country row"
            )
        rows.append(
            {
                "date": pd.Timestamp(row.date).strftime("%Y-%m-%d"),
                "home_team": row.home_team,
                "away_team": row.away_team,
                "home_score": pd.NA,
                "away_score": pd.NA,
                "tournament": TOURNAMENT,
                "city": city,
                "country": country,
                "neutral": True,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def crosscheck_completed(parsed: pd.DataFrame, reference: pd.DataFrame) -> list[dict]:
    """Return every completed World Cup result that DISAGREES with the reference frame.

    Matched on normalized (date, home, away). A worldcup.json result that the reference
    also has completed but with a different score is a disagreement; the caller must
    fail closed on a non-empty result. Rows the reference lacks (or has scheduled) are
    not disagreements — they are simply unverifiable here, never a silent pass.
    """
    if parsed.empty or reference.empty:
        return []

    _key = fixture_key_strings

    ref = reference.copy()
    ref_complete = ref[ref["is_complete"].astype("boolean").fillna(False)]
    ref_map = dict(
        zip(
            _key(ref_complete),
            zip(ref_complete["home_score"], ref_complete["away_score"], strict=True),
            strict=True,
        )
    )
    disagreements: list[dict] = []
    done = parsed[parsed["is_complete"]]
    for key, home, away, hs, as_ in zip(
        _key(done),
        done["home_team"],
        done["away_team"],
        done["home_score"],
        done["away_score"],
        strict=True,
    ):
        ref_score = ref_map.get(key)
        if ref_score is None:
            continue
        if (int(ref_score[0]), int(ref_score[1])) != (int(hs), int(as_)):
            disagreements.append(
                {
                    "date": key.split("|", 1)[0],
                    "home_team": home,
                    "away_team": away,
                    "worldcup": [int(hs), int(as_)],
                    "reference": [int(ref_score[0]), int(ref_score[1])],
                }
            )
    return disagreements
