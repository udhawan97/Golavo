"""Foreground-only discovery, capture and extraction orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from . import ai_extract, capture, extract, store, wikidata, wikipedia
from .fetch import Fetch, FetchResponse, ResearchFetchError, fetch_response, research_disabled
from .policy import ResearchPolicyError, canonicalize_url

Cancel = Callable[[], bool]
Fetcher = Callable[..., FetchResponse]


@dataclass(frozen=True)
class ResearchSource:
    source_id: str
    provider: str
    title: str
    url: str
    text: str


@dataclass
class ResearchResult:
    """Legacy narration envelope. Phase 7 never performs acquisition through it."""

    sources: list[ResearchSource] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    planned: int = 0

    def corpus(self) -> dict[str, str]:
        return {source.url: source.text for source in self.sources}

    def prompt_sources(self) -> list[dict[str, Any]]:
        return []

    def envelope_sources(self) -> list[dict[str, Any]]:
        return []


def plan_queries(bundle: dict[str, Any], depth: str = "fast") -> list[str]:
    match = bundle.get("match", {})
    home = str(match.get("home_team") or "").strip()
    away = str(match.get("away_team") or "").strip()
    competition = str(match.get("competition") or "").strip()
    values = [f"{home} {away} {competition}".strip(), home, away]
    return list(dict.fromkeys(value for value in values if value))[: (3 if depth == "deep" else 1)]


def run_research(*_args: Any, **_kwargs: Any) -> ResearchResult:
    """Compatibility path: AI narration no longer initiates network research."""
    return ResearchResult(
        notes=[
            "Start a Match research run and select sources before asking AI to use web evidence."
        ],
        planned=0,
    )


def discover(
    query: str,
    *,
    provider: str = "wikimedia",
    limit: int = 6,
    fetch: Fetch | None = None,
) -> list[dict[str, Any]]:
    if research_disabled():
        return []
    cleaned = " ".join(query.split())[:240]
    if not cleaned:
        return []
    rows: list[dict[str, Any]] = []
    failures: list[ResearchFetchError] = []
    if provider == "wikimedia":
        try:
            rows.extend(
                wikipedia.discovery(cleaned, limit=min(limit, 3), fetch=fetch, fail_soft=False)
            )
        except ResearchFetchError as exc:
            failures.append(exc)
        try:
            rows.extend(wikidata.search(cleaned, limit=min(limit, 3), fetch=fetch, fail_soft=False))
        except ResearchFetchError as exc:
            failures.append(exc)
    else:
        raise ResearchPolicyError("discovery_provider_not_allowed", "unknown discovery provider")
    result = []
    for row in rows:
        try:
            url, policy = canonicalize_url(str(row["url"]), source_id=str(row["source_id"]))
        except ResearchPolicyError:
            continue
        result.append(
            {**row, "url": url, "permitted": True, "license_namespace": policy.license_namespace}
        )
    if not result and failures:
        raise failures[0]
    return result[:limit]


def run_capture(
    root: Any,
    *,
    match: dict[str, Any],
    index_fingerprint: str,
    selected_urls: list[str],
    provider_config: dict[str, Any] | None = None,
    cancel: Cancel | None = None,
    fetcher: Fetcher = fetch_response,
) -> dict[str, Any]:
    canonical_urls: list[str] = []
    for url in selected_urls:
        canonical_url, _policy = canonicalize_url(url)
        canonical_urls.append(canonical_url)
    run = store.create_run(
        root,
        match_id=str(match["match_id"]),
        index_fingerprint=index_fingerprint,
        selected_urls=canonical_urls,
        allow_local_ai=provider_config is not None,
    )
    return execute_run(
        root,
        run=run,
        match=match,
        provider_config=provider_config,
        cancel=cancel,
        fetcher=fetcher,
    )


def execute_run(
    root: Any,
    *,
    run: dict[str, Any],
    match: dict[str, Any],
    provider_config: dict[str, Any] | None = None,
    cancel: Cancel | None = None,
    fetcher: Fetcher = fetch_response,
) -> dict[str, Any]:
    canonical_urls = list(run["selected_urls"])
    index_fingerprint = str(run["index_fingerprint"])
    counts = dict(run["counts"])
    reasons: list[str] = []
    store.update_run(root, run["run_id"], state="fetching", counts=counts)
    for url in canonical_urls:
        if cancel and cancel():
            return store.update_run(
                root,
                run["run_id"],
                state="cancelled",
                counts=counts,
                reason_codes=[*reasons, "cancelled"],
            )
        try:
            canonical_url, policy = canonicalize_url(url)
            response = fetcher(canonical_url, source_id=policy.source_id, cancel=cancel)
            document = capture.canonical_document(response, policy)
            if cancel and cancel():
                return store.update_run(
                    root,
                    run["run_id"],
                    state="cancelled",
                    counts=counts,
                    reason_codes=[*reasons, "cancelled"],
                )
            receipt = capture.capture_payload(
                run_id=run["run_id"], response=response, policy=policy, document=document
            )
            store.add_capture(root, receipt, response.body)
            counts["captured"] += 1
            current = store.update_run(
                root, run["run_id"], state="captured", counts=counts, reason_codes=reasons
            )
            if current["state"] == "cancelled" or (cancel and cancel()):
                return store.update_run(
                    root,
                    run["run_id"],
                    state="cancelled",
                    counts=counts,
                    reason_codes=[*reasons, "cancelled"],
                )
            store.update_run(
                root, run["run_id"], state="extracting", counts=counts, reason_codes=reasons
            )
            candidates = extract.deterministic_candidates(
                run_id=run["run_id"],
                match=match,
                index_fingerprint=index_fingerprint,
                capture=receipt,
                policy=policy,
                document=document,
            )
            if provider_config is not None and policy.ai_fallback and not candidates:
                try:
                    items, model, prompt_version = ai_extract.extract(
                        provider_config=provider_config,
                        match=match,
                        canonical_text=document.text,
                        cancel=cancel,
                    )
                    for item in items:
                        candidate = extract.ai_candidate(
                            item=item,
                            run_id=run["run_id"],
                            match=match,
                            index_fingerprint=index_fingerprint,
                            capture=receipt,
                            policy=policy,
                            document=document,
                            model=model,
                            prompt_version=prompt_version,
                        )
                        if candidate is not None:
                            candidates.append(candidate)
                except ai_extract.LocalExtractionError as exc:
                    if exc.reason_code == "cancelled":
                        return store.update_run(
                            root,
                            run["run_id"],
                            state="cancelled",
                            counts=counts,
                            reason_codes=[*reasons, "cancelled"],
                        )
                    reasons.append(exc.reason_code)
            seen: set[str] = set()
            for candidate in candidates:
                if candidate["candidate_id"] in seen:
                    continue
                seen.add(candidate["candidate_id"])
                _saved, created = store.add_candidate(root, policy.license_namespace, candidate)
                if created:
                    counts["candidates"] += 1
            store.update_run(
                root, run["run_id"], state="fetching", counts=counts, reason_codes=reasons
            )
        except (ResearchFetchError, ResearchPolicyError, capture.CaptureError) as exc:
            if getattr(exc, "reason_code", None) == "cancelled":
                return store.update_run(
                    root,
                    run["run_id"],
                    state="cancelled",
                    counts=counts,
                    reason_codes=[*reasons, "cancelled"],
                )
            counts["failed"] += 1
            reasons.append(getattr(exc, "reason_code", "capture_failed"))
    if cancel and cancel():
        return store.update_run(
            root,
            run["run_id"],
            state="cancelled",
            counts=counts,
            reason_codes=[*reasons, "cancelled"],
        )
    offline_reasons = {"dns_failed", "dns_empty", "network_failed", "unsafe_address"}
    if counts["captured"] == 0 and reasons and set(reasons).issubset(offline_reasons):
        state = "offline"
    elif counts["captured"] == 0:
        state = "failed"
    elif counts["failed"]:
        state = "partial"
    else:
        state = "candidates_ready"
    return store.update_run(root, run["run_id"], state=state, counts=counts, reason_codes=reasons)
