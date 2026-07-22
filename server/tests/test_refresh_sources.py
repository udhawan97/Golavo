from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

import pytest
from golavo_server import refresh_sources


class FakeFetcher(refresh_sources.Fetcher):
    def __init__(self, responses: dict[str, refresh_sources.HttpResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get(self, url: str, *, headers=None, max_bytes=0, cancel=None):  # type: ignore[override]
        self.calls.append((url, headers or {}))
        if cancel is not None and cancel.is_set():
            raise refresh_sources.RefreshCancelled()
        return self.responses[url]


def response(url: str, body: object, *, etag: str | None = None, status: int = 200):
    headers = {"content-type": "application/json"}
    if etag:
        headers["etag"] = etag
    payload = b"" if status == 304 else json.dumps(body).encode()
    return refresh_sources.HttpResponse(status, headers, payload, url)


def test_current_european_season_rolls_on_july_first() -> None:
    assert refresh_sources.current_european_season(datetime(2026, 6, 30, tzinfo=UTC)) == "2025-26"
    assert refresh_sources.current_european_season(datetime(2026, 7, 1, tzinfo=UTC)) == "2026-27"


def test_conditional_revision_check_reuses_saved_ref_on_304() -> None:
    url = "https://api.github.com/repos/martj42/international_results/commits/master"
    fetcher = FakeFetcher({url: response(url, {}, status=304)})
    previous = {
        "observed_ref": "a" * 40,
        "upstream_committed_at_utc": "2026-01-01T00:00:00Z",
        "etag": 'W/"saved"',
    }
    observed = refresh_sources.check_source(refresh_sources.MARTJ42, previous, fetcher=fetcher)
    assert observed.ref == "a" * 40
    assert observed.changed is False
    assert fetcher.calls[0][1]["If-None-Match"] == 'W/"saved"'


def test_football_absence_is_a_capability_not_an_error(tmp_path: Path) -> None:
    commit_url = "https://api.github.com/repos/openfootball/football.json/commits/master"
    ref = "b" * 40
    tree_url = (
        f"https://api.github.com/repos/openfootball/football.json/git/trees/{ref}?recursive=1"
    )
    fetcher = FakeFetcher(
        {
            commit_url: response(
                commit_url,
                {"sha": ref, "commit": {"committer": {"date": "2026-05-30T00:00:00Z"}}},
                etag="new",
            ),
            tree_url: response(
                tree_url,
                {"truncated": False, "tree": [{"path": "2025-26/en.1.json", "type": "blob"}]},
            ),
        }
    )
    observed = refresh_sources.check_source(
        refresh_sources.FOOTBALL,
        {},
        fetcher=fetcher,
        now=datetime(2026, 7, 15, tzinfo=UTC),
    )
    assert observed.season == "2026-27"
    assert observed.capability == "absent"
    assert observed.current_paths == ()
    receipt = refresh_sources.download_source_snapshot(observed, tmp_path, fetcher=fetcher)
    assert [entry["path"] for entry in receipt["files"]] == ["git-tree.json"]
    assert (tmp_path / refresh_sources.FOOTBALL / ref / "git-tree.json").is_file()


def test_domestic_txt_source_discovers_only_its_allowlisted_current_schedule() -> None:
    ref = "4" * 40
    commit_url = "https://api.github.com/repos/openfootball/england/commits/master"
    tree_url = f"https://api.github.com/repos/openfootball/england/git/trees/{ref}?recursive=1"
    fetcher = FakeFetcher(
        {
            commit_url: response(
                commit_url,
                {"sha": ref, "commit": {"committer": {"date": "2026-07-21T00:00:00Z"}}},
            ),
            tree_url: response(
                tree_url,
                {
                    "tree": [
                        {"path": "2026-27/1-premierleague.txt", "type": "blob"},
                        {"path": "2026-27/2-championship.txt", "type": "blob"},
                    ]
                },
            ),
        }
    )

    observed = refresh_sources.check_source(
        refresh_sources.ENGLAND,
        fetcher=fetcher,
        now=datetime(2026, 7, 21, tzinfo=UTC),
    )

    assert observed.capability == "available"
    assert observed.current_paths == ("2026-27/1-premierleague.txt",)
    assert refresh_sources.source_paths(observed) == (
        "2026-27/1-premierleague.txt",
        "LICENSE.md",
    )


def test_each_domestic_refresh_source_has_one_fixed_league_path() -> None:
    assert {
        source_id: refresh_sources.expected_current_paths(source_id, "2026-27")
        for source_id in refresh_sources.DOMESTIC_SOURCE_IDS
    } == {
        "openfootball-england": ("2026-27/1-premierleague.txt",),
        "openfootball-deutschland": ("2026-27/1-bundesliga.txt",),
        "openfootball-espana": ("2026-27/1-liga.txt",),
        "openfootball-italy": ("2026-27/1-seriea.txt",),
        "openfootball-europe": ("france/2026-27_fr1.txt",),
    }


def test_pinned_download_is_hash_receipted_and_leaves_no_part_file(tmp_path: Path) -> None:
    ref = "c" * 40
    observation = refresh_sources.SourceObservation(
        source_id=refresh_sources.FOOTBALL,
        ref=ref,
        committed_at_utc="2026-07-15T00:00:00Z",
        etag="e",
        checked_at_utc="2026-07-15T01:00:00Z",
        changed=True,
        capability="partial",
        season="2026-27",
        current_paths=("2026-27/en.1.json",),
    )
    data_url = (
        f"https://raw.githubusercontent.com/openfootball/football.json/{ref}/2026-27/en.1.json"
    )
    license_url = f"https://raw.githubusercontent.com/openfootball/football.json/{ref}/LICENSE.md"
    tree_url = (
        f"https://api.github.com/repos/openfootball/football.json/git/trees/{ref}?recursive=1"
    )
    fetcher = FakeFetcher(
        {
            tree_url: response(
                tree_url,
                {
                    "truncated": False,
                    "tree": [{"path": "2026-27/en.1.json", "type": "blob"}],
                },
            ),
            data_url: refresh_sources.HttpResponse(
                200, {"content-type": "application/json"}, b'{"matches":[]}', data_url
            ),
            license_url: refresh_sources.HttpResponse(
                200, {"content-type": "text/plain"}, b"CC0 1.0 Universal", license_url
            ),
        }
    )
    receipt = refresh_sources.download_source_snapshot(observation, tmp_path, fetcher=fetcher)
    assert receipt["files"][0]["sha256"]
    assert (tmp_path / refresh_sources.FOOTBALL / ref / "2026-27/en.1.json").is_file()
    assert list(tmp_path.rglob("*.part")) == []


def test_cancelled_download_creates_no_snapshot(tmp_path: Path) -> None:
    ref = "d" * 40
    observation = refresh_sources.SourceObservation(
        refresh_sources.MARTJ42,
        ref,
        "2026-01-01T00:00:00Z",
        None,
        "2026-01-01T00:00:00Z",
        True,
        "available",
    )
    cancel = Event()
    cancel.set()
    with pytest.raises(refresh_sources.RefreshCancelled):
        refresh_sources.download_source_snapshot(
            observation, tmp_path, fetcher=FakeFetcher({}), cancel=cancel
        )
