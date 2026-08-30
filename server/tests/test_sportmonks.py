"""Sportmonks outside-signal isolation, consent, identity and parsing."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from subprocess import CompletedProcess

import pytest
from fastapi.testclient import TestClient
from golavo_server import main as server_main
from golavo_server import sportmonks

MATCH = {
    "match_id": "m_exact",
    "home_team": "Manchester United",
    "away_team": "Everton",
    "competition": "English Premier League",
    "kickoff_utc": "2026-08-16T19:00:00Z",
    "kickoff_precision": "exact",
}


def _wire_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "providers" / "sportmonks"
    monkeypatch.setattr(sportmonks.runtime, "sportmonks_dir", lambda: root)
    sportmonks.configure(
        {
            "enabled": True,
            "accept_terms": True,
            "capabilities": ["external_prediction", "external_odds", "player_lens"],
        }
    )


def _fixture_payload(home: str = "Manchester United") -> dict:
    return {
        "data": [
            {
                "id": 19427573,
                "starting_at_timestamp": 1786906800,
                "league_id": 8,
                "season_id": 202627,
                "league": {"id": 8, "name": "Premier League"},
                "season": {"id": 202627, "name": "2026/2027"},
                "participants": [
                    {"id": 14, "name": home, "meta": {"location": "home"}},
                    {"id": 9, "name": "Everton", "meta": {"location": "away"}},
                ],
            }
        ],
        "pagination": {"has_more": False},
    }


def _fake_fetcher(calls: list[tuple[str, str]]):
    def fetch(path: str, token: str):
        calls.append((path, token))
        if "/fixtures/date/" in path:
            return _fixture_payload(), "a" * 64
        if "/predictions/" in path:
            return {
                "data": [
                    {
                        "id": 77,
                        "fixture_id": 19427573,
                        "type_id": 237,
                        "predictions": {"home": 48.2, "draw": 26.1, "away": 25.7},
                    }
                ]
            }, "b" * 64
        if "/odds/" in path:
            return {
                "data": [
                    {
                        "fixture_id": 19427573,
                        "market_id": 1,
                        "bookmaker_id": 2,
                        "label": label,
                        "value": value,
                        "market_description": "Match Winner",
                        "stopped": False,
                        "latest_bookmaker_update": "2026-08-16 17:00:00",
                        "bookmaker": {"name": "Example Book"},
                    }
                    for label, value in (("Home", "1.90"), ("Draw", "3.40"), ("Away", "4.20"))
                ]
            }, "c" * 64
        if "include=lineups.details.type;metadata.type" in path:
            return {
                "data": {
                    "id": 19427573,
                    "metadata": [{
                        "type_id": 572,
                        "values": True,
                        "type": {"id": 572, "developer_name": "LINEUP_CONFIRMED"},
                    }],
                    "lineups": [{
                        "id": 501,
                        "fixture_id": 19427573,
                        "player_id": 601,
                        "team_id": 14,
                        "position_id": 27,
                        "type_id": 11,
                        "player_name": "Example Forward",
                        "jersey_number": 9,
                        "details": [{
                            "id": 701,
                            "fixture_id": 19427573,
                            "player_id": 601,
                            "team_id": 14,
                            "lineup_id": 501,
                            "type_id": 52,
                            "data": {"value": 1},
                            "type": {
                                "id": 52,
                                "name": "Goals",
                                "developer_name": "GOALS",
                                "stat_group": "offensive",
                            },
                        }],
                    }],
                }
            }, "d" * 64
        raise AssertionError(path)

    return fetch


def test_consent_defaults_off_and_requires_current_terms(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(sportmonks.runtime, "sportmonks_dir", lambda: tmp_path)
    assert sportmonks.load_settings()["enabled"] is False
    with pytest.raises(PermissionError, match="review and accept"):
        sportmonks.configure({"enabled": True})
    configured = sportmonks.configure({"enabled": True, "accept_terms": True})
    assert configured["enabled"] is True
    assert configured["terms_acceptance_version"] == sportmonks.TERMS_ACCEPTANCE_VERSION
    assert configured["storage_policy"] == "derived_response_memory_only"
    assert configured["usage"]["model_input"] is False


def test_exact_match_returns_separate_prediction_and_odds_without_persistence(
    monkeypatch, tmp_path
) -> None:
    _wire_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(sportmonks, "load_api_token", lambda: ("secret-token-value", "keychain"))
    calls: list[tuple[str, str]] = []
    result = sportmonks.fetch_outside_signals(
        MATCH,
        fetcher=_fake_fetcher(calls),
        now_utc=datetime(2026, 8, 16, 18, tzinfo=UTC),
    )
    assert result["status"] == "available"
    assert result["label"] == "Outside signals — not a Golavo forecast."
    assert result["prediction"]["percent"] == {"home": 48.2, "draw": 26.1, "away": 25.7}
    assert result["odds"]["bookmakers"][0]["decimal"]["away"] == 4.2
    assert result["player_lens"]["lineup_state"] == "confirmed"
    assert result["player_lens"]["players"][0]["player_id"] == 601
    assert result["player_lens"]["players"][0]["metrics"][0]["value"] == 1
    assert result["identity"]["provider_league_id"] == 8
    assert result["identity"]["provider_season_id"] == 202627
    assert result["provenance"]["raw_response_storage"] == "not_persisted"
    assert result["provenance"]["model_input"] is False
    assert all(token == "secret-token-value" for _path, token in calls)
    assert "secret-token-value" not in repr(result)
    assert list(tmp_path.rglob("*")) == [
        tmp_path / "providers",
        tmp_path / "providers" / "sportmonks",
        tmp_path / "providers" / "sportmonks" / "settings.json",
    ]


def test_identity_mismatch_fails_closed(monkeypatch, tmp_path) -> None:
    _wire_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(sportmonks, "load_api_token", lambda: ("secret-token-value", "keychain"))

    def mismatch(path: str, _token: str):
        assert "/fixtures/date/" in path
        return _fixture_payload(home="Manchester City"), "a" * 64

    with pytest.raises(sportmonks.SportmonksError) as exc:
        sportmonks.fetch_outside_signals(MATCH, fetcher=mismatch)
    assert exc.value.code == "fixture_not_matched"
    assert exc.value.status == 404


def test_non_exact_kickoff_fails_before_provider_egress(monkeypatch, tmp_path) -> None:
    _wire_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(sportmonks, "load_api_token", lambda: ("secret-token-value", "keychain"))
    calls: list[tuple[str, str]] = []
    imprecise = {**MATCH, "kickoff_precision": "date"}

    with pytest.raises(sportmonks.SportmonksError) as exc:
        sportmonks.fetch_outside_signals(
            imprecise,
            fetcher=_fake_fetcher(calls),
        )
    assert exc.value.code == "match_precision_insufficient"
    assert exc.value.status == 422
    assert calls == []


def test_day_precision_uses_exact_domestic_scope_teams_and_calendar_date(
    monkeypatch, tmp_path
) -> None:
    _wire_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(sportmonks, "load_api_token", lambda: ("secret-token-value", "keychain"))
    calls: list[tuple[str, str]] = []
    day_match = {
        **MATCH,
        "kickoff_utc": "2026-08-16T00:00:00Z",
        "kickoff_precision": "day",
    }

    result = sportmonks.fetch_outside_signals(day_match, fetcher=_fake_fetcher(calls))

    assert result["identity"]["match_method"] == (
        "exact_competition_season_teams_and_calendar_date"
    )
    assert calls


def test_day_precision_rejects_wrong_provider_competition_before_promotion(
    monkeypatch, tmp_path
) -> None:
    _wire_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(sportmonks, "load_api_token", lambda: ("secret-token-value", "keychain"))

    def wrong_scope(path: str, token: str):
        payload, digest = _fake_fetcher([])(path, token)
        if "/fixtures/date/" in path:
            payload["data"][0]["league"] = {"id": 2, "name": "Champions League"}
        return payload, digest

    with pytest.raises(sportmonks.SportmonksError) as exc:
        sportmonks.fetch_outside_signals(
            {**MATCH, "kickoff_utc": "2026-08-16T00:00:00Z", "kickoff_precision": "day"},
            fetcher=wrong_scope,
        )
    assert exc.value.code == "fixture_not_matched"


def test_domestic_match_rejects_mismatched_base_and_included_scope_ids(
    monkeypatch, tmp_path
) -> None:
    _wire_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(sportmonks, "load_api_token", lambda: ("secret-token-value", "keychain"))

    def mismatched_scope(path: str, token: str):
        payload, digest = _fake_fetcher([])(path, token)
        if "/fixtures/date/" in path:
            payload["data"][0]["league_id"] = 999
        return payload, digest

    with pytest.raises(sportmonks.SportmonksError) as exc:
        sportmonks.fetch_outside_signals(MATCH, fetcher=mismatched_scope)
    assert exc.value.code == "fixture_not_matched"


def test_unmapped_competition_retains_exact_kickoff_matching(monkeypatch, tmp_path) -> None:
    _wire_settings(monkeypatch, tmp_path)
    sportmonks.configure({"capabilities": ["external_prediction"]})
    monkeypatch.setattr(sportmonks, "load_api_token", lambda: ("secret-token-value", "keychain"))

    result = sportmonks.fetch_outside_signals(
        {**MATCH, "competition": "UEFA Champions League"},
        fetcher=_fake_fetcher([]),
    )

    assert result["identity"]["match_method"] == "exact_normalized_teams_and_kickoff"


def test_unmapped_competition_rejects_day_precision_before_provider_egress(
    monkeypatch, tmp_path
) -> None:
    _wire_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(sportmonks, "load_api_token", lambda: ("secret-token-value", "keychain"))
    calls: list[tuple[str, str]] = []

    with pytest.raises(sportmonks.SportmonksError) as exc:
        sportmonks.fetch_outside_signals(
            {
                **MATCH,
                "competition": "UEFA Champions League",
                "kickoff_precision": "day",
            },
            fetcher=_fake_fetcher(calls),
        )
    assert exc.value.code == "match_precision_insufficient"
    assert calls == []


def test_player_lens_only_rejects_non_top_five_before_provider_egress(
    monkeypatch, tmp_path
) -> None:
    _wire_settings(monkeypatch, tmp_path)
    sportmonks.configure({"capabilities": ["player_lens"]})
    monkeypatch.setattr(sportmonks, "load_api_token", lambda: ("secret-token-value", "keychain"))
    calls: list[tuple[str, str]] = []

    with pytest.raises(sportmonks.SportmonksError) as exc:
        sportmonks.fetch_outside_signals(
            {**MATCH, "competition": "UEFA Champions League"},
            fetcher=_fake_fetcher(calls),
        )
    assert exc.value.code == "competition_not_supported"
    assert calls == []


@pytest.mark.parametrize("ambiguity", ["duplicate_home", "same_team_id"])
def test_fixture_match_rejects_ambiguous_participant_identity(
    monkeypatch, tmp_path, ambiguity
) -> None:
    _wire_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(sportmonks, "load_api_token", lambda: ("secret-token-value", "keychain"))

    def ambiguous(path: str, token: str):
        payload, digest = _fake_fetcher([])(path, token)
        if "/fixtures/date/" in path:
            participants = payload["data"][0]["participants"]
            if ambiguity == "duplicate_home":
                participants.append({
                    "id": 99,
                    "name": "Manchester United",
                    "meta": {"location": "home"},
                })
            else:
                participants[1]["id"] = participants[0]["id"]
        return payload, digest

    with pytest.raises(sportmonks.SportmonksError) as exc:
        sportmonks.fetch_outside_signals(MATCH, fetcher=ambiguous)
    assert exc.value.code == "fixture_not_matched"


def test_fixture_search_fails_closed_when_page_bound_is_truncated(
    monkeypatch, tmp_path
) -> None:
    _wire_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(sportmonks, "load_api_token", lambda: ("secret-token-value", "keychain"))
    calls: list[str] = []

    def paginated(path: str, _token: str):
        calls.append(path)
        return {**_fixture_payload(), "pagination": {"has_more": True}}, "a" * 64

    with pytest.raises(sportmonks.SportmonksError) as exc:
        sportmonks.fetch_outside_signals(MATCH, fetcher=paginated)
    assert exc.value.code == "fixture_search_truncated"
    assert len(calls) == sportmonks.MAX_FIXTURE_PAGES


def test_rejected_credential_is_not_downgraded_to_an_unavailable_capability(
    monkeypatch, tmp_path
) -> None:
    _wire_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(sportmonks, "load_api_token", lambda: ("rejected-token", "keychain"))

    def rejected(path: str, _token: str):
        if "/fixtures/date/" in path:
            return _fixture_payload(), "a" * 64
        raise sportmonks.SportmonksError(
            "credential_rejected", "Sportmonks rejected the API token", status=401
        )

    with pytest.raises(sportmonks.SportmonksError) as exc:
        sportmonks.fetch_outside_signals(MATCH, fetcher=rejected)
    assert exc.value.code == "credential_rejected"
    assert exc.value.status == 401


def test_rate_limit_stops_before_another_capability_request(monkeypatch, tmp_path) -> None:
    _wire_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(sportmonks, "load_api_token", lambda: ("secret-token-value", "keychain"))
    calls: list[str] = []

    def rate_limited(path: str, _token: str):
        calls.append(path)
        if "/fixtures/date/" in path:
            return _fixture_payload(), "a" * 64
        raise sportmonks.SportmonksError(
            "rate_limited", "Sportmonks rate limit reached", status=429, retryable=True
        )

    with pytest.raises(sportmonks.SportmonksError) as exc:
        sportmonks.fetch_outside_signals(MATCH, fetcher=rate_limited)
    assert exc.value.code == "rate_limited"
    assert len(calls) == 2
    assert "/predictions/" in calls[-1]


def test_missing_plan_stops_before_another_capability_request(monkeypatch, tmp_path) -> None:
    _wire_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(sportmonks, "load_api_token", lambda: ("secret-token-value", "keychain"))
    calls: list[str] = []

    def plan_missing(path: str, _token: str):
        calls.append(path)
        if "/fixtures/date/" in path:
            return _fixture_payload(), "a" * 64
        raise sportmonks.SportmonksError(
            "plan_missing", "Sportmonks plan does not include this feed", status=403
        )

    with pytest.raises(sportmonks.SportmonksError) as exc:
        sportmonks.fetch_outside_signals(MATCH, fetcher=plan_missing)
    assert exc.value.code == "plan_missing"
    assert len(calls) == 2
    assert "/predictions/" in calls[-1]


@pytest.mark.parametrize("kind", ["prediction", "odds"])
@pytest.mark.parametrize("row_fixture_id", [None, 999])
def test_capability_rows_must_repeat_selected_fixture_id(
    kind: str,
    row_fixture_id: int | None,
) -> None:
    def fetch(_path: str, _token: str):
        if kind == "prediction":
            return {
                "data": [
                    {
                        "id": 7,
                        "fixture_id": row_fixture_id,
                        "type_id": 237,
                        "predictions": {"home": 40, "draw": 30, "away": 30},
                    }
                ]
            }, "b" * 64
        return {
            "data": [
                {
                    "fixture_id": row_fixture_id,
                    "market_id": 1,
                    "bookmaker_id": 2,
                    "label": "Home",
                    "value": "2.0",
                    "stopped": False,
                }
            ]
        }, "c" * 64

    value, digest = (
        sportmonks._prediction(19427573, "secret", fetch)
        if kind == "prediction"
        else sportmonks._odds(19427573, "secret", fetch)
    )
    assert value["status"] == "unavailable"
    assert value["reason_code"] == "fixture_identity_mismatch"
    assert digest is None


def test_duplicate_bookmaker_selection_is_quarantined(monkeypatch, tmp_path) -> None:
    _wire_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(sportmonks, "load_api_token", lambda: ("secret-token-value", "keychain"))
    base = _fake_fetcher([])

    def duplicated(path: str, token: str):
        payload, digest = base(path, token)
        if "/odds/" in path:
            payload["data"].append({**payload["data"][0], "value": "1.95"})
        return payload, digest

    result = sportmonks.fetch_outside_signals(MATCH, fetcher=duplicated)
    assert result["prediction"]["status"] == "available"
    assert result["odds"]["status"] == "unavailable"
    assert result["odds"]["reason_code"] == "odds_unavailable"


def test_player_lens_is_top_five_only_without_provider_egress() -> None:
    calls: list[str] = []

    def fetch(path: str, _token: str):
        calls.append(path)
        raise AssertionError(path)

    value, digest = sportmonks._player_lens(
        19427573, 14, 9, "UEFA Champions League", "secret", fetch
    )
    assert value["status"] == "unavailable"
    assert value["reason_code"] == "competition_not_supported"
    assert digest is None
    assert calls == []


def test_player_lens_quarantines_duplicate_provider_player_identity() -> None:
    base = _fake_fetcher([])

    def duplicated(path: str, token: str):
        payload, digest = base(path, token)
        payload["data"]["lineups"].append({**payload["data"]["lineups"][0], "id": 502})
        return payload, digest

    value, digest = sportmonks._player_lens(
        19427573, 14, 9, "English Premier League", "secret", duplicated
    )
    assert value["status"] == "unavailable"
    assert value["reason_code"] == "player_identity_ambiguous"
    assert digest is None


def test_player_lens_quarantines_duplicate_metric_identity() -> None:
    base = _fake_fetcher([])

    def duplicated(path: str, token: str):
        payload, digest = base(path, token)
        details = payload["data"]["lineups"][0]["details"]
        details.append({**details[0], "id": 702, "data": {"value": 2}})
        return payload, digest

    value, digest = sportmonks._player_lens(
        19427573, 14, 9, "English Premier League", "secret", duplicated
    )
    assert value["status"] == "unavailable"
    assert value["reason_code"] == "player_metric_ambiguous"
    assert digest is None


@pytest.mark.parametrize("ambiguity", ["player_across_teams", "lineup_across_players"])
def test_player_lens_quarantines_cross_fixture_identity_reuse(ambiguity: str) -> None:
    base = _fake_fetcher([])

    def duplicated(path: str, token: str):
        payload, digest = base(path, token)
        first = payload["data"]["lineups"][0]
        second = {
            **first,
            "id": 502,
            "player_id": 602,
            "team_id": 9,
            "player_name": "Example Defender",
            "details": [],
        }
        if ambiguity == "player_across_teams":
            second["player_id"] = first["player_id"]
        else:
            second["id"] = first["id"]
        payload["data"]["lineups"].append(second)
        return payload, digest

    value, digest = sportmonks._player_lens(
        19427573, 14, 9, "English Premier League", "secret", duplicated
    )
    assert value["status"] == "unavailable"
    assert value["reason_code"] == "player_identity_ambiguous"
    assert digest is None


@pytest.mark.parametrize("mutation", ["duplicate", "mismatched_type"])
def test_player_lens_treats_ambiguous_lineup_confirmation_as_unverified(mutation: str) -> None:
    base = _fake_fetcher([])

    def ambiguous(path: str, token: str):
        payload, digest = base(path, token)
        metadata = payload["data"]["metadata"]
        if mutation == "duplicate":
            metadata.append({**metadata[0], "values": False})
        else:
            metadata[0]["type"]["id"] = 999
        return payload, digest

    value, digest = sportmonks._player_lens(
        19427573, 14, 9, "English Premier League", "secret", ambiguous
    )
    assert value["status"] == "available"
    assert value["lineup_state"] == "unverified"
    assert digest == "d" * 64


@pytest.mark.parametrize(
    "capabilities",
    [
        ["external_prediction"],
        ["external_odds"],
        ["player_lens"],
        ["external_prediction", "external_odds"],
        ["external_prediction", "player_lens"],
        ["external_odds", "player_lens"],
        ["external_prediction", "external_odds", "player_lens"],
    ],
)
def test_overall_status_ignores_disabled_capabilities(monkeypatch, tmp_path, capabilities) -> None:
    _wire_settings(monkeypatch, tmp_path)
    sportmonks.configure({"capabilities": capabilities})
    monkeypatch.setattr(sportmonks, "load_api_token", lambda: ("secret-token-value", "keychain"))

    result = sportmonks.fetch_outside_signals(MATCH, fetcher=_fake_fetcher([]))

    assert result["status"] == "available"
    for capability, field in (
        ("external_prediction", "prediction"),
        ("external_odds", "odds"),
        ("player_lens", "player_lens"),
    ):
        expected = "available" if capability in capabilities else "disabled"
        assert result[field]["status"] == expected


def test_keychain_write_keeps_token_out_of_process_arguments(monkeypatch) -> None:
    monkeypatch.setenv("GOLAVO_TOKEN", "launch-token")
    monkeypatch.setattr(sportmonks.sys, "platform", "darwin")
    captured: dict[str, object] = {}

    def fake_security(args, *, input_text=None):
        captured["args"] = args
        captured["input"] = input_text
        return CompletedProcess(["security"], 0, "", "")

    monkeypatch.setattr(sportmonks, "_run_security", fake_security)
    monkeypatch.setattr(sportmonks, "status", lambda: {"credential": {"configured": True}})
    result = sportmonks.save_api_token("abcdefghijklmnop")
    assert result["credential"]["configured"] is True
    assert "abcdefghijklmnop" not in repr(captured["args"])
    assert captured["input"] == "abcdefghijklmnop\n"


def test_routes_are_private_even_for_reads(monkeypatch) -> None:
    monkeypatch.delenv("GOLAVO_TOKEN", raising=False)
    client = TestClient(server_main.app)
    assert client.get("/api/v1/providers/sportmonks/settings").status_code == 403
    assert client.get("/api/v1/matches/m_exact/outside-signals").status_code == 403


def test_outside_signal_route_forbids_http_caching(monkeypatch) -> None:
    monkeypatch.setenv("GOLAVO_TOKEN", "launch-token")
    monkeypatch.setattr(
        server_main.matches,
        "get_match",
        lambda _match_id, **_kwargs: {"match": MATCH},
    )
    monkeypatch.setattr(
        sportmonks,
        "fetch_outside_signals",
        lambda _match: {"status": "available"},
    )
    client = TestClient(server_main.app)
    response = client.get(
        "/api/v1/matches/m_exact/outside-signals",
        headers={sportmonks.runtime.TOKEN_HEADER: "launch-token"},
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"


def test_request_allowlist_rejects_arbitrary_paths() -> None:
    with pytest.raises(sportmonks.SportmonksError) as exc:
        sportmonks._request_json("/v3/football/fixtures/1?redirect=https://example.com", "secret")
    assert exc.value.code == "path_rejected"


def test_request_allowlist_accepts_only_the_bounded_player_lens_shape() -> None:
    assert sportmonks._ALLOWED_PATH.fullmatch(
        "/v3/football/fixtures/19427573?include=lineups.details.type;metadata.type"
    )
    assert not sportmonks._ALLOWED_PATH.fullmatch(
        "/v3/football/fixtures/19427573?include=lineups.player;player.statistics"
    )
