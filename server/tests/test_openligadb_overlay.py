from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

import pytest
from fastapi.testclient import TestClient
from golavo_server import (
    main as server_main,
)
from golavo_server import (
    openligadb_jobs,
    openligadb_overlay,
    openligadb_source,
    openligadb_state,
    runtime,
)
from jsonschema import Draft202012Validator, FormatChecker


class FakeOpenLigaDB:
    def __init__(
        self,
        *,
        duplicate_league: bool = False,
        finished_without_final: bool = False,
        match_id: int = 83161,
        last_change: str = "2026-07-15T11:47:24.363",
    ):
        self.duplicate_league = duplicate_league
        self.finished_without_final = finished_without_final
        self.match_id = match_id
        self.last_change = last_change
        self.paths: list[str] = []

    def get_path(self, path: str, *, season: str, cancel=None, max_bytes=None):
        assert openligadb_source.approved_path(path, season=season)
        self.paths.append(path)
        if path == f"/getavailableleagues/{season}":
            league = {
                "leagueId": 4937,
                "leagueName": f"1. Fußball-Bundesliga {season}/{int(season) + 1}",
                "leagueShortcut": "bl1",
                "leagueSeason": season,
                "sport": {"sportId": 1, "sportName": "Fußball"},
            }
            payload = [league, dict(league)] if self.duplicate_league else [league]
        elif path == f"/getavailablegroups/bl1/{season}":
            payload = [{"groupName": "1. Spieltag", "groupOrderID": 1, "groupID": 50633}]
        elif path == f"/getlastchangedate/bl1/{season}/1":
            payload = self.last_change
        elif path == f"/getmatchdata/bl1/{season}/1":
            payload = [
                {
                    "matchID": self.match_id,
                    "matchDateTime": f"{season}-08-29T15:30:00",
                    "timeZoneID": "W. Europe Standard Time",
                    "leagueId": 4937,
                    "leagueName": f"1. Fußball-Bundesliga {season}/{int(season) + 1}",
                    "leagueSeason": int(season),
                    "leagueShortcut": "bl1",
                    "matchDateTimeUTC": f"{season}-08-29T13:30:00Z",
                    "group": {
                        "groupName": "1. Spieltag",
                        "groupOrderID": 1,
                        "groupID": 50633,
                    },
                    "team1": {
                        "teamId": 81,
                        "teamName": "1. FSV Mainz 05",
                        "shortName": "Mainz",
                        "teamIconUrl": "https://example.invalid/logo.svg",
                    },
                    "team2": {
                        "teamId": 31,
                        "teamName": "SC Paderborn 07",
                        "shortName": "Paderborn",
                        "teamIconUrl": "https://example.invalid/logo.svg",
                    },
                    "lastUpdateDateTime": "2026-07-03T07:36:40.837",
                    "matchIsFinished": self.finished_without_final,
                    "matchResults": [],
                    "goals": [],
                }
            ]
        else:  # pragma: no cover - a new endpoint must update the test allowlist
            raise AssertionError(path)
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        return openligadb_source.HttpResponse(
            status=200,
            headers={"content-type": "application/json; charset=utf-8"},
            body=body,
            final_url=openligadb_source.API_ORIGIN + path,
        )


class OfflineOpenLigaDB(FakeOpenLigaDB):
    def get_path(self, path: str, *, season: str, cancel=None, max_bytes=None):
        raise openligadb_source.OpenLigaDBError("offline", "source is offline")


def _ledger(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    ledger = tmp_path / "Application Support" / "com.golavo.app" / "ledger"
    ledger.mkdir(parents=True)
    monkeypatch.setenv("GOLAVO_DATA_DIR", str(ledger))
    return ledger


def _snapshot(staging: Path, fake: FakeOpenLigaDB | None = None) -> dict:
    return openligadb_source.capture_snapshot(
        staging / "raw",
        ["bl1"],
        fetcher=fake or FakeOpenLigaDB(),
        now=datetime(2026, 7, 15, tzinfo=UTC),
    )


def _install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:
    _ledger(monkeypatch, tmp_path)
    staging = openligadb_state.staging_dir() / "manual"
    staging.mkdir(parents=True)
    manifest = openligadb_overlay.write_generation(staging, _snapshot(staging))
    installed = openligadb_state.install_generation(staging, manifest["generation_id"])
    openligadb_state.activate_generation(installed.name, activated_at_utc="2026-07-15T12:00:00Z")
    openligadb_state.save_settings(
        {
            "enabled": True,
            "refresh_policy": "manual",
            "selected_competitions": ["bl1"],
            "license_accepted_at_utc": "2026-07-15T11:00:00Z",
        }
    )
    return manifest


def test_endpoint_allowlist_rejects_arbitrary_leagues_queries_hosts_and_redirects(
    monkeypatch,
) -> None:
    assert openligadb_source.approved_path("/getmatchdata/bl1/2026/1", season="2026")
    assert not openligadb_source.approved_path("/getmatchdata/epl/2026/1", season="2026")
    assert not openligadb_source.approved_path("/getmatchdata/bl1/2026/Bayern", season="2026")
    assert not openligadb_source.approved_path("/getmatchdata/bl1/2026/1?x=1", season="2026")
    with pytest.raises(openligadb_source.OpenLigaDBError, match="unapproved"):
        openligadb_source._validate_url(
            "https://example.com/getmatchdata/bl1/2026/1", season="2026"
        )

    class RedirectResponse:
        status = 200
        headers = {"Content-Type": "application/json"}

        def geturl(self):
            return openligadb_source.API_ORIGIN + "/getmatchdata/bl1/2026/2"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(openligadb_source, "urlopen", lambda *_args, **_kwargs: RedirectResponse())
    with pytest.raises(openligadb_source.OpenLigaDBError) as redirected:
        openligadb_source.ApiFetcher().get_path("/getmatchdata/bl1/2026/1", season="2026")
    assert redirected.value.code == "unsafe_redirect"


def test_source_capture_retains_raw_hashes_and_fails_closed_on_identity_conflict(tmp_path) -> None:
    staging = tmp_path / "ok"
    staging.mkdir()
    snapshot = _snapshot(staging)
    assert snapshot["source_id"] == "openligadb"
    assert snapshot["license"] == "ODbL-1.0"
    assert snapshot["capabilities"][0]["state"] == "available"
    assert len(snapshot["receipts"]) == 4
    for receipt in snapshot["receipts"]:
        raw = staging / "raw" / receipt["path"]
        assert raw.is_file()
        assert hashlib.sha256(raw.read_bytes()).hexdigest() == receipt["sha256"]

    conflict = tmp_path / "conflict"
    conflict.mkdir()
    with pytest.raises(openligadb_source.OpenLigaDBConflict, match="multiple"):
        _snapshot(conflict, FakeOpenLigaDB(duplicate_league=True))


def test_preflight_cancellation_leaves_no_partial_response(tmp_path) -> None:
    cancelled = Event()
    cancelled.set()
    raw = tmp_path / "raw"
    with pytest.raises(openligadb_source.OpenLigaDBCancelled):
        openligadb_source.capture_snapshot(
            raw,
            ["bl1"],
            fetcher=FakeOpenLigaDB(),
            cancel=cancelled,
            now=datetime(2026, 7, 15, tzinfo=UTC),
        )
    assert not list(raw.rglob("*.part"))


def test_atomic_write_failure_leaves_no_partial_response(monkeypatch, tmp_path) -> None:
    def fail_replace(*_args):
        raise OSError("simulated atomic rename failure")

    monkeypatch.setattr(openligadb_source.os, "replace", fail_replace)
    raw = tmp_path / "raw"
    with pytest.raises(OSError, match="simulated atomic rename failure"):
        openligadb_source.capture_snapshot(
            raw,
            ["bl1"],
            fetcher=FakeOpenLigaDB(),
            now=datetime(2026, 7, 15, tzinfo=UTC),
        )
    assert not list(raw.rglob("*.part"))


def test_generation_isolated_readonly_provenanced_and_display_only(monkeypatch, tmp_path) -> None:
    manifest = _install(monkeypatch, tmp_path)
    assert manifest["display_only"] is True
    assert manifest["license"] == "ODbL-1.0"
    active, fallback = openligadb_state.active_generation()
    assert active is not None and fallback is False
    assert len(list(openligadb_state.generations_dir().iterdir())) == 1

    result = openligadb_overlay.list_matches(shortcut="bl1")
    assert result["display_only"] is True
    assert result["identity_policy"].startswith("OpenLigaDB source ids only")
    assert len(result["matches"]) == 1
    match = result["matches"][0]
    assert match["source_match_id"] == 83161
    assert match["core_relation"] == "not_compared"
    assert match["provenance"]["source_id"] == "openligadb"
    assert len(match["provenance"]["raw_sha256"]) == 64

    competitions = openligadb_overlay.list_competitions()
    assert competitions["attribution"] == openligadb_source.ATTRIBUTION
    assert competitions["competitions"][0]["provenance"]["source_id"] == "openligadb"
    assert len(competitions["competitions"][0]["provenance"]["raw_sha256"]) == 64

    database = openligadb_state.active_database()
    assert database is not None
    connection = openligadb_state.open_readonly_database(database)
    try:
        create_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'matches'"
        ).fetchone()[0]
        assert "core_match_id" not in create_sql.casefold()
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute("ATTACH DATABASE ':memory:' AS core")
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute("DELETE FROM matches")
    finally:
        connection.close()


def test_identical_raw_bodies_from_distinct_endpoints_do_not_collide(tmp_path) -> None:
    staging = tmp_path / "duplicate-body"
    staging.mkdir()
    snapshot = _snapshot(staging)
    original = next(
        receipt
        for receipt in snapshot["receipts"]
        if receipt["endpoint"] == "/getlastchangedate/bl1/2026/1"
    )
    duplicate_path = Path("bl1/groups/002-last-change.json")
    body = (staging / "raw" / original["path"]).read_bytes()
    (staging / "raw" / duplicate_path).write_bytes(body)
    snapshot["receipts"].append(
        {
            **original,
            "path": duplicate_path.as_posix(),
            "endpoint": "/getlastchangedate/bl1/2026/2",
        }
    )

    openligadb_overlay.write_generation(staging, snapshot)
    connection = sqlite3.connect(staging / "overlay.sqlite3")
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM raw_responses WHERE sha256 = ?", (original["sha256"],)
        ).fetchone() == (2,)
    finally:
        connection.close()


def test_finished_match_without_one_final_result_never_activates(monkeypatch, tmp_path) -> None:
    _ledger(monkeypatch, tmp_path)
    staging = openligadb_state.staging_dir() / "conflict"
    staging.mkdir(parents=True)
    snapshot = _snapshot(staging, FakeOpenLigaDB(finished_without_final=True))
    with pytest.raises(openligadb_source.OpenLigaDBConflict, match="unambiguous final"):
        openligadb_overlay.write_generation(staging, snapshot)
    assert openligadb_state.active_database() is None


def test_two_generation_rollback_and_corrupt_active_lkg_fallback(monkeypatch, tmp_path) -> None:
    first = _install(monkeypatch, tmp_path)
    staging = openligadb_state.staging_dir() / "second"
    staging.mkdir(parents=True)
    second_snapshot = _snapshot(
        staging,
        FakeOpenLigaDB(match_id=83162, last_change="2026-07-16T01:00:00"),
    )
    second = openligadb_overlay.write_generation(staging, second_snapshot)
    installed = openligadb_state.install_generation(staging, second["generation_id"])
    openligadb_state.activate_generation(installed.name, activated_at_utc="2026-07-16T02:00:00Z")
    assert second["generation_id"] != first["generation_id"]
    assert len(list(openligadb_state.generations_dir().iterdir())) == 2

    rolled = openligadb_state.rollback(activated_at_utc="2026-07-16T03:00:00Z")
    assert rolled["active_generation_id"] == first["generation_id"]
    active_database = openligadb_state.active_database()
    assert active_database is not None
    active_database.chmod(0o644)
    active_database.write_bytes(b"corrupt")
    fallback, used_previous = openligadb_state.active_generation()
    assert fallback is not None and fallback.name == second["generation_id"]
    assert used_previous is True


def test_backend_consent_defaults_disabled_and_delete_preserves_siblings(
    monkeypatch, tmp_path
) -> None:
    ledger = _ledger(monkeypatch, tmp_path)
    sibling_refresh = ledger.parent / "refresh" / "keep.txt"
    sibling_refresh.parent.mkdir(parents=True)
    sibling_refresh.write_text("keep", encoding="utf-8")
    ledger_file = ledger / "keep.json"
    ledger_file.write_text("{}", encoding="utf-8")
    client = TestClient(server_main.app)

    initial = client.get("/api/v1/overlays/openligadb/status")
    assert initial.status_code == 200
    assert initial.json()["enabled"] is False
    assert client.get("/api/v1/overlays/openligadb/matches").status_code == 409
    rejected = client.put("/api/v1/overlays/openligadb/settings", json={"enabled": True})
    assert rejected.status_code == 409
    enabled = client.put(
        "/api/v1/overlays/openligadb/settings",
        json={
            "enabled": True,
            "accept_odbl": True,
            "refresh_policy": "manual",
            "selected_competitions": ["bl1"],
        },
    )
    assert enabled.status_code == 200
    assert enabled.json()["license"]["accepted_at_utc"]
    deleted = client.delete("/api/v1/overlays/openligadb")
    assert deleted.status_code == 200
    assert ledger_file.is_file()
    assert sibling_refresh.read_text(encoding="utf-8") == "keep"
    assert client.get("/api/v1/overlays/openligadb/status").json()["enabled"] is False


def test_coordinator_activates_atomically_then_reports_unchanged(monkeypatch, tmp_path) -> None:
    ledger = _ledger(monkeypatch, tmp_path)
    sealed = ledger / "fa_user_seal.json"
    sealed.write_text('{"immutable":"user"}\n', encoding="utf-8")
    sealed_before = sealed.read_bytes()
    openligadb_state.save_settings(
        {
            "enabled": True,
            "refresh_policy": "while_open",
            "selected_competitions": ["bl1"],
            "license_accepted_at_utc": "2026-07-15T00:00:00Z",
        }
    )
    coordinator = openligadb_jobs.OpenLigaDBCoordinator()
    first_source = FakeOpenLigaDB()
    job, _ = coordinator.start(trigger="manual", fetcher=first_source)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        current = coordinator.get(job["job_id"])
        if current and current["state"] not in ("queued", "running"):
            break
        time.sleep(0.01)
    assert current is not None and current["state"] == "done", current
    assert current["result"]["activated"] is True
    first_generation = current["result"]["active_generation_id"]
    assert any(path.startswith("/getmatchdata/") for path in first_source.paths)

    second_source = FakeOpenLigaDB()
    second, _ = coordinator.start(trigger="manual", fetcher=second_source)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        current = coordinator.get(second["job_id"])
        if current and current["state"] not in ("queued", "running"):
            break
        time.sleep(0.01)
    assert current is not None and current["state"] == "done", current
    assert current["result"] == {
        "activated": False,
        "reason": "unchanged",
        "active_generation_id": first_generation,
        "content_revision": current["result"]["content_revision"],
    }
    assert not any(path.startswith("/getmatchdata/") for path in second_source.paths)
    assert len(list(openligadb_state.generations_dir().iterdir())) == 1
    assert sealed.read_bytes() == sealed_before

    failed, _ = coordinator.start(trigger="manual", fetcher=OfflineOpenLigaDB())
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        current = coordinator.get(failed["job_id"])
        if current and current["state"] not in ("queued", "running"):
            break
        time.sleep(0.01)
    assert current is not None and current["state"] == "failed", current
    assert current["error"]["code"] == "offline"
    active, _ = openligadb_state.active_generation()
    assert active is not None and active.name == first_generation
    assert openligadb_state.load_state()["health"] == "backoff"
    assert sealed.read_bytes() == sealed_before


def test_terminal_job_is_not_deduplicated_while_worker_unwinds(monkeypatch, tmp_path) -> None:
    _ledger(monkeypatch, tmp_path)
    openligadb_state.save_settings(
        {
            "enabled": True,
            "refresh_policy": "while_open",
            "selected_competitions": ["bl1"],
            "license_accepted_at_utc": "2026-07-15T00:00:00Z",
        }
    )
    coordinator = openligadb_jobs.OpenLigaDBCoordinator()
    terminal_persisted = Event()
    release_worker = Event()
    original_finish = coordinator._finish

    def finish_then_wait(result: dict) -> None:
        original_finish(result)
        if not terminal_persisted.is_set():
            terminal_persisted.set()
            release_worker.wait(timeout=5)

    monkeypatch.setattr(coordinator, "_finish", finish_then_wait)
    first, _ = coordinator.start(trigger="manual", fetcher=FakeOpenLigaDB())
    assert terminal_persisted.wait(timeout=5)
    assert coordinator.get(first["job_id"])["state"] == "done"

    try:
        second, deduplicated = coordinator.start(trigger="manual", fetcher=FakeOpenLigaDB())
        assert deduplicated is False
        assert second["job_id"] != first["job_id"]
    finally:
        release_worker.set()

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        current = coordinator.get(second["job_id"])
        if current and current["state"] not in ("queued", "running"):
            break
        time.sleep(0.01)
    assert current is not None and current["state"] == "done", current
    assert current["result"]["reason"] == "unchanged"


def test_status_matches_published_contract(monkeypatch, tmp_path) -> None:
    _ledger(monkeypatch, tmp_path)
    payload = TestClient(server_main.app).get("/api/v1/overlays/openligadb/status").json()
    schema_path = (
        Path(__file__).resolve().parents[2] / "docs/contracts/openligadb_overlay_api.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


def test_runtime_path_is_a_sibling_not_the_ledger_or_cc0_refresh(monkeypatch, tmp_path) -> None:
    ledger = _ledger(monkeypatch, tmp_path)
    assert runtime.openligadb_dir() == ledger.parent / "overlays" / "openligadb"
    assert runtime.openligadb_dir() != runtime.refresh_dir()
    assert runtime.openligadb_dir() != runtime.data_dir()
