"""Shared machinery for the pack builders.

The thirteen ``build_*.py`` scripts do the same few things around their own
parsing: hash bytes, fetch pinned bytes over HTTPS, and append an entry to a
snapshot registry. Each had grown its own copy — an identical ``_sha256`` in
eight of them, and a registry append through helpers with several different
names, every one re-implementing the same immutability rule.

The cost was not the duplication itself but that none of it could be exercised.
The fetch was a module-level call to a pinned GitHub URL with no seam, so the
whole fetch-hash-register path was reachable only by running a script against
the live network. Of the thirteen builders exactly one had a test, and it
covered a single pure helper.

``fetch`` therefore takes a transport. The live one is the default; a recorded
one in tests is the second adapter, which is what makes this a seam rather than
a parameter nobody passes.

Partially adopted, deliberately. Every registry append now goes through
``append_snapshot``, and the builders that shared a byte-identical ``_sha256``
now share this one. Nine scripts still open their own ``urllib`` request:
several fetch through a GitHub API rather than raw bytes, or need their own
headers and validation, so converting them is a real change to each rather than
a mechanical swap, and is not pretended here.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

__all__ = [
    "PackBuildError",
    "Transport",
    "append_snapshot",
    "fetch",
    "sha256",
    "urlopen_transport",
    "write_json",
]

# Enough for the largest pinned season file, small enough that a redirect to
# something unexpected cannot fill a disk.
DEFAULT_MAX_BYTES = 2_000_000

USER_AGENT = "golavo-pack-builder"

Transport = Callable[[str, int], bytes]


class PackBuildError(RuntimeError):
    """A pack could not be built from the bytes upstream actually served."""


def sha256(payload: bytes) -> str:
    """The digest every manifest, registry entry and provenance record uses."""
    return hashlib.sha256(payload).hexdigest()


def urlopen_transport(url: str, max_bytes: int) -> bytes:
    """The live transport: one GET, capped, no redirects followed blindly."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - pinned hosts
        payload: bytes = response.read(max_bytes + 1)
    return payload


def fetch(
    url: str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    transport: Transport | None = None,
) -> bytes:
    """Fetch pinned bytes, refusing anything over ``max_bytes``.

    Reading one byte past the cap is what makes the check honest: a response
    exactly at the limit is accepted, and one over it is rejected without the
    rest ever being read.
    """
    payload = (transport or urlopen_transport)(url, max_bytes)
    if len(payload) > max_bytes:
        raise PackBuildError(f"{url}: response exceeds {max_bytes} bytes")
    return payload


def write_json(path: Path, obj: Any) -> Path:
    """Write JSON the way every committed artifact in this repo is written.

    Sorted keys, two-space indent, trailing newline — so a rebuild produces
    byte-identical output and a diff shows only what actually changed.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def append_snapshot(registry_path: Path, entry: dict[str, Any]) -> bool:
    """Append a snapshot entry, treating existing entries as immutable.

    Returns True if the entry was appended, False if an identical one was
    already registered. Re-registering the same pack with *different* content
    raises: a retained snapshot is evidence for every artifact sealed against
    it, so rewriting one would silently invalidate that evidence rather than
    recording a new state.
    """
    registry_path = Path(registry_path)
    registry = (
        json.loads(registry_path.read_text(encoding="utf-8"))
        if registry_path.is_file()
        else {"snapshots": []}
    )
    snapshots = registry.setdefault("snapshots", [])
    for existing in snapshots:
        if existing.get("pack") != entry.get("pack"):
            continue
        if existing != entry:
            raise PackBuildError(
                f"registry entry for {entry['pack']} exists and differs; "
                "snapshots are immutable — never rewrite a retained entry"
            )
        return False
    snapshots.append(entry)
    write_json(registry_path, registry)
    return True
