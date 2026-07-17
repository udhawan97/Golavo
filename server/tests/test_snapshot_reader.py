"""The one cached read over the active index generation.

Every derived server read (outlook, analysis, analytics, conditions, the
retrospective) used to hand-roll this: a 3-attempt repoint retry, a private
``_CACHE`` dict with its own eviction rule, a ``snapshot_is_current`` recheck
before returning, and a provenance stamp — while ``matches`` hardcoded the NAME
of every such module to invalidate them. Missing one silently served a retired
generation's work after a refresh. These tests pin that machinery at its single
interface, and pin the self-registration that replaced the hardcoded list.
"""

from __future__ import annotations

from typing import Any

import pytest
from golavo_server import matches


@pytest.fixture(autouse=True)
def _reset():
    matches.reset_cache()
    yield
    matches.reset_cache()


class _FakeIndex:
    """Drives readers over controlled generations without loading a real index."""

    def __init__(self, fingerprint: str = "fp-1", epoch: int = 1) -> None:
        self.fingerprint = fingerprint
        self.epoch = epoch
        self.publishes_are_current = True

    def snapshot(self) -> matches.IndexSnapshot:
        return matches.IndexSnapshot(
            frame=object(), fingerprint=self.fingerprint, epoch=self.epoch
        )

    def install(self, monkeypatch: pytest.MonkeyPatch) -> _FakeIndex:
        monkeypatch.setattr(matches, "index_snapshot", self.snapshot)
        monkeypatch.setattr(
            matches,
            "snapshot_is_current",
            lambda snapshot: (
                snapshot.fingerprint == self.fingerprint and snapshot.epoch == self.epoch
            ),
        )

        def apply_if_snapshot_current(snapshot, operation) -> bool:
            if not self.publishes_are_current or snapshot.epoch != self.epoch:
                return False
            operation()
            return True

        monkeypatch.setattr(matches, "apply_if_snapshot_current", apply_if_snapshot_current)
        return self


def test_computes_once_and_memoizes_per_generation(monkeypatch) -> None:
    _FakeIndex().install(monkeypatch)
    reader = matches.SnapshotReader("probe")
    calls = {"n": 0}

    def compute(snapshot: matches.IndexSnapshot) -> dict[str, Any]:
        calls["n"] += 1
        return {"value": calls["n"]}

    first = reader.read(compute)
    second = reader.read(compute)

    assert calls["n"] == 1
    assert first == second


def test_stamps_the_index_fingerprint_into_provenance(monkeypatch) -> None:
    """The reader knows the snapshot, so the reader owns this one fact — a caller
    can never stamp a fingerprint that is not the one it computed on."""
    _FakeIndex(fingerprint="fp-stamped").install(monkeypatch)
    reader = matches.SnapshotReader("probe", stamps_provenance=True)

    result = reader.read(lambda snapshot: {"value": 1})

    assert result["provenance"]["index_sha256"] == "fp-stamped"


def test_stamp_preserves_a_computes_own_provenance_fields(monkeypatch) -> None:
    _FakeIndex(fingerprint="fp-1").install(monkeypatch)
    reader = matches.SnapshotReader("probe", stamps_provenance=True)

    result = reader.read(lambda snapshot: {"provenance": {"pack": "p@abc"}})

    assert result["provenance"] == {"pack": "p@abc", "index_sha256": "fp-1"}


def test_an_envelope_without_provenance_is_never_given_one(monkeypatch) -> None:
    """Envelopes that declare no provenance (conditions stamps its own
    ``snapshot_sha256``; an analysis envelope carries none) must not have a field
    invented on them — their contracts would reject it."""
    _FakeIndex().install(monkeypatch)
    reader = matches.SnapshotReader("probe")

    result = reader.read(lambda snapshot: {"available": True})

    assert result == {"available": True}


def test_non_dict_results_are_returned_unstamped(monkeypatch) -> None:
    _FakeIndex().install(monkeypatch)
    reader = matches.SnapshotReader("probe", stamps_provenance=True)

    assert reader.read(lambda snapshot: None) is None


def test_a_new_generation_recomputes(monkeypatch) -> None:
    index = _FakeIndex(fingerprint="fp-1", epoch=1).install(monkeypatch)
    reader = matches.SnapshotReader("probe")
    calls = {"n": 0}

    def compute(snapshot: matches.IndexSnapshot) -> dict[str, Any]:
        calls["n"] += 1
        return {"value": calls["n"]}

    reader.read(compute)
    index.fingerprint, index.epoch = "fp-2", 2
    reader.read(compute)

    assert calls["n"] == 2


def test_extra_key_components_separate_entries(monkeypatch) -> None:
    _FakeIndex().install(monkeypatch)
    reader = matches.SnapshotReader("probe")
    calls = {"n": 0}

    def compute(snapshot: matches.IndexSnapshot) -> dict[str, Any]:
        calls["n"] += 1
        return {"value": calls["n"]}

    reader.read(compute, key=("a",))
    reader.read(compute, key=("b",))
    reader.read(compute, key=("a",))

    assert calls["n"] == 2


def test_a_callable_key_is_resolved_on_every_attempt(monkeypatch) -> None:
    """The retrospective's pack digest is resolved per attempt, not per call: the
    active pack can move under an unchanged index, and the memo must self-
    invalidate when it does."""
    _FakeIndex().install(monkeypatch)
    reader = matches.SnapshotReader("probe")
    packs = iter(["pack-a", "pack-b"])
    calls = {"n": 0}

    def compute(snapshot: matches.IndexSnapshot) -> dict[str, Any]:
        calls["n"] += 1
        return {"value": calls["n"]}

    reader.read(compute, key=lambda: (next(packs),))
    reader.read(compute, key=lambda: (next(packs),))

    assert calls["n"] == 2


def test_work_begun_on_a_retired_generation_is_never_published(monkeypatch) -> None:
    index = _FakeIndex().install(monkeypatch)
    index.publishes_are_current = False
    reader = matches.SnapshotReader("probe")
    calls = {"n": 0}

    def compute(snapshot: matches.IndexSnapshot) -> dict[str, Any]:
        calls["n"] += 1
        return {"value": calls["n"]}

    with pytest.raises(matches.MatchIndexUnavailable):
        reader.read(compute)

    assert calls["n"] == 3  # every attempt refused publication
    assert reader.entries() == {}


def test_exhausted_attempts_name_the_reader(monkeypatch) -> None:
    index = _FakeIndex().install(monkeypatch)
    index.publishes_are_current = False
    reader = matches.SnapshotReader("tournament outlook")

    with pytest.raises(matches.MatchIndexUnavailable, match="tournament outlook"):
        reader.read(lambda snapshot: {"value": 1})


def test_the_cache_is_bounded_and_evicts_oldest_first(monkeypatch) -> None:
    _FakeIndex().install(monkeypatch)
    reader = matches.SnapshotReader("probe", max_entries=2)

    for n in range(3):
        reader.read(lambda snapshot, n=n: {"value": n}, key=(n,))

    assert len(reader.entries()) == 2


def test_matches_reset_clears_every_registered_reader(monkeypatch) -> None:
    """The invalidation seam: ``matches`` must not know the name of a single
    derivative module. A reader registers itself, so a new cached read cannot
    forget to be invalidated — the failure mode that silently served stale data."""
    _FakeIndex().install(monkeypatch)
    reader = matches.SnapshotReader("probe")
    reader.read(lambda snapshot: {"value": 1})
    assert reader.entries() != {}

    matches.reset_cache()

    assert reader.entries() == {}


def test_every_shipped_cached_read_is_registered() -> None:
    """Names the real readers, so deleting one's registration fails here rather
    than in production after a refresh."""
    from golavo_server import analysis, analytics, conditions, outlook, retrospective  # noqa: F401

    registered = {reader.name for reader in matches.registered_readers()}

    assert {
        "tournament outlook",
        "season outlook",
        "match analysis",
        "competition analytics",
        "match conditions",
        "tournament retrospective",
    } <= registered
