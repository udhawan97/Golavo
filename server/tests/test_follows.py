"""Local followed-match persistence, identity and API contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient
from golavo_server import follows
from golavo_server import main as server_main
from jsonschema import Draft202012Validator, FormatChecker


def _match(**updates: object) -> dict:
    value = {
        "match_id": "match-1",
        "kickoff_utc": "2026-07-20T00:00:00Z",
        "kickoff_precision": "day",
        "home_team": "France",
        "away_team": "Spain",
        "home_score": None,
        "away_score": None,
        "competition": "FIFA World Cup",
        "country": "United States",
        "city": "Dallas",
        "neutral": True,
        "is_complete": False,
        "source_kind": "international",
        "source_id": "openfootball-worldcup-json",
        "upstream_fixture_key": "openfootball-worldcup-json:2026:72",
        "provenance": {
            "identity": "openfootball-worldcup-json",
            "kickoff": "openfootball-worldcup-json",
            "venue": "openfootball-worldcup-json",
            "result": "openfootball-worldcup-json",
        },
        "forecasts": [],
    }
    value.update(updates)
    return value


def _frame(match: dict) -> pd.DataFrame:
    row = {
        **match,
        "date": str(match["kickoff_utc"])[:10],
        "home_norm": str(match["home_team"]).casefold(),
        "away_norm": str(match["away_team"]).casefold(),
        "identity_source_id": match["provenance"]["identity"],
        "kickoff_source_id": match["provenance"]["kickoff"],
        "venue_source_id": match["provenance"]["venue"],
        "result_source_id": match["provenance"]["result"],
    }
    row.pop("provenance")
    row.pop("forecasts")
    return pd.DataFrame([row])


def _status(ref: str = "a" * 40, health: str = "current") -> dict[str, dict]:
    return {
        "openfootball-worldcup-json": {
            "source_id": "openfootball-worldcup-json",
            "health": health,
            "active_ref": ref,
            "observed_ref": ref,
            "last_checked_at_utc": "2026-07-15T12:00:00Z",
        }
    }


def test_follow_is_idempotent_and_refollow_preserves_history(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    first, created = follows.follow_match(_match(), ledger=ledger)
    second, duplicated = follows.follow_match(_match(), ledger=ledger)
    assert created is True
    assert duplicated is False
    assert second["follow_id"] == first["follow_id"]

    unfollowed = follows.unfollow(first["follow_id"], ledger=ledger)
    assert unfollowed["subscription_state"] == "unfollowed"
    refollowed, recreated = follows.follow_match(_match(), ledger=ledger)
    assert recreated is True
    assert refollowed["follow_id"] == first["follow_id"]
    assert [event["event_type"] for event in refollowed["events"]] == [
        "refollowed",
        "unfollowed",
        "followed",
    ]


def test_reconcile_records_changes_once_and_repoints_exact_stable_key(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    followed, _ = follows.follow_match(_match(), ledger=ledger)
    changed = _match(
        match_id="match-2",
        kickoff_utc="2026-07-21T00:00:00Z",
        city="Houston",
        home_score=2,
        away_score=1,
        is_complete=True,
    )
    first = follows.reconcile(
        ledger=ledger,
        frame=_frame(changed),
        index_fingerprint="f" * 64,
        generation_id="g_" + "1" * 64,
        source_status=_status(),
    )
    assert len(first["event_ids"]) == 4
    current = follows.list_follows(ledger=ledger)["items"][0]
    assert current["follow_id"] == followed["follow_id"]
    assert current["canonical_match_id"] == "match-2"
    assert current["data_state"] == "completed"
    assert {event["event_type"] for event in current["events"]} >= {
        "match_repointed",
        "kickoff_changed",
        "venue_changed",
        "score_published",
    }

    repeated = follows.reconcile(
        ledger=ledger,
        frame=_frame(changed),
        index_fingerprint="f" * 64,
        generation_id="g_" + "1" * 64,
        source_status=_status(),
    )
    assert repeated["event_ids"] == []


def test_reconcile_never_fuzzy_merges_an_unstable_identity(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    original = _match(
        source_id="martj42-international-results",
        upstream_fixture_key="martj42-international-results:old-date:france:spain",
        provenance={
            "identity": "martj42-international-results",
            "kickoff": "martj42-international-results",
            "venue": "martj42-international-results",
            "result": "martj42-international-results",
        },
    )
    follows.follow_match(original, ledger=ledger)
    candidate = _match(
        match_id="new-id",
        source_id="martj42-international-results",
        upstream_fixture_key="martj42-international-results:new-date:france:spain",
        provenance=original["provenance"],
    )
    result = follows.reconcile(
        ledger=ledger,
        frame=_frame(candidate),
        index_fingerprint="f" * 64,
        generation_id=None,
        source_status={},
    )
    assert len(result["event_ids"]) == 1
    item = follows.list_follows(ledger=ledger)["items"][0]
    assert item["canonical_match_id"] == "match-1"
    assert item["resolution_state"] == "identity_unresolved"


def test_openligadb_cannot_enter_core_follow_store(tmp_path: Path) -> None:
    match = _match(source_id="openligadb")
    try:
        follows.follow_match(match, ledger=tmp_path / "ledger")
    except follows.FollowError as exc:
        assert exc.reason_code == "unsupported_follow_source"
    else:
        raise AssertionError("ODbL identities must fail closed")


def test_notifications_require_local_opt_in_and_claim_once(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    follows.follow_match(_match(), ledger=ledger)
    changed = _match(kickoff_utc="2026-07-21T00:00:00Z")
    follows.reconcile(
        ledger=ledger,
        frame=_frame(changed),
        index_fingerprint="f" * 64,
        generation_id="g_" + "2" * 64,
        source_status=_status("b" * 40),
    )
    assert follows.claim_notifications(ledger=ledger)["events"] == []
    follows.update_settings(True, ledger=ledger, notifications_supported=True)
    claim = follows.claim_notifications(ledger=ledger)
    assert claim["batch_id"].startswith("fn_")
    assert [event["event_type"] for event in claim["events"]] == ["kickoff_changed"]
    assert follows.claim_notifications(ledger=ledger)["events"] == []


def test_verified_completed_snapshot_reports_settlement_availability_without_mutating_seal(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    artifact = ledger / "fa_pending.json"
    artifact.write_text(
        json.dumps(
            {
                "artifact_id": "fa_pending",
                "status": "sealed",
                "match": {
                    "match_id": "match-1",
                    "kickoff_utc": "2026-07-20T00:00:00Z",
                    "home_team": "France",
                    "away_team": "Spain",
                },
                "forecast": {},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    sealed_bytes = artifact.read_bytes()
    follows.follow_match(_match(), ledger=ledger)
    completed = _match(home_score=2, away_score=1, is_complete=True)
    result = follows.reconcile(
        ledger=ledger,
        frame=_frame(completed),
        index_fingerprint="f" * 64,
        generation_id="g_" + "3" * 64,
        source_status=_status(),
    )
    events = follows.list_follows(ledger=ledger)["items"][0]["events"]
    assert "settlement_available" in {event["event_type"] for event in events}
    assert len(result["event_ids"]) == 2
    assert artifact.read_bytes() == sealed_bytes


def test_structured_refresh_conflict_keeps_active_snapshot(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    followed, _ = follows.follow_match(_match(), ledger=ledger)
    event_ids = follows.record_conflicts(
        [
            {
                "kind": "changed_sealed_fixture",
                "match_id": "match-1",
                "field": "kickoff_utc",
                "before": "2026-07-20T00:00:00Z",
                "candidate": "2026-07-21T00:00:00Z",
            }
        ],
        ledger=ledger,
        source_status=_status("b" * 40, health="conflict"),
    )
    assert len(event_ids) == 1
    current = follows.list_follows(ledger=ledger)["items"][0]
    assert current["follow_id"] == followed["follow_id"]
    assert current["data_state"] == "source_conflict"
    assert current["current"]["kickoff_utc"] == "2026-07-20T00:00:00Z"
    assert current["events"][0]["conflict"]["candidate"] == "2026-07-21T00:00:00Z"


def test_remove_history_is_scoped_to_follow_directory(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    seal = ledger / "fa_keep.json"
    seal.parent.mkdir(parents=True)
    seal.write_text("{}", encoding="utf-8")
    follows.follow_match(_match(), ledger=ledger)
    result = follows.remove_history(ledger=ledger)
    assert result["removed"] is True
    assert seal.read_text(encoding="utf-8") == "{}"
    assert follows.list_follows(ledger=ledger)["items"] == []


def test_follow_api_and_contract(monkeypatch, tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    monkeypatch.setattr(
        server_main.matches,
        "get_match",
        lambda match_id, **_kwargs: {
            "schema_version": "0.2.0",
            "match": _match(match_id=match_id),
            "linked_by": None,
        },
    )
    monkeypatch.setattr(server_main.matches, "index_fingerprint", lambda: "f" * 64)
    monkeypatch.setattr(
        server_main.refresh_jobs,
        "status",
        lambda: {
            "active_generation": {"generation_id": "g_" + "1" * 64},
            "sources": [next(iter(_status().values()))],
        },
    )
    client = TestClient(server_main.app)
    created = client.put("/api/v1/matches/match-1/follow")
    assert created.status_code == 201
    assert client.put("/api/v1/matches/match-1/follow").status_code == 200
    listing = client.get("/api/v1/follows").json()

    schema = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "docs/contracts/followed_match.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(listing)

    follow_id = listing["items"][0]["follow_id"]
    assert client.delete(f"/api/v1/follows/{follow_id}").status_code == 200
    assert client.request("DELETE", "/api/v1/follows/history", json={}).status_code == 422
    removed = client.request(
        "DELETE",
        "/api/v1/follows/history",
        json={"confirm": "remove_follow_history"},
    )
    assert removed.status_code == 200


def test_follow_runtime_path_is_inside_ledger(monkeypatch, tmp_path: Path) -> None:
    from golavo_server import runtime

    ledger = tmp_path / "Application Support" / "Golavo" / "ledger"
    monkeypatch.setenv("GOLAVO_DATA_DIR", str(ledger))
    assert runtime.follows_dir() == ledger / "follows"
