"""Phase 8: the exact-score matrix must stay coherent with the sealed 1X2 forecast.

These tests are the machine-checked guarantee behind the feature: the grid a user
sees is exactly the distribution the sealed numbers imply, or there is no grid.
"""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from golavo_core.artifacts import seal_forecast, validate_artifact
from golavo_core.ingest import load_matches, training_rows
from golavo_core.models import fit_model
from golavo_core.score_matrix import (
    GOALS_TOLERANCE,
    PROB_TOLERANCE,
    SCORE_MATRIX_DISPLAY_N,
    build_score_matrix,
    expected_goals,
    outcome_probabilities,
    stored_coherence_violations,
    stored_marginals,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK = REPO_ROOT / "packs/martj42-internationals"
SAMPLES = REPO_ROOT / "data/fixtures/sample_artifacts"

# A scheduled fixture whose window (snapshot anchor .. kickoff) admits a seal, and
# whose sides both clear the min-sample gate (so a real forecast is produced).
FIXTURE = {
    "date": "2026-07-11",
    "home_team": "Norway",
    "away_team": "England",
    "as_of_utc": "2026-07-10T20:00:00Z",
}
POISSON_FAMILIES = ("poisson_independent", "dixon_coles", "bivariate_poisson")
NON_GOAL_FAMILIES = ("elo_ordlogit", "climatological")


def _seal(tmp_path: Path, family: str) -> dict:
    path = seal_forecast(pack_dir=PACK, output_dir=tmp_path / family, family=family, **FIXTURE)
    return json.loads(path.read_text(encoding="utf-8"))


def _refit_prediction(family: str):
    """Replay the seal's deterministic training selection to recover the model's
    own prediction — used to prove the sealed grid IS what the fitted model emits."""
    matches = load_matches(PACK)
    row = matches.loc[
        (~matches["is_complete"])
        & matches["home_team"].eq(FIXTURE["home_team"])
        & matches["away_team"].eq(FIXTURE["away_team"])
    ].iloc[0]
    kickoff = pd.Timestamp(row["kickoff_utc"])
    cutoff = min(
        pd.Timestamp(FIXTURE["as_of_utc"]),
        kickoff - pd.Timedelta(seconds=1),
    ).isoformat().replace("+00:00", "Z")
    train = training_rows(matches, cutoff)
    train = train.loc[~train["match_id"].eq(row["match_id"])].copy()
    model = fit_model(family, train, cutoff)
    return model.predict(FIXTURE["home_team"], FIXTURE["away_team"], bool(row["neutral"]))


@pytest.mark.parametrize("family", POISSON_FAMILIES)
def test_poisson_seal_carries_a_score_matrix(tmp_path: Path, family: str) -> None:
    forecast = _seal(tmp_path, family)["forecast"]
    score_matrix = forecast["score_matrix"]
    n = score_matrix["max_goals"]
    assert n == SCORE_MATRIX_DISPLAY_N
    assert len(score_matrix["grid"]) == n + 1
    assert all(len(row) == n + 1 for row in score_matrix["grid"])
    assert score_matrix["resolution"] >= n
    assert abs(score_matrix["total_probability"] - 1.0) <= PROB_TOLERANCE


@pytest.mark.parametrize("family", POISSON_FAMILIES)
def test_stored_grid_and_tail_reproduce_the_sealed_1x2(tmp_path: Path, family: str) -> None:
    """THE CRUX (artifact-only): win/draw/loss reconstructed from grid + tail equals
    forecast.probs. No model needed — only the stored JSON."""
    forecast = _seal(tmp_path, family)["forecast"]
    home, draw, away = stored_marginals(forecast["score_matrix"])
    assert home == pytest.approx(forecast["probs"]["home"], abs=PROB_TOLERANCE)
    assert draw == pytest.approx(forecast["probs"]["draw"], abs=PROB_TOLERANCE)
    assert away == pytest.approx(forecast["probs"]["away"], abs=PROB_TOLERANCE)
    assert stored_coherence_violations(forecast["score_matrix"], forecast["probs"]) == []


@pytest.mark.parametrize("family", POISSON_FAMILIES)
def test_matrix_reproduces_sealed_probs_and_expected_goals(tmp_path: Path, family: str) -> None:
    """Model-level: the fitted matrix reproduces BOTH the sealed probs and the sealed
    expected goals, and re-deriving the model yields the identical stored grid."""
    forecast = _seal(tmp_path, family)["forecast"]
    prediction = _refit_prediction(family)

    home, draw, away = outcome_probabilities(prediction.matrix)
    assert home == pytest.approx(forecast["probs"]["home"], abs=PROB_TOLERANCE)
    assert draw == pytest.approx(forecast["probs"]["draw"], abs=PROB_TOLERANCE)
    assert away == pytest.approx(forecast["probs"]["away"], abs=PROB_TOLERANCE)

    eg_home, eg_away = expected_goals(prediction.matrix)
    assert eg_home == pytest.approx(forecast["expected_goals"]["home"], abs=GOALS_TOLERANCE)
    assert eg_away == pytest.approx(forecast["expected_goals"]["away"], abs=GOALS_TOLERANCE)

    rebuilt = build_score_matrix(prediction.matrix)
    assert np.allclose(rebuilt["grid"], forecast["score_matrix"]["grid"], atol=1e-12)
    assert rebuilt["tail"] == forecast["score_matrix"]["tail"]
    assert rebuilt["most_likely"] == forecast["score_matrix"]["most_likely"]


@pytest.mark.parametrize("family", POISSON_FAMILIES)
def test_seal_matrix_is_byte_identical(tmp_path: Path, family: str) -> None:
    first = seal_forecast(pack_dir=PACK, output_dir=tmp_path / "a", family=family, **FIXTURE)
    second = seal_forecast(pack_dir=PACK, output_dir=tmp_path / "b", family=family, **FIXTURE)
    assert first.read_bytes() == second.read_bytes()


@pytest.mark.parametrize("family", POISSON_FAMILIES)
def test_display_tail_is_small_for_a_realistic_fixture(tmp_path: Path, family: str) -> None:
    """The N chosen keeps the '8+' tail small for realistic international scoring."""
    score_matrix = _seal(tmp_path, family)["forecast"]["score_matrix"]
    assert score_matrix["tail"]["probability"] < 0.01
    tail = score_matrix["tail"]
    assert tail["home"] + tail["draw"] + tail["away"] == pytest.approx(
        tail["probability"], abs=PROB_TOLERANCE
    )


@pytest.mark.parametrize("family", NON_GOAL_FAMILIES)
def test_non_goal_family_has_no_score_matrix(tmp_path: Path, family: str) -> None:
    forecast = _seal(tmp_path, family)["forecast"]
    assert "score_matrix" not in forecast


def test_abstained_seal_has_no_score_matrix(tmp_path: Path) -> None:
    """Even a goal family carries no grid when the min-sample gate abstains."""
    sparse = tmp_path / "sparse"
    shutil.copytree(PACK, sparse)
    rows = pd.read_csv(sparse / "results.csv")
    target = rows.loc[
        rows["date"].eq(FIXTURE["date"])
        & rows["home_team"].eq(FIXTURE["home_team"])
        & rows["away_team"].eq(FIXTURE["away_team"])
    ]
    history = rows.loc[
        rows["home_score"].notna()
        & (
            rows["home_team"].isin([FIXTURE["home_team"], FIXTURE["away_team"]])
            | rows["away_team"].isin([FIXTURE["home_team"], FIXTURE["away_team"]])
        )
    ].tail(4)
    pd.concat([history, target]).to_csv(sparse / "results.csv", index=False)
    manifest_path = sparse / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["retrieved_at_utc"] = "2026-07-10T19:35:25Z"
    import hashlib

    for entry in manifest["files"]:
        entry["sha256"] = hashlib.sha256((sparse / entry["name"]).read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact = json.loads(
        seal_forecast(
            pack_dir=sparse,
            output_dir=tmp_path / "art",
            family="poisson_independent",
            **FIXTURE,
        ).read_text(encoding="utf-8")
    )
    assert artifact["status"] == "abstained"
    assert artifact["forecast"]["probs"] is None
    assert "score_matrix" not in artifact["forecast"]


def _samples_with_matrix() -> list[Path]:
    paths = []
    for path in sorted(SAMPLES.glob("fa_*.json")):
        if json.loads(path.read_text(encoding="utf-8"))["forecast"].get("score_matrix"):
            paths.append(path)
    return paths


def test_sample_fixtures_include_and_exclude_matrices() -> None:
    with_matrix = _samples_with_matrix()
    assert with_matrix, "expected at least one sample fixture carrying a score_matrix"
    # And at least one WITHOUT (elo / abstained) so the optional field is exercised both ways.
    all_samples = sorted(SAMPLES.glob("fa_*.json"))
    assert len(with_matrix) < len(all_samples)


@pytest.mark.parametrize("path", _samples_with_matrix(), ids=lambda p: p.name[:15])
def test_sample_matrices_are_coherent(path: Path) -> None:
    artifact = json.loads(path.read_text(encoding="utf-8"))
    validate_artifact(artifact)  # enforces stored coherence; raises otherwise
    assert stored_coherence_violations(
        artifact["forecast"]["score_matrix"], artifact["forecast"]["probs"]
    ) == []


def test_legacy_artifact_without_score_matrix_still_validates() -> None:
    """A 0.1.0-shaped seal (no score_matrix) must remain valid — the field is additive."""
    sample = json.loads(_samples_with_matrix()[0].read_text(encoding="utf-8"))
    legacy = copy.deepcopy(sample)
    legacy["schema_version"] = "0.1.0"
    del legacy["forecast"]["score_matrix"]
    validate_artifact(legacy)  # must not raise


def test_validate_rejects_an_incoherent_matrix() -> None:
    """Tampering with a single grid cell breaks W/D/L reproduction and is rejected."""
    artifact = json.loads(_samples_with_matrix()[0].read_text(encoding="utf-8"))
    artifact["forecast"]["score_matrix"]["grid"][0][0] += 0.25
    with pytest.raises(ValueError, match="incoherent score_matrix"):
        validate_artifact(artifact)


def test_build_score_matrix_is_an_exact_partition() -> None:
    """Unit: grid + tail is a re-bucketing of the input distribution — no mass lost,
    win/draw/loss preserved exactly, tail is only the cells beyond the display cap."""
    rng = np.random.default_rng(0)  # seeded so this is deterministic
    raw = rng.random((21, 21)) + 1e-6
    matrix = raw / raw.sum()
    n = 5
    built = build_score_matrix(matrix, display_n=n)

    grid = np.array(built["grid"])
    tail = built["tail"]
    assert grid.shape == (n + 1, n + 1)
    # Grid cells are the exact sub-block of the input.
    assert np.allclose(grid, matrix[: n + 1, : n + 1], atol=1e-9)
    # Grid + tail conserves total mass and each outcome's mass (up to 9-dp cell
    # rounding accumulated over the grid, ~1e-8).
    assert grid.sum() + tail["probability"] == pytest.approx(1.0, abs=1e-7)
    full_home, full_draw, full_away = outcome_probabilities(matrix)
    home, draw, away = stored_marginals(built)
    assert home == pytest.approx(full_home, abs=1e-7)
    assert draw == pytest.approx(full_draw, abs=1e-7)
    assert away == pytest.approx(full_away, abs=1e-7)
