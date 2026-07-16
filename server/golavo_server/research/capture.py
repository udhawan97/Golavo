"""Deterministic canonical-text extraction and immutable capture receipts."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlsplit

from .fetch import FetchResponse
from .policy import SourcePolicy
from .store import now_z

MAX_CANONICAL_CHARS = 12_000
_SPACE = re.compile(r"[ \t]+")


class CaptureError(ValueError):
    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(detail)
        self.reason_code = reason_code
        self.detail = detail


@dataclass(frozen=True)
class CanonicalDocument:
    text: str
    revision_id: str | None
    document_url: str
    parsed: dict[str, Any]


def _clean_text(value: str) -> str:
    lines = []
    for raw in (
        unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ):
        line = _SPACE.sub(" ", raw).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)[:MAX_CANONICAL_CHARS]


def _page_values(page: dict[str, Any]) -> tuple[str, str, str | None]:
    title = str(page.get("title") or "").strip()
    text = str(page.get("extract") or "").strip()
    revision: str | None = None
    revisions = page.get("revisions")
    if isinstance(revisions, list) and revisions and isinstance(revisions[0], dict):
        value = revisions[0].get("revid") or revisions[0].get("parentid")
        revision = str(value) if value is not None else None
    return title, text, revision


def _wikipedia(raw: bytes) -> CanonicalDocument:
    try:
        payload = json.loads(raw.decode("utf-8"))
        pages = payload["query"]["pages"]
    except (UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
        raise CaptureError("invalid_wikipedia_response", "Wikipedia returned invalid JSON") from exc
    values = (
        list(pages.values())
        if isinstance(pages, dict)
        else pages
        if isinstance(pages, list)
        else []
    )
    for page in values:
        if not isinstance(page, dict):
            continue
        title, body, revision = _page_values(page)
        if not title or not body:
            continue
        text = _clean_text(f"Title: {title}\nRevision: {revision or 'unknown'}\nText:\n{body}")
        return CanonicalDocument(
            text=text,
            revision_id=revision,
            document_url=f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
            parsed={"title": title, "extract": body},
        )
    raise CaptureError("empty_wikipedia_extract", "Wikipedia returned no article text")


def _language_value(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        text = value.get("value") or value.get("text")
        return str(text).strip() if text else None
    return None


def _aliases(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        text = _language_value(item)
        if text and text not in result:
            result.append(text)
    return result


def _wikidata(raw: bytes, url: str) -> CanonicalDocument:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise CaptureError("invalid_wikidata_response", "Wikidata returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise CaptureError("invalid_wikidata_response", "Wikidata item must be an object")
    qid = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    labels = payload.get("labels") if isinstance(payload.get("labels"), dict) else {}
    aliases = payload.get("aliases") if isinstance(payload.get("aliases"), dict) else {}
    descriptions = (
        payload.get("descriptions") if isinstance(payload.get("descriptions"), dict) else {}
    )
    label = _language_value(labels.get("en")) or _language_value(payload.get("label"))
    alias_values = _aliases(aliases.get("en"))
    description = _language_value(descriptions.get("en"))
    if not label:
        raise CaptureError("wikidata_label_missing", "Wikidata item has no English label")
    lines = [f"Entity: {qid}", f"Label: {label}"]
    if alias_values:
        lines.append("Aliases: " + "; ".join(alias_values))
    if description:
        lines.append("Description: " + description)
    text = _clean_text("\n".join(lines))
    revision = payload.get("revision") or payload.get("lastrevid")
    return CanonicalDocument(
        text=text,
        revision_id=str(revision) if revision is not None else None,
        document_url=f"https://www.wikidata.org/wiki/{qid}",
        parsed={"qid": qid, "label": label, "aliases": alias_values, "description": description},
    )


def canonical_document(response: FetchResponse, policy: SourcePolicy) -> CanonicalDocument:
    if response.source_id == "wikipedia-en":
        return _wikipedia(response.body)
    if response.source_id == "wikidata":
        return _wikidata(response.body, response.canonical_url)
    if response.content_type in {"text/plain", "text/csv", "text/html"}:
        text = _clean_text(response.body.decode("utf-8", "strict"))
        if not text:
            raise CaptureError("empty_canonical_text", "source returned no usable text")
        return CanonicalDocument(
            text=text, revision_id=None, document_url=response.canonical_url, parsed={}
        )
    raise CaptureError("parser_unavailable", "no deterministic parser exists for this source")


def capture_payload(
    *,
    run_id: str,
    response: FetchResponse,
    policy: SourcePolicy,
    document: CanonicalDocument,
) -> dict[str, Any]:
    raw_sha = hashlib.sha256(response.body).hexdigest()
    text_sha = hashlib.sha256(document.text.encode("utf-8")).hexdigest()
    capture_id = (
        "rc_"
        + hashlib.sha256(
            f"{run_id}\n{policy.source_id}\n{response.canonical_url}\n{raw_sha}".encode()
        ).hexdigest()
    )
    return {
        "schema_version": "0.1.0",
        "capture_id": capture_id,
        "run_id": run_id,
        "source_id": policy.source_id,
        "license_namespace": policy.license_namespace,
        "license": policy.license,
        "license_url": policy.license_url,
        "attribution": policy.attribution,
        "modifications": "normalized plaintext excerpt",
        "canonical_url": response.canonical_url,
        "retrieved_at_utc": now_z(),
        "revision_id": document.revision_id,
        "etag": response.etag,
        "last_modified": response.last_modified,
        "content_type": response.content_type,
        "http_status": response.status,
        "raw_sha256": raw_sha,
        "raw_bytes": len(response.body),
        "canonical_text_sha256": text_sha,
        "canonical_text": document.text,
        "parser_id": policy.parser_id,
        "parser_version": policy.parser_version,
        "untrusted": True,
    }
