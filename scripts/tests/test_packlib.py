"""The pack builders' shared machinery, exercised without the network.

Before this module the fetch-hash-manifest-register path could only be run
against live GitHub, so of the twelve builders exactly one had a test and it
covered a single pure helper. These drive the parts that decide whether a pack's
provenance is trustworthy: the byte cap, the digest, and the rule that a
retained snapshot is never rewritten.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.packlib import (  # noqa: E402
    PackBuildError,
    append_snapshot,
    fetch,
    manifest_file_entry,
    sha256,
    write_json,
)


def _recorded(payload: bytes):
    """A transport serving fixed bytes — the second adapter at the fetch seam."""

    def transport(url: str, max_bytes: int) -> bytes:
        return payload[: max_bytes + 1]

    return transport


class TestFetch:
    def test_returns_the_served_bytes(self) -> None:
        assert fetch("https://example.test/f", transport=_recorded(b"hello")) == b"hello"

    def test_a_response_exactly_at_the_cap_is_accepted(self) -> None:
        assert (
            fetch("https://example.test/f", max_bytes=5, transport=_recorded(b"12345")) == b"12345"
        )

    def test_a_response_over_the_cap_is_refused(self) -> None:
        with pytest.raises(PackBuildError, match="exceeds"):
            fetch("https://example.test/f", max_bytes=4, transport=_recorded(b"12345"))

    def test_the_url_is_named_in_the_failure(self) -> None:
        with pytest.raises(PackBuildError, match="example.test/big"):
            fetch("https://example.test/big", max_bytes=1, transport=_recorded(b"xx"))


class TestDigests:
    def test_sha256_is_the_hex_digest_of_the_bytes(self) -> None:
        import hashlib

        assert sha256(b"abc") == hashlib.sha256(b"abc").hexdigest()

    def test_a_manifest_entry_declares_name_size_and_digest(self) -> None:
        entry = manifest_file_entry("results.csv", b"abc")
        assert entry == {"name": "results.csv", "bytes": 3, "sha256": sha256(b"abc")}


class TestWriteJson:
    def test_output_is_sorted_indented_and_newline_terminated(self, tmp_path: Path) -> None:
        """A rebuild must be byte-identical, so a diff shows only real change."""
        path = write_json(tmp_path / "out.json", {"b": 1, "a": 2})
        assert path.read_text(encoding="utf-8") == '{\n  "a": 2,\n  "b": 1\n}\n'

    def test_missing_parents_are_created(self, tmp_path: Path) -> None:
        path = write_json(tmp_path / "nested" / "deep" / "out.json", {})
        assert path.is_file()


class TestAppendSnapshot:
    def test_appends_to_a_registry_that_does_not_exist_yet(self, tmp_path: Path) -> None:
        registry = tmp_path / "snapshots.json"
        assert append_snapshot(registry, {"pack": "packs/a", "source_id": "s"}) is True
        assert json.loads(registry.read_text())["snapshots"] == [
            {"pack": "packs/a", "source_id": "s"}
        ]

    def test_appending_the_same_entry_twice_is_a_no_op(self, tmp_path: Path) -> None:
        """Re-running a builder on unchanged bytes must not grow the registry."""
        registry = tmp_path / "snapshots.json"
        entry = {"pack": "packs/a", "source_id": "s"}
        append_snapshot(registry, entry)
        assert append_snapshot(registry, dict(entry)) is False
        assert len(json.loads(registry.read_text())["snapshots"]) == 1

    def test_rewriting_a_retained_entry_is_refused(self, tmp_path: Path) -> None:
        """A retained snapshot is evidence for every artifact sealed against it."""
        registry = tmp_path / "snapshots.json"
        append_snapshot(registry, {"pack": "packs/a", "sha256": "old"})
        with pytest.raises(PackBuildError, match="immutable"):
            append_snapshot(registry, {"pack": "packs/a", "sha256": "new"})

    def test_a_different_pack_appends_alongside(self, tmp_path: Path) -> None:
        registry = tmp_path / "snapshots.json"
        append_snapshot(registry, {"pack": "packs/a"})
        append_snapshot(registry, {"pack": "packs/b"})
        packs = [e["pack"] for e in json.loads(registry.read_text())["snapshots"]]
        assert packs == ["packs/a", "packs/b"]

    def test_existing_registry_keys_outside_snapshots_survive(self, tmp_path: Path) -> None:
        registry = tmp_path / "snapshots.json"
        write_json(registry, {"note": "keep me", "snapshots": []})
        append_snapshot(registry, {"pack": "packs/a"})
        assert json.loads(registry.read_text())["note"] == "keep me"
