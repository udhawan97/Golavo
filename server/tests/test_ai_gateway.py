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


def test_harmless_extra_keys_are_pruned_not_rejected(bundle: dict) -> None:
    # Small local models routinely decorate items with extras (claim_id, kind,
    # confidence). The strict wire schema would reject them; pruning keeps the
    # otherwise-valid narration. The number guarantee is unaffected — the served
    # claim is rebuilt from known keys only, so nothing extra reaches the user.
    payload = _valid_response(bundle)
    payload["claims"][0].update({"claim_id": "c1", "kind": "outcome", "confidence": 0.9})
    payload["version"] = "made-up"
    env = generate_narration(bundle, _cfg(), transport=_canned(payload), cache=NarrationCache())
    assert env.status == "ok"
    served = env.narration["claims"][0]
    assert set(served) == {"text", "source_ids", "number_refs"}


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


def test_invalid_json_retry_uses_json_only_instruction(bundle: dict) -> None:
    attempts: list[str] = []

    def flaky(system: str, user: str) -> str:
        attempts.append(user)
        if len(attempts) == 1:
            return "not json"
        return json.dumps(_valid_response(bundle))

    env = generate_narration(bundle, _cfg(), transport=flaky, cache=NarrationCache())
    assert env.status == "ok"
    assert len(attempts) == 2
    assert "RETRY BECAUSE YOUR PREVIOUS RESPONSE WAS NOT VALID JSON" not in attempts[0]
    assert "RETRY BECAUSE YOUR PREVIOUS RESPONSE WAS NOT VALID JSON" in attempts[1]


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


def test_cloud_base_url_override_is_rejected_to_protect_byok_key() -> None:
    with pytest.raises(ValueError, match="only for local"):
        resolve_provider({"provider": "openai", "base_url": "https://example.test/v1"})


def test_local_provider_is_restricted_to_loopback() -> None:
    assert resolve_provider(
        {"provider": "llama_server", "base_url": "http://127.0.0.1:8080/v1"}
    ).base_url == "http://127.0.0.1:8080/v1"
    with pytest.raises(ValueError, match="loopback"):
        resolve_provider({"provider": "llama_server", "base_url": "http://example.test/v1"})


@pytest.mark.parametrize("timeout", [0, 481, float("nan"), "not-a-number"])
def test_provider_timeout_is_bounded(timeout) -> None:
    with pytest.raises(ValueError, match="between 1 and 480"):
        resolve_provider({"provider": "ollama", "timeout_s": timeout})


def test_default_timeout_follows_the_depth() -> None:
    # Fast local reads default to 120s; a deep read (bigger model, fuller prompt)
    # gets up to 8 minutes. Cloud stays snappy at 30s regardless of depth.
    assert resolve_provider({"provider": "ollama"}).timeout_s == 120.0
    assert resolve_provider({"provider": "ollama", "depth": "fast"}).timeout_s == 120.0
    assert resolve_provider({"provider": "ollama", "depth": "deep"}).timeout_s == 480.0
    assert resolve_provider({"provider": "llama_server", "depth": "deep"}).timeout_s == 480.0
    assert resolve_provider({"provider": "openai", "depth": "deep"}).timeout_s == 30.0
    # An explicit request always wins over the depth default.
    explicit = resolve_provider({"provider": "ollama", "depth": "deep", "timeout_s": 12})
    assert explicit.timeout_s == 12.0


def test_unknown_depth_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown depth"):
        resolve_provider({"provider": "ollama", "depth": "turbo"})


def test_deep_read_asks_for_more_and_uses_a_longer_output_cap() -> None:
    fast = resolve_provider({"provider": "ollama", "depth": "fast"})
    deep = resolve_provider({"provider": "ollama", "depth": "deep"})
    assert deep.max_output_tokens > fast.max_output_tokens
    fast_url, _fh, fast_body = ai_gateway.build_ollama_payload(fast, "sys", "u" * 4000)
    _du, _dh, deep_body = ai_gateway.build_ollama_payload(deep, "sys", "u" * 4000)
    assert fast_url.endswith("/api/chat")          # native, constrained-decoding endpoint
    assert fast_body["think"] is False and "format" in fast_body
    assert fast_body["options"]["num_predict"] < deep_body["options"]["num_predict"]


def test_local_model_can_be_pinned_by_env(monkeypatch) -> None:
    monkeypatch.setenv("GOLAVO_OLLAMA_MODEL", "mistral-small")
    assert resolve_provider({"provider": "ollama"}).model == "mistral-small"
    # An explicit model in the request still wins over the env pin.
    assert resolve_provider({"provider": "ollama", "model": "phi3"}).model == "phi3"


@pytest.mark.parametrize(
    "requested, installed, expected",
    [
        ("llama3.1", ["llama3.1"], "llama3.1"),               # exact
        ("llama3.1", ["gemma:2b", "llama3.1:latest"], "llama3.1:latest"),  # same base
        ("llama3.1", ["gemma4:12b", "llama3.2:latest"], "llama3.2:latest"),  # same family
        ("llama3.1", ["qwen2:7b", "mistral:latest"], "qwen2:7b"),  # first installed
    ],
)
def test_pick_local_model_prefers_the_closest_installed(requested, installed, expected) -> None:
    assert ai_gateway.pick_local_model(requested, installed) == expected


def test_list_local_models_is_empty_when_the_server_is_unreachable() -> None:
    cfg = resolve_provider(
        {"provider": "llama_server", "base_url": "http://127.0.0.1:9/v1", "timeout_s": 1}
    )
    assert ai_gateway.list_local_models(cfg) == []


def test_generate_narration_retargets_a_local_default_to_an_installed_model(
    bundle: dict, monkeypatch
) -> None:
    # The UI sends only {"provider": "ollama"}, so the server defaults to a model
    # the user may not have pulled. The gateway must probe the local server and
    # run whatever IS installed, stamping the model it actually used.
    monkeypatch.setattr(ai_gateway, "list_local_models", lambda config: ["gemma4:12b-it-qat"])
    monkeypatch.setattr(
        ai_gateway, "make_transport", lambda config: _canned(_valid_response(bundle))
    )
    cfg = resolve_provider({"provider": "ollama"})
    env = generate_narration(bundle, cfg, cache=NarrationCache())
    assert env.status == "ok"
    assert env.model == "gemma4:12b-it-qat"


def test_generate_narration_is_unavailable_when_no_local_model_is_installed(
    bundle: dict, monkeypatch
) -> None:
    def _tripwire(config):
        raise AssertionError("no model may be contacted when the local server is empty")

    monkeypatch.setattr(ai_gateway, "list_local_models", lambda config: [])
    monkeypatch.setattr(ai_gateway, "make_transport", _tripwire)
    cfg = resolve_provider({"provider": "ollama"})
    env = generate_narration(bundle, cfg, cache=NarrationCache())
    assert env.status == "unavailable"
    assert "local model" in (env.reason or "").lower()


def test_embedding_only_local_install_is_unavailable_not_a_garbage_loop(
    bundle: dict, monkeypatch
) -> None:
    # If the only installed model is an embedder, a chat narration is impossible.
    # Report it honestly instead of picking it and looping on local_only.
    def _tripwire(config):
        raise AssertionError("an embedding model must not be contacted for narration")

    monkeypatch.setattr(ai_gateway, "list_local_models", lambda config: ["nomic-embed-text:latest"])
    monkeypatch.setattr(ai_gateway, "make_transport", _tripwire)
    cfg = resolve_provider({"provider": "ollama"})
    env = generate_narration(bundle, cfg, cache=NarrationCache())
    assert env.status == "unavailable"
    assert "local model" in (env.reason or "").lower()


def test_cached_local_narration_survives_the_model_server_stopping(
    bundle: dict, monkeypatch
) -> None:
    # First run generates + caches while the local server is up; then the server
    # goes away (probe returns []). A refresh-less read must still serve the cached
    # narration rather than reporting unavailable — the cache read precedes the probe.
    cache = NarrationCache()
    monkeypatch.setattr(ai_gateway, "list_local_models", lambda config: ["gemma4:12b-it-qat"])
    monkeypatch.setattr(
        ai_gateway, "make_transport", lambda config: _canned(_valid_response(bundle))
    )
    cfg = resolve_provider({"provider": "ollama"})
    first = generate_narration(bundle, cfg, cache=cache)
    assert first.status == "ok" and first.cached is False
    assert first.model == "gemma4:12b-it-qat"  # stamped with the model that ran

    monkeypatch.setattr(ai_gateway, "list_local_models", lambda config: [])  # server stopped
    second = generate_narration(bundle, cfg, cache=cache)
    assert second.status == "ok"
    assert second.cached is True
    assert second.model == "gemma4:12b-it-qat"  # the real generating model, not the default


def test_local_only_reason_distinguishes_unreachable_from_unverified(bundle: dict) -> None:
    # All attempts fail at the transport => the honest reason is "unreachable/timed
    # out", NOT "could not be verified against the sealed numbers".
    def _boom(system: str, user: str) -> str:
        raise TimeoutError("slow model")

    env = generate_narration(bundle, _cfg(), transport=_boom, cache=NarrationCache())
    assert env.status == "local_only"
    assert "reached or timed out" in (env.reason or "")
    assert "could not be verified" not in (env.reason or "")

    # A response that comes back but fails the guards => "could not be verified".
    liar = _canned(_attack_change_probability(bundle))
    env2 = generate_narration(bundle, _cfg(), transport=liar, cache=NarrationCache())
    assert env2.status == "local_only"
    assert "could not be verified" in (env2.reason or "")


def test_truncated_local_response_falls_back_not_raises(bundle: dict) -> None:
    # urllib can raise http.client.HTTPException (e.g. IncompleteRead), which is
    # NOT an OSError/URLError. It must be caught and become a local_only fallback.
    import http.client

    def _truncated(system: str, user: str) -> str:
        raise http.client.IncompleteRead(b"partial")

    env = generate_narration(bundle, _cfg(), transport=_truncated, cache=NarrationCache())
    assert env.status == "local_only"
    assert env.narration is None


def test_openai_payload_constrains_output_to_the_schema() -> None:
    # Constrained decoding forces a small local model to emit the exact
    # {claims, scenarios, candidate_facts} shape instead of parroting the bundle.
    cfg = ProviderConfig(provider="ollama", model="llama3.2", base_url="http://127.0.0.1:11434/v1")
    _url, _headers, body = build_openai_payload(cfg, None, "sys", "user")
    rf = body["response_format"]
    assert rf["type"] == "json_schema"
    schema = rf["json_schema"]["schema"]
    assert set(schema["required"]) == {"verdict", "claims", "scenarios", "candidate_facts"}
    assert schema["additionalProperties"] is False
    assert "background" not in schema["properties"]  # off unless opted in
    assert "research_notes" not in schema["properties"]  # off unless opted in

    bg = ProviderConfig(
        provider="ollama", model="llama3.2", base_url="http://127.0.0.1:11434/v1",
        allow_background=True,
    )
    _u, _h, body_bg = build_openai_payload(bg, None, "sys", "user")
    assert "background" in body_bg["response_format"]["json_schema"]["schema"]["properties"]


def test_grounded_schema_enumerates_valid_ids_when_supplied() -> None:
    # Constrained decoding enumerates the exact citation ids so the model cannot
    # invent a source or dump every id it sees.
    schema = ai_gateway._grounded_output_schema(
        False, source_ids=("engine:x", "pack:y"), number_ids=("prob_home", "prob_away")
    )
    claim = schema["properties"]["claims"]["items"]
    assert claim["properties"]["source_ids"]["items"]["enum"] == ["engine:x", "pack:y"]
    assert claim["properties"]["number_refs"]["items"]["enum"] == ["prob_home", "prob_away"]
    # With no ids supplied there is no enum (plain strings) — e.g. a bundle-less path.
    plain = ai_gateway._grounded_output_schema(False)
    assert "enum" not in plain["properties"]["claims"]["items"]["properties"]["source_ids"]["items"]


@pytest.mark.parametrize(
    "raw, expected",
    [("11.9B", 11.9), ("3.2B", 3.2), ("270M", 0.27), (None, None), ("weird", None)],
)
def test_parse_param_size(raw, expected) -> None:
    assert ai_gateway._parse_param_size(raw) == expected


def test_generate_narration_injects_bundle_ids_for_constrained_decoding(
    bundle: dict, monkeypatch
) -> None:
    # The transport should receive a config carrying this bundle's citation
    # allow-lists so decoding can enumerate them.
    seen = {}

    def capture(config):
        seen["source_ids"] = config.allowed_source_ids
        seen["number_ids"] = config.allowed_number_ids
        return _canned(_valid_response(bundle))

    monkeypatch.setattr(ai_gateway, "list_local_models", lambda config: ["llama3.2"])
    monkeypatch.setattr(ai_gateway, "make_transport", capture)
    generate_narration(bundle, resolve_provider({"provider": "ollama"}), cache=NarrationCache())
    assert seen["source_ids"] == tuple(s["source_id"] for s in bundle["sources"])
    assert "prob_home" in seen["number_ids"]


def test_openai_transport_falls_back_to_json_object_when_schema_rejected(monkeypatch) -> None:
    # An older OpenAI-compatible server may reject json_schema response_format.
    # The transport retries once with plain json_object rather than failing.
    import urllib.error

    seen: list[str] = []

    def fake_post(url, headers, body, timeout):
        seen.append(body["response_format"]["type"])
        if body["response_format"]["type"] == "json_schema":
            raise urllib.error.HTTPError(url, 400, "unsupported response_format", {}, None)
        content = '{"claims":[],"scenarios":[],"candidate_facts":[]}'
        return {"choices": [{"message": {"content": content}}]}

    monkeypatch.setattr(ai_gateway, "_post_json", fake_post)
    cfg = ProviderConfig(provider="llama_server", model="m", base_url="http://127.0.0.1:8080/v1")
    transport = ai_gateway.make_transport(cfg)
    out = transport("sys", "user")
    assert "claims" in out
    assert seen == ["json_schema", "json_object"]  # tried schema, then fell back


def test_cache_separates_prompt_context_and_candidate_fact_mode(bundle: dict) -> None:
    cache = NarrationCache()
    calls = {"n": 0}

    def transport(system: str, user: str) -> str:
        calls["n"] += 1
        return json.dumps(_valid_response(bundle))

    generate_narration(
        bundle, _cfg(untrusted_context="context A"), transport=transport, cache=cache
    )
    generate_narration(
        bundle, _cfg(untrusted_context="context B"), transport=transport, cache=cache
    )
    generate_narration(
        bundle,
        _cfg(untrusted_context="context B", allow_candidate_facts=True),
        transport=transport,
        cache=cache,
    )
    assert calls["n"] == 3


@pytest.mark.parametrize("error", [TypeError("bad shape"), IndexError("empty response")])
def test_malformed_provider_payload_fails_closed(bundle: dict, error: Exception) -> None:
    def malformed(system: str, user: str) -> str:
        raise error

    env = generate_narration(bundle, _cfg(), transport=malformed, cache=NarrationCache())
    assert env.status == "local_only"
    assert env.narration is None


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

    # A local provider pointed at a dead port: the model list probe fails, so the
    # endpoint reports an honest, actionable "unavailable" (no model reachable)
    # rather than the misleading "local_only" (which implies a model ran and its
    # output failed verification). Either way it never blocks or crashes.
    res = client.post(
        f"/api/v1/forecasts/{artifact_id}/narrative",
        json={"provider": "llama_server", "base_url": "http://127.0.0.1:9/v1", "timeout_s": 1},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "unavailable"
    assert body["reason"] and "local model" in body["reason"].lower()
    assert body["narration"] is None
    # The citation lookups travel with every response so the UI can resolve chips
    # regardless of AI status.
    assert body["sources"] and body["sources"][0]["kind"] == "engine"
    assert any(n["id"] == "prob_home" for n in body["numbers"])


def test_endpoint_unknown_artifact_is_404(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", tmp_path / "empty")
    client = TestClient(server_main.app)
    res = client.post("/api/v1/forecasts/fa_missing00/narrative", json={"provider": "off"})
    assert res.status_code == 404
