"""On-demand, leak-safe multi-model match analysis (Replay / Preview).

Pure and write-free. This generalises the sealed-forecast engine into a *read
model*: it fits every council family for ANY indexed match at exactly the same
conservative pre-kickoff information cutoff the seal uses (``kickoff - 1s``), so
it can never read the fixture's own result or any later match. It produces no
artifact and touches no ledger — persistence, if ever wanted, stays the job of
the seal path (``golavo_core.artifacts``). Because it re-uses ``training_rows``
(which fails closed on any future row) and the same ``MIN_TEAM_MATCHES`` abstain
floor as the seal, a replay is leak-safe by construction and abstains exactly
when a seal would.

Two analysis *kinds*, distinguished only by whether the fixture already has a
result in the snapshot — the computation and the cutoff are identical:

* **replay** — a completed fixture, reconstructed with only pre-kickoff data. It
  is NOT a forecast that existed at the time and the UI must label it as such.
* **preview** — a scheduled fixture, computed from everything known so far.

The council is deliberately honest about model plurality. The three Poisson
families share one fitting class and differ only in the final joint-matrix step
(and independent/bivariate coincide on this data), so they are grouped as ONE
goal-model *voice* with disclosed *variants*; Elo is the *ratings* voice; and
climatology is a *baseline* reference — never a third opinion. No family's
probabilities are averaged into a synthetic "consensus": the summary reports the
descriptive range across the two voices and whether they agree on the likeliest
outcome.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd

# Import the abstain constants (not the writer) from the seal engine so an
# on-demand replay abstains on exactly the same data floor a seal does. These are
# plain ints; pulling them in does not couple analysis to any ledger write.
from golavo_core.artifacts import DECAY_WINDOW_DAYS, MIN_TEAM_MATCHES
from golavo_core.ingest import training_rows
from golavo_core.models import fit_model
from golavo_core.score_matrix import assert_model_coherent, build_score_matrix

ANALYSIS_SCHEMA_VERSION = "0.4.1"

# The fitted attack/defence multipliers are clipped to this band (mirrors
# PoissonModel); a baseline of 1.0 is league-average.
_STYLE_CLIP = {"min": 0.35, "max": 2.8}
_STYLE_BASELINE = 1.0

# The council, in display order. Two voices + one baseline; the goal model's
# variants are disclosed, never counted as extra opinions.
COUNCIL_FAMILIES: tuple[str, ...] = (
    "elo_ordlogit",
    "dixon_coles",
    "poisson_independent",
    "bivariate_poisson",
    "climatological",
)

# The single goal-model voice shown by default; its siblings are variants.
GOAL_VOICE = "dixon_coles"

_ROLE = {
    "elo_ordlogit": "voice",
    "dixon_coles": "voice",
    "poisson_independent": "variant",
    "bivariate_poisson": "variant",
    "climatological": "baseline",
}

_METHOD = {
    "elo_ordlogit": "ratings",
    "dixon_coles": "goals",
    "poisson_independent": "goals",
    "bivariate_poisson": "goals",
    "climatological": "base_rate",
}


class AnalysisUnavailable(Exception):
    """The fixture cannot be analysed (e.g. no kickoff timestamp)."""


def _to_utc(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def _iso(ts: pd.Timestamp) -> str:
    return ts.isoformat().replace("+00:00", "Z")


def _team_counts(
    train: pd.DataFrame, anchor: pd.Timestamp, teams: tuple[str, str]
) -> dict[str, int]:
    """Qualifying-match counts per team inside the decay window ending at ``anchor``.

    Mirrors ``golavo_core.artifacts._team_counts`` so a replay's abstain decision
    matches the seal's exactly.
    """
    start = anchor - pd.Timedelta(days=DECAY_WINDOW_DAYS)
    dates = pd.to_datetime(train["date"], utc=True)
    window = train.loc[dates >= start]
    return {
        team: int((window["home_team"].eq(team) | window["away_team"].eq(team)).sum())
        for team in teams
    }


def _uncertainty(minimum_count: int) -> str:
    return "high" if minimum_count < 20 else "medium" if minimum_count < 40 else "low"


def _recent_form(train: pd.DataFrame, team: str, n: int = 5) -> list[dict[str, Any]]:
    """The team's last ``n`` completed results BEFORE the cutoff, oldest-first.

    Descriptive history straight off the leak-safe training frame (``train`` is
    already pre-cutoff and completed-only), so it is safe to render even when the
    council abstains. Each entry is one result from the team's perspective.
    """
    home = train["home_team"].astype("string").eq(team)
    away = train["away_team"].astype("string").eq(team)
    mask = home | away
    rows = train.loc[mask]
    if rows.empty:
        return []
    rows = rows.assign(_d=pd.to_datetime(rows["date"], utc=True))
    rows = rows.sort_values(by=["_d", "match_id"], kind="mergesort").tail(n)
    out: list[dict[str, Any]] = []
    for _, r in rows.iterrows():
        is_home = str(r["home_team"]) == team
        gf = int(r["home_score"]) if is_home else int(r["away_score"])
        ga = int(r["away_score"]) if is_home else int(r["home_score"])
        result = "W" if gf > ga else "D" if gf == ga else "L"
        out.append({
            "result": result,
            "opponent": str(r["away_team"]) if is_home else str(r["home_team"]),
            "gf": gf,
            "ga": ga,
            "date": pd.Timestamp(r["date"]).date().isoformat(),
            "is_home": bool(is_home),
            "neutral": bool(r.get("neutral") or False),
        })
    return out


def _modal_outcome(probs: dict[str, float]) -> str:
    # Deterministic tie-break: home > draw > away on an exact tie.
    order = ("home", "draw", "away")
    return max(order, key=lambda k: (probs[k], -order.index(k)))


def _council_summary(voice_entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Descriptive summary over the (non-abstained) VOICE entries only.

    No averaging: reports the modal outcome each voice leans to, whether they
    agree, the per-outcome probability range across the voices, and the largest
    disagreement. When the voices disagree on the likeliest outcome there is no
    single "leading" outcome — the UI shows the disagreement instead.
    """
    with_probs = [e for e in voice_entries if e.get("probs") is not None]
    if not with_probs:
        return {
            "voices": 0,
            "voices_agree": None,
            "leading_outcome": None,
            "max_delta_p": None,
            "outcome_range": None,
        }
    modals = {_modal_outcome(e["probs"]) for e in with_probs}
    agree = len(modals) == 1
    outcome_range: dict[str, dict[str, float]] = {}
    max_delta = 0.0
    for key in ("home", "draw", "away"):
        values = [float(e["probs"][key]) for e in with_probs]
        low, high = min(values), max(values)
        outcome_range[key] = {"low": round(low, 6), "high": round(high, 6)}
        max_delta = max(max_delta, high - low)
    return {
        "voices": len(with_probs),
        "voices_agree": agree,
        "leading_outcome": next(iter(modals)) if agree else None,
        "max_delta_p": round(max_delta, 6),
        "outcome_range": outcome_range,
    }


def _derived_markets(matrix: Any) -> dict[str, Any]:
    """Exact both-teams-to-score and clean-sheet marginals from the FULL joint
    matrix (not the display-truncated grid, whose tail is decomposed only by
    outcome and so cannot recover these exactly).

    ``matrix[i, j]`` = P(home scores i, away scores j). A clean sheet for a side
    means the OPPONENT scores zero.
    """
    import numpy as np

    m = np.asarray(matrix, dtype=float)
    p_home_zero = float(m[0, :].sum())   # home scores 0
    p_away_zero = float(m[:, 0].sum())   # away scores 0
    p_nil_nil = float(m[0, 0])
    btts_yes = 1.0 - p_home_zero - p_away_zero + p_nil_nil
    btts_yes = min(1.0, max(0.0, btts_yes))
    return {
        "family": GOAL_VOICE,
        "source": "full_resolution_matrix",
        "btts": {"yes": round(btts_yes, 6), "no": round(1.0 - btts_yes, 6)},
        # A clean sheet for the home side = the away side scores zero, and v.v.
        "clean_sheets": {
            "home": round(p_away_zero, 6),
            "away": round(p_home_zero, 6),
        },
    }


def build_match_analysis(
    *,
    matches: pd.DataFrame,
    match_row: Mapping[str, Any],
    families: tuple[str, ...] = COUNCIL_FAMILIES,
) -> dict[str, Any]:
    """Compute a MatchAnalysis for one fixture — no writes, leak-safe by cutoff.

    ``matches`` must already be scoped to the fixture's own source (as the
    on-demand notebook path does) so a shared team string cannot merge a club's
    history into an international fixture. ``match_row`` is any mapping with the
    index-row fields (``match_id``, ``kickoff_utc``, ``home_team``, ``away_team``,
    ``neutral``, ``is_complete``, ``competition``, ...). Raises
    ``AnalysisUnavailable`` if the fixture has no kickoff to anchor the cutoff.
    """
    kickoff_raw = match_row.get("kickoff_utc")
    if kickoff_raw is None or (isinstance(kickoff_raw, float) and pd.isna(kickoff_raw)):
        raise AnalysisUnavailable("fixture has no kickoff timestamp to anchor a leak-safe cutoff")
    kickoff = _to_utc(kickoff_raw)
    # The one conservative cutoff, identical for replay and preview: a completed
    # fixture is reconstructed with only pre-kickoff data; a scheduled fixture
    # simply has no later data to exclude. training_rows() additionally asserts no
    # row after the cutoff survives — the machine-checked leak guard.
    cutoff = kickoff - pd.Timedelta(seconds=1)
    cutoff_iso = _iso(cutoff)

    match_id = str(match_row["match_id"])
    home_team = str(match_row["home_team"])
    away_team = str(match_row["away_team"])
    neutral = bool(match_row.get("neutral") or False)
    is_complete = bool(match_row.get("is_complete") or False)
    kind = "replay" if is_complete else "preview"

    train = training_rows(matches, cutoff_iso)
    # Belt-and-braces: never let the fixture's own row into training even if a
    # future snapshot dated it before the cutoff.
    train = train.loc[~train["match_id"].astype("string").eq(match_id)].copy()

    counts = _team_counts(train, cutoff, (home_team, away_team))
    minimum_count = min(counts.values())
    abstained = minimum_count < MIN_TEAM_MATCHES

    # Descriptive form is computed before the abstain branch: it must render even
    # when the council abstains (history exists below the model floor).
    team_form = {
        home_team: _recent_form(train, home_team),
        away_team: _recent_form(train, away_team),
    }

    goal_model = None  # the fitted goal-voice model, for the team-style profile
    goal_matrix = None  # the goal voice's full joint matrix, for derived markets
    entries: list[dict[str, Any]] = []
    for family in families:
        entry: dict[str, Any] = {
            "family": family,
            "role": _ROLE.get(family, "voice"),
            "method": _METHOD.get(family, "unknown"),
            "abstained": abstained,
            "probs": None,
            "expected_goals": None,
            "score_matrix": None,
            "params": None,
        }
        if not abstained:
            model = fit_model(family, train, cutoff_iso)
            if family == GOAL_VOICE:
                goal_model = model
            prediction = model.predict(home_team, away_team, neutral)
            probs = {
                key: round(float(value), 6)
                for key, value in zip(("home", "draw", "away"), prediction.probs, strict=True)
            }
            entry["probs"] = probs
            entry["params"] = dict(prediction.params)
            if prediction.expected_goals is not None:
                expected_goals = {
                    "home": round(float(prediction.expected_goals[0]), 6),
                    "away": round(float(prediction.expected_goals[1]), 6),
                }
                entry["expected_goals"] = expected_goals
                if prediction.matrix is not None:
                    score_matrix = build_score_matrix(prediction.matrix)
                    # Same seal-time proof: the grid reproduces the probs and the
                    # expected goals, or we do not attach it.
                    assert_model_coherent(prediction.matrix, score_matrix, probs, expected_goals)
                    entry["score_matrix"] = score_matrix
                    if family == GOAL_VOICE:
                        goal_matrix = prediction.matrix
        entries.append(entry)

    voice_entries = [e for e in entries if e["role"] == "voice"]
    council = _council_summary(voice_entries)

    # The analysis-level exact-score distribution is the goal voice's, labelled as
    # such — Elo and climatology model no goal process.
    goal_entry = next((e for e in entries if e["family"] == GOAL_VOICE), None)
    score_matrix = goal_entry["score_matrix"] if goal_entry else None

    # "How they attack & defend" — the goal voice's own fitted per-team multipliers
    # (time-decayed, prior-shrunk, from results only). These are exactly the numbers
    # the council already trusts, read off the fitted model — no new estimator, no
    # new leak surface. None when abstained (nothing was fitted).
    team_style = None
    if goal_model is not None and goal_entry is not None:
        eg = goal_entry.get("expected_goals") or {"home": None, "away": None}

        def _style(team: str, xg_for: Any, xg_against: Any) -> dict[str, Any]:
            return {
                "attack": round(float(goal_model.attack.get(team, _STYLE_BASELINE)), 6),
                "defence": round(float(goal_model.defence.get(team, _STYLE_BASELINE)), 6),
                "expected_goals_for": xg_for,
                "expected_goals_against": xg_against,
            }

        team_style = {
            "family": GOAL_VOICE,
            "derivation": "fitted_from_results",
            "baseline": _STYLE_BASELINE,
            "clip": dict(_STYLE_CLIP),
            "teams": {
                home_team: _style(home_team, eg.get("home"), eg.get("away")),
                away_team: _style(away_team, eg.get("away"), eg.get("home")),
            },
        }

    # Exact BTTS / clean-sheet marginals — computed from the goal voice's full
    # joint matrix at build time because they are NOT exactly recoverable from the
    # stored, outcome-decomposed score grid. None when the goal voice abstained.
    derived_markets = _derived_markets(goal_matrix) if goal_matrix is not None else None

    reason = None
    if abstained:
        reason = (
            f"insufficient history: {home_team}={counts[home_team]}, "
            f"{away_team}={counts[away_team]}; the models need {MIN_TEAM_MATCHES} qualifying "
            "matches per side"
        )

    return {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "analysis_kind": kind,
        "match": {
            "match_id": match_id,
            "competition": str(match_row.get("competition") or ""),
            "kickoff_utc": _iso(kickoff),
            "home_team": home_team,
            "away_team": away_team,
            "neutral_venue": neutral,
            "is_complete": is_complete,
        },
        "information_cutoff_utc": cutoff_iso,
        "abstained": abstained,
        "abstain_reason": reason,
        "uncertainty": _uncertainty(minimum_count),
        "team_history": {home_team: counts[home_team], away_team: counts[away_team]},
        "min_team_matches": MIN_TEAM_MATCHES,
        "team_form": team_form,
        "team_style": team_style,
        "council": council,
        "models": entries,
        "score_matrix": score_matrix,
        "score_matrix_family": GOAL_VOICE if score_matrix is not None else None,
        "derived_markets": derived_markets,
    }
