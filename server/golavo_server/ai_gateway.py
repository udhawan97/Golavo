"""The AI gateway — the ONLY module in Golavo that talks to an LLM.

Everything safety-critical lives in ``golavo_core.ai`` (pure, network-free) and
``golavo_core.evidence`` (the deterministic bundle). This module wires a provider
call around those guards and always fails closed:

    off        -> AI is disabled; return immediately, no call.
    unavailable-> provider selected but not usable (no key, cost cap, bad config).
    local_only -> a call was attempted but its output failed the guards (or the
                  provider was unreachable) after one retry; the app shows the
                  deterministic forecast alone.
    ok         -> a guard-validated narration, stamped with provenance.

The engine owns every number. This module can only ever pass a validated
narration through or drop it; it can never let an unsupported number reach the
user. Provider config is injected (never hardcoded); the transport is injectable
so CI exercises the whole pipeline with canned and adversarial responses and no
live model. API keys are read from the environment or the OS keychain, used only
in a request header, and never logged, cached, or returned.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import math
import os
import re
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any
from urllib.parse import urlparse

from golavo_core.ai import (
    BACKGROUND_ADDENDUM,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
    review_narration,
)
from golavo_core.ai.sanitize import sanitize_untrusted

# provider -> whether it is a local (free, keyless) or cloud (BYOK) endpoint.
LOCAL_PROVIDERS = ("ollama", "llama_server")
CLOUD_PROVIDERS = ("openai", "anthropic")
KNOWN_PROVIDERS = ("off", *LOCAL_PROVIDERS, *CLOUD_PROVIDERS)

_DEFAULT_BASE_URLS = {
    "ollama": "http://localhost:11434/v1",
    "llama_server": "http://127.0.0.1:8080/v1",
    "openai": "https://api.openai.com/v1",
}
_DEFAULT_MODELS = {
    "ollama": "llama3.1",
    "llama_server": "local-model",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
}
_ENV_KEYS = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
_ENV_BASE_URLS = {"ollama": "OLLAMA_BASE_URL", "llama_server": "LLAMACPP_BASE_URL"}
# Optional pin for the local model to use, for machines with several pulled.
# When unset, a local provider auto-resolves to whatever model is installed.
_ENV_MODELS = {"ollama": "GOLAVO_OLLAMA_MODEL", "llama_server": "GOLAVO_LLAMACPP_MODEL"}

# A transport takes (system_prompt, user_prompt) and returns the model's raw
# text. It never receives an API key — the real transports add the key to a
# request header internally, so an injected/test transport cannot see or log one.
Transport = Callable[[str, str], str]

_THINK_RE = re.compile(r"(?is)<think>.*?</think>")
_FENCE_RE = re.compile(r"(?is)```(?:json)?\s*(.*?)\s*```")


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    model: str
    base_url: str | None
    allow_candidate_facts: bool = False
    allow_background: bool = False
    timeout_s: float = 30.0
    untrusted_context: str | None = None

    @property
    def is_off(self) -> bool:
        return self.provider == "off"

    @property
    def is_cloud(self) -> bool:
        return self.provider in CLOUD_PROVIDERS

    def redacted(self) -> dict[str, Any]:
        """A log/response-safe view. No secret is ever stored here to begin with."""
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "allow_candidate_facts": self.allow_candidate_facts,
            "allow_background": self.allow_background,
        }


def resolve_provider(config: dict[str, Any] | None) -> ProviderConfig:
    """Build a ProviderConfig from an untrusted request body. Defaults to off."""
    config = config or {}
    provider = str(config.get("provider", "off")).lower()
    if provider not in KNOWN_PROVIDERS:
        raise ValueError(f"unknown provider {provider!r}; expected one of {KNOWN_PROVIDERS}")
    env_model = os.environ.get(_ENV_MODELS[provider]) if provider in _ENV_MODELS else None
    model = str(
        config.get("model") or env_model or _DEFAULT_MODELS.get(provider, "local-model")
    ).strip()
    if not model or len(model) > 120:
        raise ValueError("model must contain 1-120 characters")
    requested_base_url = config.get("base_url")
    if requested_base_url and provider in CLOUD_PROVIDERS:
        raise ValueError("base_url overrides are allowed only for local providers")
    base_url = requested_base_url
    if not base_url and provider in _ENV_BASE_URLS:
        base_url = os.environ.get(_ENV_BASE_URLS[provider])
    if not base_url:
        base_url = _DEFAULT_BASE_URLS.get(provider)
    if provider in LOCAL_PROVIDERS:
        base_url = _validated_loopback_url(base_url)
    # Local models run cold and free: the first call also loads the weights, which
    # a small default would time out before generation even starts. Give them a
    # generous default; cloud stays snappy. An explicit timeout_s always wins.
    default_timeout = 90.0 if provider in LOCAL_PROVIDERS else 30.0
    try:
        timeout_s = float(config.get("timeout_s", default_timeout))
    except (TypeError, ValueError) as exc:
        raise ValueError("timeout_s must be a number between 1 and 120") from exc
    if not math.isfinite(timeout_s) or not 1 <= timeout_s <= 120:
        raise ValueError("timeout_s must be a number between 1 and 120")
    return ProviderConfig(
        provider=provider,
        model=model,
        base_url=base_url,
        allow_candidate_facts=bool(config.get("allow_candidate_facts", False)),
        allow_background=bool(config.get("allow_background", False)),
        timeout_s=timeout_s,
        untrusted_context=config.get("untrusted_context"),
    )


def _validated_loopback_url(value: Any) -> str:
    """Accept only explicit loopback HTTP(S) endpoints for local providers."""
    url = str(value or "").strip()
    parsed = urlparse(url)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("local provider base_url must be an HTTP(S) loopback URL")
    return url.rstrip("/")


@dataclass
class NarrationEnvelope:
    """What the endpoint returns. Never carries a key or raw model text."""

    status: str  # ok | disabled | unavailable | local_only
    provider: str
    model: str
    prompt_version: str
    bundle_hash: str
    narration: dict[str, Any] | None = None
    cached: bool = False
    reason: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "provider": self.provider,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "bundle_hash": self.bundle_hash,
            "narration": self.narration,
            "cached": self.cached,
            "reason": self.reason,
            "notes": self.notes,
        }


# --- API key loading ---------------------------------------------------------

def load_api_key(provider: str) -> str | None:
    """Return the BYOK key for a cloud provider, or None. Never logged.

    Environment variable first (dev/source mode); then the macOS keychain, where
    the packaged desktop app stores it (`security add-generic-password -s
    golavo-<provider> -a golavo -w <key>`). Any lookup failure yields None.
    """
    env_name = _ENV_KEYS.get(provider)
    if env_name and os.environ.get(env_name):
        return os.environ[env_name]
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", f"golavo-{provider}", "-a", "golavo", "-w"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    key = result.stdout.strip()
    return key or None


# --- Transports (real network calls; injectable for tests) -------------------

def build_openai_payload(
    config: ProviderConfig, key: str | None, system: str, user: str
) -> tuple[str, dict[str, str], dict[str, Any]]:
    """(url, headers, body) for an OpenAI-compatible chat completion.

    The key goes ONLY in the Authorization header — never in the body — so it
    cannot leak into the prompt, the cache, or a log of the request body.
    """
    url = f"{(config.base_url or '').rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    return url, headers, body


def build_anthropic_payload(
    config: ProviderConfig, key: str | None, system: str, user: str
) -> tuple[str, dict[str, str], dict[str, Any]]:
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    if key:
        headers["x-api-key"] = key
    body: dict[str, Any] = {
        "model": config.model,
        "max_tokens": 1024,
        "temperature": 0,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    return url, headers, body


def _post_json(
    url: str, headers: dict[str, str], body: dict[str, Any], timeout: float
) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (loopback/BYOK only)
        return json.loads(response.read().decode("utf-8"))


def make_transport(config: ProviderConfig) -> Transport | None:
    """Build the real transport for ``config``; None if a required key is absent."""
    key = load_api_key(config.provider) if config.is_cloud else None
    if config.is_cloud and not key:
        return None

    if config.provider == "anthropic":
        def transport(system: str, user: str) -> str:
            url, headers, body = build_anthropic_payload(config, key, system, user)
            payload = _post_json(url, headers, body, config.timeout_s)
            return payload["content"][0]["text"]
    else:
        def transport(system: str, user: str) -> str:
            url, headers, body = build_openai_payload(config, key, system, user)
            payload = _post_json(url, headers, body, config.timeout_s)
            return payload["choices"][0]["message"]["content"]

    return transport


# --- Local model discovery ---------------------------------------------------
# A local provider (Ollama, llama.cpp) is keyless and free, but the user may not
# have pulled the model this app defaults to. Rather than fail every attempt with
# a "model not found" the user cannot see, we ask the local server which models
# it actually has and target one of those. Both servers expose the
# OpenAI-compatible ``GET /v1/models``. Any failure yields an empty list, which
# the caller turns into an honest "no local model" message.

# Substrings that mark a model as embedding-only (no chat completion). Picking
# one as the fallback would produce garbage the guards reject, stranding the user
# in a "local_only" loop; treating it as absent yields an honest "pull a model".
_EMBEDDING_HINTS = ("embed", "bge", "nomic-embed", "minilm", "e5-", "gte-")


def list_local_models(config: ProviderConfig) -> list[str]:
    """Model ids installed on a local provider; ``[]`` on any failure."""
    url = f"{(config.base_url or '').rstrip('/')}/models"
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=min(config.timeout_s, 5.0)) as response:  # noqa: S310 (loopback only)
            payload = json.loads(response.read().decode("utf-8"))
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            return []
        return [str(m["id"]) for m in data if isinstance(m, dict) and m.get("id")]
    except (
        urllib.error.URLError,
        http.client.HTTPException,
        TimeoutError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
    ):
        return []


def usable_local_models(installed: list[str]) -> list[str]:
    """Installed models a chat completion can actually run — embedding-only models
    removed. Empty means "nothing usable is installed", which the caller reports
    honestly rather than trying (and failing) to narrate with an embedder."""
    return [m for m in installed if not any(h in m.lower() for h in _EMBEDDING_HINTS)]


def _family_root(model: str) -> str:
    """The model family without a tag or minor version: ``llama3.1:q4`` -> ``llama3``."""
    base = model.split(":", 1)[0]
    return re.sub(r"\.\d+$", "", base)


def pick_local_model(requested: str, installed: list[str]) -> str:
    """Choose an installed model for a local run, preferring the requested one.

    In order: an exact match; a model sharing the requested base name (a
    ``llama3.1`` default happily uses an installed ``llama3.1:latest``); a model
    in the same family (``llama3.1`` default prefers an installed ``llama3.2``
    over an unrelated one, so the app's own default family wins over, say, a
    heavyweight the user also happens to have pulled); finally the first installed
    model, so the app still works with whatever is present.
    """
    if requested in installed:
        return requested
    base = requested.split(":", 1)[0]
    for name in installed:
        if name.split(":", 1)[0] == base:
            return name
    root = _family_root(requested)
    for name in installed:
        if _family_root(name) == root:
            return name
    return installed[0]


# --- JSON extraction ---------------------------------------------------------

def extract_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort extraction of the first balanced JSON object from model text.

    Strips <think> blocks and code fences, then scans for one brace-balanced
    object. Returns None if nothing parses — the caller treats that as a failed
    attempt (retry, then local-only fallback)."""
    if not isinstance(text, str):
        return None
    cleaned = _THINK_RE.sub(" ", text)
    fence = _FENCE_RE.search(cleaned)
    if fence:
        cleaned = fence.group(1)
    start = cleaned.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(cleaned)):
        char = cleaned[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start : index + 1])
                except json.JSONDecodeError:
                    return None
    return None


# --- Caching -----------------------------------------------------------------

class NarrationCache:
    """In-memory cache keyed by every input that can affect a narration.

    Keyed by the REQUESTED model (as the user asked, before local auto-resolution),
    so a cached read is served even after the local model server is later stopped —
    the cache read never depends on a live ``/v1/models`` probe. The model that
    actually produced the narration is stored alongside it so the served envelope
    stamps the real model, not the requested default.
    """

    def __init__(self) -> None:
        self._store: dict[tuple[str, str, str, str, bool, bool, str], dict[str, Any]] = {}

    @staticmethod
    def key(bundle_hash: str, config: ProviderConfig) -> tuple[str, str, str, str, bool, bool, str]:
        context = sanitize_untrusted(config.untrusted_context or "")
        context_hash = hashlib.sha256(context.encode("utf-8")).hexdigest() if context else ""
        # allow_background is part of the key: a no-background cached read must
        # never be served to a background-enabled request (and vice versa).
        return (
            bundle_hash,
            config.provider,
            config.model,
            PROMPT_VERSION,
            config.allow_candidate_facts,
            config.allow_background,
            context_hash,
        )

    def get(self, bundle_hash: str, config: ProviderConfig) -> dict[str, Any] | None:
        """Return ``{"narration": ..., "model": ...}`` for a hit, else None."""
        return self._store.get(self.key(bundle_hash, config))

    def set(
        self,
        bundle_hash: str,
        config: ProviderConfig,
        narration: dict[str, Any],
        model: str,
    ) -> None:
        self._store[self.key(bundle_hash, config)] = {"narration": narration, "model": model}


_CACHE = NarrationCache()

MAX_ATTEMPTS = 2  # initial attempt + one retry, then local-only fallback.


def generate_narration(
    bundle: dict[str, Any],
    config: ProviderConfig,
    *,
    transport: Transport | None = None,
    cache: NarrationCache | None = None,
    refresh: bool = False,
) -> NarrationEnvelope:
    """Produce a guard-validated narration for ``bundle``, or a safe fallback.

    ``transport`` is injected in tests; in production it is built from ``config``.
    ``refresh`` skips the cache READ (a user-requested regeneration) but still
    writes the new validated narration back, so a refresh never weakens a guard —
    it only re-runs the same fail-closed pipeline. Never raises for
    provider/transport failures — those become an ``unavailable`` or
    ``local_only`` envelope so the caller (and UI) always has the forecast.
    """
    bundle_hash = bundle["bundle_hash"]
    cache = cache if cache is not None else _CACHE
    # ``config`` is the REQUESTED config (default/requested model); it keys the
    # cache and is the default stamp. Local auto-resolution swaps the model only
    # for the actual generation, into ``run_config``.

    def envelope(status: str, *, model: str | None = None, **kwargs: Any) -> NarrationEnvelope:
        return NarrationEnvelope(
            status=status,
            provider=config.provider,
            model=model or config.model,
            prompt_version=PROMPT_VERSION,
            bundle_hash=bundle_hash,
            **kwargs,
        )

    if config.is_off:
        return envelope("disabled", reason="AI is turned off; showing the local forecast only.")

    # Cache read comes BEFORE any live probe, keyed by the requested model: a
    # narration generated earlier is still served even if the local model server
    # has since been stopped. The stored model is what actually produced it.
    if not refresh:
        cached = cache.get(bundle_hash, config)
        if cached is not None:
            return envelope("ok", narration=cached["narration"], model=cached["model"], cached=True)

    # Local providers: target a model the server actually has, and fail fast with
    # an honest, actionable message when it has none — otherwise a missing default
    # model surfaces to the user as an unexplained "could not be verified" loop.
    # Only in the production path: an injected transport (tests) brings its own
    # canned output and must not trigger a live probe.
    run_config = config
    if transport is None and config.provider in LOCAL_PROVIDERS:
        usable = usable_local_models(list_local_models(config))
        if not usable:
            return envelope(
                "unavailable",
                reason="No local model is reachable. Start Ollama (or llama.cpp) and "
                "pull at least one model, then try again.",
            )
        run_config = replace(config, model=pick_local_model(config.model, usable))

    if transport is None:
        transport = make_transport(run_config)
    if transport is None:
        return envelope(
            "unavailable",
            reason="No API key found for this provider. Add one to use it, or keep AI off.",
        )

    # The background addendum is appended ONLY when the user opted in; it relaxes
    # nothing about the grounded rules. PROMPT_VERSION already covers the change,
    # and allow_background is in the cache key, so a background run never reuses a
    # grounded-only cached narration.
    system = SYSTEM_PROMPT + (BACKGROUND_ADDENDUM if run_config.allow_background else "")
    user = build_user_prompt(bundle, run_config.untrusted_context)

    reasons: list[str] = []
    reached_provider = False  # did any attempt get a response back from the model?
    for _ in range(MAX_ATTEMPTS):
        try:
            raw_text = transport(system, user)
        except (
            urllib.error.URLError,
            http.client.HTTPException,
            TimeoutError,
            OSError,
            KeyError,
            ValueError,
            TypeError,
            IndexError,
        ) as exc:
            # Never surface provider internals or anything that might echo a key.
            reasons.append(f"provider call failed ({type(exc).__name__})")
            continue
        reached_provider = True
        raw = extract_json_object(raw_text)
        if raw is None:
            reasons.append("model output was not valid JSON")
            continue
        review = review_narration(
            raw,
            bundle,
            allow_candidate_facts=run_config.allow_candidate_facts,
            allow_background=run_config.allow_background,
        )
        if review.accepted and review.narration is not None:
            cache.set(bundle_hash, config, review.narration, model=run_config.model)
            return envelope(
                "ok", model=run_config.model, narration=review.narration, notes=review.dropped
            )
        reasons.append("; ".join(review.rejections) or "narration failed review")

    # Honest reason: distinguish "never reached the model" (unreachable/timed out)
    # from "the model answered but its output failed the guards".
    if reached_provider:
        reason = (
            "AI output could not be verified against the sealed numbers; "
            "showing the local forecast only."
        )
    else:
        reason = (
            "The AI provider could not be reached or timed out; "
            "showing the local forecast only."
        )
    return envelope("local_only", model=run_config.model, reason=reason, notes=reasons)
