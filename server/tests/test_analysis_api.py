"""Tests for the on-demand MatchAnalysis + recent-matches routes.

Builds a tiny typed index (the frozen 17 columns) with enough history for a
non-abstaining council, repoints ``matches.INDEX_PATH`` at it, and drives the API
through a TestClient. Guards the honest shape (two voices + baseline), the
Replay/Preview split, leak-safe cutoff, and the empty-upcoming rail state.
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from golavo_server import analysis as server_analysis
from golavo_server import main as server_main
from golavo_server import matches

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
_INTL = "martj42-international-results"
TEAMS = ["Alpha", "Beta", "Gamma", "Delta"]


def _row(match_id, date, home, away, hs, aws, complete):
    return {
        "match_id": match_id,
        "date": date,
        "kickoff_utc": f"{date}T00:00:00Z",
        "home_team": home,
        "away_team": away,
        "home_norm": home.lower(),
        "away_norm": away.lower(),
        "home_score": hs,
        "away_score": aws,
        "is_complete": complete,
        "tournament": "Friendly",
        "competition": "Friendly",
        "city": "City",
        "country": "Country",
        "neutral": False,
        "source_id": _INTL,
        "source_kind": "international",
    }


def _rows() -> list[dict]:
    rows: list[dict] = []
    n = 0
    for round_no in range(6):
        for i in range(len(TEAMS)):
            for j in range(len(TEAMS)):
                if i == j:
                    continue
                n += 1
                month = 1 + round_no
                rows.append(
                    _row(
                        f"m_h{n:04d}",
                        f"2024-{month:02d}-{(n % 27) + 1:02d}",
                        TEAMS[i],
                        TEAMS[j],
                        (n % 3),
                        (n % 2),
                        True,
                    )
                )
    # A completed target fixture (replay) and a far-future one (preview).
    rows.append(_row("m_target", "2025-01-15", "Alpha", "Beta", 2, 1, True))
    rows.append(_row("m_future", "2030-06-01", "Alpha", "Beta", None, None, False))
    return rows


def _build_index(path: Path, rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["kickoff_utc"] = pd.to_datetime(df["kickoff_utc"], utc=True)
    df["home_score"] = pd.array(list(df["home_score"]), dtype="Int16")
    df["away_score"] = pd.array(list(df["away_score"]), dtype="Int16")
    df["is_complete"] = df["is_complete"].astype(bool)
    df["neutral"] = pd.array(list(df["neutral"]), dtype="boolean")
    for col in (
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
        df[col] = df[col].astype("string")
    df[COLUMNS].to_parquet(path)


@pytest.fixture(autouse=True)
def _reset_cache():
    matches.reset_cache()
    server_analysis.reset_cache()
    yield
    matches.reset_cache()
    server_analysis.reset_cache()


@pytest.fixture
def client(tmp_path, monkeypatch):
    index_path = tmp_path / "matches_index.parquet"
    _build_index(index_path, _rows())
    monkeypatch.setattr(matches, "INDEX_PATH", index_path)
    empty_ledger = tmp_path / "ledger"
    empty_ledger.mkdir()
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", empty_ledger)
    return TestClient(server_main.app)


def test_replay_analysis_shape_and_leak_safe_cutoff(client):
    body = client.get("/api/v1/matches/m_target/analysis").json()
    assert body["provenance"]["index_sha256"] == matches.index_fingerprint()
    assert body["available"] is True
    a = body["analysis"]
    assert a["schema_version"] == "0.5.0"
    assert a["analysis_kind"] == "replay"
    # 0.4.x additions present on a modelled fixture.
    assert set(a["team_form"]) == {"Alpha", "Beta"}
    assert a["team_style"] is not None
    assert a["abstained"] is False
    # Two voices, never five; the score grid is the goal voice's.
    assert a["council"]["voices"] == 2
    assert a["score_matrix_family"] == "dixon_coles"
    # 0.4.1: exact BTTS + clean-sheet marginals from the goal voice's full matrix.
    dm = a["derived_markets"]
    assert dm is not None and dm["source"] == "full_resolution_matrix"
    assert abs(dm["btts"]["yes"] + dm["btts"]["no"] - 1.0) < 1e-6
    assert 0.0 <= dm["clean_sheets"]["home"] <= 1.0
    roles = {m["family"]: m["role"] for m in a["models"]}
    assert roles["elo_ordlogit"] == "voice"
    assert roles["dixon_coles"] == "voice"
    assert roles["poisson_independent"] == "variant"
    assert roles["bivariate_poisson"] == "variant"
    assert roles["climatological"] == "baseline"
    # Leak guard surfaced to the client: cutoff strictly precedes kickoff.
    assert a["information_cutoff_utc"] < a["match"]["kickoff_utc"]


def test_preview_analysis_kind(client):
    a = client.get("/api/v1/matches/m_future/analysis").json()["analysis"]
    assert a["analysis_kind"] == "preview"


def test_unknown_match_is_404(client):
    assert client.get("/api/v1/matches/m_nope/analysis").status_code == 404


def test_club_analysis_hands_the_core_what_it_needs_to_scope(tmp_path, monkeypatch):
    """Scoping is the core's (``ingest.leak_safe_training_view``), which needs the
    fixture's source AND kind to know a club fixture must not train across
    competitions. This pins the handoff; that the rule then holds is pinned
    directly, on training rows, in core/tests/test_leak_safe_view.py.
    """
    rows = _rows()
    for row in rows:
        row["source_id"] = "openfootball-shared"
        row["source_kind"] = "club"
        row["competition"] = "League A"
        row["tournament"] = "League A"
    contaminant = _row("m_other", "2024-12-01", "Other A", "Other B", 4, 0, True)
    contaminant.update(
        source_id="openfootball-shared",
        source_kind="club",
        competition="League B",
        tournament="League B",
    )
    rows.append(contaminant)
    index_path = tmp_path / "matches_index.parquet"
    _build_index(index_path, rows)
    monkeypatch.setattr(matches, "INDEX_PATH", index_path)

    captured: dict[str, Any] = {}
    import golavo_core.analysis as core_analysis

    def _capture(*, matches, match_row):
        captured["match_row"] = match_row
        return {"schema_version": "0.5.0", "match": match_row}

    monkeypatch.setattr(core_analysis, "build_match_analysis", _capture)
    body = server_analysis.match_analysis("m_target")

    assert body is not None and body["available"] is True
    assert captured["match_row"]["source_id"] == "openfootball-shared"
    assert captured["match_row"]["source_kind"] == "club"
    assert captured["match_row"]["competition"] == "League A"


def test_club_analysis_never_mixes_competitions_with_a_shared_source(tmp_path, monkeypatch):
    """End to end, with the real engine: a League A fixture's council must never
    have seen a League B result from the same source."""
    rows = _rows()
    for row in rows:
        row["source_id"] = "openfootball-shared"
        row["source_kind"] = "club"
        row["competition"] = "League A"
        row["tournament"] = "League A"
    contaminant = _row("m_other", "2024-12-01", "Other A", "Other B", 4, 0, True)
    contaminant.update(
        source_id="openfootball-shared",
        source_kind="club",
        competition="League B",
        tournament="League B",
    )
    rows.append(contaminant)
    index_path = tmp_path / "matches_index.parquet"
    _build_index(index_path, rows)
    monkeypatch.setattr(matches, "INDEX_PATH", index_path)

    seen: dict[str, Any] = {}
    from golavo_core.ingest import snapshot as core_snapshot

    real_view = core_snapshot.leak_safe_training_view

    def recording_view(frame, match_row, **kwargs):
        view = real_view(frame, match_row, **kwargs)
        seen["competitions"] = set(view.rows["competition"].astype(str))
        return view

    monkeypatch.setattr(core_snapshot, "leak_safe_training_view", recording_view)
    import golavo_core.analysis as core_analysis

    monkeypatch.setattr(core_analysis, "leak_safe_training_view", recording_view)

    body = server_analysis.match_analysis("m_target")

    assert body is not None and body["available"] is True
    assert seen["competitions"] == {"League A"}


def test_recent_rails_have_results_and_honest_upcoming(client):
    body = client.get("/api/v1/matches/recent").json()
    assert body["schema_version"] == "0.2.0"
    assert len(body["recent"]) > 0
    # The only future-dated row is m_future — it should surface in upcoming.
    assert any(m["match_id"] == "m_future" for m in body["upcoming"])
    # Recent is completed, newest first.
    assert all(m["is_complete"] for m in body["recent"])


def test_recent_is_declared_before_match_id_route(client):
    # "recent" must not be swallowed as a match id (would 404 as a match).
    assert client.get("/api/v1/matches/recent").status_code == 200


# --------------------------------------------------------------------------- #
# L2 disk cache (R7 latency mitigation)
# --------------------------------------------------------------------------- #
@pytest.fixture
def cached_client(tmp_path, monkeypatch):
    """A client with a real meta.json (for the fingerprint) and a writable disk
    cache dir, so the L2 path is exercised."""
    from golavo_server import runtime

    index_path = tmp_path / "matches_index.parquet"
    _build_index(index_path, _rows())
    meta_path = tmp_path / "matches_index.meta.json"
    meta_path.write_text('{"row_count": 98, "manifest_sha256": "abc"}', encoding="utf-8")
    cache_dir = tmp_path / "analysis-cache"
    monkeypatch.setattr(matches, "INDEX_PATH", index_path)
    monkeypatch.setattr(matches, "INDEX_META_PATH", meta_path)
    monkeypatch.setattr(runtime, "analysis_cache_dir", lambda: cache_dir)
    empty_ledger = tmp_path / "ledger"
    empty_ledger.mkdir()
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", empty_ledger)
    return TestClient(server_main.app), cache_dir, meta_path


def test_disk_cache_survives_an_l1_reset(cached_client, monkeypatch):
    client, cache_dir, _ = cached_client
    first = client.get("/api/v1/matches/m_target/analysis").json()
    assert first["available"] is True
    assert list(cache_dir.glob("an_*.json")), "a disk cache file should be written"

    # Clear the in-process memo; the second call must be served from disk. Prove it
    # by making a recompute impossible — any refit would raise.
    matches.reset_cache()
    server_analysis.reset_cache()
    import golavo_core.analysis as core_analysis

    def _boom(*a, **k):
        raise AssertionError("should have been served from the disk cache, not recomputed")

    monkeypatch.setattr(core_analysis, "build_match_analysis", _boom)
    second = client.get("/api/v1/matches/m_target/analysis").json()
    assert second["available"] is True
    assert second["analysis"]["schema_version"] == "0.5.0"


def test_disk_cache_invalidates_when_the_fingerprint_changes(cached_client, monkeypatch):
    client, cache_dir, meta_path = cached_client
    client.get("/api/v1/matches/m_target/analysis")
    assert list(cache_dir.glob("an_*.json"))

    # A new index (meta bytes change) → new fingerprint → the old file is not read.
    matches.reset_cache()
    server_analysis.reset_cache()
    meta_path.write_text('{"row_count": 98, "manifest_sha256": "DIFFERENT"}', encoding="utf-8")
    import golavo_core.analysis as core_analysis

    monkeypatch.setattr(
        core_analysis,
        "build_match_analysis",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("miss expected")),
    )
    # A miss now hits the (raising) recompute → fails closed to available:false,
    # proving the stale-fingerprint file was NOT served.
    body = client.get("/api/v1/matches/m_target/analysis").json()
    assert body["available"] is False


def test_analysis_retries_when_repoint_happens_after_snapshot(
    tmp_path, monkeypatch
) -> None:
    """An old frame can never be cached under the newly activated fingerprint."""
    import golavo_core.analysis as core_analysis
    from golavo_server import runtime

    old_rows = _rows()
    new_rows = _rows()
    for row in old_rows:
        row["city"] = "old-generation"
    for row in new_rows:
        row["city"] = "new-generation"
        if row["match_id"].startswith("m_h"):
            row["home_score"], row["away_score"] = row["away_score"], row["home_score"]

    old_index = tmp_path / "old.parquet"
    new_index = tmp_path / "new.parquet"
    old_meta = tmp_path / "old.meta.json"
    new_meta = tmp_path / "new.meta.json"
    _build_index(old_index, old_rows)
    _build_index(new_index, new_rows)
    old_meta.write_text('{"generation":"old"}', encoding="utf-8")
    new_meta.write_text('{"generation":"new"}', encoding="utf-8")
    cache_dir = tmp_path / "analysis-cache"
    monkeypatch.setattr(runtime, "analysis_cache_dir", lambda: cache_dir)
    monkeypatch.setattr(matches, "INDEX_PATH", old_index)
    monkeypatch.setattr(matches, "INDEX_META_PATH", old_meta)
    monkeypatch.setattr(matches, "GOALSCORERS_PATH", matches.GOALSCORERS_PATH)
    monkeypatch.setattr(matches, "SHOOTOUTS_PATH", matches.SHOOTOUTS_PATH)
    monkeypatch.setattr(matches, "ALIASES_PATH", matches.ALIASES_PATH)
    matches.reset_cache()

    snapshot_taken = threading.Event()
    allow_analysis_to_continue = threading.Event()
    real_snapshot = matches.index_snapshot
    first = True

    def blocked_snapshot() -> matches.IndexSnapshot:
        nonlocal first
        snapshot = real_snapshot()
        if first:
            first = False
            snapshot_taken.set()
            assert allow_analysis_to_continue.wait(5), "test barrier timed out"
        return snapshot

    seen_generations: list[str] = []
    real_build = core_analysis.build_match_analysis

    def recording_build(*, matches: pd.DataFrame, match_row: dict) -> dict:
        seen_generations.append(str(matches.iloc[0]["city"]))
        return real_build(matches=matches, match_row=match_row)

    monkeypatch.setattr(matches, "index_snapshot", blocked_snapshot)
    monkeypatch.setattr(core_analysis, "build_match_analysis", recording_build)
    monkeypatch.setattr(
        matches,
        "_resolve_index_paths",
        lambda: {
            "index": new_index,
            "meta": new_meta,
            "goalscorers": tmp_path / "new-goalscorers.parquet",
            "shootouts": tmp_path / "new-shootouts.parquet",
            "aliases": tmp_path / "new-aliases.json",
        },
    )

    result: list[dict | None] = []
    worker = threading.Thread(
        target=lambda: result.append(server_analysis.match_analysis("m_target")),
        daemon=True,
    )
    worker.start()
    try:
        assert snapshot_taken.wait(5), "analysis never captured the old generation"
        matches.repoint_to_refreshed()
    finally:
        allow_analysis_to_continue.set()
        worker.join(15)

    assert not worker.is_alive()
    assert result and result[0] is not None and result[0]["available"] is True
    assert seen_generations == ["old-generation", "new-generation"]
    assert result[0]["analysis"]["models"] != []

    # After L1 is cleared, the active-generation disk entry must still be the
    # new analysis. A refit would prove that publication missed the right key.
    server_analysis.reset_cache()

    def fail_build(*_args, **_kwargs):
        raise AssertionError("new-generation analysis should be served from L2")

    monkeypatch.setattr(core_analysis, "build_match_analysis", fail_build)
    again = server_analysis.match_analysis("m_target")
    assert again == result[0]


def test_corrupt_cache_file_is_ignored_and_recomputed(cached_client):
    client, cache_dir, _ = cached_client
    # Prime the cache to learn the file path, then corrupt it.
    client.get("/api/v1/matches/m_target/analysis")
    files = list(cache_dir.glob("an_*.json"))
    assert files
    files[0].write_text("{ not json", encoding="utf-8")

    matches.reset_cache()
    server_analysis.reset_cache()
    body = client.get("/api/v1/matches/m_target/analysis").json()
    assert body["available"] is True  # recomputed despite the corrupt file
    assert body["analysis"]["schema_version"] == "0.5.0"


def test_schema_invalid_cache_is_rejected_even_with_a_matching_hash(cached_client):
    client, cache_dir, _ = cached_client
    client.get("/api/v1/matches/m_target/analysis")
    path = next(cache_dir.glob("an_*.json"))
    record = json.loads(path.read_text(encoding="utf-8"))
    record["envelope"]["analysis"]["explanation"]["averaged_consensus"] = True
    payload = json.dumps(
        record["envelope"], sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    record["payload_sha256"] = hashlib.sha256(payload).hexdigest()
    path.write_text(
        json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    matches.reset_cache()
    server_analysis.reset_cache()
    body = client.get("/api/v1/matches/m_target/analysis").json()
    assert body["available"] is True
    assert body["analysis"]["explanation"]["averaged_consensus"] is False


def test_source_mode_writes_no_disk_cache(client, monkeypatch):
    # Default client has no analysis_cache_dir override → runtime returns None.
    from golavo_server import runtime

    monkeypatch.setattr(runtime, "analysis_cache_dir", lambda: None)
    body = client.get("/api/v1/matches/m_target/analysis").json()
    assert body["available"] is True  # still works, memo-only
