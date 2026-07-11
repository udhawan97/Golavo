#!/usr/bin/env python3
"""Audit the vendored openfootball top-league packs for club-coverage fitness.

This is the club-coverage GATE (Phase 1 for the English Premier League, Phase 2
for La Liga, Bundesliga, Serie A, and Ligue 1). It is allowed to fail honestly.
It writes docs/handoff/openfootball-audit.{md,json} with an explicit PASS/FAIL
per criterion and a per-league scope verdict:

- ACCEPT_HISTORICAL : a usable run of clean completed seasons exists to build on.
- REJECT            : completeness/consistency fails; the league stays out.

Correctness is assessed as double-round-robin structural integrity derived from
the ACTUAL team count n per season (n*(n-1) matches; every team n-1 home and
n-1 away; no self-matches; no duplicate ordered pairs), which catches
transcription corruption without depending on a second source. Because a
season that silently dropped one club entirely would still be self-consistent
(n-1 teams, (n-1)(n-2) matches), the actual team count must ALSO equal the
league's constitutional size for that season: 20 for the Premier League,
La Liga, and Serie A; 18 for the Bundesliga; 20 for Ligue 1 through 2022-23 and
18 from 2023-24.

A result counts as COMPLETE only when ``score.ft`` is a two-integer list.
Openfootball's divergent ``[0, 0]`` LIST encoding (uniformly zero, only in
2025-26 captures) and empty ``{}``/missing scores are treated as INCOMPLETE —
never fabricated as real results. Incomplete seasons are excluded from the
clean set but their *played* matches remain legitimate training evidence.
Independent second-source cross-checking (footballcsv) stays DEFERRED: it is
stale to ~2020/21 and uses divergent team names.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from golavo_core.ingest.openfootball import LEAGUES
from golavo_core.ingest.snapshot import validate_pack

PACKS = {
    "en.1": Path("packs/openfootball-eng-pl"),
    "es.1": Path("packs/openfootball-esp-ll"),
    "de.1": Path("packs/openfootball-deu-bl"),
    "it.1": Path("packs/openfootball-ita-sa"),
    "fr.1": Path("packs/openfootball-fra-l1"),
}
OUT_MD = Path("docs/handoff/openfootball-audit.md")
OUT_JSON = Path("docs/handoff/openfootball-audit.json")
UPSTREAM_COMMIT_DATE = "2026-05-30"  # commit a5dd38b, from the pinned manifest ref
MIN_CLEAN_SEASONS = 10  # enough for chronological train + multi-fold backtest
SEASON_FILE = re.compile(r"^(?P<season>\d{4}-\d{2})\.(?P<code>[a-z]{2}\.\d)\.json$")

# Constitutional league sizes (not derived from the files, by design — see module
# docstring). Ligue 1 contracted from 20 to 18 clubs starting with 2023-24.
EXPECTED_TEAMS = {"en.1": 20, "es.1": 20, "de.1": 18, "it.1": 20, "fr.1": 20}
LIGUE1_18_FROM = "2023-24"


def expected_team_count(code: str, season: str) -> int:
    if code == "fr.1" and season >= LIGUE1_18_FROM:
        return 18
    return EXPECTED_TEAMS[code]


def _extract_ft(match: dict) -> tuple[int, int] | None:
    """Return (home, away) only for a well-formed dict `score.ft`; else None."""
    score = match.get("score")
    if isinstance(score, dict):
        ft = score.get("ft")
        if isinstance(ft, list) and len(ft) == 2 and all(isinstance(x, int) for x in ft):
            return ft[0], ft[1]
    return None


def _season_stats(code: str, season: str, name: str, matches: list[dict]) -> dict:
    teams: set[str] = set()
    home_count: dict[str, int] = {}
    away_count: dict[str, int] = {}
    ordered_pairs: dict[tuple, int] = {}
    complete = 0
    negative = 0
    self_matches = 0
    anomalous_encoding = 0
    dates: list[str] = []
    for m in matches:
        t1, t2 = m.get("team1"), m.get("team2")
        teams.update([t1, t2])
        home_count[t1] = home_count.get(t1, 0) + 1
        away_count[t2] = away_count.get(t2, 0) + 1
        ordered_pairs[(t1, t2)] = ordered_pairs.get((t1, t2), 0) + 1
        if t1 == t2:
            self_matches += 1
        if isinstance(m.get("score"), list):
            anomalous_encoding += 1
        ft = _extract_ft(m)
        if ft is not None:
            complete += 1
            if ft[0] < 0 or ft[1] < 0:
                negative += 1
        if m.get("date"):
            dates.append(m["date"])
    n_teams = len(teams)
    expected_teams = expected_team_count(code, season)
    expected_matches = n_teams * (n_teams - 1)  # double round robin from ACTUAL n
    home_vals = sorted(home_count.values())
    away_vals = sorted(away_count.values())
    stats = {
        "season": season,
        "name": name,
        "n_matches": len(matches),
        "n_complete": complete,
        "n_anomalous_encoding": anomalous_encoding,
        "n_teams": n_teams,
        "expected_teams": expected_teams,
        "expected_matches": expected_matches,
        "self_matches": self_matches,
        "negative_scores": negative,
        "duplicate_ordered_pairs": sum(1 for v in ordered_pairs.values() if v > 1),
        "home_per_team_range": [home_vals[0], home_vals[-1]] if home_vals else [0, 0],
        "away_per_team_range": [away_vals[0], away_vals[-1]] if away_vals else [0, 0],
        "date_min": min(dates) if dates else None,
        "date_max": max(dates) if dates else None,
    }
    stats["reasons"] = _flag_reasons(stats)
    stats["clean"] = not stats["reasons"]
    return stats


def _flag_reasons(s: dict) -> list[str]:
    per_side = s["n_teams"] - 1
    reasons = []
    if s["n_teams"] != s["expected_teams"]:
        reasons.append(f"team-count mismatch: {s['n_teams']} teams, league size is {s['expected_teams']}")
    if s["n_matches"] != s["expected_matches"]:
        reasons.append(f"{s['n_matches']} fixtures, double round robin needs {s['expected_matches']}")
    if s["n_complete"] != s["n_matches"]:
        reasons.append(f"{s['n_matches'] - s['n_complete']} of {s['n_matches']} results missing")
    if s["n_anomalous_encoding"]:
        reasons.append(f"{s['n_anomalous_encoding']} divergent [0, 0] list-encoded scores")
    if s["self_matches"]:
        reasons.append(f"{s['self_matches']} self-matches")
    if s["negative_scores"]:
        reasons.append(f"{s['negative_scores']} negative scores")
    if s["duplicate_ordered_pairs"]:
        reasons.append(f"{s['duplicate_ordered_pairs']} duplicate ordered home/away pairs")
    if s["home_per_team_range"] != [per_side, per_side]:
        reasons.append(f"home matches per team {s['home_per_team_range']}, expected {per_side}")
    if s["away_per_team_range"] != [per_side, per_side]:
        reasons.append(f"away matches per team {s['away_per_team_range']}, expected {per_side}")
    return reasons


def audit_league(pack_dir: Path, code: str) -> dict:
    """Audit one league pack; returns the per-league verdict block."""
    manifest = validate_pack(pack_dir)  # provenance: bytes match manifest hashes
    competition = LEAGUES[code][0]
    if manifest.get("competition") != competition:
        raise ValueError(
            f"{pack_dir}: manifest competition {manifest.get('competition')!r} "
            f"!= registry {competition!r}"
        )
    seasons: dict[str, dict] = {}
    for entry in manifest["files"]:
        parsed = SEASON_FILE.match(entry["name"])
        if parsed is None:
            continue
        if parsed["code"] != code:
            raise ValueError(f"{pack_dir}: unexpected league file {entry['name']}")
        season = parsed["season"]
        data = json.loads((pack_dir / entry["name"]).read_text(encoding="utf-8"))
        seasons[season] = _season_stats(
            code, season, data.get("name", ""), data.get("matches", [])
        )

    clean = sorted(s for s, st in seasons.items() if st["clean"])
    flagged = sorted(s for s, st in seasons.items() if not st["clean"])
    latest_clean = clean[-1] if clean else None

    criteria = {
        "usable_clean_seasons": len(clean) >= MIN_CLEAN_SEASONS,
        "structural_consistency_all_seasons": all(
            st["self_matches"] == 0
            and st["negative_scores"] == 0
            and st["duplicate_ordered_pairs"] == 0
            and st["n_teams"] == st["expected_teams"]
            for st in seasons.values()
        ),
        "latest_completed_season_clean": latest_clean is not None,
        "three_recent_clean_folds": len(clean) >= 3,
    }
    verdict = "ACCEPT_HISTORICAL" if all(criteria.values()) else "REJECT"
    return {
        "code": code,
        "competition": competition,
        "pack": str(pack_dir),
        "upstream_ref": manifest["upstream_ref"],
        "n_seasons": len(seasons),
        "clean_seasons": clean,
        "flagged_seasons": flagged,
        "flag_reasons": {s: seasons[s]["reasons"] for s in flagged},
        "latest_clean_season": latest_clean,
        "fold_seasons": clean[-3:] if len(clean) >= 3 else [],
        "criteria": criteria,
        "verdict": verdict,
        "seasons": seasons,
    }


def run_audit(packs: dict[str, Path] = PACKS) -> dict:
    leagues = {code: audit_league(pack_dir, code) for code, pack_dir in packs.items()}
    return {
        "upstream_ref": next(iter(leagues.values()))["upstream_ref"],
        "upstream_commit_date": UPSTREAM_COMMIT_DATE,
        "min_clean_seasons": MIN_CLEAN_SEASONS,
        "live_in_season_updating": "UNVERIFIED until the 2026-27 season starts",
        "independent_cross_source": (
            "DEFERRED (footballcsv stale to ~2020/21; divergent team names)"
        ),
        "cross_league_calibration": (
            "NONE — domestic files carry no inter-league matches, so each league is "
            "modeled independently and strengths are NOT comparable across leagues"
        ),
        "leagues": leagues,
    }


def _league_md(result: dict) -> list[str]:
    c = result["criteria"]
    clean = result["clean_seasons"]
    span = f"{clean[0]} → {clean[-1]}" if clean else "none"
    lines = [
        f"## {result['competition']} (`{result['code']}`) — **{result['verdict']}**",
        "",
        f"- **Pack:** `{result['pack']}`",
        f"- **Seasons vendored:** {result['n_seasons']}",
        f"- **Clean seasons:** {len(clean)} ({span})",
        f"- **Flagged seasons:** {', '.join(result['flagged_seasons']) or 'none'}",
        f"- **Backtest folds (3 most recent clean):** {', '.join(result['fold_seasons']) or 'n/a'}",
        "",
        "| Criterion | Result | Basis |",
        "|---|---|---|",
        f"| Usable clean seasons (≥{MIN_CLEAN_SEASONS}) | {'PASS' if c['usable_clean_seasons'] else 'FAIL'} "
        f"| {len(clean)} complete double-round-robin seasons |",
        f"| Structural consistency (all seasons) | {'PASS' if c['structural_consistency_all_seasons'] else 'FAIL'} "
        "| no self-matches, negative scores, duplicate ordered pairs, or team-count mismatches |",
        f"| Latest clean season present | {'PASS' if c['latest_completed_season_clean'] else 'FAIL'} "
        f"| {result['latest_clean_season']} |",
        f"| Three recent clean folds | {'PASS' if c['three_recent_clean_folds'] else 'FAIL'} "
        f"| {', '.join(result['fold_seasons']) or 'unavailable'} |",
    ]
    if result["flagged_seasons"]:
        lines += ["", "**Excluded seasons and why:**", ""]
        for season in result["flagged_seasons"]:
            reasons = "; ".join(result["flag_reasons"][season])
            lines.append(f"- `{season}` — {reasons}")
    lines += [
        "",
        "| Season | Fixtures | Complete | Anomalous | Teams | Home/team | Away/team | Clean |",
        "|---|--:|--:|--:|--:|:--:|:--:|:--:|",
    ]
    for season in sorted(result["seasons"]):
        s = result["seasons"][season]
        lines.append(
            f"| {season} | {s['n_matches']} | {s['n_complete']} | {s['n_anomalous_encoding']} | "
            f"{s['n_teams']} | {s['home_per_team_range'][0]}–{s['home_per_team_range'][1]} | "
            f"{s['away_per_team_range'][0]}–{s['away_per_team_range'][1]} | "
            f"{'yes' if s['clean'] else 'NO'} |"
        )
    lines.append("")
    return lines


def _write_reports(result: dict) -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    leagues = result["leagues"]
    lines = [
        "# openfootball top-league coverage audit (club gate)",
        "",
        f"- **Source:** openfootball/football.json pinned at `{result['upstream_ref']}` "
        f"(committed {result['upstream_commit_date']}), CC0-1.0",
        "- **Scope:** men's top-5 European leagues, HISTORICAL completed seasons only — not live",
        f"- **Live in-season updating:** {result['live_in_season_updating']}",
        f"- **Independent cross-source correctness:** {result['independent_cross_source']}",
        f"- **Cross-league calibration:** {result['cross_league_calibration']}",
        "",
        "| League | Verdict | Clean seasons | Flagged | Backtest folds |",
        "|---|---|---|---|---|",
    ]
    for code in sorted(leagues):
        r = leagues[code]
        clean = r["clean_seasons"]
        span = f"{len(clean)} ({clean[0]} → {clean[-1]})" if clean else "0"
        lines.append(
            f"| {r['competition']} | **{r['verdict']}** | {span} | "
            f"{', '.join(r['flagged_seasons']) or 'none'} | {', '.join(r['fold_seasons']) or 'n/a'} |"
        )
    lines += [
        "",
        "A season is **clean** only when, with n = the actual number of teams in the file:",
        "it has exactly n·(n−1) fixtures, every one carrying a well-formed two-integer",
        "`score.ft`; every team plays exactly n−1 home and n−1 away; there are no",
        "self-matches, duplicate ordered pairs, or negative scores; and n equals the",
        "league's constitutional size for that season (20 for the Premier League, La Liga,",
        "Serie A; 18 for the Bundesliga; 20 for Ligue 1 through 2022-23, 18 from 2023-24 —",
        "the last check catches a season that silently dropped a whole club, which the",
        "derived-n arithmetic alone cannot see).",
        "",
        "## Recurring anomalies (why seasons are excluded)",
        "",
        "- **Partial 2025-26 captures (every league).** The pin was taken 2026-05-30;",
        "  unfinalized results appear either as a divergent `[0, 0]` LIST encoding (seen",
        "  in no completed season, uniformly zero — the signature of placeholders, not real",
        "  goalless draws) or as empty `{}` scores. Golavo treats both as INCOMPLETE and",
        "  never fabricates them as results.",
        "- **La Liga & Serie A 2024-25.** The entire final Matchday 38 (10 fixtures each,",
        "  played 2025-05-23/25) has empty `{}` scores at this capture — the seasons were",
        "  completed in reality, but this snapshot's record of them is incomplete, so they",
        "  are excluded rather than patched from a second source.",
        "- **Ligue 1 2019-20.** Abandoned early in the COVID-19 pandemic: 101 of 380",
        "  listed fixtures (Matchday 28 onward) were never played. Excluded as a test",
        "  fold; its 279 played matches remain legitimate training evidence.",
        "",
        "Incomplete seasons are excluded from the clean set, never fabricated. Played",
        "matches inside them still count as training rows — they really happened; what is",
        "missing is the remainder of the season, which only disqualifies the season as a",
        "*test fold*.",
        "",
    ]
    for code in sorted(leagues):
        lines += _league_md(leagues[code])
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    result = run_audit()
    _write_reports(result)
    for code in sorted(result["leagues"]):
        r = result["leagues"][code]
        clean = r["clean_seasons"]
        span = f"{clean[0]} → {clean[-1]}" if clean else "none"
        print(f"{r['competition']:<24} {r['verdict']:<17} clean={len(clean)} ({span}) "
              f"flagged={r['flagged_seasons']}")
    print(f"wrote {OUT_MD} and {OUT_JSON}")


if __name__ == "__main__":
    main()
