"""The in-app seal route: eligibility, the single write endpoint, and its typed
failures.

Follows the match-API pattern: each test builds a TINY typed index in tmp_path and
repoints ``matches.INDEX_PATH`` at it. The successful-seal path uses the REAL
committed martj42 pack (via the default ``seal.PACKS_DIR``) and the actual
scheduled Norway v England row, with the clock frozen just before its 00:00 UTC
kickoff proxy — so the deterministic engine runs for real and writes a genuine
artifact, not a stub.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from golavo_server import main as server_main
from golavo_server import matches, seal

COLUMNS = [
    "match_id", "date", "kickoff_utc", "home_team", "away_team", "home_norm",
    "away_norm", "home_score", "away_score", "is_complete", "tournament",
    "competition", "city", "country", "neutral", "source_id", "source_kind",
]

_CLUB = "openfootball-football-json"
_INTL = "martj42-international-results"

# The real index/pack id for the scheduled Norway v England World Cup fixture;
# using the true id means the pack's _find_match resolves it exactly.
_NE_ID = "m_21afc636a82c181e"
# A moment inside the seal window: after the pack's retrieval anchor
# (2026-07-10T19:35:25Z), before the 2026-07-11T00:00Z kickoff proxy.
_PRE_KICKOFF = datetime(2026, 7, 10, 20, 0, 0, tzinfo=UTC)


def _row(match_id, date, home, away, home_norm, away_norm, complete, source_id, source_kind,
         *, competition="FIFA World Cup"):
    return {
        "match_id": match_id, "date": date, "kickoff_utc": f"{date}T00:00:00Z",
        "home_team": home, "away_team": away, "home_norm": home_norm, "away_norm": away_norm,
        "home_score": None, "away_score": None, "is_complete": complete, "tournament": competition,
        "competition": competition, "city": "City", "country": "Country", "neutral": False,
        "source_id": source_id, "source_kind": source_kind,
    }


_ROWS = [
    _row("m_done", "2024-05-01", "Brazil", "Chile", "brazil", "chile", True, _INTL,
         "international"),
    _row("m_club", "2024-07-01", "Valencia", "Betis", "valencia", "betis", False, _CLUB, "club",
         competition="La Liga"),
    _row(_NE_ID, "2026-07-11", "Norway", "England", "norway", "england", False, _INTL,
         "international"),
    # A genuinely-future international that the real pack does NOT contain — used to
    # prove eligibility (pack exists, kickoff ahead) can still fail at seal time.
    _row("m_future", "2035-06-01", "Japan", "Qatar", "japan", "qatar", False, _INTL,
         "international", competition="Friendly"),
]


def _build_index(path: Path, rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["kickoff_utc"] = pd.to_datetime(df["kickoff_utc"], utc=True)
    df["home_score"] = pd.array(list(df["home_score"]), dtype="Int16")
    df["away_score"] = pd.array(list(df["away_score"]), dtype="Int16")
    df["is_complete"] = df["is_complete"].astype(bool)
    df["neutral"] = pd.array(list(df["neutral"]), dtype="boolean")
    for col in ("match_id", "home_team", "away_team", "home_norm", "away_norm",
                "tournament", "competition", "city", "country", "source_id", "source_kind"):
        df[col] = df[col].astype("string")
    df[COLUMNS].to_parquet(path)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    index_path = tmp_path / "index.parquet"
    _build_index(index_path, _ROWS)
    monkeypatch.setattr(matches, "INDEX_PATH", index_path)
    matches.reset_cache()
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", tmp_path / "ledger")
    # Pin sealing to the canonical fallback pack (the stable, co-source-free martj42
    # snapshot whose Norway v England id and 00:00 kickoff proxy these tests assume).
    # The greatest-anchor-pack resolution is covered hermetically in
    # test_seal_pack_resolution.py.
    monkeypatch.setattr(seal, "_active_bundled_pack", lambda source_id, competition=None: None)
    return TestClient(server_main.app)


def _freeze_now(monkeypatch: pytest.MonkeyPatch, when: datetime = _PRE_KICKOFF) -> None:
    # Honour an explicit now_utc (so eligibility and the sealed as-of stay coupled),
    # otherwise return the frozen instant for a wall-clock read.
    monkeypatch.setattr(
        seal, "_now", lambda now_utc=None: (now_utc.astimezone(UTC) if now_utc else when)
    )


def _advancing_now(monkeypatch: pytest.MonkeyPatch, start: datetime, step_seconds: int) -> None:
    """A fake wall clock that advances by ``step_seconds`` on each unforced read.

    Mirrors seal._now: an explicit now_utc passes through unchanged; only a
    now_utc=None (wall-clock) read advances. So each seal request stamps a distinct
    as-of — exercising the clock-drift path the idempotency scan must survive.
    """
    state = {"t": start}

    def fake_now(now_utc: datetime | None = None) -> datetime:
        if now_utc is not None:
            return now_utc.astimezone(UTC).replace(microsecond=0)
        current = state["t"]
        state["t"] = current + timedelta(seconds=step_seconds)
        return current

    monkeypatch.setattr(seal, "_now", fake_now)


# --- eligibility surfaced on the match detail ------------------------------------

def test_completed_fixture_is_not_eligible(client: TestClient) -> None:
    elig = client.get("/api/v1/matches/m_done").json()["seal_eligibility"]
    assert elig["eligible"] is False
    assert elig["reason_code"] == "fixture_complete"


def test_club_without_a_bundled_pack_reports_pack_unavailable(client: TestClient) -> None:
    # A club fixture is a supported kind now — it reaches pack resolution rather
    # than a categorical 'unsupported'. This hermetic build bundles no league pack
    # (_active_bundled_pack is stubbed to None), so it honestly reports the missing
    # pack; a real build resolves the league's own openfootball pack.
    elig = client.get("/api/v1/matches/m_club").json()["seal_eligibility"]
    assert elig["eligible"] is False
    assert elig["reason_code"] == "pack_unavailable"


def test_scheduled_international_is_eligible_before_kickoff(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_now(monkeypatch)
    elig = client.get(f"/api/v1/matches/{_NE_ID}").json()["seal_eligibility"]
    assert elig["eligible"] is True
    assert elig["reason_code"] == "eligible"
    assert elig["family"] == "dixon_coles"


def test_seal_window_closes_at_the_midnight_proxy(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Once the 00:00 UTC kickoff proxy has passed, the fixture is honestly
    # ineligible on match day — the same rule that empties the 'upcoming' filter,
    # surfaced as a typed reason instead of a silent gap.
    _freeze_now(monkeypatch, when=datetime(2026, 7, 11, 12, 0, 0, tzinfo=UTC))
    elig = client.get(f"/api/v1/matches/{_NE_ID}").json()["seal_eligibility"]
    assert elig["eligible"] is False
    assert elig["reason_code"] == "kickoff_passed"


# --- the write route -------------------------------------------------------------

def test_seal_creates_persists_and_is_idempotent(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_now(monkeypatch)
    created = client.post(f"/api/v1/matches/{_NE_ID}/seal")
    assert created.status_code == 201
    body = created.json()
    assert body["created"] is True
    assert body["status"] == "sealed"
    assert body["family"] == "dixon_coles"
    artifact_id = body["artifact_id"]

    # It persists: the ledger now serves this real artifact (and drops off samples).
    listed = client.get("/api/v1/forecasts").json()
    assert artifact_id in {a["artifact_id"] for a in listed}
    assert client.get("/api/v1/meta").json()["forecast_source"] == "ledger"
    detail = client.get(f"/api/v1/forecasts/{artifact_id}")
    assert detail.status_code == 200
    assert detail.json()["forecast"]["score_matrix"] is not None  # dixon_coles grid

    # The precomputed notebook landed beside it.
    facts = client.get(f"/api/v1/forecasts/{artifact_id}/facts").json()
    assert facts["available"] is True

    assert facts["notebook"] is not None  # real content, not just an empty envelope

    # A repeat is idempotent per (fixture, family): same id, created=False, 200.
    again = client.post(f"/api/v1/matches/{_NE_ID}/seal")
    assert again.status_code == 200
    assert again.json() == {**body, "created": False}


def test_repeat_seal_is_idempotent_even_as_the_clock_advances(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Each request stamps a distinct as-of, so a naive implementation would mint a
    # second artifact with a different content id. The (fixture, family) idempotency
    # scan under the seal lock must return the first seal instead.
    _advancing_now(monkeypatch, start=datetime(2026, 7, 10, 20, 0, 0, tzinfo=UTC), step_seconds=5)
    first = client.post(f"/api/v1/matches/{_NE_ID}/seal")
    second = client.post(f"/api/v1/matches/{_NE_ID}/seal")
    assert first.status_code == 201 and first.json()["created"] is True
    assert second.status_code == 200 and second.json()["created"] is False
    assert second.json()["artifact_id"] == first.json()["artifact_id"]
    ledger = server_main.ARTIFACT_DIR
    assert len(list(ledger.glob("fa_*.json"))) == 1  # exactly one artifact, no drift duplicate


def test_seal_with_a_non_matrix_family_carries_no_score_grid(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_now(monkeypatch)
    created = client.post(f"/api/v1/matches/{_NE_ID}/seal", json={"family": "elo_ordlogit"})
    assert created.status_code == 201
    body = created.json()
    assert body["family"] == "elo_ordlogit"
    detail = client.get(f"/api/v1/forecasts/{body['artifact_id']}").json()
    assert detail["forecast"]["probs"] is not None
    # elo has no goal model, so the exact-score grid is omitted entirely (an honest
    # "no score distribution" state) rather than present-but-null.
    assert "score_matrix" not in detail["forecast"]


def test_seal_reappears_after_a_fresh_client(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _freeze_now(monkeypatch)
    artifact_id = client.post(f"/api/v1/matches/{_NE_ID}/seal").json()["artifact_id"]
    # A brand-new client over the same ledger dir (simulating an app restart).
    matches.reset_cache()
    fresh = TestClient(server_main.app)
    listed = fresh.get("/api/v1/forecasts").json()
    assert artifact_id in {a["artifact_id"] for a in listed}


def test_seal_rejects_a_completed_fixture(client: TestClient) -> None:
    resp = client.post("/api/v1/matches/m_done/seal")
    assert resp.status_code == 422
    assert resp.json()["detail"]["reason_code"] == "fixture_complete"


def test_seal_rejects_a_club_fixture_without_a_bundled_pack(client: TestClient) -> None:
    # Clubs are supported now, but this hermetic build bundles no league pack, so
    # the seal is refused for a missing pack rather than an unsupported competition.
    resp = client.post("/api/v1/matches/m_club/seal")
    assert resp.status_code == 503
    assert resp.json()["detail"]["reason_code"] == "pack_unavailable"


def test_seal_rejects_an_unknown_family(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_now(monkeypatch)
    resp = client.post(f"/api/v1/matches/{_NE_ID}/seal", json={"family": "bivariate_poisson"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["reason_code"] == "unsupported_family"


def test_seal_unknown_match_is_404(client: TestClient) -> None:
    resp = client.post("/api/v1/matches/does_not_exist/seal")
    assert resp.status_code == 404
    assert resp.json()["detail"]["reason_code"] == "match_not_found"


def test_eligible_fixture_absent_from_pack_fails_at_seal(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The 2035 fixture passes eligibility (pack resolves, kickoff ahead) but is not
    # in the pinned pack — an honest typed 422, not a crash.
    _freeze_now(monkeypatch)
    resp = client.post("/api/v1/matches/m_future/seal")
    assert resp.status_code == 422
    assert resp.json()["detail"]["reason_code"] == "fixture_not_in_pack"


# --- unit coverage of the seal module --------------------------------------------

def test_resolve_pack_dir_only_maps_internationals() -> None:
    intl = seal.resolve_pack_dir(_INTL, "international")
    assert intl is not None and (intl / "manifest.json").is_file()
    assert seal.resolve_pack_dir(_CLUB, "club") is None
    assert seal.resolve_pack_dir("something-else", "international") is None


def test_eligibility_is_pure_over_the_row_view() -> None:
    base = {"kickoff_utc": "2035-01-01T00:00:00Z", "source_kind": "international",
            "source_id": _INTL, "is_complete": False, "forecasts": [{"artifact_id": "fa_x"}]}
    ok = seal.eligibility(base)
    assert ok["eligible"] is True
    assert ok["existing_artifact_ids"] == ["fa_x"]
    assert seal.eligibility({**base, "is_complete": True})["reason_code"] == "fixture_complete"
    # A club is a supported kind now; without a resolvable league pack (no
    # competition here) it reports the missing pack, not an unsupported kind.
    assert seal.eligibility({**base, "source_kind": "club", "source_id": _CLUB})["reason_code"] == (
        "pack_unavailable"
    )
    # A truly unknown source kind stays categorically unsupported.
    assert seal.eligibility({**base, "source_kind": "exhibition", "source_id": "x"})[
        "reason_code"
    ] == "unsupported_competition"
    past = seal.eligibility({**base, "kickoff_utc": "2000-01-01T00:00:00Z"})
    assert past["reason_code"] == "kickoff_passed"
