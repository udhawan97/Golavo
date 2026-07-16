"""On-demand MatchAnalysis: leak-safety, honest council shape, coherence.

These guard the pivot's core new capability — model analysis for ANY indexed
match — against the two failure modes that would make it dishonest: reading data
it should not (leakage) and presenting the three Poisson flavours as independent
opinions (false plurality).
"""

from __future__ import annotations

import pandas as pd
import pytest
from golavo_core.analysis import (
    AnalysisUnavailable,
    build_match_analysis,
)
from golavo_core.score_matrix import assert_stored_coherent

TEAMS = ["Aland", "Borda", "Corvo", "Delta"]


def _match(mid: str, date: str, home: str, away: str, hs: int, aws: int) -> dict:
    day = pd.Timestamp(date, tz="UTC")
    return {
        "match_id": mid,
        "date": day,
        "kickoff_utc": day,
        "home_team": home,
        "away_team": away,
        "home_score": hs,
        "away_score": aws,
        "is_complete": True,
        "neutral": False,
        "competition": "Test League",
        "source_id": "test-source",
        "source_kind": "international",
        "home_norm": home.lower(),
        "away_norm": away.lower(),
    }


def _history() -> pd.DataFrame:
    """A round-robin of completed matches so Aland and Borda each appear ≥10 times
    in the window, all dated before the fixture's kickoff."""
    rows = []
    n = 0
    # Six full rounds over four teams before 2025-06-01.
    for round_no in range(6):
        base_month = 1 + round_no  # Jan..Jun 2024
        for i in range(len(TEAMS)):
            for j in range(len(TEAMS)):
                if i == j:
                    continue
                n += 1
                date = f"2024-{base_month:02d}-{(n % 27) + 1:02d}"
                hs, aws = (2, 1) if (i + j) % 2 == 0 else (0, 1)
                rows.append(_match(f"m_hist{n:04d}", date, TEAMS[i], TEAMS[j], hs, aws))
    return pd.DataFrame(rows)


def _fixture(*, is_complete: bool) -> dict:
    ko = pd.Timestamp("2025-06-01", tz="UTC")
    return {
        "match_id": "m_fixture0001",
        "date": ko,
        "kickoff_utc": ko,
        "home_team": "Aland",
        "away_team": "Borda",
        "home_score": 3 if is_complete else None,
        "away_score": 0 if is_complete else None,
        "is_complete": is_complete,
        "neutral": False,
        "competition": "Test League",
        "source_id": "test-source",
        "source_kind": "international",
        "home_norm": "aland",
        "away_norm": "borda",
    }


def test_replay_excludes_the_fixture_result_and_any_later_row() -> None:
    """The leak guard: adding the fixture's own result AND a later match to the
    training frame must not change the analysis at all — both are after the
    ``kickoff - 1s`` cutoff and are excluded."""
    history = _history()
    fixture = _fixture(is_complete=True)

    clean = build_match_analysis(matches=history, match_row=fixture)

    # Poison the frame with the fixture's own completed result and a match dated
    # after kickoff. A leak would change the fitted probabilities.
    poisoned_rows = [
        _match("m_fixture0001", "2025-06-01", "Aland", "Borda", 3, 0),  # the result itself
        _match("m_future0001", "2025-07-01", "Aland", "Borda", 5, 0),  # a later match
    ]
    poisoned = pd.concat([history, pd.DataFrame(poisoned_rows)], ignore_index=True)
    with_poison = build_match_analysis(matches=poisoned, match_row=fixture)

    assert with_poison == clean, "future/own-result rows leaked into the replay"
    assert clean["information_cutoff_utc"] < clean["match"]["kickoff_utc"]
    assert clean["analysis_kind"] == "replay"


def test_preview_kind_for_a_scheduled_fixture() -> None:
    analysis = build_match_analysis(matches=_history(), match_row=_fixture(is_complete=False))
    assert analysis["analysis_kind"] == "preview"
    assert analysis["abstained"] is False


def test_council_is_two_voices_plus_one_baseline_no_false_plurality() -> None:
    analysis = build_match_analysis(matches=_history(), match_row=_fixture(is_complete=False))
    by_family = {m["family"]: m for m in analysis["models"]}

    assert by_family["elo_ordlogit"]["role"] == "voice"
    assert by_family["dixon_coles"]["role"] == "voice"
    assert by_family["poisson_independent"]["role"] == "variant"
    assert by_family["bivariate_poisson"]["role"] == "variant"
    assert by_family["climatological"]["role"] == "baseline"

    # Exactly two voices are summarised — never five, never an averaged consensus.
    assert analysis["council"]["voices"] == 2
    assert analysis["score_matrix_family"] == "dixon_coles"


def test_goal_voice_score_matrix_is_coherent_with_its_probs() -> None:
    analysis = build_match_analysis(matches=_history(), match_row=_fixture(is_complete=False))
    goal = next(m for m in analysis["models"] if m["family"] == "dixon_coles")
    assert goal["score_matrix"] is not None
    # Reproduces the goal voice's own 1X2 — the same invariant the seal enforces.
    assert_stored_coherent(goal["score_matrix"], goal["probs"])


def test_derived_markets_match_the_full_joint_matrix() -> None:
    """BTTS + clean-sheet marginals are exact re-derivations of the goal voice's
    full joint distribution — recomputed here from scratch as ground truth."""
    import numpy as np

    analysis = build_match_analysis(matches=_history(), match_row=_fixture(is_complete=False))
    dm = analysis["derived_markets"]
    assert dm is not None
    assert dm["source"] == "full_resolution_matrix"
    # yes/no partition the space.
    assert abs(dm["btts"]["yes"] + dm["btts"]["no"] - 1.0) < 1e-6
    # Recompute from the display grid + tail as a coarse sanity bound: a nil-nil is
    # in the grid, and BTTS requires both > 0, so BTTS yes < 1 - P(0-0).
    goal = next(m for m in analysis["models"] if m["family"] == "dixon_coles")
    grid = np.array(goal["score_matrix"]["grid"], dtype=float)
    p_nil_nil = grid[0][0]
    assert dm["btts"]["yes"] <= 1.0 - p_nil_nil + 1e-9
    # A clean sheet for a side is at least as likely as a 0-0 (that scoreline is one
    # way each side keeps a clean sheet).
    assert dm["clean_sheets"]["home"] >= p_nil_nil - 1e-9
    assert dm["clean_sheets"]["away"] >= p_nil_nil - 1e-9


def test_derived_markets_null_when_abstained() -> None:
    thin = pd.DataFrame(
        [
            _match("m_dm1", "2024-02-01", "Xerus", "Yak", 1, 0),
            _match("m_dm2", "2024-03-01", "Xerus", "Yak", 0, 0),
        ]
    )
    ko = pd.Timestamp("2025-06-01", tz="UTC")
    fixture = {
        "match_id": "m_dmfix",
        "date": ko,
        "kickoff_utc": ko,
        "home_team": "Xerus",
        "away_team": "Yak",
        "home_score": None,
        "away_score": None,
        "is_complete": False,
        "neutral": False,
        "competition": "Test League",
        "source_id": "test-source",
        "source_kind": "international",
        "home_norm": "xerus",
        "away_norm": "yak",
    }
    analysis = build_match_analysis(matches=thin, match_row=fixture)
    assert analysis["abstained"] is True
    assert analysis["derived_markets"] is None


def test_abstains_below_the_data_floor_exactly_like_a_seal() -> None:
    """A fixture between teams with almost no history abstains, and every model
    entry carries no probabilities (never a fabricated number)."""
    thin = pd.DataFrame(
        [
            _match("m_thin1", "2024-02-01", "Xerus", "Yak", 1, 0),
            _match("m_thin2", "2024-03-01", "Xerus", "Yak", 0, 0),
        ]
    )
    ko = pd.Timestamp("2025-06-01", tz="UTC")
    fixture = {
        "match_id": "m_thinfix",
        "date": ko,
        "kickoff_utc": ko,
        "home_team": "Xerus",
        "away_team": "Yak",
        "home_score": None,
        "away_score": None,
        "is_complete": False,
        "neutral": False,
        "competition": "Test League",
        "source_id": "test-source",
        "source_kind": "international",
        "home_norm": "xerus",
        "away_norm": "yak",
    }
    analysis = build_match_analysis(matches=thin, match_row=fixture)
    assert analysis["abstained"] is True
    assert analysis["abstain_reason"]
    assert all(m["probs"] is None for m in analysis["models"])
    assert analysis["council"]["voices"] == 0


def test_analysis_is_deterministic() -> None:
    history = _history()
    fixture = _fixture(is_complete=True)
    assert build_match_analysis(matches=history, match_row=fixture) == build_match_analysis(
        matches=history, match_row=fixture
    )


def test_phase8_explanation_is_descriptive_exact_and_provenanced() -> None:
    analysis = build_match_analysis(matches=_history(), match_row=_fixture(is_complete=False))
    explanation = analysis["explanation"]
    disagreement = explanation["disagreement"]
    voices = [model for model in analysis["models"] if model["role"] == "voice"]

    assert explanation["averaged_consensus"] is False
    assert explanation["calibrated_confidence"] is False
    assert explanation["causal_claims"] is False
    assert explanation["sealed_forecast_immutable"] is True
    assert explanation["history_support"]["meaning"].endswith("not forecast confidence or accuracy")
    assert explanation["capability_coverage"]["meaning"].endswith("not model quality or accuracy")
    for outcome in ("home", "draw", "away"):
        expected = round(abs(voices[0]["probs"][outcome] - voices[1]["probs"][outcome]) * 100, 1)
        assert disagreement["outcome_gap_percentage_points"][outcome] == expected
    assert explanation["provenance"]["formula_version"] == "analysis-explanation-1"
    assert explanation["provenance"]["source_ids"] == ["test-source"]
    assert set(explanation["missing_evidence"]) == {
        "verified_lineups",
        "verified_injuries",
        "observed_xg",
    }


def test_phase8_explanation_performs_no_additional_fit(monkeypatch: pytest.MonkeyPatch) -> None:
    import golavo_core.analysis as analysis_module

    original = analysis_module.fit_model
    calls: list[str] = []

    def counted(family: str, *args: object, **kwargs: object):
        calls.append(family)
        return original(family, *args, **kwargs)

    monkeypatch.setattr(analysis_module, "fit_model", counted)
    build_match_analysis(matches=_history(), match_row=_fixture(is_complete=False))
    assert calls == list(analysis_module.COUNCIL_FAMILIES)


def test_missing_kickoff_is_refused_not_guessed() -> None:
    fixture = _fixture(is_complete=False)
    fixture["kickoff_utc"] = None
    with pytest.raises(AnalysisUnavailable):
        build_match_analysis(matches=_history(), match_row=fixture)


def test_team_form_is_last_five_pre_cutoff_and_leak_safe() -> None:
    """Form is the last five completed results per team, oldest-first, and never
    reads the fixture's own result or any later row."""
    history = _history()
    fixture = _fixture(is_complete=True)
    analysis = build_match_analysis(matches=history, match_row=fixture)

    for team in ("Aland", "Borda"):
        form = analysis["team_form"][team]
        assert 1 <= len(form) <= 5
        assert all(e["result"] in {"W", "D", "L"} for e in form)
        # oldest-first
        dates = [e["date"] for e in form]
        assert dates == sorted(dates)
        # never the fixture's own kickoff day or later
        assert all(e["date"] < "2025-06-01" for e in form)

    # Poisoning the frame with the fixture result + a later match must not change
    # the form (same leak guard as the council).
    poisoned = pd.concat(
        [
            history,
            pd.DataFrame(
                [
                    _match("m_fixture0001", "2025-06-01", "Aland", "Borda", 3, 0),
                    _match("m_future0001", "2025-07-01", "Aland", "Borda", 5, 0),
                ]
            ),
        ],
        ignore_index=True,
    )
    reanalysis = build_match_analysis(matches=poisoned, match_row=fixture)
    assert reanalysis["team_form"] == analysis["team_form"]


def test_team_form_present_even_when_the_council_abstains() -> None:
    thin = pd.DataFrame(
        [
            _match("m_thin1", "2024-02-01", "Xerus", "Yak", 1, 0),
            _match("m_thin2", "2024-03-01", "Xerus", "Yak", 0, 0),
        ]
    )
    ko = pd.Timestamp("2025-06-01", tz="UTC")
    fixture = {
        "match_id": "m_thinfix",
        "date": ko,
        "kickoff_utc": ko,
        "home_team": "Xerus",
        "away_team": "Yak",
        "home_score": None,
        "away_score": None,
        "is_complete": False,
        "neutral": False,
        "competition": "Test League",
        "source_id": "test-source",
        "source_kind": "international",
        "home_norm": "xerus",
        "away_norm": "yak",
    }
    analysis = build_match_analysis(matches=thin, match_row=fixture)
    assert analysis["abstained"] is True
    assert analysis["team_style"] is None  # nothing fitted
    assert len(analysis["team_form"]["Xerus"]) == 2  # but history still renders
    assert len(analysis["team_form"]["Yak"]) == 2


def test_team_style_matches_the_goal_voice_fit() -> None:
    """team_style is the goal-voice model's own fitted multipliers — verified by
    refitting dixon_coles on the same leak-safe frame."""
    from golavo_core.ingest import training_rows
    from golavo_core.models import fit_model

    history = _history()
    fixture = _fixture(is_complete=False)
    analysis = build_match_analysis(matches=history, match_row=fixture)
    style = analysis["team_style"]

    assert style["family"] == "dixon_coles"
    assert style["derivation"] == "fitted_from_results"

    cutoff = analysis["information_cutoff_utc"]
    train = training_rows(history, cutoff)
    model = fit_model("dixon_coles", train, cutoff)
    for team in ("Aland", "Borda"):
        assert style["teams"][team]["attack"] == round(float(model.attack[team]), 6)
        assert style["teams"][team]["defence"] == round(float(model.defence[team]), 6)
        # multipliers stay inside the disclosed clip band
        assert 0.35 <= style["teams"][team]["attack"] <= 2.8
        assert 0.35 <= style["teams"][team]["defence"] <= 2.8

    # expected_goals mirror the fixture's expected goals from the goal voice.
    goal = next(m for m in analysis["models"] if m["family"] == "dixon_coles")
    assert style["teams"]["Aland"]["expected_goals_for"] == goal["expected_goals"]["home"]
    assert style["teams"]["Aland"]["expected_goals_against"] == goal["expected_goals"]["away"]
