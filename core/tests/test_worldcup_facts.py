"""Isolated World Cup history, templates, and as-of leak safety."""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest
from golavo_core.facts import load_wc_history, worldcup
from golavo_core.facts._history import TemplateContext
from golavo_core.facts.guardrails import build_fact
from golavo_core.facts.registry import REGISTRY

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK = REPO_ROOT / "packs/fjelstul-worldcup-f942c6b"


def _ctx(as_of: str = "2026-01-01") -> TemplateContext:
    return TemplateContext(
        matches=pd.DataFrame(),
        home_team="France",
        away_team="Morocco",
        competition="FIFA World Cup",
        neutral=True,
        as_of=pd.Timestamp(as_of, tz="UTC"),
        kickoff=pd.Timestamp(as_of, tz="UTC"),
        source_ids=("match-source",),
        wc_history=load_wc_history(PACK),
    )


def _fact(candidate, template_id: str, as_of: str = "2026-01-01") -> dict:
    template = next(item for item in REGISTRY if item.id == template_id)
    source_ids = tuple(candidate.extra["source_ids"])
    return build_fact(candidate, template, source_ids, pd.Timestamp(as_of, tz="UTC"))[0]


def test_loader_returns_typed_mens_frames_and_none_when_absent(tmp_path: Path) -> None:
    history = load_wc_history(PACK)
    assert history is not None
    assert len(history.standings) == 88
    assert len(history.awards) == 141
    assert str(history.standings["position"].dtype) == "Int8"
    assert history.appearances["tournament_name"].str.contains("Men's World Cup").all()
    assert load_wc_history(tmp_path / "missing") is None


def test_loader_rejects_a_tampered_pack(tmp_path: Path) -> None:
    copied = tmp_path / "pack"
    shutil.copytree(PACK, copied)
    (copied / "tournaments.csv").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sha256 mismatch"):
        load_wc_history(copied)


def test_pedigree_values_are_source_backed() -> None:
    candidates = worldcup.wc_pedigree(_ctx())
    france = next(candidate for candidate in candidates if candidate.subject == "France")
    morocco = next(candidate for candidate in candidates if candidate.subject == "Morocco")
    assert france.values == {
        "titles": 2,
        "title_years": [1998, 2018],
        "finals": 4,
        "appearances": 16,
        "best_recent": {"position": 1, "year": 2018},
    }
    assert morocco.values["best_recent"] == {"position": 4, "year": 2022}
    assert _fact(france, "wc_pedigree")["source_ids"] == ["fjelstul-worldcup"]


def test_awards_are_structured_and_missing_team_skips() -> None:
    candidates = worldcup.wc_awards(_ctx())
    france = next(candidate for candidate in candidates if candidate.subject == "France")
    assert len(france.values["awards"]) == 12
    assert {item["year"] for item in france.values["awards"]} <= set(range(1930, 2023))
    assert not any(candidate.subject == "Morocco" for candidate in candidates)


def test_2014_replay_cannot_see_2014_completion_or_2018_title() -> None:
    candidates = worldcup.wc_pedigree(_ctx("2014-06-12"))
    france = next(candidate for candidate in candidates if candidate.subject == "France")
    assert france.values["title_years"] == [1998]
    assert france.values["appearances"] == 13
    assert france.last_date.year == 2010
