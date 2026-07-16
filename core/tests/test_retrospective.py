from __future__ import annotations

import json

import pandas as pd
import pytest
from golavo_core.analysis import build_match_analysis
from golavo_core.retrospective import (
    RANKING_FAMILY,
    RETROSPECTIVE_FAMILIES,
    RetrospectiveCancelled,
    RetrospectiveUnavailable,
    world_cup_2026_retrospective,
)

TEAMS = ("France", "Spain", "England", "Argentina")


def _history(n: int = 80) -> list[dict]:
    rows = []
    for index in range(n):
        day = pd.Timestamp("2025-01-01", tz="UTC") + pd.Timedelta(days=index)
        rows.append(
            {
                "match_id": f"m_hist_{index:03d}",
                "date": day.tz_localize(None),
                "kickoff_utc": day,
                "home_team": TEAMS[index % 4],
                "away_team": TEAMS[(index + 1) % 4],
                "home_score": index % 3,
                "away_score": (index + 1) % 2,
                "is_complete": True,
                "neutral": True,
                "competition": "Friendly",
                "kickoff_precision": "day",
                "source_id": "martj42-international-results",
                "source_kind": "international",
            }
        )
    return rows


def _wc_match(mid: str, kickoff: str, home: str, away: str, hs, aws, precision="exact") -> dict:
    k = pd.Timestamp(kickoff)
    return {
        "match_id": mid,
        "date": k.tz_convert(None).normalize(),
        "kickoff_utc": k,
        "home_team": home,
        "away_team": away,
        "home_score": hs,
        "away_score": aws,
        "is_complete": hs is not None,
        "neutral": True,
        "competition": "FIFA World Cup",
        "kickoff_precision": precision,
        "source_id": "martj42-international-results",
        "source_kind": "international",
    }


def _frame(wc_rows: list[dict] | None = None) -> pd.DataFrame:
    rows = wc_rows if wc_rows is not None else [
        _wc_match("m_wc1", "2026-06-20T12:00:00Z", "France", "Spain", 1, 0),
        _wc_match("m_wc2", "2026-06-20T20:00:00Z", "England", "Argentina", 2, 1),
    ]
    return pd.DataFrame([*_history(), *rows])


def test_returns_one_row_per_completed_match_ranked_by_log_loss() -> None:
    result = world_cup_2026_retrospective(_frame())
    assert result["schema_version"] == "0.1.0"
    assert result["ledger_status"] == "never_persisted_or_scored_as_a_seal"
    assert [row["match_id"] for row in result["matches"]] == ["m_wc1", "m_wc2"]
    for row in result["matches"]:
        assert set(row["families"]) == set(RETROSPECTIVE_FAMILIES)
        assert row["log_loss"] == pytest.approx(
            row["families"][RANKING_FAMILY]["log_loss"]
        )
    # biggest_surprises is the same rows ordered by the ranking family's loss
    losses = [row["log_loss"] for row in result["biggest_surprises"]]
    assert losses == sorted(losses, reverse=True)


def test_bivariate_poisson_is_not_offered_as_a_separate_voice() -> None:
    assert "bivariate_poisson" not in RETROSPECTIVE_FAMILIES
    result = world_cup_2026_retrospective(_frame())
    assert "bivariate_poisson" not in result["matches"][0]["families"]


def test_a_later_same_day_result_never_reaches_an_earlier_match() -> None:
    """The story layer's whole claim is a pre-kickoff forecast."""
    clean = world_cup_2026_retrospective(_frame())
    poisoned_rows = [
        _wc_match("m_wc1", "2026-06-20T12:00:00Z", "France", "Spain", 1, 0),
        _wc_match("m_wc2", "2026-06-20T20:00:00Z", "England", "Argentina", 9, 0),
    ]
    poisoned = world_cup_2026_retrospective(_frame(poisoned_rows))
    first_clean = next(r for r in clean["matches"] if r["match_id"] == "m_wc1")
    first_poisoned = next(r for r in poisoned["matches"] if r["match_id"] == "m_wc1")
    assert first_clean["families"] == first_poisoned["families"], (
        "a 20:00 result changed the 12:00 forecast"
    )


def test_future_rows_never_change_any_forecast() -> None:
    clean = world_cup_2026_retrospective(_frame())
    extra = _frame().to_dict("records") + [
        {
            **_history(1)[0],
            "match_id": "m_poison",
            "date": pd.Timestamp("2026-08-01"),
            "kickoff_utc": pd.Timestamp("2026-08-01T12:00:00Z"),
            "home_score": 99,
            "away_score": 0,
        }
    ]
    poisoned = world_cup_2026_retrospective(pd.DataFrame(extra))
    assert clean["matches"] == poisoned["matches"]


def test_is_deterministic_byte_for_byte() -> None:
    a = world_cup_2026_retrospective(_frame())
    b = world_cup_2026_retrospective(_frame())
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_day_precision_rows_are_carried_not_hidden() -> None:
    rows = [
        _wc_match("m_wc1", "2026-06-20T00:00:00Z", "France", "Spain", 1, 0, precision="day"),
        _wc_match("m_wc2", "2026-06-21T20:00:00Z", "England", "Argentina", 2, 1),
    ]
    result = world_cup_2026_retrospective(_frame(rows))
    by_id = {row["match_id"]: row for row in result["matches"]}
    assert by_id["m_wc1"]["kickoff_precision"] == "day"
    assert by_id["m_wc2"]["kickoff_precision"] == "exact"


def test_scheduled_matches_are_reported_as_typed_pending_not_scored() -> None:
    rows = [
        _wc_match("m_wc1", "2026-06-20T12:00:00Z", "France", "Spain", 1, 0),
        _wc_match("m_wc2", "2026-07-19T19:00:00Z", "Spain", "Argentina", None, None),
    ]
    result = world_cup_2026_retrospective(_frame(rows))
    assert [row["match_id"] for row in result["matches"]] == ["m_wc1"]
    assert result["coverage"]["scored"] == 1
    assert result["coverage"]["pending"] == 1
    assert result["coverage"]["status"] == "partial"
    assert "not yet played" in result["coverage"]["note"]


def test_complete_tournament_reports_complete_coverage() -> None:
    result = world_cup_2026_retrospective(_frame())
    assert result["coverage"]["status"] == "complete"
    assert result["coverage"]["pending"] == 0


def test_no_world_cup_rows_is_typed_unavailable() -> None:
    frame = pd.DataFrame(_history())
    with pytest.raises(RetrospectiveUnavailable, match="no completed 2026 World Cup"):
        world_cup_2026_retrospective(frame)


def test_progress_is_reported_and_cancellation_is_honoured() -> None:
    seen: list[tuple[int, int]] = []
    world_cup_2026_retrospective(_frame(), progress=lambda done, total: seen.append((done, total)))
    assert seen[-1] == (2, 2)

    with pytest.raises(RetrospectiveCancelled):
        world_cup_2026_retrospective(_frame(), is_cancelled=lambda: True)


def test_same_day_proxy_exposure_is_disclosed_not_hidden() -> None:
    """A day-precision (00:00 UTC) row sharing a match's calendar day is a real
    exposure inherited from ``training_rows`` (never fixed by a stricter cutoff),
    so it must be counted and surfaced rather than silently trained on."""
    rows = [
        _wc_match("m_wc_day", "2026-06-24T00:00:00Z", "France", "Spain", 1, 2, precision="day"),
        _wc_match(
            "m_wc_exact", "2026-06-24T02:00:00Z", "England", "Argentina", 1, 0, precision="exact"
        ),
    ]
    result = world_cup_2026_retrospective(_frame(rows))
    by_id = {row["match_id"]: row for row in result["matches"]}

    # The 00:00 proxy match kicked off (by its own stamp) before the 02:00 exact
    # match's cutoff, so it lands in that match's training frame.
    assert by_id["m_wc_exact"]["training_same_day_proxy_rows"] == 1
    # The day-proxy match's own cutoff (23:59:59 the day before) excludes the
    # 02:00 exact match, which has not "happened" yet at that cutoff.
    assert by_id["m_wc_day"]["training_same_day_proxy_rows"] == 0

    assert result["exposure"]["rows_with_same_day_proxies"] == 1
    note = result["exposure"]["note"]
    assert "day-precision" in note
    assert "cannot prove" in note


def test_matches_the_apps_own_build_match_analysis() -> None:
    """The module's whole claim is fidelity to the app's live analysis path —
    pin it directly against ``build_match_analysis`` so a scoping regression
    (e.g. reverting to source_kind) fails CI instead of shipping silently."""
    frame = _frame()
    result = world_cup_2026_retrospective(frame)
    row = next(r for r in result["matches"] if r["match_id"] == "m_wc1")

    fixture = frame.loc[frame["match_id"] == "m_wc1"].iloc[0]
    match_row = {
        "match_id": str(fixture["match_id"]),
        "kickoff_utc": fixture["kickoff_utc"],
        "home_team": fixture["home_team"],
        "away_team": fixture["away_team"],
        "home_score": int(fixture["home_score"]),
        "away_score": int(fixture["away_score"]),
        "is_complete": bool(fixture["is_complete"]),
        "neutral": bool(fixture["neutral"]),
        "competition": fixture["competition"],
        "source_id": fixture["source_id"],
    }
    scoped = frame.loc[frame["source_id"].astype("string") == str(fixture["source_id"])]

    analysis = build_match_analysis(
        matches=scoped, match_row=match_row, families=RETROSPECTIVE_FAMILIES
    )

    assert analysis["information_cutoff_utc"] == row["information_cutoff_utc"]
    entries = {entry["family"]: entry for entry in analysis["models"]}
    for family in RETROSPECTIVE_FAMILIES:
        for outcome in ("home", "draw", "away"):
            assert round(row["families"][family]["probs"][outcome], 6) == pytest.approx(
                entries[family]["probs"][outcome], abs=1e-9
            )
