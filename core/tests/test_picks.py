from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from golavo_core.picks import (
    PICK_SCHEMA_VERSION,
    canonical_pick_bytes,
    derive_rival_picks,
    football_season,
    outcome_of,
    pick_id,
    pick_payload_sha256,
    score_pick,
    season_summary,
    validate_user_pick,
    verify_pick_integrity,
)
from jsonschema import Draft202012Validator, FormatChecker, ValidationError


def _analysis() -> dict:
    goal_matrix = {"most_likely": {"home": 2, "away": 1, "probability": 0.14}}
    return {
        "schema_version": "0.5.0",
        "index_fingerprint": "index-abc",
        "information_cutoff_utc": "2025-08-01T14:59:59Z",
        "models": [
            {
                "family": "dixon_coles",
                "abstained": False,
                "probs": {"home": 0.5, "draw": 0.3, "away": 0.2},
                "score_matrix": goal_matrix,
            },
            {
                "family": "poisson_independent",
                "abstained": False,
                "probs": {"home": 0.4, "draw": 0.3, "away": 0.3},
                "score_matrix": goal_matrix,
            },
            {
                "family": "bivariate_poisson",
                "abstained": False,
                "probs": {"home": 0.4, "draw": 0.3, "away": 0.3},
                "score_matrix": goal_matrix,
            },
            {
                "family": "elo_ordlogit",
                "abstained": False,
                "probs": {"home": 0.4, "draw": 0.4, "away": 0.2},
                "score_matrix": None,
            },
            {
                "family": "climatological",
                "abstained": True,
                "probs": None,
                "score_matrix": None,
            },
        ],
    }


def _draft(*, kickoff: str = "2025-08-01T15:00:00Z") -> dict:
    derived = derive_rival_picks(_analysis())
    return {
        "schema_version": PICK_SCHEMA_VERSION,
        "pick_id": None,
        "status": "draft",
        "match": {
            "match_id": "m_1",
            "kickoff_utc": kickoff,
            "kickoff_time_known": True,
            "home_team": "Aland",
            "away_team": "Borda",
            "home_norm": "aland",
            "away_norm": "borda",
            "competition": "Test League",
        },
        "user_pick": {"home_goals": 2, "away_goals": 1, "outcome": "home"},
        "rivals": derived["rivals"],
        "analysis_fingerprint": derived["analysis_fingerprint"],
        "created_at_utc": "2025-08-01T12:00:00Z",
        "updated_at_utc": "2025-08-01T12:00:00Z",
        "lock_at_utc": kickoff,
        "locked_at_utc": None,
        "payload_sha256": None,
    }


def _locked(*, kickoff: str = "2025-08-01T15:00:00Z") -> dict:
    record = _draft(kickoff=kickoff)
    record.update(
        {
            "status": "locked",
            "locked_at_utc": kickoff,
            "updated_at_utc": kickoff,
        }
    )
    stable = copy.deepcopy(record)
    stable.pop("pick_id")
    stable.pop("payload_sha256")
    record["pick_id"] = pick_id(stable)
    record["payload_sha256"] = pick_payload_sha256(record)
    return record


def _view(
    match_id: str,
    kickoff: str,
    *,
    user_score: tuple[int, int],
    result: tuple[int, int] | None,
    status: str = "scored",
) -> dict:
    record = _locked(kickoff=kickoff)
    record["match"]["match_id"] = match_id
    record["user_pick"] = {
        "home_goals": user_score[0],
        "away_goals": user_score[1],
        "outcome": outcome_of(*user_score),
    }
    # Aggregation consumes already-verified views, so changing the helper after
    # sealing is fine here; integrity itself is tested independently below.
    if result is None:
        return {
            "schema_version": PICK_SCHEMA_VERSION,
            "status": status,
            "record": record,
            "result": None,
            "scoring": None,
        }
    result_obj = {
        "home_goals": result[0],
        "away_goals": result[1],
        "outcome": outcome_of(*result),
    }
    return {
        "schema_version": PICK_SCHEMA_VERSION,
        "status": status,
        "record": record,
        "result": result_obj,
        "scoring": score_pick(record, result_obj),
    }


def test_outcome_of() -> None:
    assert outcome_of(2, 1) == "home"
    assert outcome_of(1, 1) == "draw"
    assert outcome_of(0, 2) == "away"


def test_rival_derivation_preserves_score_and_capability() -> None:
    derived = derive_rival_picks(_analysis())
    rivals = {rival["family"]: rival for rival in derived["rivals"]}
    assert rivals["dixon_coles"]["score_pick"] == {"home_goals": 2, "away_goals": 1}
    assert rivals["dixon_coles"]["outcome_pick"] == "home"
    assert rivals["dixon_coles"]["capability"] == "score"
    assert rivals["elo_ordlogit"]["score_pick"] is None
    assert rivals["elo_ordlogit"]["outcome_pick"] == "home"  # tie-break
    assert rivals["elo_ordlogit"]["capability"] == "outcome_only"
    assert rivals["climatological"]["capability"] == "abstained"
    assert rivals["climatological"]["outcome_pick"] is None
    assert derived["analysis_fingerprint"] == {
        "index_fingerprint": "index-abc",
        "analysis_schema_version": "0.5.0",
        "information_cutoff_utc": "2025-08-01T14:59:59Z",
    }
    assert derived == derive_rival_picks(copy.deepcopy(_analysis()))


def test_scoring_exact_is_four_base_plus_strict_bonus() -> None:
    scored = score_pick(_locked(), {"home_goals": 2, "away_goals": 1})
    assert scored["user"] == {"exact": 3, "outcome": 1, "bonus": 0, "total": 4}
    assert scored["best_rival_total"] == 4
    assert scored["beat_ai"] is False  # tie never earns the bonus


def test_scoring_winner_miss_and_beat_ai_bonus() -> None:
    record = _locked()
    for rival in record["rivals"]:
        if rival["capability"] != "abstained":
            rival["score_pick"] = None
            rival["outcome_pick"] = "away"
            rival["capability"] = "outcome_only"
    winner = score_pick(record, {"home_goals": 4, "away_goals": 0})
    assert winner["user"] == {"exact": 0, "outcome": 1, "bonus": 1, "total": 2}
    assert winner["best_rival_total"] == 0

    miss = score_pick(record, {"home_goals": 0, "away_goals": 1})
    assert miss["user"]["total"] == 0


def test_outcome_only_rival_caps_at_one_and_all_abstained_disables_bonus() -> None:
    record = _locked()
    elo = next(r for r in record["rivals"] if r["family"] == "elo_ordlogit")
    assert score_pick(record, {"home_goals": 7, "away_goals": 0})["rivals"][3]["total"] == 1
    assert elo["score_pick"] is None

    for rival in record["rivals"]:
        rival.update(capability="abstained", score_pick=None, outcome_pick=None)
    scored = score_pick(record, {"home_goals": 2, "away_goals": 0})
    assert scored["user"]["outcome"] == 1
    assert scored["user"]["bonus"] == 0
    assert scored["beat_ai"] is False


def test_canonical_bytes_id_and_integrity_reject_tamper_and_rename() -> None:
    left = {"b": 2, "a": {"y": 4, "x": 3}}
    right = {"a": {"x": 3, "y": 4}, "b": 2}
    assert canonical_pick_bytes(left) == canonical_pick_bytes(right)
    assert pick_id(left) == pick_id(right)

    locked = _locked()
    assert verify_pick_integrity(copy.deepcopy(locked)) == locked
    with pytest.raises(ValueError, match="filename"):
        verify_pick_integrity(locked, expected_id="pk_00000000000000000000")
    tampered = copy.deepcopy(locked)
    tampered["user_pick"]["home_goals"] = 9
    with pytest.raises(ValueError, match="payload_sha256"):
        verify_pick_integrity(tampered)


def test_season_summary_order_streak_accuracy_mae_and_void_gap() -> None:
    views = [
        _view("m3", "2025-08-03T12:00:00Z", user_score=(1, 0), result=(0, 1)),
        _view("void", "2025-08-02T12:00:00Z", user_score=(1, 0), result=None, status="void"),
        _view("m1", "2025-08-01T12:00:00Z", user_score=(2, 1), result=(2, 1)),
        _view("m2", "2025-08-01T12:00:00Z", user_score=(1, 1), result=(2, 2)),
    ]
    summary = season_summary(views)
    assert [point["match_id"] for point in summary["series"]] == ["m1", "m2", "m3"]
    assert summary["counts"] == {"draft": 0, "locked": 0, "scored": 3, "void": 1}
    assert summary["accuracy"] == {"exact": 1 / 3, "winner": 2 / 3}
    assert summary["streak"] == {"current": 0, "best": 2}
    assert summary["goal_diff_mae"] == pytest.approx(2 / 3)
    assert summary["series"][-1]["user_total"] == summary["user"]["total"]


def test_empty_summary_and_july_boundary_filter() -> None:
    empty = season_summary([])
    assert empty["user"] == {"total": 0, "exact": 0, "outcome": 0, "bonus": 0}
    assert empty["accuracy"] == {"exact": 0.0, "winner": 0.0}
    assert empty["goal_diff_mae"] == 0.0
    assert football_season("2025-06-30T23:59:59Z") == "2024-25"
    assert football_season("2025-07-01T00:00:00Z") == "2025-26"

    june = _view("june", "2025-06-30T12:00:00Z", user_score=(1, 0), result=(1, 0))
    july = _view("july", "2025-07-01T00:00:00Z", user_score=(1, 0), result=(1, 0))
    assert season_summary([june, july], season="2025-26")["counts"]["scored"] == 1


def test_schema_validates_every_state() -> None:
    schema_path = Path(__file__).parents[2] / "docs" / "contracts" / "user_pick.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    draft = _draft()
    locked = _locked()
    scored = _view("m1", "2025-08-01T15:00:00Z", user_score=(2, 1), result=(2, 1))
    void = _view("gone", "2025-08-02T15:00:00Z", user_score=(0, 0), result=None, status="void")
    summary = season_summary([scored, void])
    listed = {
        "schema_version": PICK_SCHEMA_VERSION,
        "items": [scored, void],
        "total": 2,
        "limit": 50,
        "offset": 0,
    }
    for value in (draft, locked, scored, void, summary, listed):
        validator.validate(value)
    validate_user_pick(draft, schema_path)
    validate_user_pick(locked, schema_path)

    broken = copy.deepcopy(draft)
    broken["pick_id"] = "pk_0123456789abcdef0123"
    with pytest.raises(ValidationError):
        validate_user_pick(broken, schema_path)
