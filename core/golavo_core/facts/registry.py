"""The pre-registered, versioned family of fact templates.

This registry IS the multiple-comparison control. The family is fixed per
release: ``family_size()`` — the number of pre-registered hypotheses evaluated
for one match — is a constant of the code, not a function of the data, so the
notebook can never widen its search until something looks significant. Adding,
removing, or re-labelling a template changes ``REGISTRY_VERSION`` and is a
reviewed, logged change (see docs/handoff/codex-phase7.md).

Each entry also carries the guardrail parameters the engine enforces:
``min_sample`` (a claim below its sample floor is suppressed) and
``staleness_days`` (a form fact whose last contributing match is older than this
is auto-hidden; ``None`` marks a structural, all-time fact that never goes stale).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from . import coincidence, context, events, predictive, signature
from ._history import Candidate, TemplateContext

REGISTRY_VERSION = "2026.07.14"

_ID_RE = re.compile(r"[a-z][a-z0-9_]*\Z")
_LABELS = ("predictive", "context", "coincidence")
_SCOPES = ("team", "head_to_head", "match", "competition")
# Which vendored dataset a template reads from — used ONLY to attribute a fact to
# a finer source id (``<pack>#<dataset>``) in the AI evidence bundle, so the
# citation chips vary instead of all resolving to one "data pack". Never changes
# the leak-safe computation.
_DATASETS = ("results", "goalscorers", "shootouts")

# The maximum coincidence-labelled facts the notebook will emit for one match.
COINCIDENCE_CAP = 3


@dataclass(frozen=True)
class Template:
    """One pre-registered template and the guardrail parameters it runs under."""

    id: str
    version: str
    label: str
    scope: str
    # arity = the maximum number of hypotheses this template tests for one match
    # (2 for templates evaluated once per side, 1 for head-to-head / competition
    # templates). Summed, these are the fixed multiple-comparison bound.
    arity: int
    min_sample: int
    staleness_days: int | None
    fn: Callable[[TemplateContext], list[Candidate]]
    # The vendored dataset this template reads (for citation attribution only).
    dataset: str = "results"


REGISTRY: tuple[Template, ...] = (
    # --- context: team form ---
    Template("unbeaten_run", "1.0.0", "context", "team", 2, 3, 400, context.unbeaten_run),
    Template("winless_run", "1.0.0", "context", "team", 2, 3, 400, context.winless_run),
    Template("win_streak", "1.0.0", "context", "team", 2, 3, 400, context.win_streak),
    Template("clean_sheet_run", "1.0.0", "context", "team", 2, 3, 400, context.clean_sheet_run),
    Template("home_away_form", "1.0.0", "context", "team", 2, 5, 400, context.home_away_form),
    # --- context: records ---
    Template("biggest_win", "1.0.0", "context", "team", 2, 10, None, context.biggest_win),
    Template(
        "head_to_head_record", "1.0.0", "context", "head_to_head", 1, 3, 365 * 12,
        context.head_to_head_record,
    ),
    Template(
        "neutral_venue_record", "1.0.0", "context", "team", 2, 5, None,
        context.neutral_venue_record,
    ),
    # --- context: signature stats (the unusual form insights) ---
    Template(
        "both_teams_scored_rate", "1.0.0", "context", "team", 2, 10, 400,
        signature.both_teams_scored_rate,
    ),
    Template(
        "clean_sheet_rate", "1.0.0", "context", "team", 2, 10, 400,
        signature.clean_sheet_rate,
    ),
    Template("scoring_trend", "1.0.0", "context", "team", 2, 12, 400, signature.scoring_trend),
    Template(
        "head_to_head_goals", "1.0.0", "context", "head_to_head", 1, 4, 365 * 12,
        signature.head_to_head_goals,
    ),
    # --- context: internationals-only (scorers + shootouts) ---
    Template(
        "top_scorer", "1.0.0", "context", "team", 2, 10, None, context.top_scorer,
        dataset="goalscorers",
    ),
    Template(
        "in_form_scorer", "1.0.0", "context", "team", 2, 5, 400, context.in_form_scorer,
        dataset="goalscorers",
    ),
    Template(
        "shootout_record", "1.0.0", "context", "team", 2, 3, None, context.shootout_record,
        dataset="shootouts",
    ),
    # --- context: event-derived from the goalscorers/shootouts packs (new) ---
    Template(
        "goal_timing_profile", "1.0.0", "context", "team", 2, 20, 400,
        events.goal_timing_profile, dataset="goalscorers",
    ),
    Template(
        "penalty_goal_share", "1.0.0", "context", "team", 2, 5, 400,
        events.penalty_goal_share, dataset="goalscorers",
    ),
    Template(
        "tournament_record", "1.0.0", "context", "team", 2, 8, None,
        context.tournament_record,
    ),
    Template(
        "shootout_first_shooter_edge", "1.0.0", "predictive", "competition", 1, 50, None,
        events.shootout_first_shooter_edge, dataset="shootouts",
    ),
    # --- predictive: labelled base rates (never applied to the model here) ---
    Template(
        "home_advantage_base_rate", "1.0.0", "predictive", "competition", 1, 100, None,
        predictive.home_advantage_base_rate,
    ),
    Template(
        "competition_debut_base_rate", "1.0.0", "predictive", "competition", 1, 200, None,
        predictive.competition_debut_base_rate,
    ),
    # --- coincidence: quarantined, capped, never folded into the AI bundle ---
    Template(
        "day_of_week_streak", "1.0.0", "coincidence", "team", 2, 4, 400,
        coincidence.day_of_week_streak,
    ),
    Template(
        "scoreline_repeat", "1.0.0", "coincidence", "head_to_head", 1, 2, None,
        coincidence.scoreline_repeat,
    ),
    Template(
        "calendar_date_repeat", "1.0.0", "coincidence", "team", 2, 3, None,
        coincidence.calendar_date_repeat,
    ),
    Template(
        "own_goal_quirk", "1.0.0", "coincidence", "team", 2, 3, None,
        events.own_goal_quirk, dataset="goalscorers",
    ),
)


# template id -> the vendored dataset it reads, for per-dataset AI citation
# attribution (see golavo_core.facts.evidence.notebook_to_evidence).
DATASET_BY_TEMPLATE: dict[str, str] = {tmpl.id: tmpl.dataset for tmpl in REGISTRY}


def _validate_registry() -> None:
    seen: set[str] = set()
    for tmpl in REGISTRY:
        if not _ID_RE.match(tmpl.id):
            raise ValueError(f"template id must match [a-z][a-z0-9_]*: {tmpl.id!r}")
        if tmpl.id in seen:
            raise ValueError(f"duplicate template id: {tmpl.id!r}")
        seen.add(tmpl.id)
        if tmpl.label not in _LABELS:
            raise ValueError(f"template {tmpl.id!r} has unknown label {tmpl.label!r}")
        if tmpl.scope not in _SCOPES:
            raise ValueError(f"template {tmpl.id!r} has unknown scope {tmpl.scope!r}")
        if tmpl.arity < 1:
            raise ValueError(f"template {tmpl.id!r} must have arity >= 1")
        if tmpl.min_sample < 1:
            raise ValueError(f"template {tmpl.id!r} must have min_sample >= 1")
        if tmpl.dataset not in _DATASETS:
            raise ValueError(f"template {tmpl.id!r} has unknown dataset {tmpl.dataset!r}")


_validate_registry()


def family_size() -> int:
    """The fixed number of pre-registered hypotheses evaluated for one match.

    This is the multiple-comparison exposure bound. It depends only on the
    registry, never on the data.
    """
    return sum(tmpl.arity for tmpl in REGISTRY)


def by_label(label: str) -> tuple[Template, ...]:
    return tuple(tmpl for tmpl in REGISTRY if tmpl.label == label)
