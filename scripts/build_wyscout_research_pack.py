#!/usr/bin/env python3
"""Build compact, team-only research artifacts from the public Wyscout corpus.

The raw event archive is intentionally never copied into the repository or app.
This builder reads one competition at a time, emits aggregate team rows, and
records the transformation and source hashes in the isolated pack manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

GRID_X, GRID_Y = 12, 8
CELLS = GRID_X * GRID_Y
SUCCESSFUL = 1801
GOAL = 101

SPECS = {
    "England": ("england-premier-league", "Premier League", "2017/18"),
    "Spain": ("spain-la-liga", "La Liga", "2017/18"),
    "Germany": ("germany-bundesliga", "Bundesliga", "2017/18"),
    "Italy": ("italy-serie-a", "Serie A", "2017/18"),
    "France": ("france-ligue-1", "Ligue 1", "2017/18"),
    "European_Championship": ("uefa-euro", "UEFA Euro", "2016"),
    "World_Cup": ("fifa-world-cup", "FIFA World Cup", "2018"),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cell(position: dict[str, Any]) -> int:
    x = min(99.999, max(0.0, float(position.get("x", 0))))
    y = min(99.999, max(0.0, float(position.get("y", 0))))
    return int(y * GRID_Y / 100) * GRID_X + int(x * GRID_X / 100)


def _tags(event: dict[str, Any]) -> set[int]:
    return {int(tag["id"]) for tag in event.get("tags", []) if "id" in tag}


def _is_shot(event: dict[str, Any]) -> bool:
    return event.get("eventName") == "Shot" or event.get("subEventName") in {
        "Free kick shot",
        "Penalty",
    }


def _solve_xt(
    actions: list[int],
    shots: list[int],
    goals: list[int],
    transitions: Counter[tuple[int, int]],
) -> list[float]:
    """Solve a disclosed 12x8 positive-transition research xT grid."""
    values = [0.0] * CELLS
    for _ in range(100):
        updated: list[float] = []
        for origin in range(CELLS):
            denom = actions[origin]
            if not denom:
                updated.append(0.0)
                continue
            shot_value = (goals[origin] / shots[origin]) if shots[origin] else 0.0
            immediate = (shots[origin] / denom) * shot_value
            continuation = sum(
                (count / denom) * values[destination]
                for (start, destination), count in transitions.items()
                if start == origin
            )
            updated.append(immediate + continuation)
        if max(abs(a - b) for a, b in zip(values, updated, strict=True)) < 1e-10:
            values = updated
            break
        values = updated
    return values


def build_competition(
    events: list[dict[str, Any]],
    matches: list[dict[str, Any]],
    team_names: dict[int, str],
    *,
    competition_id: str,
    competition_name: str,
    era: str,
) -> dict[str, Any]:
    stats: dict[int, Counter[str]] = defaultdict(Counter)
    team_moves: dict[int, Counter[tuple[int, int]]] = defaultdict(Counter)
    actions, shots, goals = ([0] * CELLS for _ in range(3))
    transitions: Counter[tuple[int, int]] = Counter()

    for match in matches:
        for raw_id in match.get("teamsData", {}):
            stats[int(raw_id)]["matches"] += 1

    active: tuple[int, int, float, float, int] | None = None

    def close_chain() -> None:
        nonlocal active
        if active is None:
            return
        _match_id, team_id, start_x, end_x, event_count = active
        stats[team_id]["chains"] += 1
        stats[team_id]["chain_events"] += event_count
        if end_x - start_x >= 20:
            stats[team_id]["progressive_chains"] += 1
        active = None

    for event in events:
        team_id = int(event.get("teamId") or 0)
        positions = event.get("positions") or []
        if not team_id or not positions:
            continue
        match_id = int(event.get("matchId") or 0)
        start_x = float(positions[0].get("x", 0))
        end_x = float(positions[-1].get("x", start_x))
        if active is None or active[0] != match_id or active[1] != team_id:
            close_chain()
            active = (match_id, team_id, start_x, end_x, 1)
        else:
            active = (match_id, team_id, active[2], end_x, active[4] + 1)

        origin = _cell(positions[0])
        event_tags = _tags(event)
        if event.get("eventName") == "Pass":
            actions[origin] += 1
            stats[team_id]["passes"] += 1
            if SUCCESSFUL in event_tags and len(positions) > 1:
                destination = _cell(positions[-1])
                stats[team_id]["completed_passes"] += 1
                transitions[(origin, destination)] += 1
                team_moves[team_id][(origin, destination)] += 1
                if end_x - start_x >= 20:
                    stats[team_id]["progressive_passes"] += 1
        elif _is_shot(event):
            actions[origin] += 1
            shots[origin] += 1
            stats[team_id]["shots"] += 1
            if GOAL in event_tags:
                goals[origin] += 1
                stats[team_id]["goals"] += 1
    close_chain()

    xt = _solve_xt(actions, shots, goals, transitions)
    rows = []
    for team_id, row in stats.items():
        played = int(row["matches"])
        if not played:
            continue
        xt_created = sum(
            count * max(0.0, xt[destination] - xt[origin])
            for (origin, destination), count in team_moves[team_id].items()
        )
        passes_attempted = int(row["passes"])
        rows.append(
            {
                "team_id": team_id,
                "team": team_names.get(team_id, f"Team {team_id}"),
                "matches": played,
                "passes_attempted": passes_attempted,
                "passes_completed": int(row["completed_passes"]),
                "pass_completion_pct": round(100 * row["completed_passes"] / passes_attempted, 1)
                if passes_attempted
                else 0.0,
                "progressive_passes_per_match": round(row["progressive_passes"] / played, 2),
                "shots_per_match": round(row["shots"] / played, 2),
                "goals_per_match": round(row["goals"] / played, 2),
                "chain_proxy_events": int(row["chain_events"]),
                "chain_proxy_count": int(row["chains"]),
                "progressive_chains_per_match": round(row["progressive_chains"] / played, 2),
                "research_xt_created_per_match": round(xt_created / played, 3),
            }
        )
    rows.sort(key=lambda item: item["team"])
    return {
        "schema_version": "0.1.0",
        "status": "available",
        "label": "Historical team research — never a live model input",
        "competition_id": competition_id,
        "competition_name": competition_name,
        "era": era,
        "team_scope": "team_aggregate_only",
        "coverage": {"matches": len(matches), "events": len(events), "teams": len(rows)},
        "methods": {
            "progressive_pass": "successful pass with normalized attacking x gain >= 20",
            "chain_proxy": (
                "consecutive same-team event run; a transparent proxy, "
                "not provider possession"
            ),
            "research_xt": (
                "own 12x8 transition grid trained within this competition slice; "
                "positive completed-pass gains only"
            ),
        },
        "teams": rows,
        "provenance": {
            "source_id": "pappalardo-wyscout-events",
            "license": "CC-BY-4.0",
            "attribution": (
                "Event data: Pappalardo et al., Scientific Data 6:236 (2019), "
                "CC BY 4.0 (collected by Wyscout)."
            ),
            "modifications": (
                "Golavo aggregated raw events to competition-era team summaries; "
                "player identities and raw events are not redistributed."
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--matches", type=Path, required=True)
    parser.add_argument("--teams", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    team_names = {
        int(item["wyId"]): str(item["name"])
        for item in json.loads(args.teams.read_text(encoding="utf-8"))
    }
    generated: list[dict[str, Any]] = []
    totals = Counter()
    with zipfile.ZipFile(args.events) as events_zip, zipfile.ZipFile(args.matches) as matches_zip:
        for stem, (competition_id, name, era) in SPECS.items():
            with events_zip.open(f"events_{stem}.json") as handle:
                events = json.load(handle)
            with matches_zip.open(f"matches_{stem}.json") as handle:
                matches = json.load(handle)
            artifact = build_competition(
                events,
                matches,
                team_names,
                competition_id=competition_id,
                competition_name=name,
                era=era,
            )
            target = args.output / f"{competition_id}.json"
            target.write_text(
                json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            generated.append({"name": target.name, "sha256": _sha(target)})
            totals.update(matches=len(matches), events=len(events))
            del events, matches
    if totals != {"matches": 1941, "events": 3251294}:
        raise SystemExit(f"source total mismatch: {dict(totals)}")
    for name in ("ATTRIBUTION.md", "LICENSE.md"):
        generated.append({"name": name, "sha256": _sha(args.output / name)})
    manifest = {
        "schema_version": "0.2.0",
        "source_id": "pappalardo-wyscout-events",
        "url": "https://figshare.com/collections/Soccer_match_event_dataset/4415000",
        "upstream_ref": "doi:10.6084/m9.figshare.c.4415000.v5",
        "retrieved_at_utc": "2026-07-15T17:18:00Z",
        "license": "CC-BY-4.0",
        "license_class": "research-pack",
        "citation_key": "pappalardo2019dataset",
        "attribution": (
            "Event data: Pappalardo et al., Scientific Data 6:236 (2019), "
            "CC BY 4.0 (collected by Wyscout)."
        ),
        "modifications": (
            "Compact competition-era team aggregates generated by Golavo; "
            "raw events and player identities excluded."
        ),
        "source_files": [
            {"name": "events.zip", "sha256": _sha(args.events)},
            {"name": "matches.zip", "sha256": _sha(args.matches)},
            {"name": "teams.json", "sha256": _sha(args.teams)},
        ],
        "files": sorted(generated, key=lambda item: item["name"]),
        "coverage": {"matches": totals["matches"], "events": totals["events"], "competitions": 7},
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
