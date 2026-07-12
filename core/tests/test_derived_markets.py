"""Derived markets must be EXACT marginals of the sealed distribution.

Each helper is checked against ground truth computed directly from the full joint
score matrix the seal was built from — so a figure the UI shows can never diverge
from the sealed grid. Only exactly-recoverable markets exist (double chance,
total-goal over/under with line < N+1, total-goal bands); tail-ambiguous ones
(BTTS, clean sheets, team totals) are deliberately absent and not tested here
because they are not offered.
"""

from __future__ import annotations

import json
from math import exp, factorial
from pathlib import Path

import numpy as np
import pytest
from golavo_core.artifacts import seal_forecast
from golavo_core.score_matrix import (
    build_score_matrix,
    double_chance,
    total_goals_bands,
    total_goals_over_under,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK = REPO_ROOT / "packs/martj42-internationals"
_LINES = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5]


def _poisson_matrix(lam_home: float, lam_away: float, size: int = 21) -> np.ndarray:
    """A normalised independent-Poisson joint matrix — a stand-in for a fitted model."""
    home = np.array([exp(-lam_home) * lam_home**k / factorial(k) for k in range(size)])
    away = np.array([exp(-lam_away) * lam_away**k / factorial(k) for k in range(size)])
    matrix = np.outer(home, away)
    return matrix / matrix.sum()


def _truth_total_distribution(matrix: np.ndarray) -> dict[int, float]:
    truth: dict[int, float] = {}
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            truth[i + j] = truth.get(i + j, 0.0) + float(matrix[i, j])
    return truth


# The stored grid is quantised to 9 dp per cell (GRID_PRECISION), so a marginal
# agrees with the unrounded model matrix only to within that quantisation floor,
# which accumulates to a few ×1e-9 across the grid. GROUND_TRUTH_TOL sits safely
# above that noise yet far below any real logic error (a wrong cell is off by
# O(1e-2)). PARTITION_TOL checks the tighter invariant that no mass is lost: the
# helper's own outputs sum back to the stored total_probability.
GROUND_TRUTH_TOL = 1e-7
PARTITION_TOL = 1e-8


def test_total_goals_bands_are_exact_marginals() -> None:
    matrix = _poisson_matrix(1.7, 1.1)
    sm = build_score_matrix(matrix)
    n = int(sm["max_goals"])
    truth = _truth_total_distribution(matrix)

    bands = total_goals_bands(sm)
    for total in range(n + 1):
        assert bands[str(total)] == pytest.approx(truth[total], abs=GROUND_TRUTH_TOL)
    tail_truth = sum(p for t, p in truth.items() if t >= n + 1)
    assert bands[f"{n + 1}_plus"] == pytest.approx(tail_truth, abs=GROUND_TRUTH_TOL)
    # No mass lost: the bands sum back to the stored total probability.
    assert sum(bands.values()) == pytest.approx(float(sm["total_probability"]), abs=PARTITION_TOL)


def test_over_under_is_exact_for_every_supported_line() -> None:
    matrix = _poisson_matrix(1.4, 1.9)
    sm = build_score_matrix(matrix)
    truth = _truth_total_distribution(matrix)
    total_probability = float(sm["total_probability"])

    for line in _LINES:
        ou = total_goals_over_under(sm, line)
        over_truth = sum(p for t, p in truth.items() if t > line)
        assert ou["over"] == pytest.approx(over_truth, abs=GROUND_TRUTH_TOL)
        # over + under is an exact partition of the stored grid.
        assert ou["over"] + ou["under"] == pytest.approx(total_probability, abs=PARTITION_TOL)

    overs = [total_goals_over_under(sm, line)["over"] for line in _LINES]
    assert all(overs[k] >= overs[k + 1] for k in range(len(overs) - 1))


def test_over_under_refuses_a_line_it_cannot_recover_exactly() -> None:
    sm = build_score_matrix(_poisson_matrix(1.2, 1.0))
    n = int(sm["max_goals"])
    for bad in (0.0, -1.0, float(n + 1), float(n + 2), 100.0):
        with pytest.raises(ValueError, match="exactly recoverable"):
            total_goals_over_under(sm, bad)


def test_double_chance_is_exact_pair_sums() -> None:
    probs = {"home": 0.52, "draw": 0.27, "away": 0.21}
    dc = double_chance(probs)
    assert dc["home_or_draw"] == pytest.approx(0.79)
    assert dc["home_or_away"] == pytest.approx(0.73)
    assert dc["draw_or_away"] == pytest.approx(0.48)


def test_derived_markets_agree_with_a_real_sealed_artifact(tmp_path: Path) -> None:
    """End-to-end: the markets reconcile with a genuine dixon_coles seal's grid."""
    path = seal_forecast(
        pack_dir=PACK,
        output_dir=tmp_path / "ledger",
        date="2026-07-11",
        home_team="Norway",
        away_team="England",
        as_of_utc="2026-07-10T20:00:00Z",
        family="dixon_coles",
    )
    sm = json.loads(path.read_text(encoding="utf-8"))["forecast"]["score_matrix"]
    assert sm is not None

    bands = total_goals_bands(sm)
    assert sum(bands.values()) == pytest.approx(1.0, abs=1e-6)
    # P(over 0.5) == 1 - P(exactly 0-0); consistent with the bands view.
    ou = total_goals_over_under(sm, 0.5)
    assert ou["under"] == pytest.approx(bands["0"], abs=1e-9)
    assert ou["over"] + ou["under"] == pytest.approx(1.0, abs=1e-6)
