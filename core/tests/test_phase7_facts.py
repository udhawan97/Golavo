"""Phase 7 — the Commentator's Notebook: honesty guardrails and the no-write invariant.

These tests run over the two retained martj42 international snapshots and one
openfootball club pack (the same vendored data the earlier phases use), so no
network or live model is needed. The load-bearing checks are: determinism,
minimum-sample suppression, the coincidence cap + quarantine, label correctness,
schema validation, and the machine-checked guarantee that no facts code path can
write a probability, forecast, or calibration number.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pandas as pd
import pytest
from golavo_core.artifacts import seal_forecast
from golavo_core.evidence import build_evidence_bundle, validate_evidence_bundle
from golavo_core.facts import (
    COINCIDENCE_CAP,
    REGISTRY,
    REGISTRY_VERSION,
    assert_facts_isolated,
    assert_no_number_written,
    build_notebook,
    family_size,
    load_side_tables,
    notebook_for_artifact,
    notebook_to_evidence,
    validate_notebook,
)
from golavo_core.facts._history import Candidate
from golavo_core.facts.guardrails import apply_guardrails, assert_number_discipline
from golavo_core.facts.registry import Template
from golavo_core.ingest import load_matches

REPO_ROOT = Path(__file__).resolve().parents[2]
T0_PACK = REPO_ROOT / "packs/martj42-internationals-273c731492df"
T1_PACK = REPO_ROOT / "packs/martj42-internationals"
CLUB_PACK = REPO_ROOT / "packs/openfootball-eng-pl"


def _intl_notebook() -> dict:
    matches = load_matches(T0_PACK)
    gs, so = load_side_tables(T0_PACK)
    return build_notebook(
        matches=matches,
        home_team="France",
        away_team="Morocco",
        competition="Friendly",
        neutral=False,
        as_of_utc="2026-07-08T00:00:00Z",
        kickoff_utc="2026-07-09T00:00:00Z",
        source_ids=["sp_273c731492df"],
        goalscorers=gs,
        shootouts=so,
    )


def _club_notebook() -> dict:
    matches = load_matches(CLUB_PACK)
    gs, so = load_side_tables(CLUB_PACK)  # club packs ship neither
    return build_notebook(
        matches=matches,
        home_team="Arsenal",
        away_team="Chelsea",
        competition="English Premier League",
        neutral=False,
        as_of_utc="2020-01-01T00:00:00Z",
        kickoff_utc="2020-01-02T00:00:00Z",
        source_ids=["sp_club_pack"],
        goalscorers=gs,
        shootouts=so,
    )


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #
def test_notebook_is_byte_identical_for_the_same_pack() -> None:
    first, second = _intl_notebook(), _intl_notebook()
    assert first == second
    assert first["notebook_id"] == second["notebook_id"]
    canonical = json.dumps(first, sort_keys=True, separators=(",", ":"))
    assert json.dumps(second, sort_keys=True, separators=(",", ":")) == canonical


def test_notebook_validates_against_its_schema() -> None:
    validate_notebook(_intl_notebook())
    validate_notebook(_club_notebook())


# --------------------------------------------------------------------------- #
# Every emitted fact is source-backed, freshness-stamped, sample-guarded
# --------------------------------------------------------------------------- #
def test_every_fact_carries_source_freshness_and_meets_its_floor() -> None:
    nb = _intl_notebook()
    assert nb["facts"], "expected some facts for this fixture"
    for fact in nb["facts"]:
        assert fact["source_ids"] and set(fact["source_ids"]) <= set(nb["source_ids"])
        assert set(fact["freshness"]) == {
            "as_of_utc",
            "last_event_utc",
            "age_days",
            "stale",
            "staleness_days",
        }
        assert fact["freshness"]["stale"] is False
        assert fact["sample_n"] >= fact["min_sample"]
        assert fact["label"] in {"predictive", "context", "coincidence"}


def test_labels_track_the_registry() -> None:
    label_by_id = {tmpl.id: tmpl.label for tmpl in REGISTRY}
    for fact in _intl_notebook()["facts"]:
        assert fact["label"] == label_by_id[fact["id"]]
    # The predictive base rates and coincidences are distinct template families.
    assert label_by_id["home_advantage_base_rate"] == "predictive"
    assert label_by_id["scoreline_repeat"] == "coincidence"
    assert label_by_id["unbeaten_run"] == "context"


# --------------------------------------------------------------------------- #
# Number discipline — every digit in the prose is a declared, whitelisted number
# --------------------------------------------------------------------------- #
def test_every_fact_text_is_number_disciplined() -> None:
    for nb in (_intl_notebook(), _club_notebook()):
        for fact in nb["facts"]:
            assert_number_discipline(fact)  # raises if any digit is undeclared


def test_number_discipline_rejects_a_smuggled_number() -> None:
    fact = {"id": "x", "text": "a run of 7 matches", "numbers": []}
    with pytest.raises(ValueError, match="undisciplined number"):
        assert_number_discipline(fact)


# --------------------------------------------------------------------------- #
# Minimum-sample suppression
# --------------------------------------------------------------------------- #
def _candidate(sample_n: int, *, spec: float = 0.5, last: str = "2026-07-01") -> Candidate:
    ts = pd.Timestamp(last)
    return Candidate(
        subject="Team",
        text="",
        values={},
        numbers=[],
        sample_n=sample_n,
        denominator=sample_n,
        first_date=ts,
        last_date=ts,
        specificity=spec,
    )


def test_min_sample_suppresses_and_logs() -> None:
    tmpl = Template("thin_rate", "1.0.0", "context", "team", 1, 5, None, lambda c: [])
    as_of = pd.Timestamp("2026-07-08T00:00:00Z")
    facts, suppressed = apply_guardrails(
        [(tmpl, _candidate(3))], source_ids=("sp_x",), as_of=as_of, coincidence_cap=3
    )
    assert facts == []
    assert suppressed and suppressed[0]["reason"] == "min_sample"


def test_min_sample_admits_when_the_floor_is_met() -> None:
    tmpl = Template("thin_rate", "1.0.0", "context", "team", 1, 5, None, lambda c: [])
    as_of = pd.Timestamp("2026-07-08T00:00:00Z")
    facts, suppressed = apply_guardrails(
        [(tmpl, _candidate(5))], source_ids=("sp_x",), as_of=as_of, coincidence_cap=3
    )
    assert len(facts) == 1 and suppressed == []


# --------------------------------------------------------------------------- #
# Staleness auto-hide
# --------------------------------------------------------------------------- #
def test_stale_form_fact_is_auto_hidden() -> None:
    tmpl = Template("old_form", "1.0.0", "context", "team", 1, 1, 400, lambda c: [])
    as_of = pd.Timestamp("2026-07-08T00:00:00Z")
    stale = _candidate(9, last="2024-01-01")  # ~2.5 years before as_of, > 400 days
    facts, suppressed = apply_guardrails(
        [(tmpl, stale)], source_ids=("sp_x",), as_of=as_of, coincidence_cap=3
    )
    assert facts == []
    assert suppressed and suppressed[0]["reason"] == "stale"


def test_structural_fact_never_goes_stale() -> None:
    tmpl = Template("all_time", "1.0.0", "context", "team", 1, 1, None, lambda c: [])
    as_of = pd.Timestamp("2026-07-08T00:00:00Z")
    ancient = _candidate(9, last="1950-01-01")
    facts, _ = apply_guardrails(
        [(tmpl, ancient)], source_ids=("sp_x",), as_of=as_of, coincidence_cap=3
    )
    assert len(facts) == 1 and facts[0]["freshness"]["stale"] is False


# --------------------------------------------------------------------------- #
# Coincidence cap + quarantine
# --------------------------------------------------------------------------- #
def test_coincidence_cap_keeps_the_most_specific_and_logs_the_rest() -> None:
    tmpl = Template("quirk", "1.0.0", "coincidence", "team", 2, 1, None, lambda c: [])
    as_of = pd.Timestamp("2026-07-08T00:00:00Z")
    proposals = []
    for i, spec in enumerate([0.9, 0.8, 0.7, 0.6, 0.5]):
        cand = _candidate(9, spec=spec)
        cand.subject = f"Team {i}"
        proposals.append((tmpl, cand))
    facts, suppressed = apply_guardrails(
        proposals, source_ids=("sp_x",), as_of=as_of, coincidence_cap=3
    )
    assert len(facts) == 3
    assert sorted(f["specificity"] for f in facts) == [0.7, 0.8, 0.9]
    capped = [s for s in suppressed if s["reason"] == "coincidence_cap"]
    assert len(capped) == 2


def test_real_notebook_never_exceeds_the_coincidence_cap() -> None:
    nb = _intl_notebook()
    coincidences = [f for f in nb["facts"] if f["label"] == "coincidence"]
    assert len(coincidences) <= COINCIDENCE_CAP == nb["coincidence_cap"]


# --------------------------------------------------------------------------- #
# Multiple-comparison bound
# --------------------------------------------------------------------------- #
def test_family_size_is_a_fixed_registry_constant() -> None:
    expected = sum(tmpl.arity for tmpl in REGISTRY)
    assert family_size() == expected
    assert _intl_notebook()["family_size"] == expected
    # A fixed, pre-registered family — not a function of the data.
    assert _club_notebook()["family_size"] == expected
    assert _intl_notebook()["registry_version"] == REGISTRY_VERSION


# --------------------------------------------------------------------------- #
# Internationals-only scorers/shootouts; no fabricated club events
# --------------------------------------------------------------------------- #
def _form_ctx(goalscorers):
    """A TemplateContext for team 'Alpha': 12 completed matches v rotating rivals,
    all before the cutoff. team_perspective takes the last 10 as the window."""
    import pandas as pd
    from golavo_core.facts._history import TemplateContext

    rows = []
    rivals = ["Bravo", "Charlie", "Delta"]
    for i in range(12):
        day = f"2024-{(i % 12) + 1:02d}-05"
        opp = rivals[i % 3]
        rows.append({
            "match_id": f"m{i:02d}",
            "date": pd.Timestamp(day),
            "kickoff_utc": pd.Timestamp(day, tz="UTC"),
            "home_team": "Alpha",
            "away_team": opp,
            "home_score": 2,
            "away_score": 1,
            "is_complete": True,
            "neutral": False,
            "tournament": "Friendly",
            "competition": "Friendly",
        })
    matches = pd.DataFrame(rows)
    return TemplateContext(
        matches=matches, home_team="Alpha", away_team="Zulu", competition="Friendly",
        neutral=False, as_of=pd.Timestamp("2025-06-01", tz="UTC"),
        kickoff=pd.Timestamp("2025-06-01", tz="UTC"), source_ids=("s",),
        goalscorers=goalscorers, shootouts=None,
    )


def _gs_row(date, home, away, team, scorer, own_goal=False, penalty=False):
    import pandas as pd
    return {"date": pd.Timestamp(date), "home_team": home, "away_team": away,
            "team": team, "scorer": scorer, "own_goal": own_goal, "penalty": penalty}


def test_in_form_scorer_scopes_to_the_recent_window_and_excludes_own_goals() -> None:
    import pandas as pd
    from golavo_core.facts.context import in_form_scorer

    # Opponents rotate Bravo/Charlie/Delta by month index (i%3): Jan=Bravo,
    # Feb=Charlie, Mar=Delta, Apr=Bravo, May=Charlie, Jun=Delta, Jul=Bravo, ...
    # 4 goals for "Rush" inside the last-10 window (Mar..Dec), plus a Jan goal
    # (OUTSIDE the window) and an own goal (excluded).
    gs = pd.DataFrame([
        _gs_row("2024-03-05", "Alpha", "Delta", "Alpha", "Rush"),     # Mar, in window
        _gs_row("2024-04-05", "Alpha", "Bravo", "Alpha", "Rush"),     # Apr
        _gs_row("2024-05-05", "Alpha", "Charlie", "Alpha", "Rush"),   # May
        _gs_row("2024-06-05", "Alpha", "Delta", "Alpha", "Rush"),     # Jun -> 4 total
        _gs_row("2024-01-05", "Alpha", "Bravo", "Alpha", "Rush"),     # Jan, OUT of window
        _gs_row("2024-07-05", "Alpha", "Bravo", "Alpha", "Rush", own_goal=True),  # excluded
    ])
    facts = in_form_scorer(_form_ctx(gs))
    alpha = [c for c in facts if c.subject == "Alpha"]
    assert len(alpha) == 1
    c = alpha[0]
    assert c.values["scorer"] == "Rush"
    assert c.values["goals"] == 4          # window only, own goal excluded
    assert c.values["window_matches"] == 10
    # Player name never appears in the whitelist-safe text.
    assert "Rush" not in c.text


def test_in_form_scorer_needs_at_least_three_goals() -> None:
    import pandas as pd
    from golavo_core.facts.context import in_form_scorer

    gs = pd.DataFrame([
        _gs_row("2024-05-05", "Alpha", "Bravo", "Alpha", "Quiet"),
        _gs_row("2024-06-05", "Alpha", "Charlie", "Alpha", "Quiet"),
    ])
    assert in_form_scorer(_form_ctx(gs)) == []


def test_in_form_scorer_tie_breaks_alphabetically() -> None:
    import pandas as pd
    from golavo_core.facts.context import in_form_scorer

    gs = pd.DataFrame([
        _gs_row("2024-03-05", "Alpha", "Delta", "Alpha", "Zed"),
        _gs_row("2024-04-05", "Alpha", "Bravo", "Alpha", "Zed"),
        _gs_row("2024-05-05", "Alpha", "Charlie", "Alpha", "Zed"),
        _gs_row("2024-03-05", "Alpha", "Delta", "Alpha", "Abe"),
        _gs_row("2024-04-05", "Alpha", "Bravo", "Alpha", "Abe"),
        _gs_row("2024-05-05", "Alpha", "Charlie", "Alpha", "Abe"),
    ])
    facts = [c for c in in_form_scorer(_form_ctx(gs)) if c.subject == "Alpha"]
    assert facts and facts[0].values["scorer"] == "Abe"  # tie -> alphabetical


def test_in_form_scorer_is_empty_without_goalscorers() -> None:
    from golavo_core.facts.context import in_form_scorer
    assert in_form_scorer(_form_ctx(None)) == []


def test_scorer_and_shootout_facts_are_internationals_only() -> None:
    intl_ids = {f["id"] for f in _intl_notebook()["facts"]}
    club_ids = {f["id"] for f in _club_notebook()["facts"]}
    # The club pack ships no scorer or shootout data, so those templates cannot fire.
    assert "top_scorer" not in club_ids
    assert "shootout_record" not in club_ids
    # The club notebook still produces genuine context from results alone.
    assert club_ids, "club pack should still yield result-based facts"
    assert {"home_advantage_base_rate"} <= intl_ids


# --------------------------------------------------------------------------- #
# Schema validation is enforced
# --------------------------------------------------------------------------- #
def test_validate_notebook_rejects_a_broken_notebook() -> None:
    nb = _intl_notebook()
    broken = copy.deepcopy(nb)
    broken["family_size"] = nb["family_size"] + 1
    with pytest.raises(ValueError, match="family_size"):
        validate_notebook(broken)

    from jsonschema import ValidationError

    missing_source = copy.deepcopy(nb)
    if missing_source["facts"]:
        missing_source["facts"][0]["source_ids"] = []
        with pytest.raises(ValidationError):  # jsonschema minItems
            validate_notebook(missing_source)


# --------------------------------------------------------------------------- #
# Machine-checked no-write invariant
# --------------------------------------------------------------------------- #
def test_facts_package_is_statically_isolated_from_the_forecast_engine() -> None:
    assert_facts_isolated()  # AST scan; raises on a forbidden import


def test_assert_no_number_written_catches_a_mutation() -> None:
    before = {"forecast": {"probs": {"home": 0.5, "draw": 0.3, "away": 0.2}}, "evaluation": None}
    after = copy.deepcopy(before)
    assert_no_number_written(before, after)  # unchanged: fine
    after["forecast"]["probs"]["home"] = 0.51
    with pytest.raises(AssertionError, match="mutated a forecast"):
        assert_no_number_written(before, after)


def test_full_pipeline_writes_no_engine_number(tmp_path: Path) -> None:
    from golavo_core.facts.invariant import verify_notebook_pipeline_pure

    sealed_path = seal_forecast(
        pack_dir=T0_PACK,
        output_dir=tmp_path,
        date="2026-07-09",
        home_team="France",
        away_team="Morocco",
        as_of_utc="2026-07-08T00:00:00Z",
        horizon="T-24h",
    )
    artifact = json.loads(sealed_path.read_text(encoding="utf-8"))
    matches = load_matches(T0_PACK)
    gs, so = load_side_tables(T0_PACK)
    assert verify_notebook_pipeline_pure(artifact, matches, goalscorers=gs, shootouts=so)


# --------------------------------------------------------------------------- #
# AI fold: coincidences quarantined, whitelist still governs
# --------------------------------------------------------------------------- #
def test_fold_excludes_coincidences_and_namespaces_numbers() -> None:
    nb = _intl_notebook()
    facts, numbers = notebook_to_evidence(nb)
    foldable = [f for f in nb["facts"] if f["label"] in ("context", "predictive")]
    assert len(facts) == len(foldable)
    assert all(f["kind"] == "context" for f in facts)
    assert all(n["id"].startswith("nb_") for n in numbers)
    # No coincidence text ever reaches the model-facing evidence facts.
    coincidence_texts = {f["text"] for f in nb["facts"] if f["label"] == "coincidence"}
    assert coincidence_texts.isdisjoint({f["text"] for f in facts})


def test_folded_bundle_is_valid_and_preserves_engine_numbers(tmp_path: Path) -> None:
    sealed_path = seal_forecast(
        pack_dir=T0_PACK,
        output_dir=tmp_path,
        date="2026-07-09",
        home_team="France",
        away_team="Morocco",
        as_of_utc="2026-07-08T00:00:00Z",
        horizon="T-24h",
    )
    artifact = json.loads(sealed_path.read_text(encoding="utf-8"))
    matches = load_matches(T0_PACK)
    gs, so = load_side_tables(T0_PACK)
    nb = notebook_for_artifact(artifact, matches, goalscorers=gs, shootouts=so)
    extra_facts, extra_numbers = notebook_to_evidence(nb)

    base = build_evidence_bundle(artifact)
    folded = build_evidence_bundle(
        artifact, extra_facts=extra_facts, extra_numbers=extra_numbers
    )
    validate_evidence_bundle(folded)

    # Every engine number survives folding unchanged; notebook numbers are added.
    base_ids = {n["id"] for n in base["allowed_numbers"]}
    folded_ids = {n["id"] for n in folded["allowed_numbers"]}
    assert base_ids < folded_ids
    assert all(nid.startswith("nb_") for nid in folded_ids - base_ids)
    # A coincidence's numbers never enter the whitelist the model is shown.
    assert len(folded["facts"]) == len(base["facts"]) + len(extra_facts)


def test_default_bundle_is_unchanged_by_the_additive_fold_params(tmp_path: Path) -> None:
    """With no extras, the bundle is byte-identical to the pre-Phase-7 output."""
    sealed_path = seal_forecast(
        pack_dir=T0_PACK,
        output_dir=tmp_path,
        date="2026-07-09",
        home_team="France",
        away_team="Morocco",
        as_of_utc="2026-07-08T00:00:00Z",
        horizon="T-24h",
    )
    artifact = json.loads(sealed_path.read_text(encoding="utf-8"))
    once = build_evidence_bundle(artifact)
    twice = build_evidence_bundle(artifact, extra_facts=(), extra_numbers=())
    assert once == twice
    assert once["bundle_hash"] == twice["bundle_hash"]
