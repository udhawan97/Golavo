"""Phase 1 club-coverage tests: openfootball ingestion, the audit gate, EPL evaluation."""

from __future__ import annotations

import sys
from pathlib import Path

from golavo_core.evaluation import CLUB_FOLDS, _validate_summary, evaluate_club
from golavo_core.ingest import load_matches, load_openfootball_table
from golavo_core.ingest.openfootball import canonical_team
from golavo_core.models import FAMILIES

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK = REPO_ROOT / "packs/openfootball-eng-pl"
INTL_PACK = REPO_ROOT / "packs/martj42-internationals"
SCHEMA = REPO_ROOT / "docs/contracts/forecast_artifact.schema.json"
CANONICAL_COLUMNS = {
    "match_id", "date", "home_team", "away_team", "home_score", "away_score",
    "tournament", "city", "country", "neutral", "kickoff_utc", "is_complete",
    "kickoff_precision", "ht_home_score", "ht_away_score",
}


def test_canonical_team() -> None:
    assert canonical_team("Arsenal FC") == "Arsenal"
    assert canonical_team("AFC Bournemouth") == "Bournemouth"
    assert canonical_team("Brighton & Hove Albion FC") == "Brighton & Hove Albion"
    assert canonical_team("Tottenham Hotspur") == "Tottenham Hotspur"


def test_openfootball_loader_schema_and_counts() -> None:
    frame = load_openfootball_table(PACK)
    assert CANONICAL_COLUMNS <= set(frame.columns)
    # 16 football.json seasons + the 2026-27 Football.TXT fixture list, which
    # football.json does not publish (see ingest.domestictxt).
    assert len(frame) == 16 * 380 + 380
    # Unchanged by the fixture list: all 16 football.json seasons are complete,
    # 2025-26 included once its bare-list goalless draws are read as results.
    # A schedule must add no result at all.
    assert int(frame["is_complete"].sum()) == 16 * 380
    assert not any(str(team).endswith(" FC") for team in frame["home_team"].unique())
    assert frame["match_id"].is_unique
    assert bool(frame["neutral"].any()) is False
    assert set(frame["tournament"].unique()) == {"English Premier League"}
    # Only the 2026-27 schedule is incomplete, and it carries NA scores: a fixture
    # with no result never gets a fabricated one.
    assert frame.loc[~frame["is_complete"], "home_score"].isna().all()
    # In 2025-26 the 27 bare-list rows are the only completed ones with no half
    # time: that shape states a full-time score and nothing else, so the half is
    # recorded as missing rather than inferred from the final score.
    season = frame[
        frame["is_complete"]
        & frame["date"].between("2025-08-01", "2026-06-30")
    ]
    assert len(season) == 380
    assert int(season["ht_home_score"].isna().sum()) == 27
    assert str(frame["ht_home_score"].dtype) == "Int16"
    assert frame["kickoff_precision"].eq("day").all()
    assert frame["kickoff_utc"].dt.hour.eq(0).all()


def test_load_matches_dispatch() -> None:
    club = load_matches(PACK)
    assert set(club["tournament"].unique()) == {"English Premier League"}
    internationals = load_matches(INTL_PACK)
    assert "English Premier League" not in set(internationals["tournament"].unique())


def test_audit_verdict_accept_historical() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.audit_openfootball import audit_league

    result = audit_league(PACK, "en.1")
    assert result["verdict"] == "ACCEPT_HISTORICAL"
    assert len(result["clean_seasons"]) == 16
    assert result["flagged_seasons"] == []
    assert result["fold_seasons"] == ["2023-24", "2024-25", "2025-26"]


def test_club_evaluation_gate_and_schema() -> None:
    summary = evaluate_club(PACK)
    _validate_summary(summary, SCHEMA)
    assert summary["primary_metric"] == "log_loss"
    assert len(summary["folds"]) == len(CLUB_FOLDS)
    for fold in summary["folds"]:
        assert fold["n_matches"] == 380
        by_family = {model["family"]: model["log_loss"] for model in fold["models"]}
        assert set(by_family) == set(FAMILIES)
        # Gate: a candidate must beat the climatological baseline on log loss.
        assert min(by_family.values()) < by_family["climatological"]
