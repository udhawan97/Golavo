"""Deterministic Phase 0 candidate models for international 1X2 forecasts."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import poisson

from golavo_core.ingest import assert_no_future_rows
from golavo_core.score_matrix import SCORE_MATRIX_RESOLUTION

FAMILIES = (
    "climatological",
    "elo_ordlogit",
    "poisson_independent",
    "dixon_coles",
    "bivariate_poisson",
)

# The Elo update constants and rule, shared so the standalone ratings table
# (golavo_core.ratings) computes byte-identically to the forecast model below.
# Changing any of these changes both.
ELO_INITIAL = 1500.0
ELO_K_FACTOR = 28.0
ELO_HOME_ADVANTAGE = 60.0


def elo_match_delta(
    home_rating: float,
    away_rating: float,
    home_score: int,
    away_score: int,
    neutral: bool,
    *,
    k_factor: float = ELO_K_FACTOR,
    home_advantage: float = ELO_HOME_ADVANTAGE,
) -> float:
    """The rating change the home team earns from one match (the away team's is its negation).

    Goal-difference weighted (log1p) with a home advantage on non-neutral ground —
    the single source of truth for the Elo update.
    """
    advantage = 0.0 if neutral else home_advantage
    expected = 1.0 / (1.0 + 10.0 ** (-((home_rating + advantage) - away_rating) / 400.0))
    if home_score > away_score:
        actual = 1.0
    elif home_score == away_score:
        actual = 0.5
    else:
        actual = 0.0
    goal_difference = abs(int(home_score) - int(away_score))
    multiplier = max(1.0, math.log1p(goal_difference))
    return k_factor * multiplier * (actual - expected)


@dataclass(frozen=True)
class Prediction:
    probs: tuple[float, float, float]
    expected_goals: tuple[float, float] | None
    params: dict[str, Any]
    # The full normalised joint score matrix (rows=home goals, cols=away goals)
    # for goal-based families; None for families that model no goal process
    # (climatological, elo_ordlogit). compare=False keeps the array out of the
    # frozen dataclass's __eq__/__hash__.
    matrix: np.ndarray | None = field(default=None, compare=False)


def _normalise(values: np.ndarray) -> tuple[float, float, float]:
    clipped = np.clip(values.astype(float), 1e-12, None)
    clipped /= clipped.sum()
    return tuple(float(value) for value in clipped)  # type: ignore[return-value]


def _outcomes(matches: pd.DataFrame) -> np.ndarray:
    return np.where(
        matches["home_score"].to_numpy() > matches["away_score"].to_numpy(),
        0,
        np.where(
            matches["home_score"].to_numpy() == matches["away_score"].to_numpy(), 1, 2
        ),
    )


class ClimatologicalModel:
    family = "climatological"

    def __init__(self) -> None:
        self.probs = np.array([1 / 3, 1 / 3, 1 / 3], dtype=float)

    def fit(self, matches: pd.DataFrame, cutoff_utc: str) -> ClimatologicalModel:
        assert_no_future_rows(matches, cutoff_utc)
        counts = np.bincount(_outcomes(matches), minlength=3).astype(float) + 1.0
        self.probs = counts / counts.sum()
        return self

    def predict(self, home_team: str, away_team: str, neutral: bool) -> Prediction:
        del home_team, away_team, neutral
        return Prediction(_normalise(self.probs), None, {"laplace_alpha": 1.0})


class EloOrdinalLogitModel:
    family = "elo_ordlogit"

    def __init__(
        self,
        *,
        k_factor: float = ELO_K_FACTOR,
        home_advantage: float = ELO_HOME_ADVANTAGE,
        scale: float = 300.0,
        threshold: float = 0.575,
    ) -> None:
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.scale = scale
        self.threshold = threshold
        self.ratings: dict[str, float] = {}

    def fit(self, matches: pd.DataFrame, cutoff_utc: str) -> EloOrdinalLogitModel:
        assert_no_future_rows(matches, cutoff_utc)
        ratings: dict[str, float] = {}
        ordered = matches.sort_values(
            ["date", "home_team", "away_team", "match_id"], kind="mergesort"
        )
        for row in ordered.itertuples(index=False):
            home_rating = ratings.get(str(row.home_team), ELO_INITIAL)
            away_rating = ratings.get(str(row.away_team), ELO_INITIAL)
            delta = elo_match_delta(
                home_rating,
                away_rating,
                row.home_score,
                row.away_score,
                bool(row.neutral),
                k_factor=self.k_factor,
                home_advantage=self.home_advantage,
            )
            ratings[str(row.home_team)] = home_rating + delta
            ratings[str(row.away_team)] = away_rating - delta
        self.ratings = ratings
        return self

    def predict(self, home_team: str, away_team: str, neutral: bool) -> Prediction:
        advantage = 0.0 if neutral else self.home_advantage
        strength = (
            self.ratings.get(home_team, ELO_INITIAL)
            - self.ratings.get(away_team, ELO_INITIAL)
            + advantage
        ) / self.scale
        lower = -self.threshold
        upper = self.threshold
        cdf_away = 1.0 / (1.0 + math.exp(-(lower - strength)))
        cdf_draw = 1.0 / (1.0 + math.exp(-(upper - strength)))
        probs = np.array([1.0 - cdf_draw, cdf_draw - cdf_away, cdf_away])
        params = {
            "k_factor": self.k_factor,
            "home_advantage": self.home_advantage,
            "scale": self.scale,
            "threshold": self.threshold,
        }
        return Prediction(_normalise(probs), None, params)


class PoissonModel:
    def __init__(self, family: str, *, xi: float = 0.001, rho: float = -0.08) -> None:
        if family not in {"poisson_independent", "dixon_coles", "bivariate_poisson"}:
            raise ValueError(f"unsupported Poisson family: {family}")
        self.family = family
        self.xi = xi
        self.rho = rho
        self.as_of = pd.Timestamp("1970-01-01", tz="UTC")
        self.base_home = 1.4
        self.base_away = 1.1
        self.attack: dict[str, float] = {}
        self.defence: dict[str, float] = {}
        self.shared = 0.08

    def fit(self, matches: pd.DataFrame, cutoff_utc: str) -> PoissonModel:
        assert_no_future_rows(matches, cutoff_utc)
        self.as_of = pd.Timestamp(cutoff_utc)
        if self.as_of.tzinfo is None:
            self.as_of = self.as_of.tz_localize("UTC")
        else:
            self.as_of = self.as_of.tz_convert("UTC")
        dates = pd.to_datetime(matches["date"], utc=True)
        days = (self.as_of - dates).dt.total_seconds().to_numpy() / 86400.0
        weights = np.exp(-self.xi * np.maximum(days, 0.0))

        home_goals = matches["home_score"].to_numpy(dtype=float)
        away_goals = matches["away_score"].to_numpy(dtype=float)
        neutral = matches["neutral"].to_numpy(dtype=bool)
        non_neutral = ~neutral
        if non_neutral.any():
            self.base_home = float(
                np.average(home_goals[non_neutral], weights=weights[non_neutral])
            )
            self.base_away = float(
                np.average(away_goals[non_neutral], weights=weights[non_neutral])
            )
        neutral_base = float(np.average((home_goals + away_goals) / 2.0, weights=weights))
        overall_base = max(0.2, neutral_base)

        goals_for: dict[str, float] = defaultdict(float)
        goals_against: dict[str, float] = defaultdict(float)
        team_weight: dict[str, float] = defaultdict(float)
        for row, weight in zip(matches.itertuples(index=False), weights, strict=True):
            home = str(row.home_team)
            away = str(row.away_team)
            goals_for[home] += weight * float(row.home_score)
            goals_against[home] += weight * float(row.away_score)
            goals_for[away] += weight * float(row.away_score)
            goals_against[away] += weight * float(row.home_score)
            team_weight[home] += weight
            team_weight[away] += weight

        prior_weight = 8.0
        for team in sorted(team_weight):
            denominator = team_weight[team] + prior_weight
            gf = (goals_for[team] + prior_weight * overall_base) / denominator
            ga = (goals_against[team] + prior_weight * overall_base) / denominator
            self.attack[team] = float(np.clip(gf / overall_base, 0.35, 2.8))
            self.defence[team] = float(np.clip(ga / overall_base, 0.35, 2.8))

        residual_home = home_goals - np.average(home_goals, weights=weights)
        residual_away = away_goals - np.average(away_goals, weights=weights)
        covariance = float(np.average(residual_home * residual_away, weights=weights))
        self.shared = float(np.clip(covariance, 0.0, 0.3))
        return self

    def _rates(self, home_team: str, away_team: str, neutral: bool) -> tuple[float, float]:
        if neutral:
            base = math.sqrt(self.base_home * self.base_away)
            home_base = away_base = base
        else:
            home_base, away_base = self.base_home, self.base_away
        home = home_base * self.attack.get(home_team, 1.0) * self.defence.get(away_team, 1.0)
        away = away_base * self.attack.get(away_team, 1.0) * self.defence.get(home_team, 1.0)
        return float(np.clip(home, 0.15, 5.0)), float(np.clip(away, 0.15, 5.0))

    def _matrix(
        self, home_rate: float, away_rate: float, max_goals: int = SCORE_MATRIX_RESOLUTION
    ) -> np.ndarray:
        values = np.arange(max_goals + 1)
        if self.family == "bivariate_poisson":
            shared = min(self.shared, home_rate * 0.4, away_rate * 0.4)
            matrix = np.zeros((max_goals + 1, max_goals + 1), dtype=float)
            for common in range(max_goals + 1):
                common_p = poisson.pmf(common, shared)
                for home_only in range(max_goals + 1 - common):
                    for away_only in range(max_goals + 1 - common):
                        matrix[home_only + common, away_only + common] += (
                            common_p
                            * poisson.pmf(home_only, max(home_rate - shared, 1e-9))
                            * poisson.pmf(away_only, max(away_rate - shared, 1e-9))
                        )
        else:
            matrix = np.outer(poisson.pmf(values, home_rate), poisson.pmf(values, away_rate))
        if self.family == "dixon_coles":
            matrix[0, 0] *= 1.0 - home_rate * away_rate * self.rho
            matrix[0, 1] *= 1.0 + home_rate * self.rho
            matrix[1, 0] *= 1.0 + away_rate * self.rho
            matrix[1, 1] *= 1.0 - self.rho
        matrix = np.clip(matrix, 0.0, None)
        matrix /= matrix.sum()
        return matrix

    def predict(self, home_team: str, away_team: str, neutral: bool) -> Prediction:
        home_rate, away_rate = self._rates(home_team, away_team, neutral)
        # The sealed 1X2 probabilities AND the exact-score matrix are both derived
        # from this one converged matrix, so they are coherent by construction.
        matrix = self._matrix(home_rate, away_rate)
        probs = np.array(
            [np.tril(matrix, -1).sum(), np.trace(matrix), np.triu(matrix, 1).sum()]
        )
        params: dict[str, Any] = {"xi": self.xi, "prior_matches": 8}
        if self.family == "dixon_coles":
            params["rho"] = self.rho
        if self.family == "bivariate_poisson":
            params["shared_lambda"] = self.shared
        expected = (home_rate, away_rate)
        return Prediction(_normalise(probs), expected, params, matrix=matrix)

    def predict_duration(
        self,
        home_team: str,
        away_team: str,
        neutral: bool,
        *,
        fraction: float,
    ) -> Prediction:
        """Predict a declared fraction of a regulation match with the same fit.

        Tournament outlooks use this only for the pre-registered 30-minute
        extra-time branch (``fraction=1/3``).  The fitted attack, defence and
        dependence parameters are unchanged; only both scoring intensities are
        scaled by the declared duration.  Keeping the operation on the model
        prevents a simulation from inventing a second goal process beside the
        one Golavo already exposes.
        """
        if not 0.0 < fraction <= 1.0:
            raise ValueError("fraction must be in (0, 1]")
        home_rate, away_rate = self._rates(home_team, away_team, neutral)
        home_rate *= fraction
        away_rate *= fraction
        matrix = self._matrix(home_rate, away_rate)
        probs = np.array(
            [np.tril(matrix, -1).sum(), np.trace(matrix), np.triu(matrix, 1).sum()]
        )
        params: dict[str, Any] = {
            "xi": self.xi,
            "prior_matches": 8,
            "duration_fraction": fraction,
        }
        if self.family == "dixon_coles":
            params["rho"] = self.rho
        if self.family == "bivariate_poisson":
            params["shared_lambda"] = self.shared
        return Prediction(
            _normalise(probs),
            (home_rate, away_rate),
            params,
            matrix=matrix,
        )


def fit_model(
    family: str, matches: pd.DataFrame, cutoff_utc: str, *, xi: float = 0.001
) -> ClimatologicalModel | EloOrdinalLogitModel | PoissonModel:
    """Fit one frozen Phase 0 candidate family."""
    if family == "climatological":
        return ClimatologicalModel().fit(matches, cutoff_utc)
    if family == "elo_ordlogit":
        return EloOrdinalLogitModel().fit(matches, cutoff_utc)
    if family in {"poisson_independent", "dixon_coles", "bivariate_poisson"}:
        return PoissonModel(family, xi=xi).fit(matches, cutoff_utc)
    raise ValueError(f"unknown model family: {family}")
