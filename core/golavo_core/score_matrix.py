"""Exact-score distribution: the grid the sealed 1X2 forecast already implies.

Phase 8, additive. The Poisson candidate families (independent, Dixon-Coles,
bivariate) already fit a full joint distribution over (home goals, away goals):
``PoissonModel`` builds a normalised score matrix and derives its sealed 1X2
probabilities from that exact matrix (home = mass below the diagonal, draw = the
diagonal, away = mass above it). This module turns that same matrix into a
compact, honest, JSON-serialisable ``score_matrix`` object and — the crux —
proves it stays *coherent* with the sealed numbers.

Coherence is a machine-checked invariant, split into two guarantees:

* **Artifact-level (needs only the stored JSON):** the displayed grid plus the
  outcome-decomposed tail bucket is an exact partition of the distribution, so
  its win/draw/loss marginals reproduce ``forecast.probs`` to within a stated
  rounding tolerance, and grid + tail sum to one. ``validate_artifact`` enforces
  this on every load — a hand-edited or incoherent matrix is rejected.
* **Model-level (needs the fitted model, checked at seal time and in tests):**
  the matrix mean reproduces ``forecast.expected_goals`` to within a stated
  tolerance, and re-deriving the model yields a byte-identical matrix.

There is no post-hoc probability calibration transform applied to a seal (the
Golavo calibration record is an empirical reliability ledger, not a re-scaler),
so the matrix and the 1X2 numbers cannot diverge under calibration: they are
both raw outputs of the *same* fitted model. If a future transform is ever
introduced it must be applied to this joint distribution and the marginals
re-derived — the coherence checks here would catch any asymmetric application.
"""

from __future__ import annotations

from typing import Any

import numpy as np

# Internal resolution the model integrates the joint distribution to. Chosen so
# truncation is negligible even at the rate clip (P(X>20) < 1e-7 at lambda=5):
# the matrix mean reproduces the raw Poisson rate to ~1e-6 and the 1X2 marginals
# are converged to ~1e-8. Both sealed probs and this grid come from this one
# matrix, so they are coherent by shared source rather than by luck.
SCORE_MATRIX_RESOLUTION = 20

# Display cap: concrete scorelines 0..N per side. Internationals and the top-5
# leagues almost never see a side score more than seven; everything beyond folds
# into one honest, outcome-decomposed tail bucket. Stored on the artifact so the
# contract is explicit rather than a magic constant.
SCORE_MATRIX_DISPLAY_N = 7

# Stored cell precision. Nine decimals keeps the accumulated rounding drift over
# the whole grid below 1e-7 while remaining ample for any display formatting.
GRID_PRECISION = 9

# Coherence tolerances (documented in docs/methodology). Before the seal is
# written the reproduction is exact to ~1e-12; PROB_TOLERANCE covers the loss
# after the sealed probs are quantised to six decimals with a drift correction on
# the largest outcome (worst case ~2.5e-6) plus grid rounding. GOALS_TOLERANCE
# covers the ~2e-6 matrix-mean-vs-rate residual plus the six-decimal rounding of
# expected_goals. Both are far tighter than any real incoherence, which is O(1e-2+).
PROB_TOLERANCE = 1e-5
GOALS_TOLERANCE = 1e-4


def outcome_probabilities(matrix: np.ndarray) -> tuple[float, float, float]:
    """(home, draw, away) win probabilities implied by a joint score matrix."""
    matrix = np.asarray(matrix, dtype=float)
    return (
        float(np.tril(matrix, -1).sum()),
        float(np.trace(matrix)),
        float(np.triu(matrix, 1).sum()),
    )


def expected_goals(matrix: np.ndarray) -> tuple[float, float]:
    """(home, away) mean goals implied by a joint score matrix."""
    matrix = np.asarray(matrix, dtype=float)
    goals = np.arange(matrix.shape[0])
    return (
        float((matrix.sum(axis=1) * goals).sum()),
        float((matrix.sum(axis=0) * goals).sum()),
    )


def build_score_matrix(
    matrix: np.ndarray,
    *,
    display_n: int = SCORE_MATRIX_DISPLAY_N,
    precision: int = GRID_PRECISION,
) -> dict[str, Any]:
    """Turn a full normalised joint matrix into the ``score_matrix`` contract object.

    Rows are home goals, columns away goals. The returned grid holds the exact
    per-scoreline probabilities for 0..``display_n`` on each side; every cell with
    a side scoring more than ``display_n`` folds into ``tail``, decomposed by
    outcome so the win/draw/loss marginals stay exactly recoverable. Grid + tail
    is a re-bucketing of the same distribution — no mass is created or dropped.
    """
    matrix = np.asarray(matrix, dtype=float)
    resolution = matrix.shape[0] - 1
    n = display_n
    goals = np.arange(matrix.shape[0])
    rows, cols = np.meshgrid(goals, goals, indexing="ij")
    home_mask = rows > cols
    draw_mask = rows == cols
    away_mask = rows < cols

    # Everything outside the displayed grid is the tail; zero the grid block so a
    # single boolean sum per outcome partitions it cleanly.
    outside = matrix.copy()
    outside[: n + 1, : n + 1] = 0.0
    tail_home = round(float(outside[home_mask].sum()), precision)
    tail_draw = round(float(outside[draw_mask].sum()), precision)
    tail_away = round(float(outside[away_mask].sum()), precision)
    tail_probability = round(tail_home + tail_draw + tail_away, precision)

    grid_block = matrix[: n + 1, : n + 1]
    grid = [[round(float(grid_block[i, j]), precision) for j in range(n + 1)] for i in range(n + 1)]

    # Most likely concrete scoreline, taken from the STORED (rounded) grid with an
    # explicit tie-break (highest probability, then fewest home goals, then fewest
    # away goals) so it matches the validator exactly even when a near-tie rounds
    # to equal values.
    ml_value, ml_home, ml_away = max(
        ((grid[i][j], i, j) for i in range(n + 1) for j in range(n + 1)),
        key=lambda cell: (cell[0], -cell[1], -cell[2]),
    )
    most_likely = {"home": int(ml_home), "away": int(ml_away), "probability": ml_value}

    total = round(sum(sum(row) for row in grid) + tail_probability, precision)
    return {
        "max_goals": int(n),
        "resolution": int(resolution),
        "grid": grid,
        "tail": {
            "probability": tail_probability,
            "home": tail_home,
            "draw": tail_draw,
            "away": tail_away,
        },
        "most_likely": most_likely,
        "total_probability": total,
    }


def stored_marginals(score_matrix: dict[str, Any]) -> tuple[float, float, float]:
    """(home, draw, away) reconstructed from the STORED grid + tail alone.

    Uses only the artifact JSON — no model — so it is the exact quantity
    ``validate_artifact`` checks against the sealed 1X2 probabilities.
    """
    n = int(score_matrix["max_goals"])
    grid = score_matrix["grid"]
    home = draw = away = 0.0
    for i in range(n + 1):
        for j in range(n + 1):
            value = float(grid[i][j])
            if i > j:
                home += value
            elif i == j:
                draw += value
            else:
                away += value
    tail = score_matrix["tail"]
    return (
        home + float(tail["home"]),
        draw + float(tail["draw"]),
        away + float(tail["away"]),
    )


def stored_coherence_violations(
    score_matrix: dict[str, Any],
    probs: dict[str, float],
    *,
    prob_tol: float = PROB_TOLERANCE,
) -> list[str]:
    """Artifact-only coherence problems (empty list == coherent).

    Checks that only need the stored JSON: the grid is well-formed, the tail
    decomposition reconciles, grid + tail sums to one, the win/draw/loss
    marginals reproduce the sealed probabilities, and the flagged most-likely
    scoreline really is the grid's argmax.
    """
    violations: list[str] = []
    n = int(score_matrix["max_goals"])
    grid = score_matrix["grid"]

    if len(grid) != n + 1 or any(len(row) != n + 1 for row in grid):
        violations.append(f"grid is not {n + 1}x{n + 1}")
        return violations  # further checks assume a well-formed grid

    tail = score_matrix["tail"]
    tail_sum = float(tail["home"]) + float(tail["draw"]) + float(tail["away"])
    tail_prob = float(tail["probability"])
    if abs(tail_sum - tail_prob) > prob_tol:
        violations.append(
            f"tail decomposition {tail_sum:.9f} != tail.probability {tail_prob:.9f}"
        )

    total = sum(float(v) for row in grid for v in row) + float(tail["probability"])
    if abs(total - 1.0) > prob_tol:
        violations.append(f"grid + tail sums to {total:.9f}, not 1")
    if abs(float(score_matrix["total_probability"]) - total) > prob_tol:
        violations.append("total_probability disagrees with grid + tail")

    home, draw, away = stored_marginals(score_matrix)
    for key, got in (("home", home), ("draw", draw), ("away", away)):
        want = float(probs[key])
        if abs(got - want) > prob_tol:
            violations.append(
                f"marginal {key}={got:.9f} does not reproduce sealed prob {want:.9f}"
            )

    flat = [(float(grid[i][j]), i, j) for i in range(n + 1) for j in range(n + 1)]
    best = max(flat, key=lambda t: (t[0], -t[1], -t[2]))
    ml = score_matrix["most_likely"]
    if (int(ml["home"]), int(ml["away"])) != (best[1], best[2]):
        violations.append("most_likely is not the grid argmax")
    elif abs(float(ml["probability"]) - best[0]) > prob_tol:
        violations.append("most_likely.probability disagrees with its grid cell")
    return violations


def assert_stored_coherent(
    score_matrix: dict[str, Any],
    probs: dict[str, float],
    *,
    prob_tol: float = PROB_TOLERANCE,
) -> None:
    """Raise ValueError if the stored score matrix is not coherent with ``probs``."""
    violations = stored_coherence_violations(score_matrix, probs, prob_tol=prob_tol)
    if violations:
        raise ValueError("incoherent score_matrix: " + "; ".join(violations))


def assert_model_coherent(
    matrix: np.ndarray,
    score_matrix: dict[str, Any],
    probs: dict[str, float],
    expected_goals_dict: dict[str, float],
    *,
    prob_tol: float = PROB_TOLERANCE,
    goals_tol: float = GOALS_TOLERANCE,
) -> None:
    """Seal-time proof: the fitted matrix reproduces BOTH the sealed 1X2 probs and
    expected goals, and the stored grid is a faithful re-bucketing of it.

    Raises ValueError (which aborts the seal) if any invariant is violated, so an
    incoherent matrix is never written — satisfying the "never display a matrix
    the sealed numbers don't imply" guarantee.
    """
    violations: list[str] = []
    home, draw, away = outcome_probabilities(matrix)
    for key, got in (("home", home), ("draw", draw), ("away", away)):
        want = float(probs[key])
        if abs(got - want) > prob_tol:
            violations.append(f"matrix marginal {key}={got:.9f} != sealed prob {want:.9f}")

    eg_home, eg_away = expected_goals(matrix)
    if abs(eg_home - float(expected_goals_dict["home"])) > goals_tol:
        violations.append(
            f"matrix E[home goals]={eg_home:.6f} != expected_goals.home "
            f"{float(expected_goals_dict['home']):.6f}"
        )
    if abs(eg_away - float(expected_goals_dict["away"])) > goals_tol:
        violations.append(
            f"matrix E[away goals]={eg_away:.6f} != expected_goals.away "
            f"{float(expected_goals_dict['away']):.6f}"
        )

    violations.extend(stored_coherence_violations(score_matrix, probs, prob_tol=prob_tol))
    if violations:
        raise ValueError("incoherent score_matrix at seal time: " + "; ".join(violations))


# --- Derived markets --------------------------------------------------------
#
# Analysis views a reader can compute from a SEALED artifact with no new data and
# no new model — pure re-buckets of numbers the seal already committed to. Only
# the markets that are EXACTLY recoverable from the stored grid + outcome-tail are
# offered here, so every figure is a true marginal of the same sealed distribution
# the coherence checks above already guarantee. Deliberately NOT included: both-
# teams-to-score, clean sheets, and per-team totals — the tail is decomposed by
# match outcome only (home/draw/away), so those quantities carry an unstated tail
# error and would need exact marginals sealed at seal time (a schema bump) to be
# honest. This module uses analysis language ("chance of over 2.5 goals"), never
# betting-product framing.


def double_chance(probs: dict[str, float]) -> dict[str, float]:
    """The three double-chance probabilities: the sealed 1X2 taken two at a time.

    Pure sums of ``forecast.probs`` — exact and independent of the score grid.
    """
    home, draw, away = float(probs["home"]), float(probs["draw"]), float(probs["away"])
    return {
        "home_or_draw": round(home + draw, 6),
        "home_or_away": round(home + away, 6),
        "draw_or_away": round(draw + away, 6),
    }


def total_goals_bands(score_matrix: dict[str, Any]) -> dict[str, float]:
    """Exact distribution of total match goals, bucketed so every figure is a true
    marginal of the stored grid.

    Totals ``0..N`` (``N = score_matrix['max_goals']``, the per-side display cap)
    lie entirely inside the grid and are individually exact. Everything from
    ``N+1`` up folds into one ``'(N+1)_plus'`` bucket — exact because the tail (a
    side scoring more than ``N``) always contributes at least ``N+1`` total goals,
    so grid cells with total ``> N`` plus the whole tail is precisely
    ``P(total >= N+1)``. Individual totals ``N+1..2N`` are intentionally not split
    out: the grid holds only part of their mass and the rest is in the tail.
    """
    n = int(score_matrix["max_goals"])
    grid = score_matrix["grid"]
    bands = {str(t): 0.0 for t in range(n + 1)}
    over_bucket = float(score_matrix["tail"]["probability"])
    for i in range(n + 1):
        for j in range(n + 1):
            total = i + j
            value = float(grid[i][j])
            if total <= n:
                bands[str(total)] = round(bands[str(total)] + value, GRID_PRECISION)
            else:
                over_bucket = round(over_bucket + value, GRID_PRECISION)
    bands[f"{n + 1}_plus"] = round(over_bucket, GRID_PRECISION)
    return bands


def total_goals_over_under(score_matrix: dict[str, Any], line: float) -> dict[str, float]:
    """Exact P(total goals over / under a half-goal ``line``), for ``0 < line < N+1``.

    ``over`` is ``P(total > line)``. Because every tail cell (a side scoring more
    than ``N``) has at least ``N+1`` total goals, any line below ``N+1`` puts the
    entire tail on the ``over`` side, so both sides are exact partitions of the
    stored grid. A line at or above ``N+1`` would require splitting the tail by
    total goals — mass the artifact does not carry — and is refused rather than
    approximated.
    """
    n = int(score_matrix["max_goals"])
    if not 0 < line < n + 1:
        raise ValueError(
            f"total-goals line must lie in (0, {n + 1}) to be exactly recoverable "
            f"from the stored grid; got {line}"
        )
    grid = score_matrix["grid"]
    over = float(score_matrix["tail"]["probability"])  # every tail total exceeds the line
    under = 0.0
    for i in range(n + 1):
        for j in range(n + 1):
            value = float(grid[i][j])
            if i + j > line:
                over += value
            else:
                under += value
    return {
        "line": float(line),
        "over": round(over, GRID_PRECISION),
        "under": round(under, GRID_PRECISION),
    }
