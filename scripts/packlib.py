"""Shared machinery for the pack builders.

Every ``build_*.py`` script does the same four things around its own parsing:
hash bytes, fetch pinned bytes over HTTPS, write a manifest, and append an entry
to a snapshot registry. Each had grown its own copy — ``_sha256`` was written
out identically in six scripts, ten opened their own ``urllib`` request, and six
appended to a registry through helpers with five different names.

The cost was not the duplication itself but that none of it could be exercised.
The fetch was a module-level call to a pinned GitHub URL with no seam, so the
whole fetch-hash-manifest-register path was reachable only by running a script
against the live network. Of the twelve builders exactly one had a test, and it
covered a single pure helper.

``fetch`` therefore takes a transport. The live one is the default; a recorded
one in tests is the second adapter, which is what makes this a seam rather than
a parameter nobody passes.
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
    "manifest_file_entry",
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


def manifest_file_entry(name: str, payload: bytes) -> dict[str, Any]:
    """One declared file in a pack manifest: its name, size and digest."""
    return {"name": name, "bytes": len(payload), "sha256": sha256(payload)}


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
