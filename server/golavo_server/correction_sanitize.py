"""Plain-text evidence capture with separate raw and display hashes."""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from typing import Any

MAX_EVIDENCE_BYTES = 65536
_TAG_RE = re.compile(r"<[^>]{0,2048}>")
_PROMPT_TOKEN_RE = re.compile(
    r"(?:<\|/?(?:system|assistant|user|tool)[^>]*\|>|\[(?:/?INST|SYSTEM|ASSISTANT)\])",
    re.IGNORECASE,
)
_BIDI_AND_INVISIBLE = {
    "\u061c",
    "\u200b",
    "\u200c",
    "\u200d",
    "\u200e",
    "\u200f",
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2060",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
    "\ufeff",
}


class EvidenceError(ValueError):
    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(detail)
        self.reason_code = reason_code
        self.detail = detail


def sanitize(value: str) -> tuple[bytes, str]:
    if not isinstance(value, str):
        raise EvidenceError("invalid_evidence", "captured evidence must be text")
    raw = value.encode("utf-8", errors="strict")
    if not raw:
        raise EvidenceError("evidence_required", "captured evidence cannot be empty")
    if len(raw) > MAX_EVIDENCE_BYTES:
        raise EvidenceError(
            "evidence_too_large", f"captured evidence exceeds {MAX_EVIDENCE_BYTES} bytes"
        )
    display = unicodedata.normalize("NFC", html.unescape(value))
    display = _TAG_RE.sub(" ", display)
    display = _PROMPT_TOKEN_RE.sub(" ", display)
    chars: list[str] = []
    for char in display:
        if char in _BIDI_AND_INVISIBLE:
            continue
        category = unicodedata.category(char)
        if category in {"Cc", "Cf"} and char not in {"\n", "\t"}:
            continue
        chars.append(char)
    display = " ".join("".join(chars).replace("\t", " ").split())
    if not display:
        raise EvidenceError("evidence_empty_after_sanitize", "evidence has no displayable text")
    return raw, display


def receipt(raw: bytes, display: str) -> dict[str, Any]:
    return {
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_bytes": len(raw),
        "sanitized_text": display,
        "sanitized_sha256": hashlib.sha256(display.encode("utf-8")).hexdigest(),
    }
