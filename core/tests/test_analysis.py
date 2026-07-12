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


def test_missing_kickoff_is_refused_not_guessed() -> None:
    fixture = _fixture(is_complete=False)
    fixture["kickoff_utc"] = None
    with pytest.raises(AnalysisUnavailable):
        build_match_analysis(matches=_history(), match_row=fixture)
