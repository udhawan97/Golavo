"""Match-analysis evidence bundles (`ma_*`, schema 0.2.0) and their guards.

Proves the cockpit's "AI deep read of the notes" path is governed by exactly the
same fail-closed machinery as the sealed path: schema-valid bundles, referential
integrity, an honest non-artifact identity, and a review that accepts only
narrations grounded in the whitelist.
"""

from __future__ import annotations

import pandas as pd
from golavo_core.ai import review_narration
from golavo_core.analysis import build_match_analysis
from golavo_core.evidence import build_match_evidence_bundle

TEAMS = ["Aland", "Borda", "Corvo", "Delta"]


def _match(mid: str, date: str, home: str, away: str, hs: int, aws: int) -> dict:
    day = pd.Timestamp(date, tz="UTC")
    return {
        "match_id": mid, "date": day, "kickoff_utc": day, "home_team": home,
        "away_team": away, "home_score": hs, "away_score": aws, "is_complete": True,
        "neutral": False, "competition": "Test League", "tournament": "Test League",
        "source_id": "test-source", "source_kind": "international",
        "home_norm": home.lower(), "away_norm": away.lower(),
    }


def _history() -> pd.DataFrame:
    rows, n = [], 0
    for round_no in range(6):
        for i in range(len(TEAMS)):
            for j in range(len(TEAMS)):
                if i == j:
                    continue
                n += 1
                rows.append(
                    _match(f"m_h{n:04d}", f"2024-{1 + round_no:02d}-{(n % 27) + 1:02d}",
                           TEAMS[i], TEAMS[j], (n % 3), (n % 2))
                )
    return pd.DataFrame(rows)


def _fixture() -> dict:
    ko = pd.Timestamp("2025-06-01", tz="UTC")
    return {
        "match_id": "m_fix1", "date": ko, "kickoff_utc": ko, "home_team": "Aland",
        "away_team": "Borda", "home_score": 2, "away_score": 1, "is_complete": True,
        "neutral": False, "competition": "Test League", "tournament": "Test League",
        "source_id": "test-source", "source_kind": "international",
        "home_norm": "aland", "away_norm": "borda",
    }


def _bundle() -> dict:
    analysis = build_match_analysis(matches=_history(), match_row=_fixture())
    return build_match_evidence_bundle(analysis, pack_source_ids=("test-source",))


def test_match_bundle_is_valid_and_honestly_identified() -> None:
    bundle = _bundle()
    # ma_ prefix + replay status: can never masquerade as a sealed artifact bundle.
    assert bundle["artifact_id"].startswith("ma_")
    assert bundle["artifact_status"] == "replay"
    assert bundle["schema_version"] == "0.2.0"
    # Council numbers exist for both voices and the baseline; variants excluded.
    ids = {n["id"] for n in bundle["allowed_numbers"]}
    assert "mc_elo_ordlogit_prob_home" in ids
    assert "mc_dixon_coles_prob_home" in ids
    assert "mc_climatological_prob_home" in ids
    assert not any("poisson_independent" in i or "bivariate" in i for i in ids)
    # The goal model's expected goals and most-likely scoreline are citable.
    assert "mc_dixon_coles_xg_home" in ids
    assert "mc_most_likely_prob" in ids


def test_match_bundle_is_deterministic() -> None:
    assert _bundle() == _bundle()


def test_review_accepts_a_grounded_synthesis_and_rejects_an_invented_number() -> None:
    bundle = _bundle()
    prob = next(n for n in bundle["allowed_numbers"] if n["id"] == "mc_dixon_coles_prob_home")
    grounded = {
        "claims": [
            {
                "text": f"The goal model puts the home side at {prob['display']}.",
                "source_ids": ["engine:match_analysis"],
                "number_refs": ["mc_dixon_coles_prob_home"],
            }
        ],
        "scenarios": [],
        "candidate_facts": [],
    }
    review = review_narration(grounded, bundle)
    assert review.accepted, review.rejections

    invented = {
        "claims": [
            {
                # 87.3% appears nowhere in the whitelist — must void the output.
                "text": "The home side wins 87.3% of the time.",
                "source_ids": ["engine:match_analysis"],
                "number_refs": ["mc_dixon_coles_prob_home"],
            }
        ],
        "scenarios": [],
        "candidate_facts": [],
    }
    review = review_narration(invented, bundle)
    assert not review.accepted


def test_notebook_numbers_fold_into_the_match_bundle() -> None:
    from golavo_core.facts import build_notebook, notebook_to_evidence

    history = _history()
    fixture = _fixture()
    notebook = build_notebook(
        matches=history,
        home_team="Aland",
        away_team="Borda",
        competition="Test League",
        neutral=False,
        as_of_utc="2025-05-31T23:59:59Z",
        kickoff_utc="2025-06-01T00:00:00Z",
        source_ids=["test-source"],
        validate=True,
    )
    nb_facts, nb_numbers = notebook_to_evidence(notebook)
    analysis = build_match_analysis(matches=history, match_row=fixture)
    bundle = build_match_evidence_bundle(
        analysis,
        notebook_facts=nb_facts,
        notebook_numbers=nb_numbers,
        pack_source_ids=("test-source",),
    )
    ids = {n["id"] for n in bundle["allowed_numbers"]}
    assert any(i.startswith("nb_") for i in ids), "notebook numbers must be citable"
    # Engine numbers keep their ids alongside the fold — nothing was displaced.
    assert "mc_elo_ordlogit_prob_home" in ids


def test_preview_kind_flows_through() -> None:
    fixture = _fixture()
    fixture["home_score"] = None
    fixture["away_score"] = None
    fixture["is_complete"] = False
    analysis = build_match_analysis(matches=_history(), match_row=fixture)
    bundle = build_match_evidence_bundle(analysis, pack_source_ids=("test-source",))
    assert bundle["artifact_status"] == "preview"
