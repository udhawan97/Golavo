"""Tests for the auto-seal watcher's future-fixture detection (network-free)."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


_CSV = """date,home_team,away_team,home_score,away_score,tournament,city,country,neutral
2026-07-11,Norway,England,NA,NA,FIFA World Cup,Miami,United States,TRUE
2026-07-12,Foo,Bar,NA,NA,Friendly,X,Y,FALSE
2026-07-19,Spain,Brazil,NA,NA,FIFA World Cup,NJ,United States,TRUE
2026-07-19,France,Argentina,3,1,FIFA World Cup,NJ,United States,TRUE"""


def test_detects_only_genuinely_future_scheduled_fixtures() -> None:
    watch = _load("watch_and_seal")
    now = datetime(2026, 7, 12, 10, 0, tzinfo=UTC)
    found = watch.future_fixtures_from_csv(_CSV, now)
    # 07-11 already past; 07-12's 00:00 UTC proxy has passed (it's 10:00 now);
    # France-Argentina already has a score. Only Spain v Brazil (07-19) is ahead.
    assert [(f["date"], f["home_team"], f["away_team"]) for f in found] == [
        ("2026-07-19", "Spain", "Brazil")
    ]


def test_no_future_fixtures_yields_empty() -> None:
    watch = _load("watch_and_seal")
    now = datetime(2026, 7, 20, 0, 0, tzinfo=UTC)  # past every fixture above
    assert watch.future_fixtures_from_csv(_CSV, now) == []
