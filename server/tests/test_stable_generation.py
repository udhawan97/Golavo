"""Doing work on an index generation that provably did not move under it.

Reads have had a seam for this since SnapshotReader: register once, and cache
invalidation on a refresh is handled for you. Writes did not. Following a match,
reconciling follows and proposing a correction each hand-inlined the same
three-attempt loop — read the refresh status, take a snapshot, read the status
again, compare generation ids, retry if they moved — and the only way to
exercise it was to stand up the whole app and mutate refresh_jobs.status().
These tests drive it directly.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from golavo_server import matches


class _Snapshot:
    """Stands in for an IndexSnapshot; the seam only passes it through."""

    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.fingerprint = tag
        self.frame = None
        self.epoch = 0


class _StoreError(Exception):
    """A local store failure, carrying the reason code the ledgers use."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


def _run(work: Any, *, detail: str = "index moved; retry") -> Any:
    return asyncio.run(matches.run_on_stable_generation(work, detail=detail))


@pytest.fixture
def index(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A generation that stays put unless a test says otherwise."""
    state: dict[str, Any] = {"ids": None, "current": True, "generation_id": "gen-1"}

    def status() -> dict[str, Any]:
        generation_id = next(state["ids"]) if state["ids"] else state["generation_id"]
        return {
            "active_generation": {"generation_id": generation_id},
            "sources": [{"source_id": "martj42", "last_checked_at_utc": "2026-07-01T00:00:00Z"}],
        }

    monkeypatch.setattr(matches, "index_snapshot", lambda: _Snapshot("snap"))
    monkeypatch.setattr(matches, "snapshot_is_current", lambda snapshot: bool(state["current"]))
    monkeypatch.setattr(matches, "_generation_status", status)
    return state


def test_returns_the_work_result_on_a_stable_generation(index: dict[str, Any]) -> None:
    async def work(stable: Any) -> str:
        stable.require_stable()
        return "ok"

    assert _run(work) == "ok"


def test_exposes_the_generation_and_sources_to_the_work(index: dict[str, Any]) -> None:
    seen: dict[str, Any] = {}

    async def work(stable: Any) -> str:
        stable.require_stable()
        seen["generation_id"] = stable.generation_id
        seen["sources"] = stable.sources
        seen["snapshot"] = stable.snapshot
        return "ok"

    _run(work)
    assert seen["generation_id"] == "gen-1"
    assert seen["sources"]["martj42"]["last_checked_at_utc"] == "2026-07-01T00:00:00Z"
    assert isinstance(seen["snapshot"], _Snapshot)


def test_retries_when_the_snapshot_is_no_longer_current(index: dict[str, Any]) -> None:
    """A refresh republished the frame between taking it and using it."""
    index["current"] = False
    attempts = {"count": 0}

    async def work(stable: Any) -> str:
        attempts["count"] += 1
        if attempts["count"] == 2:
            index["current"] = True
        stable.require_stable()
        return "ok"

    assert _run(work) == "ok"
    assert attempts["count"] == 2


def test_retries_when_the_generation_id_changed_mid_window(index: dict[str, Any]) -> None:
    """Activation landed while the work was reading, so the window is void.

    The check must bracket the read, not just the snapshot acquisition: the
    status is read once when the window opens and again inside require_stable,
    so a refresh activating during a match lookup still invalidates it.
    """
    index["ids"] = iter(["gen-1", "gen-2", "gen-2", "gen-2"])
    attempts = {"count": 0}

    async def work(stable: Any) -> str:
        attempts["count"] += 1
        stable.require_stable()
        return "ok"

    assert _run(work) == "ok"
    assert attempts["count"] == 2


def test_a_status_source_without_an_id_is_skipped_not_fatal(
    index: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The route this replaced tolerated a malformed source entry."""
    monkeypatch.setattr(
        matches,
        "_generation_status",
        lambda: {
            "active_generation": {"generation_id": "gen-1"},
            "sources": [{"last_checked_at_utc": "2026-07-01T00:00:00Z"}, {"source_id": "martj42"}],
        },
    )

    async def work(stable: Any) -> Any:
        stable.require_stable()
        return stable.sources

    assert _run(work) == {"martj42": {"source_id": "martj42"}}


def test_retries_when_a_store_reports_the_generation_changed(index: dict[str, Any]) -> None:
    """The write itself lost the race, after the pre-check had passed."""
    attempts = {"count": 0}

    async def work(stable: Any) -> str:
        stable.require_stable()
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise _StoreError("index_generation_changed")
        return "ok"

    assert _run(work) == "ok"
    assert attempts["count"] == 2


def test_any_other_store_failure_is_raised_untouched(index: dict[str, Any]) -> None:
    async def work(stable: Any) -> str:
        stable.require_stable()
        raise _StoreError("already_followed")

    with pytest.raises(_StoreError) as caught:
        _run(work)
    assert caught.value.reason_code == "already_followed"


def test_gives_up_fail_closed_after_three_attempts(index: dict[str, Any]) -> None:
    """A pathological repoint loop must fail closed, never spin or half-write."""
    index["current"] = False
    attempts = {"count": 0}

    async def work(stable: Any) -> str:
        attempts["count"] += 1
        stable.require_stable()
        return "unreachable"

    with pytest.raises(matches.MatchIndexUnavailable) as caught:
        _run(work, detail="index moved while following the match")
    assert attempts["count"] == 3
    assert "index moved while following the match" in str(caught.value)


def test_commit_publishes_only_for_the_snapshot_it_was_given(
    index: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The commit hook every write route builds by hand, built once here."""
    seen: dict[str, Any] = {}
    monkeypatch.setattr(
        matches,
        "apply_if_snapshot_current",
        lambda snapshot, operation: seen.setdefault("snapshot", snapshot) is not None,
    )

    async def work(stable: Any) -> bool:
        stable.require_stable()
        return stable.commit(lambda: None)

    assert _run(work) is True
    assert isinstance(seen["snapshot"], _Snapshot)
