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

# The five Phase 0 candidates, frozen: their fitted numbers must not move, so
# every committed backtest stays comparable with the one before it.
FROZEN_FAMILIES = (
    "climatological",
    "elo_ordlogit",
    "poisson_independent",
    "dixon_coles",
    "bivariate_poisson",
)

# Every registered candidate. Later entries are club-league candidates on trial:
# they are fitted and reported, but earn a council seat only by beating the
# incumbents, and no international fold evaluates them (see evaluation.evaluate).
FAMILIES = (*FROZEN_FAMILIES, "contextual_dixon_coles")

# Families whose joint matrix carries the Dixon-Coles low-score correction. The
# contextual family is a Dixon-Coles at heart — it adds context to the rates, not
# a second goal process — so it inherits the same rho adjustment.
_DIXON_COLES_FAMILIES = frozenset({"dixon_coles", "contextual_dixon_coles"})
_POISSON_FAMILIES = frozenset(
    {"poisson_independent", "dixon_coles", "bivariate_poisson", "contextual_dixon_coles"}
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


def schedule_rest_days(
    matches: pd.DataFrame,
) -> tuple[list[float | None], list[float | None]]:
    """Days since each side last played, for every row, read from dates alone.

    Deliberately score-blind: a published fixture list is enough to compute it,
    which is what makes rest quotable before kickoff rather than a fact only the
    final whistle settles. A club's first appearance in the frame has no gap and
    is reported as ``None`` rather than guessed.

    Returned lists are aligned to ``matches``' row order, not to the chronological
    order the walk uses, so a caller may hand in any frame and index the result
    positionally.
    """
    frame = matches.reset_index(drop=True)
    dates = pd.to_datetime(frame["date"], utc=True)
    # Order by the PARSED instants, never the raw column: a pack whose dates are
    # strings would otherwise sort lexically, and one with mixed offsets by wall
    # clock, either of which silently reorders the walk and mismeasures a gap.
    tie_breaks = [key for key in ("home_team", "away_team", "match_id") if key in frame.columns]
    order = (
        frame.assign(_instant=dates)
        .sort_values(["_instant", *tie_breaks], kind="mergesort")
        .index
    )

    home_rest: list[float | None] = [None] * len(frame)
    away_rest: list[float | None] = [None] * len(frame)
    last_seen: dict[str, pd.Timestamp] = {}
    for position in order:
        date = dates.iloc[position]
        home = str(frame["home_team"].iloc[position])
        away = str(frame["away_team"].iloc[position])
        for team, output in ((home, home_rest), (away, away_rest)):
            previous = last_seen.get(team)
            if previous is not None:
                gap = (date - previous).days
                output[position] = float(gap) if gap >= 0 else None
        last_seen[home] = date
        last_seen[away] = date
    return home_rest, away_rest


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
        if family not in _POISSON_FAMILIES:
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
        if self.family in _DIXON_COLES_FAMILIES:
            matrix[0, 0] *= 1.0 - home_rate * away_rate * self.rho
            matrix[0, 1] *= 1.0 + home_rate * self.rho
            matrix[1, 0] *= 1.0 + away_rate * self.rho
            matrix[1, 1] *= 1.0 - self.rho
        matrix = np.clip(matrix, 0.0, None)
        matrix /= matrix.sum()
        return matrix

    def _prediction(
        self,
        home_rate: float,
        away_rate: float,
        extra_params: dict[str, Any] | None = None,
    ) -> Prediction:
        """Assemble one prediction from a settled pair of scoring rates.

        The sealed 1X2 probabilities AND the exact-score matrix are both derived
        from this one converged matrix, so they are coherent by construction.
        Every family that models goals arrives here, which is what keeps a
        variant from inventing a second goal process beside the declared one.
        """
        matrix = self._matrix(home_rate, away_rate)
        probs = np.array(
            [np.tril(matrix, -1).sum(), np.trace(matrix), np.triu(matrix, 1).sum()]
        )
        params: dict[str, Any] = {"xi": self.xi, "prior_matches": 8}
        if self.family in _DIXON_COLES_FAMILIES:
            params["rho"] = self.rho
        if self.family == "bivariate_poisson":
            params["shared_lambda"] = self.shared
        if extra_params:
            params.update(extra_params)
        return Prediction(_normalise(probs), (home_rate, away_rate), params, matrix=matrix)

    def predict(self, home_team: str, away_team: str, neutral: bool) -> Prediction:
        return self._prediction(*self._rates(home_team, away_team, neutral))

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
        return self._prediction(
            home_rate * fraction, away_rate * fraction, {"duration_fraction": fraction}
        )


class ContextualDixonColesModel(PoissonModel):
    """Dixon-Coles plus a per-club home advantage and a rest-days correction.

    The goal process is untouched Dixon-Coles. Two corrections sit on top of the
    rates, each estimated *against the base fit's own expectations* — actual goals
    over the goals the base model predicted — so anything matching expectation
    gets a multiplier of exactly 1.0 and is left alone:

    * **Per-club home advantage.** The frozen five apply one league-wide home
      boost to every club, so a fortress (strong at home, ordinary away) has its
      two forms averaged into one strength. Shrunk toward 1.0 by
      ``HOME_EDGE_PRIOR_MATCHES`` and clipped, so a club with two home matches on
      record cannot earn a large edge and no fit produces a runaway rate.
    * **Rest days.** Days since each side last played, banded short/normal/long.

    **This candidate lost its gate and is seated on no council.** It is kept
    registered because a losing candidate stays in the evaluation report rather
    than disappearing, and because the measurement is the point: a club's home
    edge in one era predicts its edge in the next with a correlation of -0.007,
    and the rest correction changes sign between folds (above ordinary rest in 8
    of 15 fitted league-seasons, below in 7). Both signals are noise in this data,
    so a better estimator would estimate the same noise more precisely.
    Before reviving this, re-run the persistence check in
    ``docs/research/contextual-signals-2026-07.md`` — if it is still near zero,
    the estimator was never the problem.
    """

    # Callers check this to decide whether to do the extra work of measuring rest;
    # the frozen five never read a date, so they carry no such flag.
    READS_SCHEDULE = True

    HOME_EDGE_PRIOR_MATCHES = 12.0
    HOME_EDGE_CLIP = (0.6, 1.6)
    # Rest is estimated league-wide, not per club: one club's congested run is far
    # too thin a sample, and the effect being modelled is a property of the
    # schedule rather than of the squad. The band is deliberately narrow — a
    # documented rest effect is worth a few percent, so anything wider would be
    # this correction absorbing noise the goal model should own.
    REST_PRIOR_MATCHES = 40.0
    REST_CLIP = (0.85, 1.15)
    REST_SHORT_DAYS = 3
    REST_LONG_DAYS = 9

    def __init__(self, *, xi: float = 0.001, rho: float = -0.08) -> None:
        super().__init__("contextual_dixon_coles", xi=xi, rho=rho)
        self.home_attack_edge: dict[str, float] = {}
        self.home_defence_edge: dict[str, float] = {}
        self.rest_edge: dict[str, float] = {}

    def fit(self, matches: pd.DataFrame, cutoff_utc: str) -> ContextualDixonColesModel:
        super().fit(matches, cutoff_utc)
        self._fit_home_edges(matches)
        self._fit_rest_edges(matches)
        return self

    @classmethod
    def _rest_bucket(cls, days: float | None) -> str:
        """Which rest band a gap falls in; an unknown gap is always ordinary."""
        if days is None:
            return "normal"
        if days <= cls.REST_SHORT_DAYS:
            return "short"
        if days <= cls.REST_LONG_DAYS:
            return "normal"
        return "long"

    def _fit_rest_edges(self, matches: pd.DataFrame) -> None:
        """Estimate how much each rest band moves scoring, against base expectation."""
        frame = matches.reset_index(drop=True)
        # The same measurement a caller will later hand back to predict(), so the
        # bands are fitted on exactly the quantity they are looked up by.
        home_rest, away_rest = schedule_rest_days(frame)
        dates = pd.to_datetime(frame["date"], utc=True)
        days_old = (self.as_of - dates).dt.total_seconds().to_numpy() / 86400.0
        weights = np.exp(-self.xi * np.maximum(days_old, 0.0))

        actual: dict[str, float] = defaultdict(float)
        expected: dict[str, float] = defaultdict(float)
        band_weight: dict[str, float] = defaultdict(float)
        for index, (row, weight) in enumerate(
            zip(frame.itertuples(index=False), weights, strict=True)
        ):
            home, away = str(row.home_team), str(row.away_team)
            # PoissonModel._rates, not self._rates: the expectation these ratios
            # correct must be the UNcorrected base one, or each edge would be
            # measured against a rate already carrying the previous edge.
            base_home, base_away = PoissonModel._rates(self, home, away, bool(row.neutral))
            sides = (
                (float(row.home_score), base_home, home_rest[index]),
                (float(row.away_score), base_away, away_rest[index]),
            )
            for goals, base_rate, rest in sides:
                band = self._rest_bucket(rest)
                actual[band] += weight * goals
                expected[band] += weight * base_rate
                band_weight[band] += weight

        prior = self.REST_PRIOR_MATCHES
        low, high = self.REST_CLIP
        for band in ("short", "normal", "long"):
            weight = band_weight[band]
            denominator = expected[band]
            raw = actual[band] / denominator if denominator > 1e-9 else 1.0
            shrunk = (weight * raw + prior) / (weight + prior)
            self.rest_edge[band] = float(np.clip(shrunk, low, high))

    def _fit_home_edges(self, matches: pd.DataFrame) -> None:
        """Estimate each club's home split as a ratio of actual to base-expected goals."""
        dates = pd.to_datetime(matches["date"], utc=True)
        days = (self.as_of - dates).dt.total_seconds().to_numpy() / 86400.0
        weights = np.exp(-self.xi * np.maximum(days, 0.0))
        neutral = matches["neutral"].to_numpy(dtype=bool)

        scored = defaultdict(float)
        conceded = defaultdict(float)
        expected_scored = defaultdict(float)
        expected_conceded = defaultdict(float)
        home_weight = defaultdict(float)
        rows = zip(matches.itertuples(index=False), weights, neutral, strict=True)
        for row, weight, is_neutral in rows:
            # A neutral-ground match is nobody's home match; it carries no
            # evidence about a home split and must not dilute one either.
            if is_neutral:
                continue
            home = str(row.home_team)
            # The base rates this club's own fit already expects at home, so the
            # ratio below isolates the part the one-size home advantage misses.
            base_home, base_away = PoissonModel._rates(self, home, str(row.away_team), False)
            scored[home] += weight * float(row.home_score)
            conceded[home] += weight * float(row.away_score)
            expected_scored[home] += weight * base_home
            expected_conceded[home] += weight * base_away
            home_weight[home] += weight

        prior = self.HOME_EDGE_PRIOR_MATCHES
        low, high = self.HOME_EDGE_CLIP
        for team in sorted(home_weight):
            weight = home_weight[team]
            for actual, expected, edges in (
                (scored, expected_scored, self.home_attack_edge),
                (conceded, expected_conceded, self.home_defence_edge),
            ):
                denominator = expected[team]
                # Shrink toward 1.0 in ratio space: prior matches of evidence
                # saying "this club is ordinary at home" sit beside the observed
                # weight, so a thin record barely moves the edge.
                raw = actual[team] / denominator if denominator > 1e-9 else 1.0
                shrunk = (weight * raw + prior) / (weight + prior)
                edges[team] = float(np.clip(shrunk, low, high))

    def _rates(
        self,
        home_team: str,
        away_team: str,
        neutral: bool,
        *,
        home_rest_days: float | None = None,
        away_rest_days: float | None = None,
    ) -> tuple[float, float]:
        home_rate, away_rate = super()._rates(home_team, away_team, neutral)
        # Neutral ground is nobody's home, so the club-specific home split is not
        # applied there — but rest is a property of the schedule and still counts.
        if not neutral:
            home_rate *= self.home_attack_edge.get(home_team, 1.0)
            away_rate *= self.home_defence_edge.get(home_team, 1.0)
        home_rate *= self.rest_edge.get(self._rest_bucket(home_rest_days), 1.0)
        away_rate *= self.rest_edge.get(self._rest_bucket(away_rest_days), 1.0)
        return float(np.clip(home_rate, 0.15, 5.0)), float(np.clip(away_rate, 0.15, 5.0))

    def predict(
        self,
        home_team: str,
        away_team: str,
        neutral: bool,
        *,
        home_rest_days: float | None = None,
        away_rest_days: float | None = None,
    ) -> Prediction:
        """Quote a fixture, given the rest each side brings to it.

        The caller measures rest, because the caller is the one holding a
        schedule — :func:`schedule_rest_days` computes it from any fixture list,
        and a backtest replaying a season needs gaps that run past the training
        cutoff, which the fitted rows alone cannot supply. Omitting rest is
        allowed and means "ordinary", never a silent penalty. Nothing on this
        path tells the model a result.
        """
        home_rest, away_rest = home_rest_days, away_rest_days
        rates = self._rates(
            home_team,
            away_team,
            neutral,
            home_rest_days=home_rest,
            away_rest_days=away_rest,
        )
        extra: dict[str, Any] = {
            "home_edge_prior_matches": self.HOME_EDGE_PRIOR_MATCHES,
            "rest_prior_matches": self.REST_PRIOR_MATCHES,
            "home_rest_band": self._rest_bucket(home_rest),
            "away_rest_band": self._rest_bucket(away_rest),
            "rest_edge": {band: round(value, 6) for band, value in sorted(self.rest_edge.items())},
        }
        if not neutral:
            extra["home_attack_edge"] = round(self.home_attack_edge.get(home_team, 1.0), 6)
            extra["home_defence_edge"] = round(self.home_defence_edge.get(home_team, 1.0), 6)
        return self._prediction(*rates, extra)



def fit_model(
    family: str, matches: pd.DataFrame, cutoff_utc: str, *, xi: float = 0.001
) -> ClimatologicalModel | EloOrdinalLogitModel | PoissonModel:
    """Fit one frozen Phase 0 candidate family."""
    if family == "climatological":
        return ClimatologicalModel().fit(matches, cutoff_utc)
    if family == "elo_ordlogit":
        return EloOrdinalLogitModel().fit(matches, cutoff_utc)
    if family == "contextual_dixon_coles":
        return ContextualDixonColesModel(xi=xi).fit(matches, cutoff_utc)
    if family in _POISSON_FAMILIES:
        return PoissonModel(family, xi=xi).fit(matches, cutoff_utc)
    raise ValueError(f"unknown model family: {family}")
