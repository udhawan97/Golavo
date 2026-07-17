"""openfootball (football.json) ingestion into Golavo's canonical match table.

Produces exactly the same typed frame as the martj42 loader so every downstream
model, evaluation, and seal path is source-agnostic. One pack per league; the
league is read from each season file's name (``<season>.<code>.json``) and
tagged with the registry competition below. Only a well-formed ``score.ft``
two-integer object counts as a completed result; openfootball's divergent
``[0, 0]`` list encoding and empty ``{}`` scores (partial captures) are treated
as INCOMPLETE, never fabricated as real results. See
docs/handoff/openfootball-audit.md.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd

from .snapshot import validate_pack

# league code -> (competition label, country). The single registry every
# openfootball consumer (loader, audit, evaluation) keys off.
LEAGUES: dict[str, tuple[str, str]] = {
    "en.1": ("English Premier League", "England"),
    "es.1": ("La Liga", "Spain"),
    "de.1": ("Bundesliga", "Germany"),
    "it.1": ("Serie A", "Italy"),
    "fr.1": ("Ligue 1", "France"),
}
SEASON_FILE = re.compile(r"^(?P<season>\d{4}-\d{2})\.(?P<code>[a-z]{2}\.\d)\.json$")
# football.json stops at 2025-26; later seasons are published only as
# Football.TXT fixture lists, pinned into this same pack so a fixture keeps its
# own league's history (see ingest.domestictxt).
SEASON_TXT_FILE = re.compile(r"^(?P<season>\d{4}-\d{2})\.(?P<code>[a-z]{2}\.\d)\.txt$")

_SUFFIX = re.compile(r"\s+(?:FC|AFC)$")
_PREFIX = re.compile(r"^AFC\s+")

# Evidence-based canonicalization for the non-English leagues. openfootball
# switched to formal legal names in 2020-21 (fr.1: 2023-24); the fragmentation
# report (scripts/check_team_fragmentation.py, docs/handoff/team-canonicalization.md)
# enumerates every observed raw variant. Rules below collapse legal-form tokens;
# _ALIASES carries the drift the rules cannot see. Two safety properties are
# machine-checked over the pinned packs: canonicalization is injective within
# every season, and adjudicated distinct clubs (Chievo Verona vs Hellas Verona,
# AC Ajaccio vs Gazélec Ajaccio, Paris FC vs Paris Saint-Germain) stay distinct.
_DROP_ANYWHERE = frozenset({"FC", "CF"})
_LEAD_TOKENS = frozenset({
    "AC", "ACF", "AJ", "AS", "CA", "CD", "Calcio", "EA", "FSV", "OGC", "RC",
    "RCD", "SC", "SD", "SM", "SS", "SSC", "SV", "SpVgg", "TSG", "UC", "UD",
    "US", "VfB", "VfL",
})
_TRAIL_TOKENS = frozenset({
    "AC", "BC", "Balompié", "CFC", "Calcio", "FCO", "HSC", "OSC", "SC", "SCO",
    "UD",
})
_ALIASES: dict[str, dict[str, str]] = {
    "uefa": {
        "Club Atlético de Madrid": "Atlético Madrid",
        "FC Internazionale Milano": "Inter",
        "Olympique de Marseille": "Marseille",
        "Olympique Marseille": "Marseille",
        "Lazio Roma": "Lazio",
        "Real Sociedad de Fútbol": "Real Sociedad",
        "Bor. Mönchengladbach": "Borussia Mönchengladbach",
        "Olympique Lyonnais": "Lyon",
        "Racing Club de Lens": "Lens",
    },
    "es.1": {
        "Club Atlético de Madrid": "Atlético Madrid",
        "RCD Espanyol de Barcelona": "Espanyol",
        "Espanyol Barcelona": "Espanyol",
        "Real Sociedad de Fútbol": "Real Sociedad",
        "Rayo Vallecano de Madrid": "Rayo Vallecano",
        "RC Celta": "Celta Vigo",
        "RC Celta de Vigo": "Celta Vigo",
        "Deportivo Alavés": "Alavés",
        "Real Racing Club de Santander": "Racing Santander",
    },
    "de.1": {
        "Bor. Mönchengladbach": "Borussia Mönchengladbach",
        # A deep-history club (1963-64+) the token rules would mangle: the pure-digit
        # filter drops '1860', leaving the meaningless 'TSV München'.
        "TSV 1860 München": "1860 München",
    },
    "it.1": {
        "FC Internazionale Milano": "Inter",
        "Lazio Roma": "Lazio",
        "SPAL 2013 Ferrara": "SPAL",
    },
    "fr.1": {
        "Olympique Lyonnais": "Lyon",
        "Olympique Marseille": "Marseille",
        "Olympique de Marseille": "Marseille",
        "Nîmes Olympique": "Nîmes",
        "Racing Club de Lens": "Lens",
        "RC Strasbourg Alsace": "Strasbourg",
        "Girondins Bordeaux": "Bordeaux",
        "ESTAC Troyes": "Troyes",
        # The 2026-27 fixture list prints Troyes a third way; without this the
        # promoted side would be a new club to every model and the table.
        "ES Troyes AC": "Troyes",
    },
}


def _strip_legal_tokens(name: str) -> str:
    tokens = [t for t in name.split() if t.rstrip(".") and not t.rstrip(".").isdigit()]
    tokens = [t for t in tokens if t not in _DROP_ANYWHERE]
    while len(tokens) > 1 and tokens[0] in _LEAD_TOKENS:
        tokens.pop(0)
    while len(tokens) > 1 and tokens[-1] in _TRAIL_TOKENS:
        tokens.pop()
    return " ".join(tokens) or name


def canonical_team(name: str, league: str = "en.1") -> str:
    """Collapse openfootball's cross-season naming drift ('Arsenal FC' -> 'Arsenal').

    The en.1 path is byte-for-byte the Phase 1 behavior (match_ids depend on it).
    """
    raw = str(name).strip()
    if league == "en.1":
        collapsed = _PREFIX.sub("", raw)
        return _SUFFIX.sub("", collapsed).strip()
    alias = _ALIASES.get(league, {}).get(raw)
    if alias is not None:
        return alias
    return _strip_legal_tokens(raw)


def _extract_ft(match: dict) -> tuple[int, int] | None:
    score = match.get("score")
    if isinstance(score, dict):
        ft = score.get("ft")
        if isinstance(ft, list) and len(ft) == 2 and all(isinstance(x, int) for x in ft):
            return ft[0], ft[1]
    return None


def _extract_ht(match: dict) -> tuple[int, int] | None:
    """Return a recorded half-time score, never an inferred one."""
    score = match.get("score")
    if isinstance(score, dict):
        ht = score.get("ht")
        if isinstance(ht, list) and len(ht) == 2 and all(type(x) is int for x in ht):
            return ht[0], ht[1]
    return None


def load_openfootball_table(pack_dir: Path) -> pd.DataFrame:
    """Load a validated openfootball pack into Golavo's deterministic match table."""
    from .domestictxt import parse_domestic_txt  # lazy: domestictxt imports this module

    manifest = validate_pack(pack_dir)
    rows: list[dict] = []
    for entry in sorted(manifest["files"], key=lambda e: e["name"]):
        name = entry["name"]
        fixtures = SEASON_TXT_FILE.match(name)
        if fixtures is not None:
            code = fixtures["code"]
            if code not in LEAGUES:
                raise ValueError(f"{pack_dir / name}: unknown league code {code!r}")
            frame = parse_domestic_txt(
                (pack_dir / name).read_text(encoding="utf-8"),
                season=fixtures["season"],
                league_code=code,
            )
            expected = entry.get("source_match_count")
            if expected is not None and len(frame) != int(expected):
                raise ValueError(
                    f"{pack_dir / name}: parsed {len(frame)} matches, expected {expected}"
                )
            # 'local_time' is the same venue-local, timezone-less clock the
            # football.json path calls 'time', so both formats reach the shared
            # tail with one schema and it is dropped in one place.
            rows.extend(
                frame.drop(columns=["matchday", "is_complete"])
                .rename(columns={"local_time": "time"})
                .to_dict("records")
            )
            continue
        parsed = SEASON_FILE.match(name)
        if parsed is None:
            continue  # license text, etc.
        code = parsed["code"]
        if code not in LEAGUES:
            raise ValueError(f"{pack_dir / name}: unknown league code {code!r}")
        competition, country = LEAGUES[code]
        data = json.loads((pack_dir / name).read_text(encoding="utf-8"))
        for match in data.get("matches", []):
            ft = _extract_ft(match)
            ht = _extract_ht(match)
            if ht is not None and ft is not None and (ht[0] > ft[0] or ht[1] > ft[1]):
                raise ValueError(
                    f"{pack_dir / name}: half-time score exceeds full-time score"
                )
            rows.append(
                {
                    "date": match.get("date"),
                    "time": match.get("time"),
                    "home_team": canonical_team(match.get("team1"), code),
                    "away_team": canonical_team(match.get("team2"), code),
                    "home_score": ft[0] if ft is not None else pd.NA,
                    "away_score": ft[1] if ft is not None else pd.NA,
                    "ht_home_score": ht[0] if ht is not None else pd.NA,
                    "ht_away_score": ht[1] if ht is not None else pd.NA,
                    "tournament": competition,
                    "city": pd.NA,
                    "country": country,
                    "neutral": False,
                }
            )
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"])
    frame["home_score"] = frame["home_score"].astype("Int16")
    frame["away_score"] = frame["away_score"].astype("Int16")
    frame["ht_home_score"] = frame["ht_home_score"].astype("Int16")
    frame["ht_away_score"] = frame["ht_away_score"].astype("Int16")
    for column in ("home_team", "away_team", "tournament", "city", "country"):
        frame[column] = frame[column].astype("string")
    frame["neutral"] = frame["neutral"].astype("boolean")
    if (frame[["home_score", "away_score"]].dropna() < 0).any().any():
        raise ValueError("openfootball pack contains a negative score")

    frame = frame.sort_values(
        ["date", "home_team", "away_team"], kind="mergesort"
    ).reset_index(drop=True)
    identities = frame.apply(
        lambda r: "|".join(
            [
                r["date"].date().isoformat(),
                str(r["home_team"]),
                str(r["away_team"]),
                str(r["tournament"]),
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

    # Upstream clocks are venue-local but the pack has no venue timezone. Treat
    # them as date evidence only: labeling a naive local clock as UTC would be a
    # false instant and could silently move a pre-kickoff cutoff by hours.
    frame["kickoff_utc"] = pd.to_datetime(frame["date"], utc=True)
    frame["kickoff_precision"] = pd.Series("day", index=frame.index, dtype="string")
    frame["is_complete"] = frame[["home_score", "away_score"]].notna().all(axis=1)
    return frame.drop(columns=["time"])
