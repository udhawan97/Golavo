"""Tests for the read-only match search + on-demand notebook surface (Workstream B).

Every test builds a TINY typed index (the exact 17 columns + dtypes of the frozen
one) in tmp_path and repoints ``matches.INDEX_PATH`` at it. The autouse fixture
resets the module cache between tests so the immutable-within-a-process cache never
leaks one test's index into the next.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from golavo_server import main as server_main
from golavo_server import matches

# The frozen index schema, verbatim (order matters for the parquet round-trip).
COLUMNS = [
    "match_id", "date", "kickoff_utc", "home_team", "away_team", "home_norm",
    "away_norm", "home_score", "away_score", "is_complete", "tournament",
    "competition", "city", "country", "neutral", "source_id", "source_kind",
]

_CLUB = "openfootball-football-json"
_INTL = "martj42-international-results"


def _row(match_id, date, home, away, home_norm, away_norm, hs, aws, complete,
         competition, source_id, source_kind, *, neutral=False, tournament="Cup",
         city="City", country="Country"):
    return {
        "match_id": match_id, "date": date, "kickoff_utc": f"{date}T00:00:00Z",
        "home_team": home, "away_team": away, "home_norm": home_norm,
        "away_norm": away_norm, "home_score": hs, "away_score": aws,
        "is_complete": complete, "tournament": tournament, "competition": competition,
        "city": city, "country": country, "neutral": neutral, "source_id": source_id,
        "source_kind": source_kind,
    }


# A compact but representative fixture set: two club "atletico" rows (prefix vs
# substring), a played international with a Brazil win-streak history + target,
# a linkable club fixture, and a genuinely-future upcoming international.
_ROWS = [
    _row("m_s1", "2024-03-01", "Atlético", "Getafe", "atletico", "getafe", 2, 1, True,
         "La Liga", _CLUB, "club"),
    _row("m_s2", "2024-04-01", "Real Atletico", "Deportivo", "real atletico", "deportivo",
         0, 0, True, "La Liga", _CLUB, "club"),
    _row("m_s3", "2024-07-01", "Valencia", "Betis", "valencia", "betis", None, None, False,
         "La Liga", _CLUB, "club"),
    _row("m_n1", "2024-05-01", "Brazil", "Chile", "brazil", "chile", 2, 0, True,
         "Friendly", _INTL, "international"),
    _row("m_n2", "2024-05-05", "Brazil", "Peru", "brazil", "peru", 3, 1, True,
         "Friendly", _INTL, "international"),
    _row("m_n3", "2024-05-10", "Brazil", "Uruguay", "brazil", "uruguay", 1, 0, True,
         "Friendly", _INTL, "international"),
    _row("m_target", "2024-06-01", "Brazil", "Argentina", "brazil", "argentina", 2, 1, True,
         "Friendly", _INTL, "international"),
    _row("m_u1", "2030-01-01", "Japan", "Qatar", "japan", "qatar", None, None, False,
         "Asian Cup", _INTL, "international", neutral=True),
]


def _build_index(path: Path, rows: list[dict]) -> pd.DataFrame:
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
    df = df[COLUMNS]
    df.to_parquet(path)
    return df


@pytest.fixture(autouse=True)
def _reset_cache():
    matches.reset_cache()
    yield
    matches.reset_cache()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A TestClient over a tiny index, with an EMPTY real ledger by default."""
    index_path = tmp_path / "matches_index.parquet"
    _build_index(index_path, _ROWS)
    monkeypatch.setattr(matches, "INDEX_PATH", index_path)
    empty_ledger = tmp_path / "ledger"
    empty_ledger.mkdir()
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", empty_ledger)
    return TestClient(server_main.app)


def _write_artifact(ledger: Path, artifact_id, *, match_id, home, away, kickoff,
                    status="sealed", horizon="T-60m", sealed_at="2024-05-31T12:00:00Z"):
    obj = {
        "artifact_id": artifact_id,
        "status": status,
        "forecast": {"horizon": horizon, "sealed_at_utc": sealed_at},
        "match": {"match_id": match_id, "home_team": home, "away_team": away,
                  "kickoff_utc": kickoff},
    }
    (ledger / f"{artifact_id}.json").write_text(json.dumps(obj), encoding="utf-8")


# --------------------------------------------------------------------------- search

def test_search_happy_path_and_pagination(client):
    body = client.get("/api/v1/matches/search", params={"q": "brazil"}).json()
    assert body["schema_version"] == "0.2.0"
    assert body["query"] == "brazil"
    assert body["total"] == 4  # 3 history rows + the target, all Brazil (home)
    ids = {m["match_id"] for m in body["matches"]}
    assert ids == {"m_n1", "m_n2", "m_n3", "m_target"}

    page1 = client.get(
        "/api/v1/matches/search", params={"q": "brazil", "limit": 2, "offset": 0}
    ).json()
    page2 = client.get(
        "/api/v1/matches/search", params={"q": "brazil", "limit": 2, "offset": 2}
    ).json()
    assert page1["total"] == page2["total"] == 4
    assert len(page1["matches"]) == 2 and len(page2["matches"]) == 2
    # Disjoint pages, deterministic across the two calls.
    assert {m["match_id"] for m in page1["matches"]}.isdisjoint(
        {m["match_id"] for m in page2["matches"]}
    )


def test_multi_team_query_ands_tokens(client):
    # "brazil argentina" must resolve to the single Brazil v Argentina fixture — not
    # 0 results (the old whole-string bug) and not every Brazil match.
    body = client.get("/api/v1/matches/search", params={"q": "brazil argentina"}).json()
    assert {m["match_id"] for m in body["matches"]} == {"m_target"}
    # Order-independent: each token may match either team (or the competition).
    reversed_ = client.get("/api/v1/matches/search", params={"q": "argentina brazil"}).json()
    assert {m["match_id"] for m in reversed_["matches"]} == {"m_target"}
    # A token that matches nothing yields nothing (AND semantics).
    assert client.get("/api/v1/matches/search", params={"q": "brazil zzznope"}).json()["total"] == 0
    # A single-token query is unchanged (every Brazil match).
    single = client.get("/api/v1/matches/search", params={"q": "brazil"}).json()
    assert {m["match_id"] for m in single["matches"]} == {"m_n1", "m_n2", "m_n3", "m_target"}


def test_upcoming_includes_a_fixture_on_its_own_match_day(tmp_path, monkeypatch):
    # A scheduled fixture whose 00:00 UTC day-proxy kickoff is TODAY must still count
    # as upcoming; the old `kickoff >= now` excluded it the moment UTC midnight passed.
    from datetime import UTC, datetime

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    rows = [_row("m_today", today, "Foo", "Bar", "foo", "bar", None, None, False,
                 "Friendly", _INTL, "international")]
    index_path = tmp_path / "today.parquet"
    _build_index(index_path, rows)
    monkeypatch.setattr(matches, "INDEX_PATH", index_path)
    matches.reset_cache()
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", tmp_path / "ledger")
    client = TestClient(server_main.app)
    body = client.get("/api/v1/matches/search", params={"q": "foo", "status": "upcoming"}).json()
    assert [m["match_id"] for m in body["matches"]] == ["m_today"]


def test_multiword_alias_resolves_to_canonical_team(tmp_path, monkeypatch):
    # A multi-word former name (real alias "soviet union" -> Russia) must still
    # resolve to the canonical team, even though it can't match token-by-token.
    rows = [_row("m_rus", "2030-01-01", "Russia", "Foo", "russia", "foo", None, None, False,
                 "Friendly", _INTL, "international")]
    index_path = tmp_path / "alias.parquet"
    _build_index(index_path, rows)
    monkeypatch.setattr(matches, "INDEX_PATH", index_path)
    matches.reset_cache()
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", tmp_path / "ledger")
    client = TestClient(server_main.app)
    body = client.get("/api/v1/matches/search", params={"q": "soviet union"}).json()
    assert "m_rus" in {m["match_id"] for m in body["matches"]}


def test_search_min_chars_is_422(client):
    assert client.get("/api/v1/matches/search", params={"q": "a"}).status_code == 422
    assert client.get("/api/v1/matches/search", params={"q": "  "}).status_code == 422


def test_search_unknown_competition_is_empty(client):
    body = client.get(
        "/api/v1/matches/search", params={"q": "brazil", "competition": "Nope League"}
    ).json()
    assert body["total"] == 0
    assert body["matches"] == []


def test_search_is_diacritic_and_case_insensitive(client):
    # "atletico" (no accent, lowercase) must hit the row whose home_norm is "atletico".
    body = client.get("/api/v1/matches/search", params={"q": "AtLeTico"}).json()
    ids = {m["match_id"] for m in body["matches"]}
    assert "m_s1" in ids  # home_team "Atlético"
    # The displayed team name keeps its diacritic; matching used the folded norm.
    row = next(m for m in body["matches"] if m["match_id"] == "m_s1")
    assert row["home_team"] == "Atlético"


def test_search_ranks_prefix_before_substring(client):
    body = client.get("/api/v1/matches/search", params={"q": "atletico"}).json()
    assert [m["match_id"] for m in body["matches"]] == ["m_s1", "m_s2"]  # prefix first


def test_search_status_upcoming_filters_to_future_unplayed(client):
    body = client.get("/api/v1/matches/search", params={"q": "japan", "status": "upcoming"}).json()
    assert [m["match_id"] for m in body["matches"]] == ["m_u1"]
    played = client.get("/api/v1/matches/search", params={"q": "japan", "status": "played"}).json()
    assert played["matches"] == []  # m_u1 is not complete


def test_search_json_is_clean_for_nullable_columns(client):
    # An upcoming row has NA scores and (m_u1) a nullable neutral=True; all must be
    # valid JSON (null / bool), never pandas <NA>.
    body = client.get("/api/v1/matches/search", params={"q": "valencia"}).json()
    row = body["matches"][0]
    assert row["home_score"] is None and row["away_score"] is None
    assert row["is_complete"] is False


def test_search_alias_resolves_former_country_name(client, tmp_path, monkeypatch):
    # Alias file maps a normalized former name to a canonical team present in the index.
    alias_path = tmp_path / "aliases.json"
    alias_path.write_text(json.dumps({"nippon": ["Japan"]}), encoding="utf-8")
    monkeypatch.setattr(matches, "ALIASES_PATH", alias_path)
    body = client.get("/api/v1/matches/search", params={"q": "nippon"}).json()
    assert {m["match_id"] for m in body["matches"]} == {"m_u1"}  # Japan via alias


# --------------------------------------------------------------------------- detail

def test_get_match_200_and_404(client):
    body = client.get("/api/v1/matches/m_s1").json()
    assert body["schema_version"] == "0.2.0"
    assert body["match"]["match_id"] == "m_s1"
    assert body["match"]["home_team"] == "Atlético"
    assert body["linked_by"] is None  # empty ledger
    assert client.get("/api/v1/matches/does_not_exist").status_code == 404


def test_competitions_route_before_match_id(client):
    body = client.get("/api/v1/matches/competitions").json()
    assert body["schema_version"] == "0.2.0"
    comps = {(c["competition"], c["source_kind"]): c["n_matches"] for c in body["competitions"]}
    assert comps[("La Liga", "club")] == 3
    assert comps[("Friendly", "international")] == 4
    assert comps[("Asian Cup", "international")] == 1


# --------------------------------------------------------------------------- linking

def test_forecast_links_by_match_id(client, tmp_path, monkeypatch):
    ledger = tmp_path / "real_ledger"
    ledger.mkdir()
    _write_artifact(ledger, "fa_link_by_id", match_id="m_s1", home="Atlético",
                    away="Getafe", kickoff="2024-03-01T00:00:00Z")
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)

    detail = client.get("/api/v1/matches/m_s1").json()
    assert detail["linked_by"] == "match_id"
    assert [f["artifact_id"] for f in detail["match"]["forecasts"]] == ["fa_link_by_id"]
    assert detail["match"]["forecasts"][0] == {
        "artifact_id": "fa_link_by_id", "status": "sealed", "horizon": "T-60m",
        "sealed_at_utc": "2024-05-31T12:00:00Z",
    }
    # It also shows up through search.
    body = client.get("/api/v1/matches/search", params={"q": "atletico"}).json()
    hit = next(m for m in body["matches"] if m["match_id"] == "m_s1")
    assert hit["forecasts"][0]["artifact_id"] == "fa_link_by_id"


def test_forecast_links_by_fixture_when_match_id_differs(client, tmp_path, monkeypatch):
    ledger = tmp_path / "real_ledger"
    ledger.mkdir()
    # Different match_id, but same date + teams as m_s3 -> fixture link.
    _write_artifact(ledger, "fa_link_by_fixture", match_id="m_UNRELATED",
                    home="Valencia", away="Betis", kickoff="2024-07-01T00:00:00Z")
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)

    detail = client.get("/api/v1/matches/m_s3").json()
    assert detail["linked_by"] == "fixture"
    assert [f["artifact_id"] for f in detail["match"]["forecasts"]] == ["fa_link_by_fixture"]


def test_samples_never_attach_to_real_matches(client, tmp_path, monkeypatch):
    # An EMPTY real ledger must yield zero links, even though bundled samples exist.
    empty = tmp_path / "empty_ledger"
    empty.mkdir()
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", empty)
    body = client.get("/api/v1/matches/search", params={"q": "brazil"}).json()
    assert all(m["forecasts"] == [] for m in body["matches"])


def test_corrupt_ledger_file_is_skipped_not_fatal(client, tmp_path, monkeypatch):
    ledger = tmp_path / "real_ledger"
    ledger.mkdir()
    (ledger / "fa_truncated.json").write_text("{ not json", encoding="utf-8")
    _write_artifact(ledger, "fa_ok", match_id="m_s1", home="Atlético", away="Getafe",
                    kickoff="2024-03-01T00:00:00Z")
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", ledger)
    detail = client.get("/api/v1/matches/m_s1").json()
    assert detail["linked_by"] == "match_id"  # the corrupt sibling did not break linking


# ------------------------------------------------------------------- notebook (leak)

def test_notebook_on_demand_is_leak_safe(client):
    body = client.get("/api/v1/matches/m_target/notebook").json()
    assert body["available"] is True
    assert body["computed"] == "on_demand"

    notebook = body["notebook"]
    assert notebook is not None
    assert len(notebook["facts"]) >= 1  # Brazil's win streak produces facts

    # LEAK TEST: the horizon is exactly kickoff - 1s, strictly before kickoff, and
    # no fact's evidence reaches the fixture (or anything later).
    kickoff = pd.Timestamp("2024-06-01T00:00:00Z")
    as_of = pd.Timestamp(body["as_of_horizon"])
    assert as_of == kickoff - pd.Timedelta(seconds=1)
    assert as_of < kickoff
    assert notebook["as_of_utc"] == body["as_of_horizon"]
    for fact in notebook["facts"]:
        assert pd.Timestamp(fact["freshness"]["last_event_utc"]) <= as_of
        assert pd.Timestamp(fact["freshness"]["last_event_utc"]) < kickoff


def test_notebook_on_demand_is_source_scoped(tmp_path, monkeypatch):
    """A team name shared across sources must not merge one source's history into
    the other's on-demand notebook. Regression: "Monaco" is both the national side
    (internationals pack) and the Ligue 1 club (club pack). Over the full mixed
    index a team-scoped template would fold a club's form into an international
    fixture; the on-demand build is scoped to the fixture's own source_id.
    """
    rows = [
        # Three international Monaco wins in a row -> a win_streak fact (min_sample 3).
        _row("m_mi1", "2016-01-01", "Monaco", "Andorra", "monaco", "andorra", 2, 0, True,
             "Friendly", _INTL, "international"),
        _row("m_mi2", "2016-02-01", "Monaco", "Malta", "monaco", "malta", 3, 0, True,
             "Friendly", _INTL, "international"),
        _row("m_mi3", "2016-03-01", "Monaco", "Cyprus", "monaco", "cyprus", 1, 0, True,
             "Friendly", _INTL, "international"),
        # A CLUB "Monaco" LOSS after the last international win: if the two sources
        # merged it would be Monaco's most recent match and break the win streak.
        _row("m_mc1", "2016-03-15", "Monaco", "Nice", "monaco", "nice", 0, 3, True,
             "Ligue 1", _CLUB, "club"),
        # The international target fixture (kickoff after all history).
        _row("m_mtar", "2016-04-01", "Monaco", "Iceland", "monaco", "iceland", 4, 1, True,
             "Friendly", _INTL, "international"),
    ]
    index_path = tmp_path / "matches_index.parquet"
    _build_index(index_path, rows)
    monkeypatch.setattr(matches, "INDEX_PATH", index_path)
    # No side tables -> the notebook is pure results and fully deterministic.
    monkeypatch.setattr(matches, "GOALSCORERS_PATH", tmp_path / "none_gs.parquet")
    monkeypatch.setattr(matches, "SHOOTOUTS_PATH", tmp_path / "none_so.parquet")
    empty_ledger = tmp_path / "ledger"
    empty_ledger.mkdir()
    monkeypatch.setattr(server_main, "ARTIFACT_DIR", empty_ledger)
    matches.reset_cache()
    client = TestClient(server_main.app)

    body = client.get("/api/v1/matches/m_mtar/notebook").json()
    assert body["computed"] == "on_demand"
    facts = body["notebook"]["facts"]
    # Every fact draws on the international pack only, never the club row.
    assert facts, "expected at least the win-streak fact"
    for fact in facts:
        assert fact["source_ids"] == [_INTL], (fact["id"], fact["source_ids"])
    # Monaco's win streak survives -> the club LOSS was excluded from the history.
    streak = next((f for f in facts if f["id"] == "win_streak" and f["subject"] == "Monaco"), None)
    assert streak is not None and streak["sample_n"] == 3


def test_notebook_unknown_match_is_404(client):
    assert client.get("/api/v1/matches/nope/notebook").status_code == 404


# ------------------------------------------------------------------- cache coherence

def test_cache_follows_a_repointed_index_without_an_explicit_reset(
    client, tmp_path, monkeypatch
):
    # ``_CACHE`` and ``INDEX_PATH`` are two halves of one piece of state. Repointing
    # the path without calling ``reset_cache()`` used to leave the module serving a
    # frame loaded from a file it no longer names — invisibly, because the fast-path
    # cache hit never rechecked the path. That is not a hypothetical: ``monkeypatch``
    # restores ``INDEX_PATH`` at teardown but cannot restore the cache, so any test
    # that repointed the path leaked its fixture frame into every later test in the
    # process (see the module docstring's note on the autouse reset).
    assert client.get("/api/v1/matches/m_target").status_code == 200  # warms the cache

    other = tmp_path / "other_index.parquet"
    _build_index(other, [
        _row("m_only_here", "2024-02-01", "Peru", "Chile", "peru", "chile", 1, 0, True,
             "Friendly", _INTL, "international"),
    ])
    monkeypatch.setattr(matches, "INDEX_PATH", other)  # deliberately NO reset_cache()

    # The retired frame must not be reported as ready, nor served to a reader.
    assert matches.index_status()["index_ready"] is False
    assert client.get("/api/v1/matches/m_only_here").status_code == 200
    assert client.get("/api/v1/matches/m_target").status_code == 404


def test_a_directly_injected_frame_survives_a_path_recheck(client, tmp_path, monkeypatch):
    # The injected-frame compatibility path (a test placing a preloaded frame in
    # ``_CACHE`` itself) carries no provenance, so the coherence check must leave it
    # alone rather than discarding a frame it cannot attribute to any path.
    frame = _build_index(tmp_path / "injected.parquet", _ROWS)
    matches.reset_cache()
    monkeypatch.setattr(matches, "_CACHE", frame)
    assert matches._load_index() is frame


# ------------------------------------------------------------------- index failures

def test_search_503_when_index_missing(client, tmp_path, monkeypatch):
    monkeypatch.setattr(matches, "INDEX_PATH", tmp_path / "missing.parquet")
    matches.reset_cache()
    assert client.get("/api/v1/matches/search", params={"q": "brazil"}).status_code == 503


def test_search_503_when_index_corrupt(client, tmp_path, monkeypatch):
    corrupt = tmp_path / "corrupt.parquet"
    corrupt.write_bytes(b"this is not a parquet file")
    monkeypatch.setattr(matches, "INDEX_PATH", corrupt)
    matches.reset_cache()
    assert client.get("/api/v1/matches/search", params={"q": "brazil"}).status_code == 503
