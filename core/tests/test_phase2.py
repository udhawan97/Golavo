"""Phase 2 top-5 league tests: packs, audit gate, canonicalization, per-league folds."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from golavo_core.evaluation import CLUB_FOLDS_BY_COMPETITION, _validate_summary, evaluate_club
from golavo_core.ingest import load_matches
from golavo_core.ingest.openfootball import canonical_team
from golavo_core.models import FAMILIES

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = REPO_ROOT / "docs/contracts/forecast_artifact.schema.json"

# Adjudicated per-league expectations; see docs/handoff/openfootball-audit.md and
# docs/handoff/team-canonicalization.md. Row counts are fixtures (played or not),
# complete counts exclude missing/[0, 0]-encoded results, club counts are the
# proven canonical identities.
# Row counts are the football.json seasons plus the 2026-27 Football.TXT fixture
# list bundled beside them (ingest.domestictxt). Every 'complete' count below is
# unchanged by that addition: a schedule contributes fixtures, never results.
# Club counts rise only by the sides genuinely promoted for 2026-27 — France
# gains Le Mans alone, because Troyes resolves to the identity it already had.
EXPECTED = {
    "es.1": {
        "pack": "packs/openfootball-esp-ll",
        "competition": "La Liga",
        "rows": 14 * 380 + 380,
        "complete": 14 * 380 - 10 - 15,
        "clubs": 34,
        "clean": 12,
        "flagged": ["2024-25", "2025-26"],
        "fold_seasons": ["2021-22", "2022-23", "2023-24"],
        "summary": "docs/handoff/eval_summary_laliga.json",
        "fold_sizes": [380, 380, 380],
    },
    "de.1": {
        "pack": "packs/openfootball-deu-bl",
        "competition": "Bundesliga",
        "rows": 16 * 306 + 306,
        "complete": 16 * 306 - 12,
        "clubs": 33,
        "clean": 15,
        "flagged": ["2025-26"],
        "fold_seasons": ["2022-23", "2023-24", "2024-25"],
        "summary": "docs/handoff/eval_summary_bundesliga.json",
        "fold_sizes": [306, 306, 306],
    },
    "it.1": {
        "pack": "packs/openfootball-ita-sa",
        "competition": "Serie A",
        "rows": 13 * 380 + 380,
        "complete": 13 * 380 - 10 - 36,
        "clubs": 38,
        "clean": 11,
        "flagged": ["2024-25", "2025-26"],
        "fold_seasons": ["2021-22", "2022-23", "2023-24"],
        "summary": "docs/handoff/eval_summary_seriea.json",
        "fold_sizes": [380, 380, 380],
    },
    "fr.1": {
        "pack": "packs/openfootball-fra-l1",
        "competition": "Ligue 1",
        "rows": 9 * 380 + 4 * 306,
        "complete": 9 * 380 + 3 * 306 - 101 - 24,
        "clubs": 35,
        "clean": 10,
        "flagged": ["2019-20", "2025-26"],
        "fold_seasons": ["2022-23", "2023-24", "2024-25"],
        "summary": "docs/handoff/eval_summary_ligue1.json",
        "fold_sizes": [380, 306, 306],
    },
}


def test_canonical_team_merges_cross_season_drift() -> None:
    # legal-form drift collapsed by rules
    assert canonical_team("Real Madrid CF", "es.1") == canonical_team("Real Madrid", "es.1")
    assert canonical_team("FC Bayern München", "de.1") == canonical_team("Bayern München", "de.1")
    assert canonical_team("Bayer 04 Leverkusen", "de.1") == "Bayer Leverkusen"
    assert canonical_team("Juventus FC", "it.1") == "Juventus"
    assert canonical_team("Parma Calcio 1913", "it.1") == canonical_team("Parma FC", "it.1")
    # drift only an alias can see
    assert canonical_team("FC Internazionale Milano", "it.1") == canonical_team("Inter", "it.1")
    assert canonical_team("Lazio Roma", "it.1") == canonical_team("SS Lazio", "it.1")
    assert canonical_team("Deportivo Alavés", "es.1") == canonical_team("CD Alavés", "es.1")
    assert canonical_team("RC Celta de Vigo", "es.1") == canonical_team("RC Celta", "es.1")
    assert canonical_team("Racing Club de Lens", "fr.1") == canonical_team("RC Lens", "fr.1")
    assert canonical_team("Olympique de Marseille", "fr.1") == canonical_team(
        "Olympique Marseille", "fr.1"
    )
    assert canonical_team("Bor. Mönchengladbach", "de.1") == "Borussia Mönchengladbach"


def test_canonical_team_keeps_distinct_clubs_distinct() -> None:
    assert canonical_team("Chievo Verona", "it.1") != canonical_team("Hellas Verona FC", "it.1")
    assert canonical_team("AC Ajaccio", "fr.1") != canonical_team("Gazélec FC Ajaccio", "fr.1")
    assert canonical_team("Paris FC", "fr.1") != canonical_team("Paris Saint-Germain FC", "fr.1")
    assert canonical_team("Real Madrid CF", "es.1") != canonical_team(
        "Club Atlético de Madrid", "es.1"
    )
    assert canonical_team("Borussia Dortmund", "de.1") != canonical_team(
        "Bor. Mönchengladbach", "de.1"
    )
    # the en.1 path is the untouched Phase 1 behavior
    assert canonical_team("Arsenal FC") == "Arsenal"
    assert canonical_team("AFC Bournemouth") == "Bournemouth"


def test_loader_tags_and_counts_every_league() -> None:
    for code, spec in EXPECTED.items():
        frame = load_matches(REPO_ROOT / spec["pack"])
        assert set(frame["tournament"].unique()) == {spec["competition"]}, code
        assert len(frame) == spec["rows"], code
        assert int(frame["is_complete"].sum()) == spec["complete"], code
        clubs = set(frame["home_team"]) | set(frame["away_team"])
        assert len(clubs) == spec["clubs"], code
        assert frame["match_id"].is_unique, code
        assert bool(frame["neutral"].any()) is False, code
        # incomplete rows carry NA scores; placeholders are never fabricated.
        assert frame.loc[~frame["is_complete"], "home_score"].isna().all(), code


def test_audit_verdicts_per_league() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.audit_openfootball import audit_league

    for code, spec in EXPECTED.items():
        result = audit_league(REPO_ROOT / spec["pack"], code)
        assert result["verdict"] == "ACCEPT_HISTORICAL", code
        assert len(result["clean_seasons"]) == spec["clean"], code
        assert result["flagged_seasons"] == spec["flagged"], code
        assert result["fold_seasons"] == spec["fold_seasons"], code


def test_fold_registry_matches_audit_fold_seasons() -> None:
    for spec in EXPECTED.values():
        folds = CLUB_FOLDS_BY_COMPETITION[spec["competition"]]
        seasons = [fold["window_start"][:4] for fold in folds]
        assert seasons == [s[:4] for s in spec["fold_seasons"]], spec["competition"]


def test_club_evaluation_la_liga_gate_and_schema() -> None:
    summary = evaluate_club(REPO_ROOT / "packs/openfootball-esp-ll")
    _validate_summary(summary, SCHEMA)
    assert [fold["competition"] for fold in summary["folds"]] == ["La Liga"] * 3
    for fold in summary["folds"]:
        assert fold["n_matches"] == 380
        by_family = {model["family"]: model["log_loss"] for model in fold["models"]}
        assert set(by_family) == set(FAMILIES)
        # Gate: a candidate must beat the climatological baseline on log loss.
        assert min(by_family.values()) < by_family["climatological"]


def test_committed_league_summaries_are_valid_and_honest() -> None:
    """The committed per-league summaries must match the fold registry, validate
    against the schema, and truthfully carry a baseline-beating candidate."""
    for spec in EXPECTED.values():
        summary = json.loads((REPO_ROOT / spec["summary"]).read_text(encoding="utf-8"))
        _validate_summary(summary, SCHEMA)
        folds = CLUB_FOLDS_BY_COMPETITION[spec["competition"]]
        assert [f["fold_id"] for f in summary["folds"]] == [f["fold_id"] for f in folds]
        assert [f["n_matches"] for f in summary["folds"]] == spec["fold_sizes"]
        for fold in summary["folds"]:
            by_family = {model["family"]: model["log_loss"] for model in fold["models"]}
            assert min(by_family.values()) < by_family["climatological"]
