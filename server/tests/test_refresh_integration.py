from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from golavo_core.ingest import build_match_index
from golavo_server import matches, refresh, refresh_jobs, refresh_sources, refresh_state


def _write_raw(root: Path, martj_ref: str, worldcup_ref: str) -> None:
    martj = root / refresh_sources.MARTJ42 / martj_ref
    martj.mkdir(parents=True)
    (martj / "results.csv").write_text(
        "date,home_team,away_team,home_score,away_score,tournament,city,country,neutral\n"
        "2020-01-01,Alpha,Beta,2,1,Friendly,A City,Aland,FALSE\n",
        encoding="utf-8",
    )
    (martj / "former_names.csv").write_text(
        "current,former,start_date,end_date\n", encoding="utf-8"
    )
    (martj / "goalscorers.csv").write_text(
        "date,home_team,away_team,team,scorer,minute,own_goal,penalty\n", encoding="utf-8"
    )
    (martj / "shootouts.csv").write_text(
        "date,home_team,away_team,winner,first_shooter\n", encoding="utf-8"
    )
    (martj / "LICENSE").write_text("CC0 1.0 Universal", encoding="utf-8")

    worldcup = root / refresh_sources.WORLDCUP / worldcup_ref / "2026"
    worldcup.mkdir(parents=True)
    (worldcup / "worldcup.json").write_text(
        json.dumps(
            {
                "matches": [
                    {
                        "num": 104,
                        "date": "2026-08-01",
                        "time": "15:00 UTC-4",
                        "team1": "France",
                        "team2": "Spain",
                        "ground": "Test City",
                        "score": {},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (worldcup / "worldcup.stadiums.json").write_text(
        json.dumps({"stadiums": [{"city": "Test City", "cc": "us"}]}), encoding="utf-8"
    )
    (root / refresh_sources.WORLDCUP / worldcup_ref / "LICENSE.md").write_text(
        "CC0 1.0 Universal", encoding="utf-8"
    )


class FakeFetcher(refresh_sources.Fetcher):
    def __init__(self, raw: Path, refs: dict[str, str]) -> None:
        self.raw = raw
        self.refs = refs

    def get(  # type: ignore[override]
        self, url: str, *, headers=None, max_bytes=4 * 1024 * 1024, cancel=None
    ) -> refresh_sources.HttpResponse:
        del headers, max_bytes, cancel
        repo_by_source = {
            refresh_sources.MARTJ42: "martj42/international_results",
            refresh_sources.WORLDCUP: "openfootball/worldcup.json",
            refresh_sources.FOOTBALL: "openfootball/football.json",
        }
        for source_id, repo in repo_by_source.items():
            if f"/repos/{repo}/commits/" in url:
                body = json.dumps(
                    {
                        "sha": self.refs[source_id],
                        "commit": {"committer": {"date": "2026-07-15T00:00:00Z"}},
                    }
                ).encode()
                return refresh_sources.HttpResponse(200, {"etag": f'"{source_id}"'}, body, url)
        if "/git/trees/" in url:
            return refresh_sources.HttpResponse(
                200,
                {},
                json.dumps({"truncated": False, "tree": []}).encode(),
                url,
            )
        for source_id, repo in repo_by_source.items():
            prefix = f"https://raw.githubusercontent.com/{repo}/{self.refs[source_id]}/"
            if url.startswith(prefix):
                relative = url.removeprefix(prefix)
                body = (self.raw / source_id / self.refs[source_id] / relative).read_bytes()
                return refresh_sources.HttpResponse(200, {}, body, url)
        raise AssertionError(f"unexpected test URL: {url}")


def test_refresh_coordinator_builds_and_activates_generation(tmp_path: Path, monkeypatch) -> None:
    refs = {
        refresh_sources.MARTJ42: "1" * 40,
        refresh_sources.WORLDCUP: "2" * 40,
        refresh_sources.FOOTBALL: "3" * 40,
    }
    raw = tmp_path / "fixture-raw"
    _write_raw(raw, refs[refresh_sources.MARTJ42], refs[refresh_sources.WORLDCUP])

    base_pack = tmp_path / "base-pack"
    refresh.build_international_runtime_pack(
        raw,
        martj_ref=refs[refresh_sources.MARTJ42],
        martj_committed_at="2026-07-15T00:00:00Z",
        worldcup_ref=refs[refresh_sources.WORLDCUP],
        worldcup_committed_at="2026-07-15T00:00:00Z",
        retrieved_at_utc="2026-07-15T01:00:00Z",
        output_dir=base_pack,
    )
    base_index = tmp_path / "base-index" / "matches_index.parquet"
    build_match_index([base_pack], base_index)

    ledger = tmp_path / "Application Support" / "Golavo" / "ledger"
    ledger.mkdir(parents=True)
    monkeypatch.setenv("GOLAVO_DATA_DIR", str(ledger))
    monkeypatch.setattr(matches, "INDEX_PATH", base_index)

    coordinator = refresh_jobs.RefreshCoordinator()
    job, deduplicated = coordinator.start(
        mode="refresh",
        source_ids=None,
        trigger="manual",
        fetcher=FakeFetcher(raw, refs),
    )
    assert deduplicated is False
    assert job["state"] == "queued"
    assert coordinator._thread is not None
    coordinator._thread.join(timeout=10)
    assert not coordinator._thread.is_alive()

    completed = coordinator.get(job["job_id"])
    assert completed is not None
    assert completed["state"] == "done"
    assert completed["result"]["activated"] is True
    assert completed["result"]["capabilities"][0]["capability"] == "absent"

    active, fallback = refresh_state.active_generation()
    assert active is not None
    assert fallback is False
    refresh_state.verify_generation(active)
    frame = pd.read_parquet(active / "index" / "matches_index.parquet")
    fixture = frame.loc[frame["home_team"] == "France"].iloc[0]
    assert fixture["kickoff_source_id"] == refresh_sources.WORLDCUP
    assert bool(fixture["training_eligible"]) is False
    state = refresh_state.load_state()
    assert state["sources"][refresh_sources.MARTJ42]["active_ref"] == refs[refresh_sources.MARTJ42]
    assert state["sources"][refresh_sources.FOOTBALL]["capability"] == "absent"


def test_refresh_mode_rejects_partial_source_selection(tmp_path: Path, monkeypatch) -> None:
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    monkeypatch.setenv("GOLAVO_DATA_DIR", str(ledger))
    coordinator = refresh_jobs.RefreshCoordinator()
    try:
        coordinator.start(
            mode="refresh",
            source_ids=[refresh_sources.MARTJ42],
            trigger="manual",
        )
    except ValueError as exc:
        assert "complete approved source set" in str(exc)
    else:
        raise AssertionError("partial refresh selection must fail before starting a job")


def test_active_manifest_reconciles_interrupted_or_rolled_back_state() -> None:
    state = {
        "sources": {
            refresh_sources.MARTJ42: {
                "observed_ref": "2" * 40,
                "active_ref": "2" * 40,
                "health": "current",
                "error": None,
            }
        }
    }
    manifest = {
        "source_snapshots": [
            {
                "source_id": refresh_sources.MARTJ42,
                "upstream_ref": "1" * 40,
            }
        ]
    }
    refresh_jobs._sync_state_to_generation(state, manifest, "2026-07-15T12:00:00Z")
    source = state["sources"][refresh_sources.MARTJ42]
    assert source["active_ref"] == "1" * 40
    assert source["health"] == "stale"
    assert source["last_activated_at_utc"] == "2026-07-15T12:00:00Z"
