"""Deterministic RFC 5545 export for locally followed fixtures."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any


def _escape(value: object) -> str:
    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def _fold(line: str) -> list[str]:
    """Fold by UTF-8 octets, never splitting a code point."""
    chunks: list[str] = []
    prefix = ""
    current = ""
    limit = 75
    for character in line:
        candidate = current + character
        if len((prefix + candidate).encode("utf-8")) > limit and current:
            chunks.append(prefix + current)
            prefix, current, limit = " ", character, 75
        else:
            current = candidate
    chunks.append(prefix + current)
    return chunks


def _utc(value: str) -> str | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def is_exportable(item: dict[str, Any]) -> bool:
    current = item.get("current") if isinstance(item.get("current"), dict) else {}
    kickoff = current.get("kickoff_utc")
    stable = item.get("follow_id") or current.get("match_id")
    return (
        current.get("kickoff_precision") == "exact"
        and isinstance(kickoff, str)
        and _utc(kickoff) is not None
        and bool(stable)
    )


def build_calendar(items: list[dict[str, Any]], *, generated_at_utc: str) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Golavo//Followed matches//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Golavo followed matches",
    ]
    dtstamp = _utc(generated_at_utc) or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    for item in items:
        current = item.get("current") if isinstance(item.get("current"), dict) else {}
        # Unknown or date-only kickoffs are omitted: a guessed time is worse than no event.
        if not is_exportable(item):
            continue
        kickoff = current.get("kickoff_utc")
        assert isinstance(kickoff, str)
        dtstart = _utc(kickoff)
        assert dtstart is not None
        stable = str(item.get("follow_id") or current.get("match_id") or "")
        uid = hashlib.sha256(stable.encode("utf-8")).hexdigest() + "@golavo.local"
        home = current.get("home_team") or "Home"
        away = current.get("away_team") or "Away"
        description = (
            f"Followed locally in Golavo. Competition: {current.get('competition') or 'Unknown'}."
        )
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{dtstamp}",
                f"DTSTART:{dtstart}",
                f"SUMMARY:{_escape(home)} vs {_escape(away)}",
                f"DESCRIPTION:{_escape(description)}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(part for line in lines for part in _fold(line)) + "\r\n"
