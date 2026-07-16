"""Registry-owned allowlist policy for foreground match research."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from golavo_core.resources import resource

_SECRET_KEY = re.compile(r"(?:token|secret|key|auth|password)", re.IGNORECASE)


class ResearchPolicyError(ValueError):
    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(detail)
        self.reason_code = reason_code
        self.detail = detail


@dataclass(frozen=True)
class SourcePolicy:
    source_id: str
    name: str
    license: str
    license_url: str
    attribution: str
    license_namespace: str
    roles: tuple[str, ...]
    hosts: tuple[str, ...]
    schemes: tuple[str, ...]
    ports: tuple[int, ...]
    path_patterns: tuple[str, ...]
    redirect_hosts: tuple[str, ...]
    allowed_query_keys: tuple[str, ...]
    content_types: tuple[str, ...]
    max_raw_bytes: int
    permitted_fact_types: tuple[str, ...]
    parser_id: str
    parser_version: str
    ai_fallback: bool
    terms_url: str

    def public(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "name": self.name,
            "license": self.license,
            "license_url": self.license_url,
            "attribution": self.attribution,
            "roles": list(self.roles),
            "hosts": list(self.hosts),
            "license_namespace": self.license_namespace,
            "permitted_fact_types": list(self.permitted_fact_types),
            "ai_fallback": self.ai_fallback,
            "terms_url": self.terms_url,
        }


@lru_cache(maxsize=1)
def source_policies() -> dict[str, SourcePolicy]:
    registry = json.loads(resource("data", "sources", "registry.json").read_text("utf-8"))
    result: dict[str, SourcePolicy] = {}
    for source in registry["sources"]:
        access = source.get("research_access")
        if not isinstance(access, dict) or access.get("enabled") is not True:
            continue
        source_id = str(source["source_id"])
        result[source_id] = SourcePolicy(
            source_id=source_id,
            name=str(source["name"]),
            license=str(source["license"]),
            license_url=str(source["license_url"]),
            attribution=str(source["attribution"]),
            license_namespace=str(access["license_namespace"]),
            roles=tuple(str(value) for value in access["roles"]),
            hosts=tuple(str(value).casefold().rstrip(".") for value in access["hosts"]),
            schemes=tuple(str(value).casefold() for value in access["schemes"]),
            ports=tuple(int(value) for value in access["ports"]),
            path_patterns=tuple(str(value) for value in access["path_patterns"]),
            redirect_hosts=tuple(
                str(value).casefold().rstrip(".") for value in access["redirect_hosts"]
            ),
            allowed_query_keys=tuple(str(value) for value in access.get("allowed_query_keys", [])),
            content_types=tuple(str(value).casefold() for value in access["content_types"]),
            max_raw_bytes=int(access["max_raw_bytes"]),
            permitted_fact_types=tuple(str(value) for value in access["permitted_fact_types"]),
            parser_id=str(access["parser_id"]),
            parser_version=str(access["parser_version"]),
            ai_fallback=bool(access["ai_fallback"]),
            terms_url=str(access["terms_url"]),
        )
    return result


def reset_cache() -> None:
    source_policies.cache_clear()


def _validate_source_query(policy: SourcePolicy, path: str, pairs: list[tuple[str, str]]) -> None:
    values: dict[str, list[str]] = {}
    for key, value in pairs:
        values.setdefault(key, []).append(value)
    if any(len(items) != 1 for items in values.values()):
        raise ResearchPolicyError("duplicate_query_key", "query keys must be unique")
    if any(_SECRET_KEY.search(key) for key in values):
        raise ResearchPolicyError("secret_query_key", "credential-shaped query keys are refused")
    if any(len(value) > 500 for items in values.values() for value in items):
        raise ResearchPolicyError(
            "query_value_too_long", "query values are capped at 500 characters"
        )
    if policy.source_id == "wikipedia-en":
        if path != "/w/api.php" or values.get("action") != ["query"]:
            raise ResearchPolicyError(
                "endpoint_not_allowed", "only read-only Wikipedia queries are allowed"
            )
        search = values.get("list") == ["search"]
        extract = "extracts" in (
            values.get("prop", [""])[0].split("|") if values.get("prop") else []
        )
        if not (search or extract) or values.get("format") != ["json"]:
            raise ResearchPolicyError("endpoint_not_allowed", "unsupported Wikipedia API operation")
    if policy.source_id == "wikidata" and path == "/w/api.php":
        if values.get("action") != ["wbsearchentities"] or values.get("format") != ["json"]:
            raise ResearchPolicyError(
                "endpoint_not_allowed", "only Wikidata entity search is allowed"
            )
    if (
        policy.source_id == "wikidata"
        and path.startswith("/w/rest.php/wikibase/v1/entities/items/")
        and pairs
    ):
        raise ResearchPolicyError(
            "query_key_not_allowed", "Wikidata item captures do not accept query parameters"
        )


def canonicalize_url(url: str, *, source_id: str | None = None) -> tuple[str, SourcePolicy]:
    try:
        parsed = urlsplit(url.strip())
        port = parsed.port
    except ValueError as exc:
        raise ResearchPolicyError("invalid_url", "research URL is invalid") from exc
    host = (parsed.hostname or "").casefold().rstrip(".")
    if not host or parsed.username or parsed.password:
        raise ResearchPolicyError("invalid_url", "research URLs cannot contain credentials")
    if parsed.fragment:
        raise ResearchPolicyError("fragment_not_allowed", "research URLs cannot contain fragments")
    candidates = source_policies().values()
    if source_id is not None:
        selected = source_policies().get(source_id)
        if selected is None:
            raise ResearchPolicyError("source_not_registered", "source is not enabled for research")
        candidates = (selected,)
    for policy in candidates:
        effective_port = port or (443 if parsed.scheme.casefold() == "https" else 80)
        if (
            parsed.scheme.casefold() not in policy.schemes
            or host not in policy.hosts
            or effective_port not in policy.ports
            or not any(
                re.fullmatch(pattern, parsed.path or "/") for pattern in policy.path_patterns
            )
        ):
            continue
        pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=False)
        allowed = set(policy.allowed_query_keys)
        if any(key not in allowed for key, _value in pairs):
            raise ResearchPolicyError(
                "query_key_not_allowed", "research URL has an unapproved query key"
            )
        _validate_source_query(policy, parsed.path or "/", pairs)
        netloc = host if effective_port == 443 else f"{host}:{effective_port}"
        canonical_query = urlencode(sorted(pairs), doseq=True)
        return urlunsplit(("https", netloc, parsed.path or "/", canonical_query, "")), policy
    raise ResearchPolicyError("url_not_allowlisted", "URL is not on an approved research endpoint")


def redirect_allowed(policy: SourcePolicy, target_url: str) -> bool:
    try:
        target, target_policy = canonicalize_url(target_url, source_id=policy.source_id)
    except ResearchPolicyError:
        return False
    host = (urlsplit(target).hostname or "").casefold().rstrip(".")
    return target_policy.source_id == policy.source_id and (
        host in policy.hosts or host in policy.redirect_hosts
    )
