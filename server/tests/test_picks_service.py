from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest
from golavo_server import analysis, matches, picks

COLUMNS = [
    "match_id",
    "date",
    "kickoff_utc",
    "home_team",
    "away_team",
    "home_norm",
    "away_norm",
    "home_score",
    "away_score",
    "is_complete",
    "tournament",
    "competition",
    "city",
    "country",
    "neutral",
    "source_id",
    "source_kind",
]


def _row(
    match_id: str = "m_up",
    *,
    kickoff: str = "2026-08-01T12:00:00Z",
    home_score: int | None = None,
    away_score: int | None = None,
) -> dict:
    complete = home_score is not None and away_score is not None
    return {
        "match_id": match_id,
        "date": kickoff[:10],
        "kickoff_utc": kickoff,
        "home_team": "Aland",
        "away_team": "Borda",
        "home_norm": "aland",
        "away_norm": "borda",
        "home_score": home_score,
        "away_score": away_score,
        "is_complete": complete,
        "tournament": "Test Cup",
        "competition": "Test Cup",
        "city": "City",
        "country": "Country",
        "neutral": False,
        "source_id": "test-source",
        "source_kind": "club",
    }


def _write_index(path: Path, rows: list[dict]) -> None:
    frame = pd.DataFrame(rows, columns=COLUMNS)
    frame["date"] = pd.to_datetime(frame["date"])
    frame["kickoff_utc"] = pd.to_datetime(frame["kickoff_utc"], utc=True)
    frame["home_score"] = pd.array(frame["home_score"], dtype="Int16")
    frame["away_score"] = pd.array(frame["away_score"], dtype="Int16")
    frame["is_complete"] = frame["is_complete"].astype(bool)
    frame["neutral"] = pd.array(frame["neutral"], dtype="boolean")
    for column in (
        "match_id",
        "home_team",
        "away_team",
        "home_norm",
        "away_norm",
        "tournament",
        "competition",
        "city",
        "country",
        "source_id",
        "source_kind",
    ):
        frame[column] = frame[column].astype("string")
    frame.to_parquet(path)
    matches.reset_cache()


def _analysis() -> dict:
    models = []
    for family in ("dixon_coles", "poisson_independent", "bivariate_poisson"):
        models.append(
            {
                "family": family,
                "abstained": False,
                "probs": {"home": 0.6, "draw": 0.2, "away": 0.2},
                "score_matrix": {"most_likely": {"home": 2, "away": 1, "probability": 0.15}},
            }
        )
    models.extend(
        [
            {
                "family": "elo_ordlogit",
                "abstained": False,
                "probs": {"home": 0.6, "draw": 0.2, "away": 0.2},
                "score_matrix": None,
            },
            {
                "family": "climatological",
                "abstained": True,
                "probs": None,
                "score_matrix": None,
            },
        ]
    )
    return {
        "available": True,
        "reason": None,
        "analysis": {
            "schema_version": "0.5.0",
            "information_cutoff_utc": "2026-08-01T11:59:59Z",
            "models": models,
        },
    }


@pytest.fixture
def service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    index = tmp_path / "index.parquet"
    _write_index(index, [_row(), _row("m_done", home_score=1, away_score=0)])
    monkeypatch.setattr(matches, "INDEX_PATH", index)
    monkeypatch.setattr(matches, "index_fingerprint", lambda: "idx-test")
    monkeypatch.setattr(analysis, "match_analysis", lambda match_id: _analysis())
    matches.reset_cache()
    return tmp_path / "ledger", index


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def test_draft_create_edit_and_audit(service: tuple[Path, Path]) -> None:
    ledger, _ = service
    first = picks.save_pick("m_up", 1, 0, ledger=ledger, now_utc=_dt("2026-08-01T10:00:00Z"))
    second = picks.save_pick("m_up", 2, 2, ledger=ledger, now_utc=_dt("2026-08-01T10:05:00Z"))
    assert first["status"] == "draft"
    assert second["record"]["created_at_utc"] == first["record"]["created_at_utc"]
    assert second["record"]["user_pick"] == {
        "home_goals": 2,
        "away_goals": 2,
        "outcome": "draw",
    }
    lines = (ledger / "picks" / "audit.jsonl").read_text().splitlines()
    assert [json.loads(line)["event"] for line in lines] == ["pick_saved", "pick_saved"]


def test_clock_edge_freeze_is_deterministic_and_repairs_leftover_draft(
    service: tuple[Path, Path], tmp_path: Path
) -> None:
    ledger, _ = service
    draft = picks.save_pick("m_up", 2, 1, ledger=ledger, now_utc=_dt("2026-08-01T11:59:59Z"))[
        "record"
    ]
    with pytest.raises(picks.PickError) as exc:
        picks.save_pick("m_up", 3, 1, ledger=ledger, now_utc=_dt("2026-08-01T12:00:00Z"))
    assert (exc.value.status_code, exc.value.reason_code) == (409, "pick_locked")

    locked = picks.get_pick("m_up", ledger=ledger, now_utc=_dt("2026-08-01T12:30:00Z"))
    assert locked is not None
    assert locked["record"]["locked_at_utc"] == "2026-08-01T12:00:00Z"
    first_id = locked["record"]["pick_id"]

    other = tmp_path / "other-ledger"
    picks._write_draft(other, draft)
    other_locked = picks.get_pick("m_up", ledger=other, now_utc=_dt("2026-08-02T12:00:00Z"))
    assert other_locked is not None and other_locked["record"]["pick_id"] == first_id

    # Simulate a crash after immutable write but before draft deletion.
    picks._write_draft(ledger, draft)
    picks.get_pick("m_up", ledger=ledger, now_utc=_dt("2026-08-03T12:00:00Z"))
    assert not (ledger / "picks" / "drafts" / "m_up.json").exists()


def test_refresh_can_tighten_but_never_reopen(service: tuple[Path, Path], tmp_path: Path) -> None:
    ledger, index = service
    picks.save_pick("m_up", 1, 0, ledger=ledger, now_utc=_dt("2026-08-01T09:00:00Z"))

    _write_index(index, [_row(kickoff="2026-08-01T14:00:00Z")])
    still_locks = picks.get_pick("m_up", ledger=ledger, now_utc=_dt("2026-08-01T12:00:00Z"))
    assert still_locks is not None and still_locks["status"] == "locked"
    assert still_locks["record"]["lock_at_utc"] == "2026-08-01T12:00:00Z"

    earlier_ledger = tmp_path / "earlier-ledger"
    _write_index(index, [_row()])
    picks.save_pick("m_up", 1, 0, ledger=earlier_ledger, now_utc=_dt("2026-08-01T09:00:00Z"))
    _write_index(index, [_row(kickoff="2026-08-01T10:00:00Z")])
    tightened = picks.get_pick("m_up", ledger=earlier_ledger, now_utc=_dt("2026-08-01T10:00:00Z"))
    assert tightened is not None
    assert tightened["record"]["lock_at_utc"] == "2026-08-01T10:00:00Z"


def test_typed_failures_write_nothing(
    service: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger, _ = service
    with pytest.raises(picks.PickError) as invalid:
        picks.save_pick("m_up", True, 1, ledger=ledger)
    assert invalid.value.reason_code == "invalid_score"
    with pytest.raises(picks.PickError) as complete:
        picks.save_pick("m_done", 1, 0, ledger=ledger)
    assert complete.value.reason_code == "fixture_complete"
    with pytest.raises(picks.PickError) as unknown:
        picks.save_pick("missing", 1, 0, ledger=ledger)
    assert unknown.value.status_code == 404

    monkeypatch.setattr(
        analysis,
        "match_analysis",
        lambda match_id: {"available": False, "reason": "no fit", "analysis": None},
    )
    with pytest.raises(picks.PickError) as unavailable:
        picks.save_pick("m_up", 1, 0, ledger=ledger)
    assert unavailable.value.reason_code == "analysis_unavailable"
    assert not (ledger / "picks" / "drafts" / "m_up.json").exists()


def test_scored_view_outcome_only_and_fixture_fallback(service: tuple[Path, Path]) -> None:
    ledger, index = service
    picks.save_pick("m_up", 3, 0, ledger=ledger, now_utc=_dt("2026-08-01T10:00:00Z"))
    picks.get_pick("m_up", ledger=ledger, now_utc=_dt("2026-08-01T12:00:00Z"))

    # Result arrives under a new id; fixture key fallback keeps the pick alive.
    _write_index(index, [_row("m_rekeyed", home_score=4, away_score=0)])
    scored = picks.get_pick("m_rekeyed", ledger=ledger, now_utc=_dt("2026-08-02T12:00:00Z"))
    assert scored is not None and scored["status"] == "scored"
    elo = next(row for row in scored["scoring"]["rivals"] if row["family"] == "elo_ordlogit")
    assert elo == {"family": "elo_ordlogit", "exact": 0, "outcome": 1, "total": 1}

    _write_index(index, [])
    void = picks.get_pick("m_up", ledger=ledger, now_utc=_dt("2026-08-03T12:00:00Z"))
    assert void is not None and void["status"] == "void"


def test_list_summary_pagination_tamper_and_seal_non_interference(
    service: tuple[Path, Path],
) -> None:
    ledger, index = service
    picks.save_pick("m_up", 2, 1, ledger=ledger, now_utc=_dt("2026-08-01T10:00:00Z"))
    picks.get_pick("m_up", ledger=ledger, now_utc=_dt("2026-08-01T12:00:00Z"))
    _write_index(index, [_row(home_score=2, away_score=1)])

    listed = picks.list_picks(ledger=ledger, limit=1, offset=0)
    assert listed["total"] == 1 and len(listed["items"]) == 1
    summary = picks.picks_summary(ledger=ledger, season="2026-27")
    assert summary["counts"]["scored"] == 1
    assert not list(ledger.glob("fa_*.json"))

    locked_path = next((ledger / "picks").glob("pk_*.json"))
    raw = json.loads(locked_path.read_text())
    raw["user_pick"]["home_goals"] = 9
    locked_path.write_text(json.dumps(raw))
    with pytest.raises(picks.PickError) as corrupt:
        picks.get_pick("m_up", ledger=ledger)
    assert corrupt.value.reason_code == "integrity_error"
    assert picks.list_picks(ledger=ledger)["total"] == 0


def test_concurrent_saves_serialize_to_one_valid_draft(service: tuple[Path, Path]) -> None:
    ledger, _ = service

    def save(score: int) -> None:
        picks.save_pick("m_up", score, 1, ledger=ledger, now_utc=_dt("2026-08-01T10:00:00Z"))

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(save, (1, 2)))
    view = picks.get_pick("m_up", ledger=ledger, now_utc=_dt("2026-08-01T10:30:00Z"))
    assert view is not None and view["record"]["user_pick"]["home_goals"] in {1, 2}
    assert len(list((ledger / "picks" / "drafts").glob("*.json"))) == 1


def test_auto_freeze_replace_is_linearized_before_repoint(
    service: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ledger, old_index = service
    old_meta = tmp_path / "old.meta.json"
    new_meta = tmp_path / "new.meta.json"
    old_meta.write_text('{"generation":"old"}', encoding="utf-8")
    new_meta.write_text('{"generation":"new"}', encoding="utf-8")
    new_index = tmp_path / "new.parquet"
    _write_index(new_index, [_row()])
    monkeypatch.setattr(matches, "INDEX_PATH", old_index)
    monkeypatch.setattr(matches, "INDEX_META_PATH", old_meta)
    monkeypatch.setattr(matches, "GOALSCORERS_PATH", matches.GOALSCORERS_PATH)
    monkeypatch.setattr(matches, "SHOOTOUTS_PATH", matches.SHOOTOUTS_PATH)
    monkeypatch.setattr(matches, "ALIASES_PATH", matches.ALIASES_PATH)
    matches.reset_cache()
    picks.save_pick("m_up", 2, 1, ledger=ledger, now_utc=_dt("2026-08-01T10:00:00Z"))
    monkeypatch.setattr(
        matches,
        "_resolve_index_paths",
        lambda: {
            "index": new_index,
            "meta": new_meta,
            "goalscorers": tmp_path / "new-goals.parquet",
            "shootouts": tmp_path / "new-shootouts.parquet",
            "aliases": tmp_path / "new-aliases.json",
        },
    )

    replace_started = threading.Event()
    allow_replace = threading.Event()
    repoint_done = threading.Event()
    real_replace = os.replace

    def blocked_replace(source: Path, destination: Path) -> None:
        if Path(destination).name.startswith("pk_"):
            replace_started.set()
            assert allow_replace.wait(5), "pick replace barrier timed out"
        real_replace(source, destination)

    monkeypatch.setattr(os, "replace", blocked_replace)
    result: list[dict | None] = []
    freezer = threading.Thread(
        target=lambda: result.append(
            picks.get_pick(
                "m_up", ledger=ledger, now_utc=_dt("2026-08-01T12:00:00Z")
            )
        ),
        daemon=True,
    )
    freezer.start()
    assert replace_started.wait(5), "auto-freeze never reached atomic replace"
    repointer = threading.Thread(
        target=lambda: (matches.repoint_to_refreshed(), repoint_done.set()),
        daemon=True,
    )
    repointer.start()
    assert not repoint_done.wait(0.1), "repoint crossed an in-progress pick commit"
    allow_replace.set()
    freezer.join(5)
    repointer.join(5)
    assert not freezer.is_alive() and not repointer.is_alive()
    assert result[0] is not None and result[0]["status"] == "locked"
    assert not (ledger / "picks" / "drafts" / "m_up.json").exists()
    assert len(list((ledger / "picks").glob("pk_*.json"))) == 1
    assert repoint_done.is_set()


def test_read_degrades_to_virtual_lock_when_ledger_is_unwritable(
    service: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger, _ = service
    picks.save_pick("m_up", 1, 0, ledger=ledger, now_utc=_dt("2026-08-01T10:00:00Z"))

    def unwritable(ledger: Path, record: dict, **_kwargs: object) -> Path:
        raise OSError

    monkeypatch.setattr(picks, "_write_locked", unwritable)
    view = picks.get_pick("m_up", ledger=ledger, now_utc=_dt("2026-08-01T12:00:00Z"))
    assert view is not None and view["status"] == "locked"
