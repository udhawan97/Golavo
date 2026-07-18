"""The contextual Dixon-Coles candidate: per-team home advantage and rest days.

The frozen five each apply one league-wide home advantage to every club and know
nothing about congestion. This sixth family estimates both from the same rows,
so the tests below are written against the *difference* it makes rather than
against absolute rates: a fortress must out-rate its own away form by more than
plain Dixon-Coles allows, and a short-rested side must not be quoted the same
attack as a rested one.
"""

from __future__ import annotations

import pandas as pd
import pytest
from golavo_core.analysis import COUNCIL_FAMILIES
from golavo_core.models import FAMILIES, fit_model
from golavo_core.models.candidates import schedule_rest_days

CUTOFF = "2026-01-01T00:00:00Z"


def _match(
    match_id: str,
    date: str,
    home: str,
    away: str,
    home_score: int,
    away_score: int,
) -> dict[str, object]:
    return {
        "match_id": match_id,
        "date": pd.Timestamp(date),
        "kickoff_utc": pd.Timestamp(f"{date}T15:00:00Z"),
        "home_team": home,
        "away_team": away,
        "home_score": home_score,
        "away_score": away_score,
        "neutral": False,
    }


def _league(
    *,
    fortress: str | None = None,
    seasons: int = 4,
) -> pd.DataFrame:
    """A synthetic double round-robin league, optionally with one fortress club.

    Every club is otherwise identical (1 goal a side), so any asymmetry a model
    reports is the fortress effect and not a strength gradient. ``fortress``
    scores 3 at home and 1 away, conceding 0 at home — a club whose splits a
    single league-wide home advantage cannot represent.
    """
    teams = ["A", "B", "C", "D", "E", "F"]
    rows: list[dict[str, object]] = []
    day = pd.Timestamp("2022-01-05")
    index = 0
    for _ in range(seasons):
        for home in teams:
            for away in teams:
                if home == away:
                    continue
                if home == fortress:
                    home_score, away_score = 3, 0
                elif away == fortress:
                    home_score, away_score = 1, 1
                else:
                    home_score, away_score = 1, 1
                rows.append(
                    _match(
                        f"m{index}",
                        day.strftime("%Y-%m-%d"),
                        home,
                        away,
                        home_score,
                        away_score,
                    )
                )
                index += 1
                day += pd.Timedelta(days=7)
    return pd.DataFrame(rows)


def _round_robin(teams: list[str]) -> list[list[tuple[str, str]]]:
    """Circle-method pairings: every club plays once per round, all pairs covered."""
    order = list(teams)
    size = len(order)
    rounds: list[list[tuple[str, str]]] = []
    for _ in range(size - 1):
        rounds.append([(order[i], order[size - 1 - i]) for i in range(size // 2)])
        order = [order[0], order[-1], *order[1:-1]]
    return rounds


def _congested_league(cycles: int = 6) -> pd.DataFrame:
    """A league that alternates rested rounds with a congested block.

    Rested rounds sit 7 days apart and finish 1-1; congested rounds sit 2 days
    apart and finish 0-0. The effect is league-wide and attaches to the spacing,
    not to any club, so a model that only knows club strength cannot represent it.
    """
    teams = ["A", "B", "C", "D", "E", "F"]
    rows: list[dict[str, object]] = []
    day = pd.Timestamp("2022-01-05")
    index = 0
    for _ in range(cycles):
        for rested, spacing, score in ((True, 7, 1), (False, 2, 0)):
            for pairs in _round_robin(teams) if rested else _round_robin(teams)[:2]:
                for home, away in pairs:
                    rows.append(
                        _match(
                            f"c{index}",
                            day.strftime("%Y-%m-%d"),
                            home,
                            away,
                            score,
                            score,
                        )
                    )
                    index += 1
                day += pd.Timedelta(days=spacing)
    return pd.DataFrame(rows)


def test_contextual_family_is_registered() -> None:
    assert "contextual_dixon_coles" in FAMILIES


def test_short_rest_lowers_the_quoted_attack() -> None:
    """Two days between matches must not be quoted the same attack as seven.

    The congested league scores nothing on two days' rest and once a side on
    seven, so a model given the gap has to separate them. The frozen five cannot:
    they never see a schedule at all.
    """
    matches = _congested_league()
    model = fit_model("contextual_dixon_coles", matches, CUTOFF)

    congested = model.predict("A", "B", False, home_rest_days=2.0).expected_goals[0]
    rested = model.predict("A", "B", False, home_rest_days=7.0).expected_goals[0]

    assert congested < rested


def test_prediction_without_rest_days_assumes_ordinary_rest() -> None:
    """No gap supplied, no rest claim — the model must fall back, not guess.

    Every caller that cannot measure rest (a bare what-if, a fixture with no
    prior match on record) gets the ordinary-rest quote, never a silent penalty.
    """
    matches = _congested_league()
    model = fit_model("contextual_dixon_coles", matches, CUTOFF)

    unspecified = model.predict("A", "B", False).expected_goals
    ordinary = model.predict(
        "A", "B", False, home_rest_days=7.0, away_rest_days=7.0
    ).expected_goals

    assert unspecified == pytest.approx(ordinary)


def test_a_registered_candidate_is_not_automatically_a_scored_rival() -> None:
    """The season game scores five rivals however many candidates exist.

    ``derive_rival_picks`` reads whatever a council contains, so seating any new
    voice would silently rewrite the scoring rule every existing season was
    played under ("beat all five models"). The roster is therefore pinned
    independently of the registry, and a candidate joins it only after earning a
    council seat — which this family has not.
    """
    from golavo_core.picks import derive_rival_picks

    analysis = {
        "models": [
            {"family": family, "probs": {"home": 0.5, "draw": 0.3, "away": 0.2}, "abstained": False}
            for family in FAMILIES
        ]
    }

    rivals = derive_rival_picks(analysis)["rivals"]
    families = [rival["family"] for rival in rivals]

    assert "contextual_dixon_coles" not in families
    assert len(families) == 5


def test_the_candidate_is_registered_for_backtests_but_seated_on_no_council() -> None:
    """Registered and measured, but not a voice — the gate's honest middle state.

    A candidate that loses stays in the report rather than disappearing, which is
    the same rule the committed evaluation reports state for Elo. Seating is a
    separate, earned decision.
    """
    assert "contextual_dixon_coles" in FAMILIES
    assert "contextual_dixon_coles" not in COUNCIL_FAMILIES


def test_schedule_rest_days_reads_gaps_and_leaves_the_first_match_unknown() -> None:
    """Rest comes from the fixture list, and nobody has a gap before their first match."""
    matches = pd.DataFrame(
        [
            _match("m1", "2026-02-01", "A", "B", 1, 0),
            _match("m2", "2026-02-04", "A", "C", 1, 1),
            _match("m3", "2026-02-15", "B", "A", 0, 0),
        ]
    )

    home_rest, away_rest = schedule_rest_days(matches)

    assert home_rest[0] is None and away_rest[0] is None
    assert home_rest[1] == 3.0  # A last played 2026-02-01
    assert away_rest[1] is None  # C's first appearance
    assert home_rest[2] == 14.0  # B last played 2026-02-01
    assert away_rest[2] == 11.0  # A last played 2026-02-04


def test_schedule_rest_days_never_reads_a_score() -> None:
    """The rest clock must work on a bare fixture list.

    This is the leak-safety argument for using in-fold dates: a published
    schedule carries no results, so a frame with no score columns at all has to
    produce the same gaps. If this ever needed a score, rest would be a
    backward-looking fact and could not be quoted before kickoff.
    """
    matches = pd.DataFrame(
        [
            _match("m1", "2026-02-01", "A", "B", 1, 0),
            _match("m2", "2026-02-04", "A", "C", 1, 1),
        ]
    )
    fixtures_only = matches.drop(columns=["home_score", "away_score"])

    assert schedule_rest_days(fixtures_only) == schedule_rest_days(matches)


def test_each_side_is_quoted_its_own_rest() -> None:
    """A rested home side facing a congested away side must not be quoted symmetrically.

    Rest belongs to a club, not to the fixture, so the two rates have to move
    independently — otherwise a mismatch in the schedule vanishes into an average.
    """
    matches = _congested_league()
    model = fit_model("contextual_dixon_coles", matches, CUTOFF)

    home_rate, away_rate = model.predict(
        "A", "B", False, home_rest_days=7.0, away_rest_days=2.0
    ).expected_goals
    swapped_home, swapped_away = model.predict(
        "A", "B", False, home_rest_days=2.0, away_rest_days=7.0
    ).expected_goals

    assert home_rate > swapped_home
    assert away_rate < swapped_away


def test_fortress_gets_a_bigger_home_edge_than_plain_dixon_coles() -> None:
    """A club that only performs at home must out-rate the one-size home advantage.

    Plain Dixon-Coles folds a fortress's home form into a single attack strength
    that it then also applies away, so it under-rates the club at home. The
    contextual family estimates the split per club and must quote the higher
    home rate.
    """
    matches = _league(fortress="A")

    plain = fit_model("dixon_coles", matches, CUTOFF)
    contextual = fit_model("contextual_dixon_coles", matches, CUTOFF)

    plain_home_rate = plain.predict("A", "B", False).expected_goals[0]
    contextual_home_rate = contextual.predict("A", "B", False).expected_goals[0]

    assert contextual_home_rate > plain_home_rate


def test_a_symmetric_league_leaves_the_home_edge_near_neutral() -> None:
    """With no club-specific home form, the correction must stay out of the way.

    This is the guard against the edge inventing signal: every club here has
    identical splits, so the contextual rates must track plain Dixon-Coles.
    """
    matches = _league(fortress=None)

    plain = fit_model("dixon_coles", matches, CUTOFF)
    contextual = fit_model("contextual_dixon_coles", matches, CUTOFF)

    plain_rate = plain.predict("A", "B", False).expected_goals[0]
    contextual_rate = contextual.predict("A", "B", False).expected_goals[0]

    assert contextual_rate == pytest.approx(plain_rate, rel=0.05)
