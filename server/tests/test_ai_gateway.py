"""Phase 5 — AI gateway: happy path, caching, and adversarial fail-closed.

No live LLM. Every provider response is a canned string fed through an injected
transport, so the retry → local-only fallback is exercised deterministically in
CI. The gateway must pass a guard-validated narration through or fall back; it
can never let an unsupported number reach the caller.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from golavo_core.artifacts import seal_forecast
from golavo_core.evidence import build_evidence_bundle
from golavo_server import ai_gateway
from golavo_server import main as server_main
from golavo_server.ai_gateway import (
    NarrationCache,
    ProviderConfig,
    build_anthropic_payload,
    build_openai_payload,
    extract_json_object,
    generate_narration,
    resolve_provider,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
T0_PACK = REPO_ROOT / "packs/martj42-internationals-273c731492df"


@pytest.fixture(scope="module")
def bundle(tmp_path_factory: pytest.TempPathFactory) -> dict:
    output = tmp_path_factory.mktemp("ledger")
    path = seal_forecast(
        pack_dir=T0_PACK,
        output_dir=output,
        date="2026-07-09",
        home_team="France",
        away_team="Morocco",
        as_of_utc="2026-07-08T00:00:00Z",
        horizon="T-24h",
    )
    return build_evidence_bundle(json.loads(path.read_text(encoding="utf-8")))


def _cfg(provider: str = "llama_server", **kw) -> ProviderConfig:
    return ProviderConfig(provider=provider, model="test-model", base_url="http://x/v1", **kw)


def _canned(payload) -> ai_gateway.Transport:
    text = payload if isinstance(payload, str) else json.dumps(payload)

    def transport(system: str, user: str) -> str:
        return text

    return transport


def _valid_response(bundle: dict) -> dict:
    engine = bundle["sources"][0]["source_id"]
    display = {n["id"]: n["display"] for n in bundle["allowed_numbers"]}
    return {
        "claims": [
            {
                "text": f"The most likely single result is a France win at {display['prob_home']}.",
                "source_ids": [engine],
                "number_refs": ["prob_home"],
            }
        ],
        "scenarios": [],
        "candidate_facts": [],
    }


# --- Off / disabled ----------------------------------------------------------

def test_off_provider_never_calls_a_model(bundle: dict) -> None:
    called = False

    def transport(system: str, user: str) -> str:
        nonlocal called
        called = True
        return "{}"

    env = generate_narration(bundle, resolve_provider({"provider": "off"}), transport=transport)
    assert env.status == "disabled"
    assert env.narration is None
    assert called is False


# --- Happy path + caching ----------------------------------------------------

def test_valid_response_is_accepted_and_stamped(bundle: dict) -> None:
    cache = NarrationCache()
    env = generate_narration(
        bundle, _cfg(), transport=_canned(_valid_response(bundle)), cache=cache
    )
    assert env.status == "ok"
    assert env.narration is not None
    assert len(env.narration["claims"]) == 1
    assert env.prompt_version and env.bundle_hash == bundle["bundle_hash"]
    assert env.cached is False


def test_second_call_is_served_from_cache(bundle: dict) -> None:
    cache = NarrationCache()
    calls = {"n": 0}

    def transport(system: str, user: str) -> str:
        calls["n"] += 1
        return json.dumps(_valid_response(bundle))

    cfg = _cfg()
    first = generate_narration(bundle, cfg, transport=transport, cache=cache)
    second = generate_narration(bundle, cfg, transport=transport, cache=cache)
    assert first.status == second.status == "ok"
    assert second.cached is True
    assert calls["n"] == 1  # cache hit; no second model call


def test_response_with_fences_and_thinking_is_parsed(bundle: dict) -> None:
    raw = "<think>plan</think>\n```json\n" + json.dumps(_valid_response(bundle)) + "\n```"
    env = generate_narration(bundle, _cfg(), transport=_canned(raw), cache=NarrationCache())
    assert env.status == "ok"


# --- Adversarial transports fail closed to local_only ------------------------

def _attack_change_probability(bundle: dict) -> dict:
    r = _valid_response(bundle)
    r["claims"][0]["text"] = "France win probability is actually 91%."
    return r


def _attack_betting(bundle: dict) -> dict:
    r = _valid_response(bundle)
    r["claims"][0]["text"] = "France are a lock with three units of value."
    return r


def _attack_fake_citation(bundle: dict) -> dict:
    r = _valid_response(bundle)
    r["claims"][0]["source_ids"] = ["source:not_in_bundle"]
    r["claims"][0]["number_refs"] = []
    r["claims"][0]["text"] = "France look strong."
    return r


def _attack_key_leak(bundle: dict) -> dict:
    r = _valid_response(bundle)
    r["claims"][0]["text"] = "Debug key sk-ABCD1234efgh5678IJKL for reference."
    return r


ATTACKS = {
    "change_probability": _attack_change_probability,
    "betting": _attack_betting,
    "fake_citation": _attack_fake_citation,
    "key_leak": _attack_key_leak,
    "not_json": lambda b: "I cannot comply, here is prose only.",
    "empty_object": lambda b: {"claims": [], "scenarios": [], "candidate_facts": []},
}


@pytest.mark.parametrize("name", list(ATTACKS))
def test_adversarial_response_falls_back_to_local_only(name: str, bundle: dict) -> None:
    payload = ATTACKS[name](bundle)
    env = generate_narration(bundle, _cfg(), transport=_canned(payload), cache=NarrationCache())
    assert env.status == "local_only", f"attack {name!r} was not contained"
    assert env.narration is None
    # No fabricated content survives anywhere in the returned envelope.
    dumped = json.dumps(env.to_dict())
    assert "91%" not in dumped
    assert "sk-ABCD1234" not in dumped


def test_retry_then_fallback_and_a_late_success_is_used(bundle: dict) -> None:
    attempts = {"n": 0}

    def flaky(system: str, user: str) -> str:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return "not json"
        return json.dumps(_valid_response(bundle))

    env = generate_narration(bundle, _cfg(), transport=flaky, cache=NarrationCache())
    assert env.status == "ok"
    assert attempts["n"] == 2  # first failed, retry succeeded


def test_transport_error_becomes_local_only(bundle: dict) -> None:
    def boom(system: str, user: str) -> str:
        raise ConnectionError("connection refused")

    env = generate_narration(bundle, _cfg(), transport=boom, cache=NarrationCache())
    assert env.status == "local_only"
    assert env.narration is None


# --- Provider resolution + key handling --------------------------------------

def test_cloud_provider_without_key_is_unavailable(bundle: dict, monkeypatch) -> None:
    monkeypatch.setattr(ai_gateway, "load_api_key", lambda provider: None)
    env = generate_narration(bundle, resolve_provider({"provider": "openai"}))
    assert env.status == "unavailable"
    assert env.narration is None


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ValueError):
        resolve_provider({"provider": "definitely-not-a-provider"})


def test_api_key_only_ever_lives_in_the_request_header() -> None:
    cfg = _cfg(provider="openai")
    key = "sk-secret-value-1234567890"
    url, headers, body = build_openai_payload(cfg, key, "system prompt", "user prompt")
    assert headers["Authorization"] == f"Bearer {key}"
    assert key not in json.dumps(body)  # never in the body/messages
    assert cfg.redacted().get("api_key") is None  # config carries no key at all

    aurl, aheaders, abody = build_anthropic_payload(_cfg(provider="anthropic"), key, "s", "u")
    assert aheaders["x-api-key"] == key
    assert key not in json.dumps(abody)


def test_extract_json_object_handles_noise() -> None:
    assert extract_json_object('prefix {"a": 1} suffix') == {"a": 1}
    assert extract_json_object("no object here") is None
    assert extract_json_object('{"nested": {"x": 1}, "y": 2}') == {"nested": {"x": 1}, "y": 2}


# --- Endpoint ----------------------------------------------------------------

def test_endpoint_off_by_default(monkeypatch, tmp_path) -> None:
    ledger = tmp_path / "ledger"
    sealed = seal_forecast(
        pack_dir=T0_PACK,
        output_dir=ledger,
        date="2026-07-09",
        home_team="France",
        away_team="Morocco",
        as_of_utc="2026-07-08T00:00:00Z",
    )
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    client = TestClient(server_main.app)
    artifact_id = json.loads(sealed.read_text())["artifact_id"]

    # No body at all -> disabled, and no model is ever contacted.
    res = client.post(f"/api/v1/forecasts/{artifact_id}/narrative")
    assert res.status_code == 200
    assert res.json()["status"] == "disabled"

    res_off = client.post(
        f"/api/v1/forecasts/{artifact_id}/narrative", json={"provider": "off"}
    )
    assert res_off.json()["status"] == "disabled"


def test_endpoint_unreachable_local_provider_falls_back(monkeypatch, tmp_path) -> None:
    ledger = tmp_path / "ledger"
    sealed = seal_forecast(
        pack_dir=T0_PACK,
        output_dir=ledger,
        date="2026-07-09",
        home_team="France",
        away_team="Morocco",
        as_of_utc="2026-07-08T00:00:00Z",
    )
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    client = TestClient(server_main.app)
    artifact_id = json.loads(sealed.read_text())["artifact_id"]

    # A local provider pointed at a dead port: the call fails, we fall back. This
    # proves the endpoint never blocks on or crashes from an absent model.
    res = client.post(
        f"/api/v1/forecasts/{artifact_id}/narrative",
        json={"provider": "llama_server", "base_url": "http://127.0.0.1:9/v1", "timeout_s": 1},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "local_only"
    assert res.json()["narration"] is None


def test_endpoint_unknown_artifact_is_404(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", tmp_path / "empty")
    client = TestClient(server_main.app)
    res = client.post("/api/v1/forecasts/fa_missing00/narrative", json={"provider": "off"})
    assert res.status_code == 404
