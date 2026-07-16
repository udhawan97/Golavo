"""Fail-closed construction and validation of untrusted candidate facts."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any

from golavo_core.resources import resource
from jsonschema import Draft202012Validator

from .capture import CanonicalDocument
from .policy import SourcePolicy
from .store import canonical, now_z


def _schema() -> dict[str, Any]:
    return json.loads(
        resource("docs", "contracts", "candidate_fact.schema.json").read_text("utf-8")
    )


def _fold(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _quote_span(text: str, value: str) -> tuple[str, int, int] | None:
    index = text.find(value)
    if index < 0:
        return None
    line_start = text.rfind("\n", 0, index) + 1
    line_end = text.find("\n", index)
    if line_end < 0:
        line_end = len(text)
    if line_end - line_start > 4000:
        value_end = index + len(value)
        line_start = max(line_start, index - 1000)
        line_end = min(line_end, max(value_end + 1000, line_start + 4000))
        line_start = max(line_start, line_end - 4000)
    return text[line_start:line_end], line_start, line_end


def candidate_digest(candidate: dict[str, Any]) -> str:
    """Digest every immutable candidate field; queue state is intentionally mutable."""
    material = {
        key: value
        for key, value in candidate.items()
        if key not in {"candidate_id", "state", "queued_proposal_id"}
    }
    return hashlib.sha256(canonical(material).encode("utf-8")).hexdigest()


def validate_stored_candidate(
    candidate: dict[str, Any],
    *,
    policy: SourcePolicy,
    namespace: str,
    capture: dict[str, Any],
) -> None:
    """Re-verify persisted untrusted bytes immediately before correction import."""
    Draft202012Validator(_schema()).validate(candidate)
    if candidate["candidate_id"] != "cf_" + candidate_digest(candidate):
        raise ValueError("candidate digest mismatch")
    source = candidate["source"]
    evidence = candidate["evidence"]
    if namespace != policy.license_namespace or source["license_namespace"] != namespace:
        raise ValueError("candidate license namespace mismatch")
    if (
        source["source_id"] != policy.source_id
        or source["license"] != policy.license
        or source["license_url"] != policy.license_url
        or source["attribution"] != policy.attribution
        or source["modifications"] != "normalized plaintext excerpt"
        or source["retrieved_at_utc"] != capture["retrieved_at_utc"]
        or source["revision_id"] != capture.get("revision_id")
    ):
        raise ValueError("candidate source policy mismatch")
    if (
        capture["capture_id"] != evidence["capture_id"]
        or capture["source_id"] != policy.source_id
        or capture["license_namespace"] != namespace
        or capture["raw_sha256"] != evidence["raw_sha256"]
        or capture["canonical_text_sha256"] != evidence["canonical_text_sha256"]
    ):
        raise ValueError("candidate capture receipt mismatch")
    start = evidence["quote_start"]
    end = evidence["quote_end"]
    quote = evidence["exact_quote"]
    if capture["canonical_text"][start:end] != quote:
        raise ValueError("candidate quote mismatch")
    if candidate["correction_type"] not in policy.permitted_fact_types:
        raise ValueError("candidate field is outside source policy")
    proposed = candidate["proposed"]
    values = (
        [proposed.get("alias")]
        if candidate["correction_type"] == "team_alias"
        else [proposed.get(key) for key in ("venue_name", "city", "country")]
    )
    if not values or any(
        not isinstance(value, str) or _fold(value) not in _fold(quote) for value in values
    ):
        raise ValueError("candidate value is not present in its quote")


def _candidate(
    *,
    run_id: str,
    match: dict[str, Any],
    index_fingerprint: str,
    capture: dict[str, Any],
    policy: SourcePolicy,
    document: CanonicalDocument,
    correction_type: str,
    proposed: dict[str, Any],
    quote: str,
    quote_start: int,
    quote_end: int,
    parser_locator: str | None,
    extractor_kind: str,
    extractor_id: str,
    extractor_version: str,
    model: str | None = None,
    prompt_version: str | None = None,
) -> dict[str, Any]:
    output_sha = hashlib.sha256(canonical(proposed).encode()).hexdigest()
    payload = {
        "schema_version": "0.1.0",
        "candidate_id": "cf_" + "0" * 64,
        "run_id": run_id,
        "authority": "untrusted_candidate",
        "state": "review_required",
        "correction_type": correction_type,
        "target": {
            "match_id": match["match_id"],
            "entity_id": document.parsed.get("qid"),
            "upstream_record_key": match.get("upstream_fixture_key"),
            "index_fingerprint": index_fingerprint,
        },
        "proposed": proposed,
        "source": {
            "source_id": policy.source_id,
            "canonical_url": document.document_url,
            "retrieved_at_utc": capture["retrieved_at_utc"],
            "revision_id": capture.get("revision_id"),
            "license": policy.license,
            "license_url": policy.license_url,
            "attribution": policy.attribution,
            "modifications": "normalized plaintext excerpt",
            "license_namespace": policy.license_namespace,
        },
        "evidence": {
            "capture_id": capture["capture_id"],
            "raw_sha256": capture["raw_sha256"],
            "canonical_text_sha256": capture["canonical_text_sha256"],
            "exact_quote": quote,
            "quote_start": quote_start,
            "quote_end": quote_end,
            "parser_locator": parser_locator,
        },
        "extractor": {
            "kind": extractor_kind,
            "id": extractor_id,
            "version": extractor_version,
            "model": model,
            "prompt_version": prompt_version,
            "output_sha256": output_sha,
        },
        "validation": {
            "quote_match": document.text[quote_start:quote_end] == quote,
            "value_match": True,
            "identity_match": correction_type == "team_alias",
            "policy_match": correction_type in policy.permitted_fact_types,
            "conflict_state": "none" if correction_type == "team_alias" else "unknown",
            "reason_codes": [] if correction_type == "team_alias" else ["identity_review_required"],
        },
        "effects": {
            "authoritative_override": False,
            "forecast_input": False,
            "model_input": False,
            "settlement_input": False,
            "calibration_input": False,
        },
        "queued_proposal_id": None,
        "created_at_utc": now_z(),
    }
    payload["candidate_id"] = "cf_" + candidate_digest(payload)
    Draft202012Validator(_schema()).validate(payload)
    return payload


def deterministic_candidates(
    *,
    run_id: str,
    match: dict[str, Any],
    index_fingerprint: str,
    capture: dict[str, Any],
    policy: SourcePolicy,
    document: CanonicalDocument,
) -> list[dict[str, Any]]:
    if policy.source_id != "wikidata" or "team_alias" not in policy.permitted_fact_types:
        return []
    label = document.parsed.get("label")
    aliases = document.parsed.get("aliases")
    if not isinstance(label, str) or not isinstance(aliases, list):
        return []
    names = [label, *(value for value in aliases if isinstance(value, str))]
    exact_teams = [str(match.get("home_team") or ""), str(match.get("away_team") or "")]
    canonical_team = next(
        (
            team
            for team in exact_teams
            if team and any(_fold(team) == _fold(name) for name in names)
        ),
        None,
    )
    if canonical_team is None:
        return []
    result = []
    for alias in names:
        if _fold(alias) == _fold(canonical_team):
            continue
        span = _quote_span(document.text, alias)
        if span is None:
            continue
        quote, start, end = span
        proposed = {
            "alias": alias,
            "canonical_team": canonical_team,
            "scope": {
                "source_id": policy.source_id,
                "competition": match.get("competition"),
                "country": match.get("country"),
            },
        }
        result.append(
            _candidate(
                run_id=run_id,
                match=match,
                index_fingerprint=index_fingerprint,
                capture=capture,
                policy=policy,
                document=document,
                correction_type="team_alias",
                proposed=proposed,
                quote=quote,
                quote_start=start,
                quote_end=end,
                parser_locator=f"/aliases/en/{len(result)}",
                extractor_kind="deterministic",
                extractor_id=policy.parser_id,
                extractor_version=policy.parser_version,
            )
        )
    return result[:4]


def ai_candidate(
    *,
    item: dict[str, Any],
    run_id: str,
    match: dict[str, Any],
    index_fingerprint: str,
    capture: dict[str, Any],
    policy: SourcePolicy,
    document: CanonicalDocument,
    model: str,
    prompt_version: str,
) -> dict[str, Any] | None:
    correction_type = item.get("correction_type")
    proposed = item.get("proposed")
    quote = item.get("quote")
    if (
        correction_type not in {"team_alias", "venue"}
        or correction_type not in policy.permitted_fact_types
    ):
        return None
    if not isinstance(proposed, dict) or not isinstance(quote, str) or not quote:
        return None
    start = document.text.find(quote)
    if start < 0:
        return None
    values: list[str]
    if correction_type == "team_alias":
        canonical_team = proposed.get("canonical_team")
        alias = proposed.get("alias")
        if canonical_team not in {match.get("home_team"), match.get("away_team")}:
            return None
        proposed = {
            "alias": alias,
            "canonical_team": canonical_team,
            "scope": {
                "source_id": policy.source_id,
                "competition": match.get("competition"),
                "country": match.get("country"),
            },
        }
        values = [alias] if isinstance(alias, str) else []
    else:
        values = [proposed.get(key) for key in ("venue_name", "city", "country")]
    if not values or any(
        not isinstance(value, str) or _fold(value) not in _fold(quote) for value in values
    ):
        return None
    return _candidate(
        run_id=run_id,
        match=match,
        index_fingerprint=index_fingerprint,
        capture=capture,
        policy=policy,
        document=document,
        correction_type=correction_type,
        proposed=proposed,
        quote=quote,
        quote_start=start,
        quote_end=start + len(quote),
        parser_locator=None,
        extractor_kind="local_ai",
        extractor_id="local-evidence-extractor",
        extractor_version="1",
        model=model,
        prompt_version=prompt_version,
    )
