"""Minimal, audited Football.TXT loader for OpenFootball UEFA club packs.

This is deliberately not a general-purpose Football.TXT implementation.  It
accepts the exact schedule/result grammar used by the pinned Champions League,
Europa League and Conference League files and fails loudly when a line carrying
`` v `` cannot be parsed.  Cancelled ties are counted for source-completeness
audits but excluded from the canonical match table so they cannot appear as
historical "upcoming" fixtures.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import pandas as pd

from .openfootball import canonical_team
from .snapshot import validate_pack

UEFA_SOURCE_ID = "openfootball-champions-league"
SEASON_FILE = re.compile(
    r"^(?P<season>\d{4}-\d{2})\.(?P<code>cl|el|conf)\.txt$"
)
_TITLE = re.compile(r"^=\s+(?P<title>.+?)\s+(?P<season>\d{4}/\d{2})\s*$")
_STAGE = re.compile(r"^▪\s+(?P<stage>.+?)\s*$")
_DATE = re.compile(
    r"^\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
    r"(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
    r"(?P<day>\d{1,2})(?:\s+(?P<year>\d{4}))?\s*$"
)
_CLOCK = re.compile(r"^(?P<clock>\d{1,2}:\d{2})\s+(?P<rest>.+)$")
_TEAMS = re.compile(
    r"^(?P<home>.+?\s\([A-Z]{3}\))\s+v\s+"
    r"(?P<away>.+?\s\([A-Z]{3}\))(?:\s+(?P<result>.*))?$"
)
_COUNTRY_SUFFIX = re.compile(r"\s+\([A-Z]{3}\)$")
_SCORE = re.compile(r"(?<!\d)(?P<home>\d+)-(?P<away>\d+)(?!\d)")
_PENALTY_MATCH_SCORE = re.compile(
    r"pen\.\s+(?P<home>\d+)-(?P<away>\d+)\s+a\.e\.t\."
)
_PARENTHETICAL = re.compile(r"\((?P<body>[^()]*)\)\s*(?:\[[^]]+\])?\s*$")

_MONTH = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def _score(result: str) -> tuple[int, int] | None:
    if "[cancelled]" in result:
        return None
    penalty = _PENALTY_MATCH_SCORE.search(result)
    match = penalty or _SCORE.search(result)
    if match is None:
        return None
    return int(match["home"]), int(match["away"])


def _half_time(result: str, full_time: tuple[int, int] | None) -> tuple[int, int] | None:
    if full_time is None:
        return None
    parenthetical = _PARENTHETICAL.search(result)
    if parenthetical is None:
        return None
    scores = list(_SCORE.finditer(parenthetical["body"]))
    if not scores:
        return None
    candidate = int(scores[-1]["home"]), int(scores[-1]["away"])
    if candidate[0] > full_time[0] or candidate[1] > full_time[1]:
        raise ValueError("Football.TXT half-time score exceeds the match score")
    return candidate


def _date(match: re.Match[str], season: str) -> pd.Timestamp:
    first_year = int(season[:4])
    month = _MONTH[match["month"]]
    explicit = match["year"]
    year = int(explicit) if explicit else first_year if month >= 7 else first_year + 1
    return pd.Timestamp(year=year, month=month, day=int(match["day"]))


def parse_footballtxt(text: str, *, season: str, competition: str) -> pd.DataFrame:
    """Parse one pinned UEFA main-competition file into typed match rows."""
    rows: list[dict[str, Any]] = []
    current_date: pd.Timestamp | None = None
    current_stage = "Unspecified"
    current_clock: str | None = None
    title_seen = False
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.rstrip()
        title = _TITLE.match(line)
        if title:
            expected_season = season.replace("-", "/")
            if title["title"] != competition or title["season"] != expected_season:
                raise ValueError(
                    f"line {line_number}: Football.TXT title does not match "
                    f"{competition} {expected_season}"
                )
            title_seen = True
            continue
        stage = _STAGE.match(line.strip())
        if stage:
            current_stage = stage["stage"].strip()
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
        if teams is None:
            raise ValueError(f"line {line_number}: unsupported Football.TXT match syntax")
        result = (teams["result"] or "").strip()
        full_time = _score(result)
        half_time = _half_time(result, full_time)
        home_raw = _COUNTRY_SUFFIX.sub("", teams["home"]).strip()
        away_raw = _COUNTRY_SUFFIX.sub("", teams["away"]).strip()
        rows.append(
            {
                "date": current_date,
                "local_time": current_clock,
                "home_team": canonical_team(home_raw, "uefa"),
                "away_team": canonical_team(away_raw, "uefa"),
                "home_score": full_time[0] if full_time is not None else pd.NA,
                "away_score": full_time[1] if full_time is not None else pd.NA,
                "ht_home_score": half_time[0] if half_time is not None else pd.NA,
                "ht_away_score": half_time[1] if half_time is not None else pd.NA,
                "tournament": competition,
                "city": pd.NA,
                "country": "Europe",
                "neutral": False,
                "season": season,
                "stage": current_stage,
                "result_status": "cancelled" if "[cancelled]" in result else "played",
            }
        )
    if not title_seen:
        raise ValueError("Football.TXT file has no competition title")
    return pd.DataFrame(rows)


def load_footballtxt_table(pack_dir: Path) -> pd.DataFrame:
    """Load and integrity-check one pinned UEFA competition sourcepack."""
    manifest = validate_pack(pack_dir)
    if manifest.get("source_id") != UEFA_SOURCE_ID:
        raise ValueError(f"{pack_dir}: not an OpenFootball UEFA club pack")
    competition = str(manifest.get("competition") or "")
    frames: list[pd.DataFrame] = []
    for entry in sorted(manifest["files"], key=lambda item: item["name"]):
        parsed = SEASON_FILE.match(str(entry["name"]))
        if parsed is None:
            continue
        frame = parse_footballtxt(
            (pack_dir / entry["name"]).read_text(encoding="utf-8"),
            season=parsed["season"],
            competition=competition,
        )
        expected = int(entry["source_match_count"])
        if len(frame) != expected:
            raise ValueError(
                f"{pack_dir / entry['name']}: parsed {len(frame)} matches, expected {expected}"
            )
        cancelled = int(frame["result_status"].eq("cancelled").sum())
        if cancelled != int(entry.get("cancelled_match_count", 0)):
            raise ValueError(f"{pack_dir / entry['name']}: cancelled-match count drift")
        frames.append(frame.loc[frame["result_status"] != "cancelled"].copy())
    if not frames:
        raise ValueError(f"{pack_dir}: no UEFA Football.TXT season files")
    frame = pd.concat(frames, ignore_index=True)
    frame["home_score"] = frame["home_score"].astype("Int16")
    frame["away_score"] = frame["away_score"].astype("Int16")
    frame["ht_home_score"] = frame["ht_home_score"].astype("Int16")
    frame["ht_away_score"] = frame["ht_away_score"].astype("Int16")
    for column in (
        "home_team",
        "away_team",
        "tournament",
        "city",
        "country",
        "season",
        "stage",
    ):
        frame[column] = frame[column].astype("string")
    frame["neutral"] = frame["neutral"].astype("boolean")
    frame["is_complete"] = frame[["home_score", "away_score"]].notna().all(axis=1)
    frame["kickoff_utc"] = pd.to_datetime(frame["date"], utc=True)
    frame["kickoff_precision"] = pd.Series("day", index=frame.index, dtype="string")
    frame = frame.sort_values(
        ["date", "home_team", "away_team"], kind="mergesort"
    ).reset_index(drop=True)
    identities = frame.apply(
        lambda row: "|".join(
            [
                row["date"].date().isoformat(),
                str(row["home_team"]),
                str(row["away_team"]),
                str(row["tournament"]),
                str(row["season"]),
            ]
        ),
        axis=1,
    )
    occurrences = identities.groupby(identities, sort=False).cumcount()
    frame.insert(
        0,
        "match_id",
        [
            f"m_{hashlib.sha256(f'{identity}|{occurrence}'.encode()).hexdigest()[:16]}"
            for identity, occurrence in zip(identities, occurrences, strict=True)
        ],
    )
    return frame.drop(columns=["local_time", "result_status"])
