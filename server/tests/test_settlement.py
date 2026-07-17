"""Post-match settlement: trusted result bytes -> immutable scored successor."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from golavo_core.artifacts import seal_forecast
from golavo_core.calibration import calibration_summary
from golavo_server import main as server_main
from golavo_server import settlement
from golavo_server.settlement import (
    SettlementError,
    SourceResults,
    martj42_results,
    settle_pending_forecasts,
    world_cup_results,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK = REPO_ROOT / "packs/martj42-internationals-f73286079f8c"


def _snapshot(source_id: str, *, committed_at: str = "2026-07-15T04:00:00Z") -> dict:
    ref = "a" * 40 if source_id.startswith("martj42") else "b" * 40
    return {
        "snapshot_id": f"sp_{ref[:12]}",
        "source_id": source_id,
        "url": (
            "https://github.com/martj42/international_results"
            if source_id.startswith("martj42")
            else "https://github.com/openfootball/worldcup.json"
        ),
        "upstream_ref": ref,
        "upstream_committed_at_utc": committed_at,
        "retrieved_at_utc": "2026-07-15T05:00:00Z",
        "sha256": hashlib.sha256(source_id.encode()).hexdigest(),
        "license": "CC0-1.0",
    }


def _sealed_france_spain(ledger: Path) -> Path:
    return seal_forecast(
        pack_dir=PACK,
        output_dir=ledger,
        date="2026-07-14",
        home_team="France",
        away_team="Spain",
        as_of_utc="2026-07-13T05:56:16Z",
    )


def test_world_cup_result_settles_when_primary_source_still_has_na(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    sealed = _sealed_france_spain(ledger)
    key = ("2026-07-14", "france", "spain", "fifa world cup")

    def martj_loader(**_kwargs) -> SourceResults:
        return SourceResults(
            "martj42-international-results",
            _snapshot("martj42-international-results"),
            {},
        )

    def world_cup_loader(_year: str, **_kwargs) -> SourceResults:
        return SourceResults(
            "openfootball-worldcup-json",
            _snapshot("openfootball-worldcup-json"),
            {key: (0, 2)},
        )

    report = settle_pending_forecasts(
        ledger,
        now=datetime(2026, 7, 15, 5, tzinfo=UTC),
        martj_loader=martj_loader,
        world_cup_loader=world_cup_loader,
    )

    assert report["pending_before_check"] == 1
    assert report["errors"] == []
    assert report["scored"] == [
        {
            "sealed_artifact_id": sealed.stem,
            "scored_artifact_id": report["scored"][0]["scored_artifact_id"],
            "home_team": "France",
            "away_team": "Spain",
            "home_goals": 0,
            "away_goals": 2,
            "source_id": "openfootball-worldcup-json",
        }
    ]
    chain = calibration_summary(ledger)["chains"][0]
    assert chain["resolution"]["status"] == "scored"
    assert chain["resolution"]["actual"] == {
        "home_goals": 0,
        "away_goals": 2,
        "outcome": "away",
    }
    assert chain["resolution"]["metrics"]["log_loss"] > 0


def test_settlement_is_idempotent_and_does_not_refetch_resolved_seal(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    _sealed_france_spain(ledger)
    key = ("2026-07-14", "france", "spain", "fifa world cup")
    empty = SourceResults(
        "martj42-international-results", _snapshot("martj42-international-results"), {}
    )
    result = SourceResults(
        "openfootball-worldcup-json",
        _snapshot("openfootball-worldcup-json"),
        {key: (0, 2)},
    )
    settle_pending_forecasts(
        ledger,
        now=datetime(2026, 7, 15, 5, tzinfo=UTC),
        martj_loader=lambda **_kwargs: empty,
        world_cup_loader=lambda _year, **_kwargs: result,
    )

    def unexpected(**_kwargs):
        raise AssertionError("resolved ledgers must not hit a result source again")

    second = settle_pending_forecasts(
        ledger,
        now=datetime(2026, 7, 15, 6, tzinfo=UTC),
        martj_loader=unexpected,
        world_cup_loader=unexpected,
    )
    assert second["pending_before_check"] == 0
    assert second["sources_checked"] == []
    assert second["scored"] == []
    assert len(list(ledger.glob("fa_*.json"))) == 2


def test_conflicting_trusted_results_fail_closed(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    sealed = _sealed_france_spain(ledger)
    key = ("2026-07-14", "france", "spain", "fifa world cup")
    martj = SourceResults(
        "martj42-international-results",
        _snapshot("martj42-international-results"),
        {key: (1, 2)},
    )
    world_cup = SourceResults(
        "openfootball-worldcup-json",
        _snapshot("openfootball-worldcup-json"),
        {key: (0, 2)},
    )
    report = settle_pending_forecasts(
        ledger,
        now=datetime(2026, 7, 15, 5, tzinfo=UTC),
        martj_loader=lambda **_kwargs: martj,
        world_cup_loader=lambda _year, **_kwargs: world_cup,
    )
    assert report["scored"] == []
    assert report["still_pending"] == [
        {"artifact_id": sealed.stem, "reason": "source_conflict"}
    ]
    assert any(error["source_id"] == "consensus" for error in report["errors"])
    assert len(list(ledger.glob("fa_*.json"))) == 1


def test_recent_kickoff_is_deferred_without_network(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    sealed = _sealed_france_spain(ledger)

    def unexpected(**_kwargs):
        raise AssertionError("an in-progress match must not hit a result source")

    report = settle_pending_forecasts(
        ledger,
        now=datetime(2026, 7, 14, 20, tzinfo=UTC),
        martj_loader=unexpected,
        world_cup_loader=unexpected,
    )
    assert report["eligible"] == 0
    assert report["deferred_in_progress"] == [sealed.stem]


def test_a_club_seal_is_deferred_for_independent_confirmation_not_graded(tmp_path: Path) -> None:
    # Seal a real 2026-27 La Liga fixture, then settle after its kickoff. A club
    # prediction must never be graded on a single source: it is held pending two
    # independent sources, and the internationals result loaders are not consulted.
    esp_pack = REPO_ROOT / "packs/openfootball-esp-ll"
    ledger = tmp_path / "ledger"
    sealed = seal_forecast(
        pack_dir=esp_pack,
        output_dir=ledger,
        date="2026-08-16",
        home_team="Celta Vigo",
        away_team="Osasuna",
        as_of_utc="2026-08-01T00:00:00Z",
    )

    def unexpected(**_kwargs):
        raise AssertionError("a club seal must not hit an internationals result source")

    report = settle_pending_forecasts(
        ledger,
        now=datetime(2026, 9, 1, tzinfo=UTC),  # well after the club kickoff
        martj_loader=unexpected,
        world_cup_loader=unexpected,
    )

    assert report["eligible"] == 0
    assert report["awaiting_independent_confirmation"] == 1
    assert report["scored"] == []
    assert report["still_pending"] == [
        {"artifact_id": sealed.stem, "reason": "awaiting_independent_confirmation"}
    ]
    # The seal is untouched: no scored successor was written.
    assert len(list(ledger.glob("fa_*.json"))) == 1


def test_result_parsers_ignore_scheduled_rows_and_prefer_extra_time() -> None:
    csv_text = (
        "date,home_team,away_team,home_score,away_score,tournament,city,country,neutral\n"
        "1974-02-17,Tahiti,New Caledonia,2,1,Friendly,Papeete,Tahiti,FALSE\n"
        "1974-02-17,Tahiti,New Caledonia,1,2,Friendly,Papeete,Tahiti,FALSE\n"
        "2026-07-14,France,Spain,NA,NA,FIFA World Cup,Arlington,United States,TRUE\n"
        "2026-07-09,France,Morocco,2,0,FIFA World Cup,Atlanta,United States,TRUE\n"
    )
    target = {("2026-07-09", "france", "morocco", "fifa world cup")}
    # Historical same-day doubleheaders can share teams/competition. Filtering
    # to the exact unresolved fixture prevents an unrelated ambiguity from
    # blocking every current result check.
    assert martj42_results(csv_text, target) == {next(iter(target)): (2, 0)}
    assert world_cup_results(
        {
            "matches": [
                {
                    "date": "2026-07-14",
                    "team1": "France",
                    "team2": "Spain",
                    "score": {"ft": [1, 1], "et": [1, 2], "p": [4, 5]},
                }
            ]
        }
    ) == {("2026-07-14", "france", "spain", "fifa world cup"): (1, 2)}


def test_source_failure_is_reported_without_corrupting_ledger(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    sealed = _sealed_france_spain(ledger)

    def failed(**_kwargs):
        raise SettlementError("offline")

    report = settle_pending_forecasts(
        ledger,
        now=datetime(2026, 7, 15, 5, tzinfo=UTC),
        martj_loader=failed,
        world_cup_loader=lambda _year, **_kwargs: failed(),
    )
    assert report["scored"] == []
    assert report["still_pending"] == [
        {"artifact_id": sealed.stem, "reason": "result_not_published"}
    ]
    assert {error["source_id"] for error in report["errors"]} == {
        "martj42-international-results",
        "openfootball-worldcup-json",
    }
    assert len(list(ledger.glob("fa_*.json"))) == 1


def test_settlement_api_uses_the_writable_ledger_off_the_event_loop(
    monkeypatch, tmp_path: Path
) -> None:
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    expected = {
        "schema_version": "0.2.0",
        "checked_at_utc": "2026-07-15T05:00:00Z",
        "pending_before_check": 0,
        "eligible": 0,
        "deferred_in_progress": [],
        "sources_checked": [],
        "scored": [],
        "still_pending": [],
        "errors": [],
    }
    seen: list[Path] = []

    def fake_settle(path: Path) -> dict:
        seen.append(path)
        return expected

    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    monkeypatch.setattr(settlement, "settle_pending_forecasts", fake_settle)
    response = TestClient(server_main.app).post("/api/v1/forecasts/settle")
    assert response.status_code == 200
    assert response.json() == expected
    assert seen == [ledger]
