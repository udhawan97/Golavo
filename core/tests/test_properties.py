"""Property-based tests for Golavo's load-bearing determinism invariants.

The suite is invariant-heavy but was, until now, entirely example-based. These
Hypothesis properties fuzz the two invariants whose correctness the seal ledger
depends on most: the probability canonicalization that makes an artifact id
stable, and the chronological cutoff that keeps training leakage-free.
"""

from __future__ import annotations

import pandas as pd
from golavo_core.artifacts import canonical_bytes
from golavo_core.ingest.snapshot import assert_no_future_rows, training_rows
from hypothesis import given, settings
from hypothesis import strategies as st

# A probability triple over (home, draw, away) that sums to ~1.0. We draw three
# nonnegative weights and normalize; degenerate all-zero draws are filtered.
_weights = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


@st.composite
def _probs(draw: st.DrawFn) -> dict[str, float]:
    raw = [draw(_weights) for _ in range(3)]
    total = sum(raw)
    if total <= 0:
        raw = [1.0, 1.0, 1.0]
        total = 3.0
    return dict(zip(("home", "draw", "away"), (w / total for w in raw), strict=True))


@given(probs=_probs())
@settings(max_examples=400)
def test_canonicalized_probs_sum_to_one_and_pass_validation(probs: dict[str, float]) -> None:
    """Rounding to 6 dp with the largest-outcome drift correction always re-sums to 1.

    validate_artifact rejects any stored probs whose sum drifts past 1e-6, so this
    property guards the exact contract every seal must satisfy on load.
    """
    import json

    artifact = {"forecast": {"probs": probs, "score_matrix": None}}
    stored = json.loads(canonical_bytes(artifact).decode())["forecast"]["probs"]
    # validate_artifact rejects a stored sum drifting past 1e-6; the correction
    # must keep every canonicalized triple inside that tolerance.
    assert abs(sum(stored.values()) - 1.0) <= 1e-6
    assert all(0.0 <= v <= 1.0 for v in stored.values())


@given(probs=_probs())
@settings(max_examples=200)
def test_canonical_bytes_is_deterministic(probs: dict[str, float]) -> None:
    """The same forecast canonicalizes to byte-identical output — the id is stable."""
    a = {"forecast": {"probs": dict(probs), "score_matrix": None}}
    b = {"forecast": {"probs": dict(probs), "score_matrix": None}}
    assert canonical_bytes(a) == canonical_bytes(b)


@st.composite
def _match_frame(draw: st.DrawFn) -> tuple[pd.DataFrame, pd.Timestamp]:
    n = draw(st.integers(min_value=1, max_value=40))
    day_offsets = draw(st.lists(st.integers(min_value=-500, max_value=500), min_size=n, max_size=n))
    completes = draw(st.lists(st.booleans(), min_size=n, max_size=n))
    base = pd.Timestamp("2020-01-01", tz="UTC")
    frame = pd.DataFrame(
        {
            "match_id": [f"m_{i:04d}" for i in range(n)],
            "date": [base + pd.Timedelta(days=int(d)) for d in day_offsets],
            "is_complete": completes,
        }
    )
    cutoff = base + pd.Timedelta(days=int(draw(st.integers(min_value=-500, max_value=500))))
    return frame, cutoff


@given(data=_match_frame())
@settings(max_examples=300, deadline=None)
def test_training_rows_never_leaks_future_or_incomplete(
    data: tuple[pd.DataFrame, pd.Timestamp],
) -> None:
    """training_rows returns only completed rows at or before the cutoff.

    This is the chronological invariant every model fit relies on; a single
    post-cutoff row would be look-ahead leakage into a sealed forecast.
    """
    frame, cutoff = data
    selected = training_rows(frame, cutoff)
    dates = pd.to_datetime(selected["date"], utc=True)
    assert (dates <= cutoff).all()
    assert bool(selected["is_complete"].all())
    # The invariant checker agrees and never raises on the selection.
    assert_no_future_rows(selected, cutoff)
    # Nothing eligible was dropped: every completed on-or-before row is present.
    eligible = frame[(pd.to_datetime(frame["date"], utc=True) <= cutoff) & frame["is_complete"]]
    assert set(selected["match_id"]) == set(eligible["match_id"])


@st.composite
def _rating_frame_with_future(draw: st.DrawFn) -> tuple[pd.DataFrame, str]:
    teams = ["Alpha", "Bravo", "Charlie", "Delta"]
    n = draw(st.integers(min_value=1, max_value=25))
    rows = []
    for i in range(n):
        home, away = draw(st.sampled_from(teams)), draw(st.sampled_from(teams))
        if home == away:
            away = teams[(teams.index(home) + 1) % len(teams)]
        day = draw(st.integers(min_value=-400, max_value=400))
        rows.append(
            {
                "match_id": f"m_{i:04d}",
                "date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=day),
                "home_team": home,
                "away_team": away,
                "home_score": draw(st.integers(min_value=0, max_value=5)),
                "away_score": draw(st.integers(min_value=0, max_value=5)),
                "neutral": draw(st.booleans()),
                "is_complete": True,
            }
        )
    frame = pd.DataFrame(rows)
    frame["kickoff_utc"] = pd.to_datetime(frame["date"], utc=True)
    return frame, "2024-01-01T00:00:00Z"


@given(data=_rating_frame_with_future())
@settings(max_examples=200, deadline=None)
def test_elo_rating_as_of_is_frozen_against_later_matches(
    data: tuple[pd.DataFrame, str],
) -> None:
    """A Golavo rating at an instant is a pure replay of the past, so any matches
    after that instant — however many, however lopsided — leave it byte-identical."""
    from golavo_core.ratings import elo_trajectory

    frame, cutoff = data
    before = frame[pd.to_datetime(frame["date"]) <= pd.Timestamp(cutoff).tz_localize(None)]
    full = elo_trajectory(frame, as_of_utc=cutoff)
    only_past = elo_trajectory(before, as_of_utc=cutoff)
    assert full["teams"] == only_past["teams"]
