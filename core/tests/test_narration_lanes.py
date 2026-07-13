"""Narration 0.3.0: the verdict and web-research lanes.

Both are OPTIONAL side lanes that must NEVER void the grounded claims. The
verdict is engine-grounded (same rules as a claim); research_notes are honesty-
grounded (the quote must be verbatim in a page the sidecar actually fetched, and
any number in the note must appear in that quote — never rescued by an engine
number).
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
        "match_id": mid, "date": day, "kickoff_utc": day,
        "home_team": home, "away_team": away, "home_score": hs, "away_score": aws,
        "is_complete": True, "neutral": False, "competition": "Test League",
        "source_id": "test-source", "source_kind": "international",
        "home_norm": home.lower(), "away_norm": away.lower(),
    }


def _history() -> pd.DataFrame:
    rows, n = [], 0
    for round_no in range(6):
        base_month = 1 + round_no
        for i in range(len(TEAMS)):
            for j in range(len(TEAMS)):
                if i == j:
                    continue
                n += 1
                date = f"2024-{base_month:02d}-{(n % 27) + 1:02d}"
                hs, aws = (2, 1) if (i + j) % 2 == 0 else (0, 1)
                rows.append(_match(f"m_hist{n:04d}", date, TEAMS[i], TEAMS[j], hs, aws))
    return pd.DataFrame(rows)


def _fixture() -> dict:
    ko = pd.Timestamp("2025-06-01", tz="UTC")
    return {
        "match_id": "m_fix", "date": ko, "kickoff_utc": ko,
        "home_team": "Aland", "away_team": "Borda", "home_score": 1, "away_score": 0,
        "is_complete": True, "neutral": False, "competition": "Test League",
        "source_id": "test-source", "source_kind": "international",
        "home_norm": "aland", "away_norm": "borda",
    }


def _bundle() -> dict:
    analysis = build_match_analysis(matches=_history(), match_row=_fixture())
    return build_match_evidence_bundle(analysis, pack_source_ids=("test-source",))


def _grounded_claim(bundle: dict) -> dict:
    prob = next(n for n in bundle["allowed_numbers"] if n["id"] == "mc_dixon_coles_prob_home")
    return {
        "text": f"The goal model puts the home side at {prob['display']}.",
        "source_ids": ["engine:match_analysis"],
        "number_refs": ["mc_dixon_coles_prob_home"],
    }


# ---- verdict ---------------------------------------------------------------


def test_grounded_verdict_is_kept() -> None:
    bundle = _bundle()
    prob = next(n for n in bundle["allowed_numbers"] if n["id"] == "mc_dixon_coles_prob_home")
    raw = {
        "verdict": {
            "text": f"Aland are the most likely winners at {prob['display']}.",
            "source_ids": ["engine:match_analysis"],
            "number_refs": ["mc_dixon_coles_prob_home"],
        },
        "claims": [_grounded_claim(bundle)],
        "scenarios": [],
        "candidate_facts": [],
    }
    review = review_narration(raw, bundle)
    assert review.accepted, review.rejections
    assert review.narration["verdict"] is not None
    assert review.narration["verdict"]["number_refs"] == ["mc_dixon_coles_prob_home"]


def test_fabricated_verdict_number_nulls_the_verdict_but_keeps_claims() -> None:
    bundle = _bundle()
    raw = {
        "verdict": {
            "text": "Aland win 93.7% of the time.",  # not a whitelisted display
            "source_ids": ["engine:match_analysis"],
            "number_refs": ["mc_dixon_coles_prob_home"],
        },
        "claims": [_grounded_claim(bundle)],
        "scenarios": [],
        "candidate_facts": [],
    }
    review = review_narration(raw, bundle)
    assert review.accepted, review.rejections
    assert review.narration["verdict"] is None
    assert len(review.narration["claims"]) == 1


def test_absent_verdict_is_null() -> None:
    bundle = _bundle()
    raw = {"claims": [_grounded_claim(bundle)], "scenarios": [], "candidate_facts": []}
    review = review_narration(raw, bundle)
    assert review.accepted, review.rejections
    assert review.narration["verdict"] is None


# ---- research notes --------------------------------------------------------

_PAGE = (
    "Aland and Borda have met eleven times at this tournament. "
    "The stadium holds 42000 spectators and opened decades ago."
)
_CORPUS = {"https://en.wikipedia.org/wiki/Test": _PAGE}


def _with_research(bundle: dict, note: dict) -> dict:
    return {
        "claims": [_grounded_claim(bundle)],
        "scenarios": [],
        "candidate_facts": [],
        "research_notes": [note],
    }


def test_verbatim_research_quote_is_kept() -> None:
    bundle = _bundle()
    note = {
        "text": "The sides have a long tournament history against each other.",
        "quote": "Aland and Borda have met eleven times at this tournament.",
        "source_url": "https://en.wikipedia.org/wiki/Test",
    }
    review = review_narration(
        _with_research(bundle, note), bundle, allow_research=True, research_corpus=_CORPUS
    )
    assert review.accepted, review.rejections
    assert len(review.narration["research_notes"]) == 1


def test_paraphrased_quote_is_dropped() -> None:
    bundle = _bundle()
    note = {
        "text": "They have a long history.",
        "quote": "The two teams have faced each other many times before.",  # not verbatim
        "source_url": "https://en.wikipedia.org/wiki/Test",
    }
    review = review_narration(
        _with_research(bundle, note), bundle, allow_research=True, research_corpus=_CORPUS
    )
    assert review.accepted
    assert review.narration["research_notes"] == []


def test_unknown_source_url_is_dropped() -> None:
    bundle = _bundle()
    note = {
        "text": "History.",
        "quote": "Aland and Borda have met eleven times at this tournament.",
        "source_url": "https://evil.example/inject",  # never fetched
    }
    review = review_narration(
        _with_research(bundle, note), bundle, allow_research=True, research_corpus=_CORPUS
    )
    assert review.accepted
    assert review.narration["research_notes"] == []


def test_research_number_must_be_in_the_quote_not_the_engine() -> None:
    bundle = _bundle()
    # 42000 is in the page but not in THIS quote → the number is ungrounded.
    note = {
        "text": "The stadium holds 42000 spectators.",
        "quote": "Aland and Borda have met eleven times at this tournament.",
        "source_url": "https://en.wikipedia.org/wiki/Test",
    }
    review = review_narration(
        _with_research(bundle, note), bundle, allow_research=True, research_corpus=_CORPUS
    )
    assert review.accepted
    assert review.narration["research_notes"] == []
    # But when the quote DOES carry the number, it is kept.
    ok = {
        "text": "The stadium holds 42000 spectators.",
        "quote": "The stadium holds 42000 spectators and opened decades ago.",
        "source_url": "https://en.wikipedia.org/wiki/Test",
    }
    review2 = review_narration(
        _with_research(bundle, ok), bundle, allow_research=True, research_corpus=_CORPUS
    )
    assert review2.accepted
    assert len(review2.narration["research_notes"]) == 1


def test_research_disabled_drops_notes_but_keeps_claims() -> None:
    bundle = _bundle()
    note = {
        "text": "History.",
        "quote": "Aland and Borda have met eleven times at this tournament.",
        "source_url": "https://en.wikipedia.org/wiki/Test",
    }
    review = review_narration(_with_research(bundle, note), bundle)  # allow_research=False
    assert review.accepted
    assert review.narration["research_notes"] == []
    assert len(review.narration["claims"]) == 1


def test_a_bad_research_lane_never_voids_grounded_claims() -> None:
    bundle = _bundle()
    note = {"text": "x", "quote": "totally invented text", "source_url": "https://nope"}
    review = review_narration(
        _with_research(bundle, note), bundle, allow_research=True, research_corpus=_CORPUS
    )
    assert review.accepted  # the grounded claim still stands
    assert review.narration["research_notes"] == []
