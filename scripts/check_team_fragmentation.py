#!/usr/bin/env python3
"""Team-name fragmentation evidence + canonicalization proof for openfootball packs.

Ran BEFORE the per-league canonicalizers were written (evidence first), and kept
as the machine-checked proof afterwards. It does two things:

1. EVIDENCE — for every league pack, list each distinct raw team name with its
   season span, and cluster raw names under an aggressive normalization key
   (accent-stripped, casefolded, legal-form stop tokens dropped). Multi-variant
   clusters are candidate same-club drift; the full raw list is also printed
   because aggressive clustering can *under*-merge (e.g. 'Inter' vs
   'FC Internazionale Milano' share no key), so a human adjudicated the final
   mapping — see docs/handoff/team-canonicalization.md.

2. PROOF — verify the shipped ``canonical_team`` against the pinned packs:
   - injective within every season (two coexisting clubs never merge);
   - every adjudicated same-club pair maps to one canonical name
     (no cross-season fragmentation);
   - every adjudicated distinct pair stays distinct (including clubs that never
     coexisted in a season, which injectivity alone cannot protect);
   - the distinct canonical club count per league matches the adjudicated count.

Exits non-zero on any violation. Writes docs/handoff/team-canonicalization.md.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

from golavo_core.ingest.openfootball import LEAGUES, SEASON_FILE, canonical_team

PACKS = {
    "en.1": Path("packs/openfootball-eng-pl"),
    "es.1": Path("packs/openfootball-esp-ll"),
    "de.1": Path("packs/openfootball-deu-bl"),
    "it.1": Path("packs/openfootball-ita-sa"),
    "fr.1": Path("packs/openfootball-fra-l1"),
}
OUT_MD = Path("docs/handoff/team-canonicalization.md")

_STOP = {
    "fc", "afc", "cf", "ac", "as", "ss", "ssc", "us", "uc", "ud", "cd", "ca",
    "rc", "rcd", "sd", "sc", "sco", "osc", "hsc", "fco", "bc", "bsc", "cfc",
    "acf", "aj", "ea", "ogc", "sm", "sv", "vfb", "vfl", "tsg", "spvgg", "fsv",
    "club", "calcio", "futbol", "fussball", "football", "balompie", "1",
}

# Adjudicated same-club drift (must merge). Sources: the raw-name evidence below,
# plus club history for the two non-obvious ones — 'Parma FC' -> 'Parma Calcio
# 1913' is the 2015 bankruptcy/refoundation treated as one sporting identity,
# and 'Bor. Mönchengladbach' is an upstream abbreviation of Borussia
# Mönchengladbach.
SAME_CLUB = {
    "en.1": [
        ("Manchester City", "Manchester City FC"),
        ("Sheffield United", "Sheffield United FC"),
    ],
    "es.1": [
        ("Atlético Madrid", "Club Atlético de Madrid"),
        ("Espanyol Barcelona", "RCD Espanyol de Barcelona"),
        ("Real Betis", "Real Betis Balompié"),
        ("Real Madrid", "Real Madrid CF"),
        ("Real Sociedad", "Real Sociedad de Fútbol"),
        ("Real Valladolid", "Real Valladolid CF"),
        ("CD Alavés", "Deportivo Alavés"),
        ("RC Celta", "RC Celta de Vigo"),
        ("Rayo Vallecano", "Rayo Vallecano de Madrid"),
    ],
    "de.1": [
        ("Bayer Leverkusen", "Bayer 04 Leverkusen"),
        ("Bayern München", "FC Bayern München"),
        ("SpVgg Greuther Fürth", "SpVgg Greuther Fürth 1903"),
        ("1899 Hoffenheim", "TSG 1899 Hoffenheim"),
        ("Bor. Mönchengladbach", "Borussia Mönchengladbach"),
        ("FC St. Pauli", "FC St. Pauli 1910"),
        ("Werder Bremen", "SV Werder Bremen"),
    ],
    "it.1": [
        ("Bologna FC", "Bologna FC 1909"),
        ("Hellas Verona", "Hellas Verona FC"),
        ("Juventus", "Juventus FC"),
        ("Parma FC", "Parma Calcio 1913"),
        ("Sassuolo Calcio", "US Sassuolo Calcio"),
        ("Atalanta", "Atalanta BC"),
        ("Inter", "FC Internazionale Milano"),
        ("Lazio Roma", "SS Lazio"),
        ("Sampdoria", "UC Sampdoria"),
    ],
    "fr.1": [
        ("Olympique Marseille", "Olympique de Marseille"),
        ("AS Monaco", "AS Monaco FC"),
        ("Paris Saint-Germain", "Paris Saint-Germain FC"),
        ("Stade Rennais", "Stade Rennais FC 1901"),
        ("RC Lens", "Racing Club de Lens"),
        ("RC Strasbourg", "RC Strasbourg Alsace"),
    ],
}

# Adjudicated distinct clubs that a careless rule could merge; several never
# coexisted in one season, so within-season injectivity alone cannot catch them.
DISTINCT_CLUBS = {
    "es.1": [
        ("Real Madrid", "Club Atlético de Madrid"),
        ("Deportivo La Coruña", "Deportivo Alavés"),
    ],
    "de.1": [("Borussia Dortmund", "Borussia Mönchengladbach")],
    "it.1": [("Chievo Verona", "Hellas Verona"), ("Inter", "AC Milan")],
    "fr.1": [("AC Ajaccio", "Gazélec FC Ajaccio"), ("Paris FC", "Paris Saint-Germain")],
}

# Distinct canonical club counts, adjudicated from the evidence lists.
EXPECTED_CLUB_COUNTS = {"en.1": 41, "es.1": 33, "de.1": 32, "it.1": 38, "fr.1": 34}


def _norm_key(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    tokens = [
        t
        for t in re.split(r"[^a-z0-9]+", s.casefold())
        if t and t not in _STOP and not t.isdigit()
    ]
    return " ".join(tokens)


def _raw_names(pack_dir: Path, code: str) -> dict[str, list[str]]:
    seasons: dict[str, set[str]] = defaultdict(set)
    for path in sorted(pack_dir.iterdir()):
        parsed = SEASON_FILE.match(path.name)
        if parsed is None or parsed["code"] != code:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for match in data.get("matches", []):
            seasons[parsed["season"]].update([match["team1"], match["team2"]])
    name_spans: dict[str, list[str]] = defaultdict(list)
    for season in sorted(seasons):
        for name in seasons[season]:
            name_spans[name].append(season)
    return dict(name_spans)


def audit_league(code: str, pack_dir: Path) -> tuple[list[str], list[str]]:
    """Return (markdown lines, failures) for one league."""
    failures: list[str] = []
    name_spans = _raw_names(pack_dir, code)
    seasons: dict[str, set[str]] = defaultdict(set)
    for name, spans in name_spans.items():
        for season in spans:
            seasons[season].add(name)

    clusters: dict[str, list[str]] = defaultdict(list)
    for name in sorted(name_spans):
        clusters[_norm_key(name)].append(name)
    multi = {k: v for k, v in clusters.items() if len(v) > 1}

    canon = {name: canonical_team(name, code) for name in name_spans}

    # Proof 1: within-season injectivity.
    for season in sorted(seasons):
        raw = seasons[season]
        mapped = defaultdict(list)
        for name in raw:
            mapped[canon[name]].append(name)
        for canonical, variants in mapped.items():
            if len(variants) > 1:
                failures.append(
                    f"{code} {season}: {variants} collapse to {canonical!r} within one season"
                )

    # Proof 2: adjudicated same-club pairs merge.
    for a, b in SAME_CLUB.get(code, []):
        if a in canon and b in canon and canon[a] != canon[b]:
            failures.append(f"{code}: {a!r} -> {canon[a]!r} but {b!r} -> {canon[b]!r}")

    # Proof 3: adjudicated distinct clubs stay distinct.
    for a, b in DISTINCT_CLUBS.get(code, []):
        if a in canon and b in canon and canon[a] == canon[b]:
            failures.append(f"{code}: distinct clubs {a!r} and {b!r} merged to {canon[a]!r}")

    # Proof 4: club count matches the adjudicated evidence.
    n_clubs = len(set(canon.values()))
    if n_clubs != EXPECTED_CLUB_COUNTS[code]:
        failures.append(
            f"{code}: {n_clubs} canonical clubs, adjudicated {EXPECTED_CLUB_COUNTS[code]}"
        )

    competition = LEAGUES[code][0]
    lines = [
        f"## {competition} (`{code}`)",
        "",
        f"- raw names: {len(name_spans)} | canonical clubs: {n_clubs} "
        f"(adjudicated: {EXPECTED_CLUB_COUNTS[code]})",
        f"- multi-variant normalization clusters: {len(multi)}",
        "",
        "| Raw name | Seasons | Canonical |",
        "|---|---|---|",
    ]
    for name in sorted(name_spans):
        spans = name_spans[name]
        mark = "" if canon[name] == name else " ⟶"
        lines.append(f"| {name}{mark} | {spans[0]} → {spans[-1]} ({len(spans)}) | {canon[name]} |")
    lines.append("")
    return lines, failures


def main() -> None:
    all_lines = [
        "# openfootball team-name fragmentation & canonicalization",
        "",
        "Evidence-first: the raw-name inventory below was generated from the pinned",
        "packs BEFORE the per-league canonicalizers were written; the mapping encodes",
        "the human adjudication of that evidence, and this script re-proves it on",
        "every run. Properties proved: (1) canonicalization is injective within every",
        "season; (2) every adjudicated same-club drift pair merges (no cross-season",
        "fragmentation); (3) adjudicated distinct clubs never merge — including pairs",
        "that never coexisted (AC Ajaccio vs Gazélec Ajaccio, Paris FC vs",
        "Paris Saint-Germain, Chievo Verona vs Hellas Verona); (4) per-league distinct",
        "club counts match the adjudicated evidence.",
        "",
        "Judgment call, stated openly: `Parma FC` (to 2014-15) and `Parma Calcio 1913`",
        "(2018-19 on) are the 2015 bankruptcy/refoundation of the same sporting",
        "identity and are merged as `Parma`, matching common football-statistical",
        "practice. A ratings model is barely affected either way — the club was out",
        "of Serie A for three seasons in between.",
        "",
    ]
    failures: list[str] = []
    for code, pack_dir in PACKS.items():
        lines, league_failures = audit_league(code, pack_dir)
        all_lines.extend(lines)
        failures.extend(league_failures)

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(all_lines), encoding="utf-8")
    print(f"wrote {OUT_MD}")
    if failures:
        print("FRAGMENTATION PROOF FAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        raise SystemExit(1)
    print("canonicalization proof: OK (injectivity, merges, distinctness, counts)")


if __name__ == "__main__":
    main()
