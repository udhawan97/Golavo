"""Registry-owned source, license and export policy for local corrections."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from golavo_core.resources import resource

KNOWN_NAMESPACES = (
    "core-cc0",
    "enrichment-cc0",
    "enrichment-public-domain",
    "enrichment-cc-by-4.0",
    "overlay-odbl-1.0",
    "quarantine-unknown",
)
EXPORTABLE_NAMESPACES = {
    "core-cc0",
    "enrichment-cc0",
    "enrichment-public-domain",
    "enrichment-cc-by-4.0",
}
CORRECTION_TYPES = {
    "missing_fixture",
    "kickoff_time",
    "team_alias",
    "venue",
    "final_score",
}
_HOST_RE = re.compile(r"^[A-Za-z0-9.-]+$")
_SECRET_QUERY_RE = re.compile(r"(?:token|secret|key|auth|password)=", re.IGNORECASE)


class CorrectionPolicyError(ValueError):
    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(detail)
        self.reason_code = reason_code
        self.detail = detail


@lru_cache(maxsize=1)
def source_catalog() -> dict[str, dict[str, Any]]:
    payload = json.loads(resource("data", "sources", "registry.json").read_text(encoding="utf-8"))
    return {str(item["source_id"]): item for item in payload["sources"]}


def reset_cache() -> None:
    source_catalog.cache_clear()


def policy_for(source_id: str | None) -> dict[str, Any] | None:
    if not source_id:
        return None
    source = source_catalog().get(source_id)
    policy = source.get("corrections") if source else None
    if not isinstance(policy, dict) or policy.get("enabled") is not True:
        return None
    return {**policy, "source": source}


def namespace_for(source_id: str | None) -> str:
    policy = policy_for(source_id)
    return str(policy["license_namespace"]) if policy else "quarantine-unknown"


def validate_type(source_id: str | None, correction_type: str) -> None:
    if correction_type not in CORRECTION_TYPES:
        raise CorrectionPolicyError("unknown_correction_type", "unsupported correction type")
    policy = policy_for(source_id)
    if policy is None:
        raise CorrectionPolicyError(
            "source_unregistered", "the source is not registered for correction review"
        )
    if correction_type not in set(policy["allowed_types"]):
        raise CorrectionPolicyError(
            "field_not_allowed", "this source is not approved for that correction type"
        )


def canonical_evidence_url(source_id: str | None, value: str) -> tuple[str, str]:
    try:
        parsed = urlsplit(value.strip())
    except ValueError as exc:
        raise CorrectionPolicyError("invalid_source_url", "source URL is invalid") from exc
    host = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme.casefold() != "https" or not host or not _HOST_RE.fullmatch(host):
        raise CorrectionPolicyError(
            "invalid_source_url", "promotable evidence requires a normal HTTPS URL"
        )
    if parsed.username or parsed.password:
        raise CorrectionPolicyError(
            "source_url_contains_credentials", "source URLs cannot contain credentials"
        )
    if parsed.query and _SECRET_QUERY_RE.search(parsed.query):
        raise CorrectionPolicyError(
            "source_url_contains_secret", "source URL appears to contain a secret"
        )
    if parsed.query:
        raise CorrectionPolicyError(
            "source_url_query_not_allowed",
            "evidence URLs cannot retain query parameters; use the public canonical page URL",
        )
    policy = policy_for(source_id)
    if policy is not None and host not in {
        str(item).casefold() for item in policy["evidence_hosts"]
    }:
        raise CorrectionPolicyError(
            "source_host_not_allowed", f"{host} is not an evidence host for {source_id}"
        )
    # Fragments are browser-only and can hide visually deceptive variants. Query
    # strings are rejected above so a copied export cannot leak a signed URL.
    canonical = urlunsplit(("https", host, parsed.path or "/", "", ""))
    return canonical, host


def can_export(source_id: str | None) -> bool:
    policy = policy_for(source_id)
    return bool(
        policy
        and policy.get("redistributable_export") is True
        and policy.get("license_namespace") in EXPORTABLE_NAMESPACES
    )


def public_source(source_id: str) -> dict[str, Any]:
    policy = policy_for(source_id)
    if policy is None:
        raise CorrectionPolicyError("source_unregistered", "source is not registered")
    source = policy["source"]
    return {
        "source_id": source_id,
        "name": source["name"],
        "license": source["license"],
        "license_url": source.get("license_url"),
        "attribution": source.get("attribution"),
        "license_namespace": policy["license_namespace"],
        "allowed_types": list(policy["allowed_types"]),
        "redistributable_export": bool(policy["redistributable_export"]),
        "contribution_url": policy["contribution_url"],
    }


def capabilities(*, write_enabled: bool) -> dict[str, Any]:
    namespaces = sorted(
        {
            str(policy["corrections"]["license_namespace"])
            for policy in source_catalog().values()
            if isinstance(policy.get("corrections"), dict)
        }
        | {"quarantine-unknown"}
    )
    return {
        "schema_version": "0.1.0",
        "supported": True,
        "write_enabled": write_enabled,
        "central_service": False,
        "accounts": False,
        "telemetry": False,
        "network_evidence_fetch": False,
        "automatic_submission": False,
        "authoritative_override": False,
        "max_evidence_bytes": 65536,
        "max_evidence_items": 10,
        "namespaces": namespaces,
        "sources": [
            public_source(source_id)
            for source_id in sorted(source_catalog())
            if policy_for(source_id) is not None
        ],
    }
