"""Exact-kickoff overlay: worldcup.json parsing, the fail-closed cross-check, and the
end-to-end proof that a World Cup seal's window extends from the 00:00 UTC proxy to the
real kickoff instant.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest
from golavo_core.artifacts import seal_forecast
from golavo_core.ingest import load_match_table, load_matches
from golavo_core.ingest.worldcup import (
    crosscheck_completed,
    final_score,
    parse_kickoff,
    parse_worldcup,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK = REPO_ROOT / "packs/martj42-internationals"

# A miniature worldcup.json mirroring the real field shapes (times carry a UTC offset;
# knockout rows may be W###/L### placeholders; scores split ft/et/p).
_WC = {
    "name": "World Cup 2026",
    "matches": [
        {"round": "Matchday 1", "date": "2026-06-11", "time": "13:00 UTC-6",
         "team1": "Mexico", "team2": "South Africa", "score": {"ft": [2, 0], "ht": [1, 0]},
         "group": "Group A", "ground": "Mexico City"},
        {"round": "Round of 32", "num": 74, "date": "2026-06-29", "time": "16:30 UTC-4",
         "team1": "Germany", "team2": "Paraguay",
         "score": {"p": [3, 4], "et": [1, 1], "ft": [1, 1], "ht": [0, 1]},
         "ground": "Boston (Foxborough)"},
        {"round": "Semi-final", "num": 101, "date": "2026-07-14", "time": "21:00 UTC-5",
         "team1": "France", "team2": "Spain", "ground": "Dallas"},
        {"round": "Match for third place", "num": 103, "date": "2026-07-18", "time": "17:00 UTC-4",
         "team1": "L101", "team2": "L102", "ground": "Miami (Miami Gardens)"},
    ],
}


def test_parse_kickoff_converts_offset_and_rolls_the_date() -> None:
    # 13:00 at UTC-6 is 19:00 UTC the same day.
    assert parse_kickoff("2026-06-11", "13:00 UTC-6") == pd.Timestamp("2026-06-11T19:00:00Z")
    # 22:00 at UTC-7 rolls into the next UTC day.
    assert parse_kickoff("2026-06-11", "22:00 UTC-7") == pd.Timestamp("2026-06-12T05:00:00Z")
    # Missing or malformed times yield None (the fixture keeps its date proxy).
    assert parse_kickoff("2026-06-11", None) is None
    assert parse_kickoff("2026-06-11", "kickoff soon") is None


def test_final_score_prefers_extra_time_and_ignores_penalties() -> None:
    assert final_score({"p": [3, 4], "et": [1, 1], "ft": [1, 1]}) == (1, 1)
    assert final_score({"ft": [2, 0], "ht": [1, 0]}) == (2, 0)
    assert final_score({}) is None
    assert final_score(None) is None


def test_parse_worldcup_drops_placeholders_and_keeps_exact_kickoffs() -> None:
    parsed = parse_worldcup(_WC)
    # The L101/L102 third-place placeholder row is dropped; three real rows remain.
    assert list(zip(parsed["home_team"], parsed["away_team"], strict=True)) == [
        ("Mexico", "South Africa"),
        ("Germany", "Paraguay"),
        ("France", "Spain"),
    ]
    row = parsed[parsed["home_team"] == "Mexico"].iloc[0]
    assert row["kickoff_utc"] == pd.Timestamp("2026-06-11T19:00:00Z")
    assert bool(row["is_complete"]) and (int(row["home_score"]), int(row["away_score"])) == (2, 0)
    # The scheduled semi-final is present but not complete.
    semi = parsed[parsed["home_team"] == "France"].iloc[0]
    assert not bool(semi["is_complete"])


def test_crosscheck_flags_only_matched_disagreements() -> None:
    parsed = parse_worldcup(_WC)
    reference = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-06-11", "2026-06-29"]),
            "home_team": pd.array(["Mexico", "Germany"], dtype="string"),
            "away_team": pd.array(["South Africa", "Paraguay"], dtype="string"),
            "home_score": pd.array([2, 9], dtype="Int16"),  # Germany result doctored to disagree
            "away_score": pd.array([0, 9], dtype="Int16"),
            "is_complete": [True, True],
        }
    )
    disagreements = crosscheck_completed(parsed, reference)
    assert len(disagreements) == 1
    assert disagreements[0]["home_team"] == "Germany"
    assert disagreements[0]["worldcup"] == [1, 1] and disagreements[0]["reference"] == [9, 9]
    # When the reference agrees, there is no disagreement.
    reference.loc[1, ["home_score", "away_score"]] = [1, 1]
    assert crosscheck_completed(parsed, reference) == []


def _write_overlay_pack(tmp_path: Path, overlay_rows: list[dict]) -> Path:
    """Copy the real internationals pack and add a manifest-declared kickoffs.csv."""
    pack = tmp_path / "pack"
    shutil.copytree(PACK, pack)
    pd.DataFrame(overlay_rows).to_csv(pack / "kickoffs.csv", index=False)
    manifest_path = pack / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    names = {e["name"] for e in manifest["files"]} | {"kickoffs.csv"}
    manifest["files"] = sorted(
        ({"name": n, "sha256": hashlib.sha256((pack / n).read_bytes()).hexdigest()} for n in names),
        key=lambda e: e["name"],
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return pack


def test_apply_exact_kickoffs_overrides_only_matched_rows(tmp_path: Path) -> None:
    pack = _write_overlay_pack(
        tmp_path,
        [{"date": "2026-07-11", "home_team": "Norway", "away_team": "England",
          "tournament": "FIFA World Cup", "kickoff_utc": "2026-07-11T19:00:00Z"}],
    )
    overlaid = load_matches(pack)
    baseline = load_match_table(pack)  # same pack, no overlay applied
    # Pin the 2026 World Cup fixture (there is also a historical Norway v England friendly).
    ne = overlaid[
        (overlaid["home_team"] == "Norway")
        & (overlaid["away_team"] == "England")
        & (pd.to_datetime(overlaid["date"]).dt.strftime("%Y-%m-%d") == "2026-07-11")
    ].iloc[0]
    assert ne["kickoff_utc"] == pd.Timestamp("2026-07-11T19:00:00Z")
    assert ne["kickoff_precision"] == "exact"
    # is_complete is untouched, so an upcoming fixture still never enters training.
    assert not bool(ne["is_complete"])
    # Every other row keeps its original kickoff, and the row counts match.
    assert len(overlaid) == len(baseline)
    unmatched = overlaid["match_id"] != ne["match_id"]
    merged = overlaid[unmatched].merge(baseline, on="match_id", suffixes=("_o", "_b"))
    assert (merged["kickoff_utc_o"] == merged["kickoff_utc_b"]).all()
    assert merged["kickoff_precision_o"].eq("day").all()


def test_overlay_present_but_undeclared_fails_closed(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    shutil.copytree(PACK, pack)
    pd.DataFrame(
        [{"date": "2026-07-11", "home_team": "Norway", "away_team": "England",
          "tournament": "FIFA World Cup", "kickoff_utc": "2026-07-11T19:00:00Z"}]
    ).to_csv(pack / "kickoffs.csv", index=False)  # written but NOT added to the manifest
    with pytest.raises(ValueError, match="not declared in the manifest"):
        load_matches(pack)


def test_pack_without_overlay_is_unchanged() -> None:
    # The committed pack ships no kickoffs.csv: load_matches must equal the plain loader,
    # which is what keeps the committed index byte-identical.
    assert load_matches(PACK)["kickoff_utc"].equals(load_match_table(PACK)["kickoff_utc"])


def test_seal_window_extends_from_midnight_proxy_to_exact_kickoff(tmp_path: Path) -> None:
    """The crown-jewel end-to-end: an exact kickoff keeps the seal window open past midnight."""
    pack = _write_overlay_pack(
        tmp_path,
        [{"date": "2026-07-11", "home_team": "Norway", "away_team": "England",
          "tournament": "FIFA World Cup", "kickoff_utc": "2026-07-11T19:00:00Z"}],
    )
    kwargs = {
        "date": "2026-07-11",
        "home_team": "Norway",
        "away_team": "England",
        "family": "elo_ordlogit",
    }
    # 15:00 on match day is AFTER the 00:00 UTC proxy but BEFORE the real 19:00 kickoff.
    # Without the overlay the plain pack rejects it as kickoff_passed; with it, the seal
    # succeeds and records the exact kickoff.
    plain = tmp_path / "plain"
    shutil.copytree(PACK, plain)
    with pytest.raises(ValueError, match="before kickoff"):
        seal_forecast(pack_dir=plain, output_dir=tmp_path / "o0",
                      as_of_utc="2026-07-11T15:00:00Z", **kwargs)

    from golavo_core.artifacts import load_verified_artifact

    path = seal_forecast(pack_dir=pack, output_dir=tmp_path / "o1",
                         as_of_utc="2026-07-11T15:00:00Z", **kwargs)
    artifact = load_verified_artifact(path)
    assert artifact["match"]["kickoff_utc"] == "2026-07-11T19:00:00Z"

    # At the exact kickoff the window is closed again.
    with pytest.raises(ValueError, match="before kickoff"):
        seal_forecast(pack_dir=pack, output_dir=tmp_path / "o2",
                      as_of_utc="2026-07-11T19:00:00Z", **kwargs)
