"""World Cup history loads only for the exact competition gate."""

from __future__ import annotations

import golavo_core.facts as facts
import pandas as pd
from golavo_server import matches


def _frame(competition: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "match_id": "m_test",
                "kickoff_utc": pd.Timestamp("2026-07-01", tz="UTC"),
                "home_team": "France",
                "away_team": "Morocco",
                "competition": competition,
                "tournament": competition,
                "neutral": True,
                "source_id": "martj42-international-results",
                "source_kind": "international",
            }
        ]
    )


def test_exact_world_cup_gate_loads_history(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(matches, "_load_side_tables", lambda: (None, None))
    monkeypatch.setattr(matches, "_load_worldcup_history", lambda: "wc-history")
    monkeypatch.setattr(facts, "build_notebook", lambda **kwargs: captured.update(kwargs) or {})
    frame = _frame("FIFA World Cup")
    matches._compute_notebook_on_demand(frame.iloc[0], frame)
    assert captured["wc_history"] == "wc-history"


def test_qualification_does_not_load_world_cup_history(monkeypatch) -> None:
    captured = {}
    calls = []
    monkeypatch.setattr(matches, "_load_side_tables", lambda: (None, None))
    monkeypatch.setattr(matches, "_load_worldcup_history", lambda: calls.append(True))
    monkeypatch.setattr(facts, "build_notebook", lambda **kwargs: captured.update(kwargs) or {})
    frame = _frame("FIFA World Cup qualification")
    matches._compute_notebook_on_demand(frame.iloc[0], frame)
    assert calls == []
    assert captured["wc_history"] is None
