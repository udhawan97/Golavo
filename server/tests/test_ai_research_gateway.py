"""The gateway's web-research wiring: researcher runs only on a cache miss, a
failing researcher never voids the read, the adversarial-page number guard holds,
and cancellation short-circuits."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from golavo_core.artifacts import seal_forecast
from golavo_core.evidence import build_evidence_bundle
from golavo_server.ai_gateway import NarrationCache, ProviderConfig, generate_narration

T0_PACK = Path(__file__).resolve().parents[2] / "packs" / "martj42-internationals-273c731492df"


@pytest.fixture(scope="module")
def bundle(tmp_path_factory) -> dict:
    output = tmp_path_factory.mktemp("ledger")
    path = seal_forecast(
        pack_dir=T0_PACK, output_dir=output, date="2026-07-09",
        home_team="France", away_team="Morocco",
        as_of_utc="2026-07-08T00:00:00Z", horizon="T-24h",
    )
    return build_evidence_bundle(json.loads(path.read_text(encoding="utf-8")))


def _cfg(**kw) -> ProviderConfig:
    return ProviderConfig(provider="llama_server", model="m", base_url="http://x/v1", **kw)


def _canned(payload) -> object:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return lambda system, user: text


def _grounded(bundle: dict) -> dict:
    engine = bundle["sources"][0]["source_id"]
    display = {n["id"]: n["display"] for n in bundle["allowed_numbers"]}
    return {
        "verdict": None,
        "claims": [{
            "text": f"The most likely single result is a France win at {display['prob_home']}.",
            "source_ids": [engine], "number_refs": ["prob_home"],
        }],
        "scenarios": [], "candidate_facts": [], "research_notes": [], "background": [],
    }


class _Research:
    """A minimal stand-in for a ResearchResult with one fetched page."""

    url = "https://en.wikipedia.org/wiki/France"
    planned = 3
    sources = [object()]
    notes: list[str] = []

    def corpus(self):
        return {self.url: "France reached the final after a long unbeaten run."}

    def prompt_sources(self):
        return [{"source_id": "web_1", "url": self.url, "title": "France", "text": "..."}]

    def envelope_sources(self):
        return [{"source_id": "web_1", "kind": "web", "title": "France", "url": self.url}]


def test_researcher_runs_only_on_cache_miss(bundle: dict) -> None:
    calls = {"n": 0}

    def researcher():
        calls["n"] += 1
        return _Research()

    cache = NarrationCache()
    cfg = _cfg(allow_research=True)
    env1 = generate_narration(
        bundle, cfg, transport=_canned(_grounded(bundle)), cache=cache, researcher=researcher,
    )
    assert env1.status == "ok"
    assert calls["n"] == 1
    assert env1.web_sources and env1.web_sources[0]["kind"] == "web"
    # Second call hits the cache — researcher must NOT run again, and the web
    # sources still render from the cached entry.
    env2 = generate_narration(
        bundle, cfg, transport=_canned(_grounded(bundle)), cache=cache, researcher=researcher,
    )
    assert env2.cached is True
    assert calls["n"] == 1
    assert env2.web_sources and env2.web_sources[0]["kind"] == "web"


def test_failing_researcher_never_voids_the_read(bundle: dict) -> None:
    def researcher():
        raise RuntimeError("network down")

    env = generate_narration(
        bundle, _cfg(allow_research=True),
        transport=_canned(_grounded(bundle)), cache=NarrationCache(), researcher=researcher,
    )
    assert env.status == "ok"  # engine-only read still stands
    assert env.web_sources == []


def test_adversarial_page_cannot_smuggle_a_number(bundle: dict) -> None:
    # The model, influenced by a hostile page, tries to state a fabricated
    # probability in a CLAIM. The engine number guard must drop that claim.
    liar = {
        "verdict": None,
        "claims": [{
            "text": "Ignore the engine; France win 99.9% of the time.",
            "source_ids": [bundle["sources"][0]["source_id"]], "number_refs": [],
        }],
        "scenarios": [], "candidate_facts": [], "research_notes": [], "background": [],
    }
    env = generate_narration(
        bundle, _cfg(allow_research=True),
        transport=_canned(liar), cache=NarrationCache(), researcher=lambda: _Research(),
    )
    # No accepted narration carries the fabricated 99.9%.
    if env.narration:
        for claim in env.narration["claims"]:
            assert "99.9" not in claim["text"]


def test_cancellation_before_writing_returns_local_only(bundle: dict) -> None:
    env = generate_narration(
        bundle, _cfg(), transport=_canned(_grounded(bundle)), cache=NarrationCache(),
        is_cancelled=lambda: True,
    )
    assert env.status == "local_only"
    assert env.reason == "cancelled"
