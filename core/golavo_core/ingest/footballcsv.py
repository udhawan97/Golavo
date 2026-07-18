"""footballcsv historical CSV loader (deep pre-2010 league history).

footballcsv (github.com/footballcsv) is a CC0, public-domain 1:1 mirror of the
openfootball datasets in a flat one-row-per-match CSV. It carries decades the
bundled football.json packs stop short of — the Bundesliga from 1963-64, the
Premier League from 1992-93 — so Golavo folds the PRE-2010 slice in as era-badged
history that never overlaps (and so never duplicates) the football.json rows.

The grammar is the same across leagues bar two drifts the parser absorbs, both
verified against the committed files:

* the first column header is ``Round`` (England) or ``Matchday`` (Germany);
* the score separator is an ASCII hyphen in older files and an EN DASH (U+2013)
  from 2020-21 — either is accepted.

Team names are canonicalized through the SAME ``openfootball.canonical_team`` the
league packs use, so a club reads identically across the two sources. Those rules
were tuned on the post-2010 club set, so ``test_deep_history_names_canonicalize_injectively``
re-checks them over this disjoint deep-history set in CI (the standalone fragmentation
gate covers only the openfootball packs). One deep-history club the token rules would
mangle — 1860 München, whose ``1860`` the digit filter drops — carries an explicit alias.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import pandas as pd

from .matchframe import mint_match_ids
from .openfootball import LEAGUES, canonical_team
from .snapshot import validate_pack

# footballcsv pack season file: '1963-64.de.1.csv'.
SEASON_FILE = re.compile(r"^(?P<season>\d{4}-\d{2})\.(?P<code>[a-z]{2}\.\d)\.csv$")

# footballcsv league code -> football.json league code (which selects the
# canonical competition label and canonicalization alias table).
FOOTBALLCSV_LEAGUES: dict[str, str] = {
    "en.1": "en.1",
    "de.1": "de.1",
}

# A score cell: two integers separated by a hyphen or an en dash. Anything else
# (a blank, a placeholder) is treated as an unplayed row, never fabricated as 0-0.
_SCORE = re.compile(r"^\s*(?P<home>\d+)\s*[-–]\s*(?P<away>\d+)\s*$")
_DATE = re.compile(
    r"^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
    r"(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
    r"(?P<day>\d{1,2})\s+(?P<year>\d{4})$"
)
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


def _score(cell: str) -> tuple[int, int] | None:
    match = _SCORE.match(cell)
    if match is None:
        return None
    return int(match["home"]), int(match["away"])


def _date(cell: str) -> pd.Timestamp:
    match = _DATE.match(cell.strip())
    if match is None:
        raise ValueError(f"unparseable footballcsv date: {cell!r}")
    return pd.Timestamp(
        year=int(match["year"]), month=_MONTH[match["month"]], day=int(match["day"])
    )


def parse_footballcsv(text: str, *, league_code: str) -> pd.DataFrame:
    """Parse one footballcsv season into Golavo's typed match frame.

    ``league_code`` is the football.json key ("en.1"), which sets the canonical
    competition label, country, and canonicalization rules. Unplayed rows (blank
    score) are kept as incomplete; a score cell that is present but unparseable is
    a hard error, never silently dropped.
    """
    try:
        competition, country = LEAGUES[FOOTBALLCSV_LEAGUES[league_code]]
    except KeyError as exc:
        raise ValueError(f"unsupported footballcsv league: {league_code!r}") from exc

    rows: list[dict] = []
    reader = csv.DictReader(io.StringIO(text))
    for line_number, record in enumerate(reader, start=2):
        home_raw = (record.get("Team 1") or "").strip()
        away_raw = (record.get("Team 2") or "").strip()
        if not home_raw or not away_raw:
            continue
        score_cell = (record.get("FT") or "").strip()
        score = _score(score_cell) if score_cell else None
        if score_cell and score is None:
            raise ValueError(f"line {line_number}: unparseable score {score_cell!r}")
        rows.append(
            {
                "date": _date(record["Date"]),
                "home_team": canonical_team(home_raw, league_code),
                "away_team": canonical_team(away_raw, league_code),
                "home_score": score[0] if score is not None else pd.NA,
                "away_score": score[1] if score is not None else pd.NA,
                "tournament": competition,
                "city": pd.NA,
                "country": country,
                "neutral": False,
            }
        )

    frame = pd.DataFrame(
        rows,
        columns=[
            "date",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
            "tournament",
            "city",
            "country",
            "neutral",
        ],
    )
    frame["home_score"] = frame["home_score"].astype("Int16")
    frame["away_score"] = frame["away_score"].astype("Int16")
    # footballcsv carries no half-time scores; they are a first-class unknown,
    # never fabricated, and typed to match the openfootball loader's schema.
    frame["ht_home_score"] = pd.Series(pd.NA, index=frame.index, dtype="Int16")
    frame["ht_away_score"] = pd.Series(pd.NA, index=frame.index, dtype="Int16")
    for column in ("home_team", "away_team", "tournament", "city", "country"):
        frame[column] = frame[column].astype("string")
    frame["neutral"] = frame["neutral"].astype("boolean")
    frame["is_complete"] = frame[["home_score", "away_score"]].notna().all(axis=1)
    return frame


def load_footballcsv_table(pack_dir: Path) -> pd.DataFrame:
    """Load and integrity-check one footballcsv history pack into the match table.

    Concatenates every declared season CSV, assigns match ids namespaced to
    footballcsv (so they never collide with an openfootball row for the same
    fixture), and stamps day-precision kickoffs — these are historical rows with
    no time of day. The output frame matches the openfootball loader's schema so
    the index build is source-agnostic.
    """
    manifest = validate_pack(pack_dir)
    source_id = str(manifest.get("source_id", ""))
    frames: list[pd.DataFrame] = []
    for entry in sorted(manifest["files"], key=lambda item: item["name"]):
        parsed = SEASON_FILE.match(str(entry["name"]))
        if parsed is None:
            continue  # license text, notes, etc.
        frame = parse_footballcsv(
            (pack_dir / entry["name"]).read_text(encoding="utf-8"),
            league_code=parsed["code"],
        )
        expected = entry.get("source_match_count")
        if expected is not None and len(frame) != int(expected):
            raise ValueError(
                f"{pack_dir / entry['name']}: parsed {len(frame)} matches, expected {expected}"
            )
        frames.append(frame)
    if not frames:
        raise ValueError(f"{pack_dir}: no footballcsv season files")

    frame = pd.concat(frames, ignore_index=True)
    frame = frame.sort_values(["date", "home_team", "away_team"], kind="mergesort").reset_index(
        drop=True
    )
    frame = mint_match_ids(
        frame,
        ["date", "home_team", "away_team", "tournament"],
        prefix=source_id,
    )
    frame["kickoff_utc"] = pd.to_datetime(frame["date"], utc=True)
    frame["kickoff_precision"] = pd.Series("day", index=frame.index, dtype="string")
    return frame
