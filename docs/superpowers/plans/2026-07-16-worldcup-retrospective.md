# World Cup 2026 Retrospective Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `/lab/worldcup-2026`, a two-layer World Cup retrospective — a per-match backtest with seal semantics ("story") beside the existing evaluation fold ("trust") — computed on demand from the active pack and cached against the index fingerprint.

**Architecture:** A pure core module replays each of the 104 WC2026 matches at its own `kickoff − 1s` cutoff. A server module runs that behind `jobs.py` progress with the two-level cache copied from `analysis.py`, and recomputes `evaluation.evaluate()` on the same active pack so both layers report the same tournament. A thin React view renders the two layers with their claims kept visibly distinct.

**Tech Stack:** Python 3.12, pandas, numpy, FastAPI, pytest, React 18 + TypeScript, vitest.

**Spec:** `docs/superpowers/specs/2026-07-16-worldcup-retrospective-design.md`

## Global Constraints

- **Four families, not five:** `("climatological", "elo_ordlogit", "poisson_independent", "dixon_coles")`. `bivariate_poisson` is numerically identical to `poisson_independent` on every recorded fold; showing both implies two opinions where there is one.
- **Rank on `dixon_coles` only** — it is `DEFAULT_FAMILY` in `server/golavo_server/seal.py:36`. Ranking on a cross-family average would describe a forecast the app never makes.
- **Never call this a record.** Every number is a backtest. `ledger_status` is always the literal `"never_persisted_or_scored_as_a_seal"`.
- **Story and trust must never merge numbers.** Different cutoffs, different claims.
- **Do not invent a stricter cutoff than `analysis.py:421`.** The claim is "what the app would have told you"; fidelity to the real path *is* the feature.
- **Tournament window:** `window_start = "2026-06-11"`, `window_end = "2026-07-19"` — reuse from `evaluation.FOLDS` (the `WC2026` entry), never re-declare.
- **New pure modules start at schema version `"0.1.0"`** with a module-prefixed constant name.
- **Typed states, never empty objects.** A missing guarantee is a typed state with a reason.
- Python: `from __future__ import annotations` first; `ruff check .` must pass.
- Run tests with `PYTHONPATH=core:server /Users/umang/.pyenv/shims/python3.12 -m pytest`.
- UI tests: `npx vitest run` from `ui/` (bare `npm test` fails — vitest is not on PATH).

---

### Task 1: Core retrospective module

**Files:**
- Create: `core/golavo_core/retrospective.py`
- Test: `core/tests/test_retrospective.py`

**Interfaces:**
- Consumes: `golavo_core.ingest.training_rows`, `golavo_core.models.fit_model`, `golavo_core.evaluation.FOLDS`.
- Produces:
  - `RETROSPECTIVE_SCHEMA_VERSION: str = "0.1.0"`
  - `RETROSPECTIVE_FAMILIES: tuple[str, ...]`
  - `RANKING_FAMILY: str = "dixon_coles"`
  - `class RetrospectiveUnavailable(ValueError)`
  - `def world_cup_2026_retrospective(frame, *, progress=None, is_cancelled=None) -> dict[str, Any]`
    - `progress: Callable[[int, int], None] | None` — called as `progress(done, total)`
    - `is_cancelled: Callable[[], bool] | None` — polled per match; raises `RetrospectiveCancelled` when true
  - `class RetrospectiveCancelled(Exception)`

- [ ] **Step 1: Write the failing tests**

Create `core/tests/test_retrospective.py`:

```python
from __future__ import annotations

import json

import pandas as pd
import pytest
from golavo_core.retrospective import (
    RANKING_FAMILY,
    RETROSPECTIVE_FAMILIES,
    RetrospectiveCancelled,
    RetrospectiveUnavailable,
    world_cup_2026_retrospective,
)

TEAMS = ("France", "Spain", "England", "Argentina")


def _history(n: int = 80) -> list[dict]:
    rows = []
    for index in range(n):
        day = pd.Timestamp("2025-01-01", tz="UTC") + pd.Timedelta(days=index)
        rows.append(
            {
                "match_id": f"m_hist_{index:03d}",
                "date": day.tz_localize(None),
                "kickoff_utc": day,
                "home_team": TEAMS[index % 4],
                "away_team": TEAMS[(index + 1) % 4],
                "home_score": index % 3,
                "away_score": (index + 1) % 2,
                "is_complete": True,
                "neutral": True,
                "competition": "Friendly",
                "kickoff_precision": "day",
                "source_id": "martj42-international-results",
                "source_kind": "international",
            }
        )
    return rows


def _wc_match(mid: str, kickoff: str, home: str, away: str, hs, aws, precision="exact") -> dict:
    k = pd.Timestamp(kickoff)
    return {
        "match_id": mid,
        "date": k.tz_convert(None).normalize(),
        "kickoff_utc": k,
        "home_team": home,
        "away_team": away,
        "home_score": hs,
        "away_score": aws,
        "is_complete": hs is not None,
        "neutral": True,
        "competition": "FIFA World Cup",
        "kickoff_precision": precision,
        "source_id": "martj42-international-results",
        "source_kind": "international",
    }


def _frame(wc_rows: list[dict] | None = None) -> pd.DataFrame:
    rows = wc_rows if wc_rows is not None else [
        _wc_match("m_wc1", "2026-06-20T12:00:00Z", "France", "Spain", 1, 0),
        _wc_match("m_wc2", "2026-06-20T20:00:00Z", "England", "Argentina", 2, 1),
    ]
    return pd.DataFrame([*_history(), *rows])


def test_returns_one_row_per_completed_match_ranked_by_log_loss() -> None:
    result = world_cup_2026_retrospective(_frame())
    assert result["schema_version"] == "0.1.0"
    assert result["ledger_status"] == "never_persisted_or_scored_as_a_seal"
    assert [row["match_id"] for row in result["matches"]] == ["m_wc1", "m_wc2"]
    for row in result["matches"]:
        assert set(row["families"]) == set(RETROSPECTIVE_FAMILIES)
        assert row["log_loss"] == pytest.approx(
            row["families"][RANKING_FAMILY]["log_loss"]
        )
    # biggest_surprises is the same rows ordered by the ranking family's loss
    losses = [row["log_loss"] for row in result["biggest_surprises"]]
    assert losses == sorted(losses, reverse=True)


def test_bivariate_poisson_is_not_offered_as_a_separate_voice() -> None:
    assert "bivariate_poisson" not in RETROSPECTIVE_FAMILIES
    result = world_cup_2026_retrospective(_frame())
    assert "bivariate_poisson" not in result["matches"][0]["families"]


def test_a_later_same_day_result_never_reaches_an_earlier_match() -> None:
    """The story layer's whole claim is a pre-kickoff forecast."""
    clean = world_cup_2026_retrospective(_frame())
    poisoned_rows = [
        _wc_match("m_wc1", "2026-06-20T12:00:00Z", "France", "Spain", 1, 0),
        _wc_match("m_wc2", "2026-06-20T20:00:00Z", "England", "Argentina", 9, 0),
    ]
    poisoned = world_cup_2026_retrospective(_frame(poisoned_rows))
    first_clean = next(r for r in clean["matches"] if r["match_id"] == "m_wc1")
    first_poisoned = next(r for r in poisoned["matches"] if r["match_id"] == "m_wc1")
    assert first_clean["families"] == first_poisoned["families"], (
        "a 20:00 result changed the 12:00 forecast"
    )


def test_future_rows_never_change_any_forecast() -> None:
    clean = world_cup_2026_retrospective(_frame())
    extra = _frame().to_dict("records") + [
        {
            **_history(1)[0],
            "match_id": "m_poison",
            "date": pd.Timestamp("2026-08-01"),
            "kickoff_utc": pd.Timestamp("2026-08-01T12:00:00Z"),
            "home_score": 99,
            "away_score": 0,
        }
    ]
    poisoned = world_cup_2026_retrospective(pd.DataFrame(extra))
    assert clean["matches"] == poisoned["matches"]


def test_is_deterministic_byte_for_byte() -> None:
    a = world_cup_2026_retrospective(_frame())
    b = world_cup_2026_retrospective(_frame())
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_day_precision_rows_are_carried_not_hidden() -> None:
    rows = [
        _wc_match("m_wc1", "2026-06-20T00:00:00Z", "France", "Spain", 1, 0, precision="day"),
        _wc_match("m_wc2", "2026-06-21T20:00:00Z", "England", "Argentina", 2, 1),
    ]
    result = world_cup_2026_retrospective(_frame(rows))
    by_id = {row["match_id"]: row for row in result["matches"]}
    assert by_id["m_wc1"]["kickoff_precision"] == "day"
    assert by_id["m_wc2"]["kickoff_precision"] == "exact"


def test_scheduled_matches_are_reported_as_typed_pending_not_scored() -> None:
    rows = [
        _wc_match("m_wc1", "2026-06-20T12:00:00Z", "France", "Spain", 1, 0),
        _wc_match("m_wc2", "2026-07-19T19:00:00Z", "Spain", "Argentina", None, None),
    ]
    result = world_cup_2026_retrospective(_frame(rows))
    assert [row["match_id"] for row in result["matches"]] == ["m_wc1"]
    assert result["coverage"]["scored"] == 1
    assert result["coverage"]["pending"] == 1
    assert result["coverage"]["status"] == "partial"
    assert "not yet played" in result["coverage"]["note"]


def test_complete_tournament_reports_complete_coverage() -> None:
    result = world_cup_2026_retrospective(_frame())
    assert result["coverage"]["status"] == "complete"
    assert result["coverage"]["pending"] == 0


def test_no_world_cup_rows_is_typed_unavailable() -> None:
    frame = pd.DataFrame(_history())
    with pytest.raises(RetrospectiveUnavailable, match="no completed 2026 World Cup"):
        world_cup_2026_retrospective(frame)


def test_progress_is_reported_and_cancellation_is_honoured() -> None:
    seen: list[tuple[int, int]] = []
    world_cup_2026_retrospective(_frame(), progress=lambda done, total: seen.append((done, total)))
    assert seen[-1] == (2, 2)

    with pytest.raises(RetrospectiveCancelled):
        world_cup_2026_retrospective(_frame(), is_cancelled=lambda: True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=core:server /Users/umang/.pyenv/shims/python3.12 -m pytest core/tests/test_retrospective.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'golavo_core.retrospective'`

- [ ] **Step 3: Write the implementation**

Create `core/golavo_core/retrospective.py`:

```python
"""Per-match World Cup 2026 backtest — never a ledger artifact, never a record.

Each match is replayed at its own ``kickoff - 1s`` cutoff, the same conservative
information boundary the seal and the Match Cockpit replay use, so a row here is
exactly what the app would have said had it been asked that moment. That is the
whole claim: nothing here was called in advance by anyone, and nothing here is
persisted or scored as a seal.

The module is pure — no I/O, no clock, no writes.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import pandas as pd

from golavo_core.evaluation import FOLDS
from golavo_core.ingest import training_rows
from golavo_core.models import fit_model

RETROSPECTIVE_SCHEMA_VERSION = "0.1.0"

# Four voices, not five: bivariate_poisson is numerically identical to
# poisson_independent on every recorded fold, so offering both would imply two
# independent opinions where there is one.
RETROSPECTIVE_FAMILIES: tuple[str, ...] = (
    "climatological",
    "elo_ordlogit",
    "poisson_independent",
    "dixon_coles",
)

# The app's own DEFAULT_FAMILY (server/golavo_server/seal.py). The ranking must
# follow the family the app would actually have sealed with; a cross-family
# average would describe a forecast the app never makes.
RANKING_FAMILY = "dixon_coles"

RETROSPECTIVE_LABEL = (
    "Tournament retrospective — every match backtested at its own pre-kickoff cutoff. "
    "A backtest, not a sealed record."
)

_WORLD_CUP = "FIFA World Cup"
_WC2026 = next(fold for fold in FOLDS if fold["fold_id"] == "WC2026")


class RetrospectiveUnavailable(ValueError):
    """The committed snapshot cannot support an honest tournament retrospective."""


class RetrospectiveCancelled(Exception):
    """The caller asked for the run to stop."""


def _utc(value: str | pd.Timestamp) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    return (
        timestamp.tz_localize("UTC")
        if timestamp.tzinfo is None
        else timestamp.tz_convert("UTC")
    )


def _iso(value: pd.Timestamp) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _outcome(home_score: Any, away_score: Any) -> int:
    """0 = home win, 1 = draw, 2 = away win — matching Prediction.probs order."""
    home, away = int(home_score), int(away_score)
    if home > away:
        return 0
    return 1 if home == away else 2


def _tournament_rows(frame: pd.DataFrame) -> pd.DataFrame:
    kickoff = pd.to_datetime(frame["kickoff_utc"], utc=True)
    start = _utc(_WC2026["window_start"])
    end = _utc(_WC2026["window_end"]) + pd.Timedelta(days=1)
    selected = frame.loc[
        frame["competition"].astype("string").eq(_WORLD_CUP)
        & (kickoff >= start)
        & (kickoff < end)
    ].copy()
    selected["_kickoff"] = pd.to_datetime(selected["kickoff_utc"], utc=True)
    return selected.sort_values(["_kickoff", "match_id"], kind="mergesort")


def world_cup_2026_retrospective(
    frame: pd.DataFrame,
    *,
    progress: Callable[[int, int], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Replay every completed 2026 World Cup match at its own pre-kickoff cutoff."""
    # Scope to the fixture's own source kind so a shared team string cannot merge
    # club history into an international fixture.
    international = frame.loc[frame["source_kind"].astype("string").eq("international")].copy()
    tournament = _tournament_rows(frame)
    complete = tournament.loc[tournament["is_complete"].astype("boolean").fillna(False)]
    pending = int(len(tournament) - len(complete))

    if complete.empty:
        raise RetrospectiveUnavailable(
            "This snapshot has no completed 2026 World Cup matches to look back on."
        )

    total = int(len(complete))
    rows: list[dict[str, Any]] = []
    for done, (_, match) in enumerate(complete.iterrows(), start=1):
        if is_cancelled is not None and is_cancelled():
            raise RetrospectiveCancelled()

        kickoff = _utc(match["kickoff_utc"])
        cutoff = kickoff - pd.Timedelta(seconds=1)
        cutoff_iso = _iso(cutoff)
        match_id = str(match["match_id"])

        train = training_rows(international, cutoff_iso)
        # Belt-and-braces: never let the fixture's own row train its own forecast,
        # even if a malformed snapshot dated it before the cutoff.
        train = train.loc[~train["match_id"].astype("string").eq(match_id)].copy()

        home = str(match["home_team"])
        away = str(match["away_team"])
        neutral = bool(match.get("neutral") or False)
        outcome = _outcome(match["home_score"], match["away_score"])

        families: dict[str, Any] = {}
        for family in RETROSPECTIVE_FAMILIES:
            fitted = fit_model(family, train, cutoff_iso)
            probs = fitted.predict(home, away, neutral).probs
            assigned = min(max(float(probs[outcome]), 1e-12), 1.0)
            families[family] = {
                "probs": {
                    "home": round(float(probs[0]), 9),
                    "draw": round(float(probs[1]), 9),
                    "away": round(float(probs[2]), 9),
                },
                "log_loss": round(-math.log(assigned), 9),
            }

        rows.append(
            {
                "match_id": match_id,
                "kickoff_utc": _iso(kickoff),
                "kickoff_precision": str(match.get("kickoff_precision") or "day"),
                "information_cutoff_utc": cutoff_iso,
                "home_team": home,
                "away_team": away,
                "home_score": int(match["home_score"]),
                "away_score": int(match["away_score"]),
                "outcome": ("home", "draw", "away")[outcome],
                "families": families,
                "log_loss": families[RANKING_FAMILY]["log_loss"],
            }
        )
        if progress is not None:
            progress(done, total)

    ranked = sorted(rows, key=lambda row: (-row["log_loss"], row["match_id"]))
    status = "complete" if pending == 0 else "partial"
    note = (
        "Every 2026 World Cup match in this snapshot has been played and backtested."
        if pending == 0
        else f"{pending} match(es) in this snapshot are not yet played and are not scored here."
    )

    return {
        "schema_version": RETROSPECTIVE_SCHEMA_VERSION,
        "status": "available",
        "label": RETROSPECTIVE_LABEL,
        "tournament_id": "worldcup-2026",
        "tournament_name": "2026 FIFA World Cup",
        "ledger_status": "never_persisted_or_scored_as_a_seal",
        "ranking_family": RANKING_FAMILY,
        "ranking_metric": "log_loss",
        "families": list(RETROSPECTIVE_FAMILIES),
        "window_start": _WC2026["window_start"],
        "window_end": _WC2026["window_end"],
        "coverage": {
            "status": status,
            "scored": total,
            "pending": pending,
            "note": note,
        },
        "matches": rows,
        "biggest_surprises": ranked,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=core:server /Users/umang/.pyenv/shims/python3.12 -m pytest core/tests/test_retrospective.py -q`
Expected: PASS (11 tests)

Then lint: `/Users/umang/.pyenv/shims/python3.12 -m ruff check core/golavo_core/retrospective.py core/tests/test_retrospective.py`
Expected: `All checks passed!`

- [ ] **Step 5: Sanity-check against the real index**

Run:
```bash
PYTHONPATH=core:server /Users/umang/.pyenv/shims/python3.12 -c "
import pandas as pd, time
from golavo_core.retrospective import world_cup_2026_retrospective
df = pd.read_parquet('data/index/matches_index.parquet')
t = time.time()
r = world_cup_2026_retrospective(df, progress=lambda d, n: None)
print('elapsed %.1fs' % (time.time()-t), '| coverage', r['coverage'])
for row in r['biggest_surprises'][:3]:
    print('  UPSET', row['home_team'], row['home_score'], '-', row['away_score'], row['away_team'], 'loss=%.3f' % row['log_loss'])
"
```
Expected: elapsed ~120-170s, `coverage` shows `scored: 102, pending: 2, status: partial`, and three plausible upsets.

- [ ] **Step 6: Commit**

```bash
git add core/golavo_core/retrospective.py core/tests/test_retrospective.py
git commit -m "feat: backtest every World Cup 2026 match at its own cutoff"
```

---

### Task 2: Contract schema

**Files:**
- Create: `docs/contracts/tournament_retrospective.schema.json`
- Test: `core/tests/test_retrospective.py` (append)

**Interfaces:**
- Consumes: Task 1's `world_cup_2026_retrospective` output shape.
- Produces: a schema the server test in Task 4 validates responses against.

- [ ] **Step 1: Write the failing test**

Append to `core/tests/test_retrospective.py`:

```python
def test_output_validates_against_the_published_contract() -> None:
    from pathlib import Path

    from jsonschema import Draft202012Validator, FormatChecker

    root = Path(__file__).resolve().parents[2]
    schema = json.loads(
        (root / "docs" / "contracts" / "tournament_retrospective.schema.json").read_text(
            encoding="utf-8"
        )
    )
    result = world_cup_2026_retrospective(_frame())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(result)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=core:server /Users/umang/.pyenv/shims/python3.12 -m pytest core/tests/test_retrospective.py -q -k contract`
Expected: FAIL — `FileNotFoundError: ... tournament_retrospective.schema.json`

- [ ] **Step 3: Write the schema**

Create `docs/contracts/tournament_retrospective.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Tournament retrospective",
  "description": "A per-match backtest of a finished tournament. Every number is a backtest computed at that match's own pre-kickoff cutoff. Nothing here is a sealed record.",
  "type": "object",
  "required": [
    "schema_version", "status", "label", "tournament_id", "tournament_name",
    "ledger_status", "ranking_family", "ranking_metric", "families",
    "window_start", "window_end", "coverage", "matches", "biggest_surprises"
  ],
  "additionalProperties": true,
  "properties": {
    "schema_version": { "const": "0.1.0" },
    "status": { "enum": ["available", "unavailable"] },
    "label": { "type": "string", "minLength": 1 },
    "reason": { "type": "string" },
    "tournament_id": { "const": "worldcup-2026" },
    "tournament_name": { "type": "string" },
    "ledger_status": { "const": "never_persisted_or_scored_as_a_seal" },
    "ranking_family": { "const": "dixon_coles" },
    "ranking_metric": { "const": "log_loss" },
    "families": {
      "type": "array",
      "items": {
        "enum": ["climatological", "elo_ordlogit", "poisson_independent", "dixon_coles"]
      },
      "minItems": 1,
      "uniqueItems": true
    },
    "window_start": { "type": "string" },
    "window_end": { "type": "string" },
    "coverage": {
      "type": "object",
      "required": ["status", "scored", "pending", "note"],
      "properties": {
        "status": { "enum": ["complete", "partial"] },
        "scored": { "type": "integer", "minimum": 0 },
        "pending": { "type": "integer", "minimum": 0 },
        "note": { "type": "string", "minLength": 1 }
      }
    },
    "matches": { "type": "array", "items": { "$ref": "#/$defs/Row" } },
    "biggest_surprises": { "type": "array", "items": { "$ref": "#/$defs/Row" } },
    "provenance": {
      "type": "object",
      "properties": {
        "index_sha256": { "type": "string" },
        "pack": { "type": "string" }
      }
    }
  },
  "$defs": {
    "Row": {
      "type": "object",
      "required": [
        "match_id", "kickoff_utc", "kickoff_precision", "information_cutoff_utc",
        "home_team", "away_team", "home_score", "away_score", "outcome",
        "families", "log_loss"
      ],
      "additionalProperties": false,
      "properties": {
        "match_id": { "type": "string" },
        "kickoff_utc": { "type": "string", "format": "date-time" },
        "kickoff_precision": { "enum": ["exact", "day"] },
        "information_cutoff_utc": { "type": "string", "format": "date-time" },
        "home_team": { "type": "string" },
        "away_team": { "type": "string" },
        "home_score": { "type": "integer", "minimum": 0 },
        "away_score": { "type": "integer", "minimum": 0 },
        "outcome": { "enum": ["home", "draw", "away"] },
        "log_loss": { "type": "number", "minimum": 0 },
        "families": {
          "type": "object",
          "minProperties": 1,
          "additionalProperties": {
            "type": "object",
            "required": ["probs", "log_loss"],
            "additionalProperties": false,
            "properties": {
              "log_loss": { "type": "number", "minimum": 0 },
              "probs": {
                "type": "object",
                "required": ["home", "draw", "away"],
                "additionalProperties": false,
                "properties": {
                  "home": { "type": "number", "minimum": 0, "maximum": 1 },
                  "draw": { "type": "number", "minimum": 0, "maximum": 1 },
                  "away": { "type": "number", "minimum": 0, "maximum": 1 }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `PYTHONPATH=core:server /Users/umang/.pyenv/shims/python3.12 -m pytest core/tests/test_retrospective.py -q`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add docs/contracts/tournament_retrospective.schema.json core/tests/test_retrospective.py
git commit -m "feat: publish the tournament retrospective contract"
```

---

### Task 3: Server module — cache, trust layer, compute

**Files:**
- Create: `server/golavo_server/retrospective.py`
- Modify: `server/golavo_server/matches.py:161` (register the derivative cache reset)
- Test: `server/tests/test_retrospective_api.py`

**Interfaces:**
- Consumes: Task 1's core module; `matches.index_snapshot()`, `matches.apply_if_snapshot_current`, `matches.snapshot_is_current`; `seal.resolve_pack_dir`; `golavo_core.evaluation.evaluate`; `runtime.analysis_cache_dir`.
- Produces:
  - `def reset_cache() -> None`
  - `def build(progress=None, is_cancelled=None) -> dict[str, Any]` — the cached, provenance-stamped envelope with both layers.

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_retrospective_api.py`:

```python
from __future__ import annotations

import pytest
from golavo_server import matches
from golavo_server import retrospective as server_retrospective


@pytest.fixture(autouse=True)
def _reset():
    matches.reset_cache()
    server_retrospective.reset_cache()
    yield
    matches.reset_cache()
    server_retrospective.reset_cache()


def test_matches_reset_clears_the_retrospective_cache() -> None:
    """A repointed index must never serve a retrospective from the old frame."""
    server_retrospective._CACHE[("probe",)] = {"stale": True}
    matches.reset_cache()
    assert server_retrospective._CACHE == {}


def test_build_stamps_both_layers_with_one_pack(monkeypatch) -> None:
    """Story and trust must never describe different packs."""
    monkeypatch.setattr(
        server_retrospective,
        "_story",
        lambda frame, progress, is_cancelled: {
            "schema_version": "0.1.0",
            "status": "available",
            "coverage": {"status": "complete", "scored": 1, "pending": 0, "note": "n"},
            "matches": [],
            "biggest_surprises": [],
        },
    )
    monkeypatch.setattr(
        server_retrospective, "_trust", lambda pack_dir: {"competition": "FIFA World Cup"}
    )
    result = server_retrospective.build()
    assert result["provenance"]["index_sha256"]
    assert result["provenance"]["pack"]
    assert result["trust"]["competition"] == "FIFA World Cup"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=core:server /Users/umang/.pyenv/shims/python3.12 -m pytest server/tests/test_retrospective_api.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'golavo_server.retrospective'`

- [ ] **Step 3: Write the implementation**

Create `server/golavo_server/retrospective.py`:

```python
"""Server wrapper for the World Cup retrospective — cached, never persisted.

Both layers resolve the SAME active pack. The story layer reads the index frame;
the trust layer re-runs the evaluation fold against the pack directory. Reading
the committed eval summary instead would report a different match count than the
story layer computed, which is exactly the staleness this surface avoids.
"""

from __future__ import annotations

from typing import Any

from golavo_server import matches, runtime, seal

_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}
_CACHE_ORDER: list[tuple[Any, ...]] = []
_CACHE_MAX = 4  # each entry costs minutes to build; keep a few generations

_MARTJ42 = "martj42-international-results"


def reset_cache() -> None:
    """Drop the in-process memo (tests / after an index repoint)."""
    _CACHE.clear()
    _CACHE_ORDER.clear()


def _remember(key: tuple[Any, ...], value: dict[str, Any]) -> None:
    _CACHE[key] = value
    _CACHE_ORDER.append(key)
    while len(_CACHE_ORDER) > _CACHE_MAX:
        _CACHE.pop(_CACHE_ORDER.pop(0), None)


def _story(frame: Any, progress: Any, is_cancelled: Any) -> dict[str, Any]:
    from golavo_core.retrospective import world_cup_2026_retrospective

    return world_cup_2026_retrospective(frame, progress=progress, is_cancelled=is_cancelled)


def _trust(pack_dir: Any) -> dict[str, Any] | None:
    """The WC2026 fold's report card, recomputed on the active pack."""
    from golavo_core.evaluation import evaluate

    summary = evaluate(pack_dir)
    for card in summary.get("report_cards", []):
        if card.get("competition") == "FIFA World Cup":
            return card
    return None


def build(
    *,
    progress: Any = None,
    is_cancelled: Any = None,
) -> dict[str, Any]:
    """The full two-layer retrospective for the active index and pack."""
    from golavo_core.retrospective import RetrospectiveUnavailable

    snapshot = matches.index_snapshot()
    pack_dir = seal.resolve_pack_dir(_MARTJ42, "international")
    pack_name = pack_dir.name if pack_dir is not None else "unknown"
    key = (snapshot.fingerprint, snapshot.epoch, pack_name)

    cached = _CACHE.get(key)
    if cached is not None and matches.snapshot_is_current(snapshot):
        return cached

    try:
        story = _story(snapshot.frame, progress, is_cancelled)
    except RetrospectiveUnavailable as exc:
        story = {
            "schema_version": "0.1.0",
            "status": "unavailable",
            "label": (
                "Tournament retrospective — every match backtested at its own pre-kickoff "
                "cutoff. A backtest, not a sealed record."
            ),
            "tournament_id": "worldcup-2026",
            "tournament_name": "2026 FIFA World Cup",
            "ledger_status": "never_persisted_or_scored_as_a_seal",
            "reason": str(exc),
            "coverage": {"status": "partial", "scored": 0, "pending": 0, "note": str(exc)},
            "matches": [],
            "biggest_surprises": [],
        }

    result = dict(story)
    result["trust"] = _trust(pack_dir) if pack_dir is not None else None
    result["provenance"] = {"index_sha256": snapshot.fingerprint, "pack": pack_name}

    if matches.apply_if_snapshot_current(snapshot, lambda: _remember(key, result)):
        return result
    return result
```

Then modify `server/golavo_server/matches.py:161` — add `"retrospective"` to the derivative tuple:

```python
    for module_name in ("outlook", "conditions", "analysis", "retrospective"):
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=core:server /Users/umang/.pyenv/shims/python3.12 -m pytest server/tests/test_retrospective_api.py -q`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add server/golavo_server/retrospective.py server/golavo_server/matches.py server/tests/test_retrospective_api.py
git commit -m "feat: cache the retrospective against index and pack"
```

---

### Task 4: Server routes — start job and poll

**Files:**
- Modify: `server/golavo_server/main.py` (import block ~`:16-38`; new routes near the outlook route at `:236`)
- Test: `server/tests/test_retrospective_api.py` (append)

**Interfaces:**
- Consumes: Task 3's `retrospective.build`; `jobs.store()`, `jobs.JOB_ID_RE`, `jobs.JobConflict`.
- Produces:
  - `POST /api/v1/tournaments/worldcup-2026/retrospective` — body `{"job_id": str}` → `202 {"job_id", "state": "running"}`; without `job_id`, computes synchronously in a threadpool.
  - `GET /api/v1/tournaments/worldcup-2026/retrospective/jobs/{job_id}` → `Job.to_dict()`.

**Decision (do not inherit by accident):** `jobs.py`'s `STAGES` and its `/api/v1/ai/jobs/` route are the AI lane. `update()` does not validate the stage string, so the store is reusable, but the AI-named route is not. This task adds a retrospective-scoped polling route over the same store and uses its own stage strings (`replaying`, `scoring`, `done`).

**Known deviation from the spec — L1 only, no L2 disk cache.** The spec calls for the
two-level cache from `analysis.py`, including the fingerprint-addressed disk tier that
survives restarts. This plan implements **L1 (in-memory) only**, so a restart re-runs the
~3.2 min compute.

Why: the L2 tier in `analysis.py` is ~80 lines of validation, atomic write, digest
check, and pruning, and it is per-`match_id` — a per-tournament payload with 104 embedded
rows is a different shape and a different failure surface. Shipping L1 first keeps this
plan's diff reviewable and honest; the cache is an accelerator either way, so L1-only is
correct, just less fast across restarts.

**This must not be silently dropped.** Either add the L2 tier as its own task before
shipping, or update the spec to say L1-only and record why. Do not leave the spec
promising a disk cache the code does not have.

- [ ] **Step 1: Write the failing test**

Append to `server/tests/test_retrospective_api.py`:

```python
def test_retrospective_route_validates_against_contract(monkeypatch) -> None:
    import json
    from pathlib import Path

    from fastapi.testclient import TestClient
    from golavo_server import main as server_main
    from jsonschema import Draft202012Validator, FormatChecker

    root = Path(__file__).resolve().parents[2]
    schema = json.loads(
        (root / "docs" / "contracts" / "tournament_retrospective.schema.json").read_text(
            encoding="utf-8"
        )
    )
    stub = {
        "schema_version": "0.1.0",
        "status": "available",
        "label": "Tournament retrospective — a backtest, not a sealed record.",
        "tournament_id": "worldcup-2026",
        "tournament_name": "2026 FIFA World Cup",
        "ledger_status": "never_persisted_or_scored_as_a_seal",
        "ranking_family": "dixon_coles",
        "ranking_metric": "log_loss",
        "families": ["dixon_coles"],
        "window_start": "2026-06-11",
        "window_end": "2026-07-19",
        "coverage": {"status": "complete", "scored": 0, "pending": 0, "note": "n"},
        "matches": [],
        "biggest_surprises": [],
    }
    monkeypatch.setattr(server_retrospective, "build", lambda **_: stub)
    body = TestClient(server_main.app).post(
        "/api/v1/tournaments/worldcup-2026/retrospective", json={}
    ).json()
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(body)


def test_malformed_job_id_is_rejected() -> None:
    from fastapi.testclient import TestClient
    from golavo_server import main as server_main

    client = TestClient(server_main.app)
    assert client.get(
        "/api/v1/tournaments/worldcup-2026/retrospective/jobs/bad"
    ).status_code == 400
    assert client.get(
        "/api/v1/tournaments/worldcup-2026/retrospective/jobs/rt-doesnotexist1"
    ).status_code == 404
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=core:server /Users/umang/.pyenv/shims/python3.12 -m pytest server/tests/test_retrospective_api.py -q -k "route or malformed"`
Expected: FAIL — 405 / 404 (routes do not exist)

- [ ] **Step 3: Write the routes**

In `server/golavo_server/main.py`, add `retrospective` to the `from golavo_server import (...)` block (alphabetical, after `research_pack`). Then add, immediately after the outlook route (`:244`):

```python
@app.post("/api/v1/tournaments/worldcup-2026/retrospective")
async def start_world_cup_2026_retrospective(
    request: Request, background_tasks: BackgroundTasks
) -> Any:
    """Backtest every played 2026 World Cup match at its own pre-kickoff cutoff.

    A backtest, never a seal: nothing here is persisted or scored as a record.
    The fit is minutes long, so a job_id streams progress; without one the work
    still runs off the event loop.
    """
    from golavo_server import jobs

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 -- an empty body is a valid synchronous request
        body = {}
    job_id = body.get("job_id") if isinstance(body, dict) else None

    job = None
    if isinstance(job_id, str) and job_id:
        if not jobs.JOB_ID_RE.match(job_id):
            raise HTTPException(status_code=400, detail="malformed job_id")
        try:
            job = jobs.store().start(job_id)
        except jobs.JobConflict as exc:
            raise HTTPException(status_code=409, detail="job already running") from exc

    def _progress(done: int, total: int) -> None:
        if job is not None:
            jobs.store().update(
                job.job_id,
                stage="replaying",
                detail=f"Backtesting match {done} of {total}",
                counts={"completed": done, "total": total},
            )

    def _cancelled() -> bool:
        return job is not None and jobs.store().is_cancelled(job.job_id)

    def _run() -> dict[str, Any]:
        try:
            result = retrospective.build(progress=_progress, is_cancelled=_cancelled)
            if job is not None:
                jobs.store().update(job.job_id, stage="scoring", detail="Scoring model skill")
                jobs.store().finish(job.job_id, result=result)
            return result
        except Exception as exc:
            if job is not None:
                jobs.store().fail(job.job_id, str(exc)[:240])
            raise

    if job is not None:
        background_tasks.add_task(_run)
        return JSONResponse({"job_id": job.job_id, "state": "running"}, status_code=202)
    try:
        return await run_in_threadpool(_run)
    except matches.MatchIndexUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/v1/tournaments/worldcup-2026/retrospective/jobs/{job_id}")
def world_cup_2026_retrospective_job(job_id: str) -> dict[str, Any]:
    """Progress for one retrospective run. Its own lane, not the AI job route."""
    from golavo_server import jobs

    if not jobs.JOB_ID_RE.match(job_id):
        raise HTTPException(status_code=400, detail="malformed job_id")
    job = jobs.store().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job.to_dict()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=core:server /Users/umang/.pyenv/shims/python3.12 -m pytest server/tests/test_retrospective_api.py -q`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add server/golavo_server/main.py server/tests/test_retrospective_api.py
git commit -m "feat: serve the World Cup retrospective with its own job lane"
```

---

### Task 5: UI contract types and API client

**Files:**
- Modify: `ui/src/lib/contract.ts` (append near `TournamentOutlook`, ~`:387`)
- Modify: `ui/src/lib/api.ts` (append near `fetchWorldCupOutlook`, ~`:630`)

**Interfaces:**
- Consumes: Task 2's schema, Task 4's routes.
- Produces:
  - `TournamentRetrospective`, `RetrospectiveRow` types
  - `startWorldCupRetrospective(jobId: string): Promise<string>`
  - `fetchRetrospectiveJob(jobId: string): Promise<RetrospectiveJob>`

- [ ] **Step 1: Add the contract types**

Append to `ui/src/lib/contract.ts`:

```ts
export interface RetrospectiveRow {
  match_id: string;
  kickoff_utc: string;
  kickoff_precision: "exact" | "day";
  information_cutoff_utc: string;
  home_team: string;
  away_team: string;
  home_score: number;
  away_score: number;
  outcome: "home" | "draw" | "away";
  log_loss: number;
  families: Record<string, { probs: { home: number; draw: number; away: number }; log_loss: number }>;
}

export interface TournamentRetrospective {
  schema_version: "0.1.0";
  status: "available" | "unavailable";
  label: string;
  reason?: string;
  tournament_id: "worldcup-2026";
  tournament_name: string;
  ledger_status: "never_persisted_or_scored_as_a_seal";
  ranking_family?: "dixon_coles";
  ranking_metric?: "log_loss";
  families?: ModelFamily[];
  window_start?: string;
  window_end?: string;
  coverage: {
    status: "complete" | "partial";
    scored: number;
    pending: number;
    note: string;
  };
  matches: RetrospectiveRow[];
  biggest_surprises: RetrospectiveRow[];
  trust?: ReportCard | null;
  provenance?: { index_sha256?: string; pack?: string };
}
```

- [ ] **Step 2: Add the API client**

Append to `ui/src/lib/api.ts`. Note: the job GET must NOT go through `getJson` — its 30s read-through cache would freeze the progress bar.

```ts
export interface RetrospectiveJob {
  job_id: string;
  state: "running" | "done" | "failed" | "cancelled";
  stage: string;
  detail: string | null;
  counts: { completed?: number | null; total?: number | null };
  elapsed_s: number;
  result?: TournamentRetrospective;
  error?: string;
}

/** Start the World Cup backtest. Minutes long, so progress streams via job_id. */
export async function startWorldCupRetrospective(jobId: string): Promise<string> {
  if (!API_BASE) throw new Error("The retrospective needs the Golavo engine running locally.");
  const res = await fetch(`${API_BASE}/api/v1/tournaments/worldcup-2026/retrospective`, {
    method: "POST",
    headers: { ...apiHeaders(), "content-type": "application/json" },
    body: JSON.stringify({ job_id: jobId }),
  });
  if (!res.ok) throw new ApiError("The retrospective could not start.", res.status);
  const body = (await res.json()) as { job_id?: string };
  if (!body.job_id) throw new Error("The retrospective started without a progress id.");
  return body.job_id;
}

export async function fetchRetrospectiveJob(jobId: string): Promise<RetrospectiveJob> {
  if (!API_BASE) throw new Error("The retrospective needs the Golavo engine running locally.");
  const res = await fetch(
    `${API_BASE}/api/v1/tournaments/worldcup-2026/retrospective/jobs/${encodeURIComponent(jobId)}`,
    { headers: apiHeaders() },
  );
  if (!res.ok) throw new ApiError("The retrospective progress could not be read.", res.status);
  return (await res.json()) as RetrospectiveJob;
}
```

Add `TournamentRetrospective` to the existing `import type { ... } from "./contract"` block at the top of `api.ts`.

- [ ] **Step 3: Verify it typechecks**

Run: `cd ui && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add ui/src/lib/contract.ts ui/src/lib/api.ts
git commit -m "feat: type the retrospective contract in the client"
```

---

### Task 6: UI view, route, and Lab card

**Files:**
- Create: `ui/src/views/WorldCupRetrospective.tsx`
- Create: `ui/src/views/WorldCupRetrospective.test.ts`
- Modify: `ui/src/App.tsx` (lazy import ~`:13`; route ~`:225`)
- Modify: `ui/src/views/ModelLab.tsx` (`links` array, ~`:11-43`)

**Interfaces:**
- Consumes: Task 5's `startWorldCupRetrospective`, `fetchRetrospectiveJob`, `TournamentRetrospective`.
- Produces: `WorldCupRetrospective` (route view), `WorldCupRetrospectiveBody` (pure, data-in — this is what the test renders).

- [ ] **Step 1: Write the failing test**

Create `ui/src/views/WorldCupRetrospective.test.ts`:

```ts
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { TournamentRetrospective } from "../lib/contract";
import { WorldCupRetrospectiveBody } from "./WorldCupRetrospective";

const DATA = {
  schema_version: "0.1.0",
  status: "available",
  label: "Tournament retrospective — a backtest, not a sealed record.",
  tournament_id: "worldcup-2026",
  tournament_name: "2026 FIFA World Cup",
  ledger_status: "never_persisted_or_scored_as_a_seal",
  ranking_family: "dixon_coles",
  ranking_metric: "log_loss",
  coverage: { status: "complete", scored: 2, pending: 0, note: "All played." },
  matches: [],
  biggest_surprises: [
    {
      match_id: "m_1",
      kickoff_utc: "2026-06-20T12:00:00Z",
      kickoff_precision: "exact",
      information_cutoff_utc: "2026-06-20T11:59:59Z",
      home_team: "France",
      away_team: "Spain",
      home_score: 1,
      away_score: 0,
      outcome: "home",
      log_loss: 2.1,
      families: { dixon_coles: { probs: { home: 0.1, draw: 0.3, away: 0.6 }, log_loss: 2.1 } },
    },
    {
      match_id: "m_2",
      kickoff_utc: "2026-06-21T00:00:00Z",
      kickoff_precision: "day",
      information_cutoff_utc: "2026-06-20T23:59:59Z",
      home_team: "England",
      away_team: "Argentina",
      home_score: 2,
      away_score: 1,
      outcome: "home",
      log_loss: 0.4,
      families: { dixon_coles: { probs: { home: 0.7, draw: 0.2, away: 0.1 }, log_loss: 0.4 } },
    },
  ],
} as unknown as TournamentRetrospective;

describe("WorldCupRetrospective", () => {
  it("says plainly that every number is a backtest, not a record", () => {
    const html = renderToStaticMarkup(createElement(WorldCupRetrospectiveBody, { data: DATA }));
    expect(html).toContain("backtest");
    expect(html).not.toContain("sealed forecast");
  });

  it("marks a date-proxy kickoff so same-day ordering is not implied", () => {
    const html = renderToStaticMarkup(createElement(WorldCupRetrospectiveBody, { data: DATA }));
    expect(html).toContain("date proxy");
  });

  it("renders typed unavailable copy without fabricated numbers", () => {
    const html = renderToStaticMarkup(
      createElement(WorldCupRetrospectiveBody, {
        data: {
          ...DATA,
          status: "unavailable",
          reason: "No completed matches",
          biggest_surprises: [],
        } as TournamentRetrospective,
      }),
    );
    expect(html).toContain("No completed matches");
    expect(html).not.toContain("0.0%");
  });

  it("shows the partial-coverage note from the server verbatim", () => {
    const html = renderToStaticMarkup(
      createElement(WorldCupRetrospectiveBody, {
        data: {
          ...DATA,
          coverage: { status: "partial", scored: 102, pending: 2, note: "2 not yet played." },
        } as TournamentRetrospective,
      }),
    );
    expect(html).toContain("2 not yet played.");
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd ui && npx vitest run src/views/WorldCupRetrospective.test.ts`
Expected: FAIL — cannot resolve `./WorldCupRetrospective`

- [ ] **Step 3: Write the view**

Create `ui/src/views/WorldCupRetrospective.tsx`:

```tsx
import { ChevronRight } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ErrorState } from "../components/states";
import {
  fetchRetrospectiveJob,
  startWorldCupRetrospective,
  type RetrospectiveJob,
} from "../lib/api";
import { newJobId } from "../lib/aiProgress";
import type { RetrospectiveRow, TournamentRetrospective } from "../lib/contract";

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function Row({ row, family }: { row: RetrospectiveRow; family: string }) {
  const call = row.families[family];
  return (
    <tr>
      <td>
        {row.home_team} {row.home_score}–{row.away_score} {row.away_team}
        {row.kickoff_precision === "day" && (
          <span className="small muted">
            {" "}
            · kickoff is a date proxy, so same-day order is not provable
          </span>
        )}
      </td>
      <td className="small muted">
        {call ? `${pct(call.probs.home)} / ${pct(call.probs.draw)} / ${pct(call.probs.away)}` : "—"}
      </td>
      <td>{row.log_loss.toFixed(3)}</td>
    </tr>
  );
}

export function WorldCupRetrospectiveBody({ data }: { data: TournamentRetrospective }) {
  if (data.status !== "available") {
    return (
      <div className="callout callout--info" role="status">
        <div>
          <div className="callout__title">Retrospective unavailable</div>
          <p>{data.reason}</p>
        </div>
      </div>
    );
  }
  return (
    <>
      <div className="callout callout--info" role="status">
        <div>
          <div className="callout__title">Every number here is a backtest</div>
          <p>{data.label}</p>
        </div>
      </div>

      {data.coverage.status === "partial" && (
        <div className="callout callout--warning" role="status">
          <div>
            <div className="callout__title">Tournament still in progress</div>
            <p>{data.coverage.note}</p>
          </div>
        </div>
      )}

      <h2>Where the models were most surprised</h2>
      <p className="small muted">
        Ranked by log loss on {data.ranking_family}, the family the app seals with. Higher means
        the result was more of a shock to the model.
      </p>
      <table className="table">
        <thead>
          <tr>
            <th>Match</th>
            <th>Pre-kickoff call (H/D/A)</th>
            <th>Log loss</th>
          </tr>
        </thead>
        <tbody>
          {data.biggest_surprises.map((row) => (
            <Row key={row.match_id} row={row} family={data.ranking_family ?? "dixon_coles"} />
          ))}
        </tbody>
      </table>

      {data.trust && (
        <>
          <h2>Did the models have skill?</h2>
          <p className="small muted">
            A different question, and a different cutoff: this fold trains once before the
            tournament and never sees a match inside it.
          </p>
          <table className="table">
            <thead>
              <tr>
                <th>Model</th>
                <th>Log loss</th>
                <th>Skill vs baseline</th>
              </tr>
            </thead>
            <tbody>
              {data.trust.models.map((model) => (
                <tr key={model.family}>
                  <td>{model.family}</td>
                  <td>{model.log_loss.toFixed(4)}</td>
                  <td>
                    {model.sample_status === "available" && model.skill_ci_95
                      ? `${(model.skill_score * 100).toFixed(1)}%`
                      : `Insufficient sample (a fold has <${data.trust!.minimum_matches})`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}

export function WorldCupRetrospective() {
  const [job, setJob] = useState<RetrospectiveJob | null>(null);
  const [data, setData] = useState<TournamentRetrospective | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [active, setActive] = useState<{ jobId: string } | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    // React Strict Mode mounts, cleans up, then remounts effects in dev. Reset
    // the flag on every mount so an in-flight poll is not discarded forever.
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (!active) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const next = await fetchRetrospectiveJob(active.jobId);
        if (stopped || !mounted.current) return;
        setJob(next);
        if (next.state === "running") {
          timer = setTimeout(poll, 1200);
          return;
        }
        if (next.state === "done" && next.result) setData(next.result);
        else if (next.state === "failed") setError(new Error(next.error || "The backtest failed."));
        setActive(null);
      } catch (err) {
        if (!stopped && mounted.current) {
          setError(err instanceof Error ? err : new Error("Progress was lost."));
          setActive(null);
        }
      }
    };
    void poll();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, [active]);

  const start = async () => {
    setError(null);
    setData(null);
    try {
      const jobId = newJobId().replace(/^cl-/, "rt-");
      await startWorldCupRetrospective(jobId);
      setActive({ jobId });
    } catch (err) {
      setError(err instanceof Error ? err : new Error("The backtest could not start."));
    }
  };

  const completed = job?.counts.completed ?? 0;
  const total = job?.counts.total ?? 0;

  return (
    <section className="view">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <a href="#/lab">Model Lab</a>
        <ChevronRight size={14} />
        <span aria-current="page">World Cup 2026</span>
      </nav>
      <h1>World Cup 2026 retrospective</h1>

      {!data && !active && (
        <p>
          <button type="button" className="btn" onClick={() => void start()}>
            Run the backtest
          </button>
          <span className="small muted">
            {" "}
            Replays all 104 matches at their own pre-kickoff cutoffs. Takes a few minutes the
            first time, then it is cached.
          </span>
        </p>
      )}

      {active && (
        <div className="ollama-download" aria-live="polite">
          <div className="ollama-download__label">
            <span>{job?.detail || "Starting the backtest…"}</span>
            <span>{total > 0 ? `${Math.round((completed / total) * 100)}%` : "Preparing…"}</span>
          </div>
          <progress max={total || 1} value={total ? completed : undefined} />
        </div>
      )}

      {error && <ErrorState error={error} onRetry={() => void start()} />}
      {data && <WorldCupRetrospectiveBody data={data} />}
    </section>
  );
}
```

- [ ] **Step 4: Wire the route and the Lab card**

In `ui/src/App.tsx`, add the lazy import beside the other Lab views (~`:13`):

```tsx
const WorldCupRetrospective = lazy(() =>
  import("./views/WorldCupRetrospective").then((m) => ({ default: m.WorldCupRetrospective })),
);
```

and the route inside the Model Lab block (~`:225`):

```tsx
  if (path === "/lab/worldcup-2026") return <WorldCupRetrospective />;
```

In `ui/src/views/ModelLab.tsx`, add to the `links` array:

```ts
    {
      href: "#/lab/worldcup-2026",
      title: "World Cup 2026 retrospective",
      note: "Every match backtested at its own pre-kickoff cutoff — where the models were most surprised.",
    },
```

- [ ] **Step 5: Run tests and build to verify**

Run: `cd ui && npx vitest run && npx tsc --noEmit && npm run build`
Expected: all tests pass (154 existing + 4 new), no type errors, clean build

- [ ] **Step 6: Commit**

```bash
git add ui/src/views/WorldCupRetrospective.tsx ui/src/views/WorldCupRetrospective.test.ts ui/src/App.tsx ui/src/views/ModelLab.tsx
git commit -m "feat: add the World Cup 2026 retrospective view"
```

---

### Task 7: Full verification

- [ ] **Step 1: Run the whole Python suite**

Run: `PYTHONPATH=core:server /Users/umang/.pyenv/shims/python3.12 -m pytest -q`
Expected: PASS — 738 existing + ~18 new

- [ ] **Step 2: Lint and validate**

Run:
```bash
/Users/umang/.pyenv/shims/python3.12 -m ruff check .
PYTHONPATH=core:server /Users/umang/.pyenv/shims/python3.12 scripts/validate_artifacts.py
PYTHONPATH=core:server /Users/umang/.pyenv/shims/python3.12 scripts/validate_provenance.py
```
Expected: `All checks passed!` and both validators silent

- [ ] **Step 3: Drive the real surface**

Use the `verify` skill: start the app, open `#/lab/worldcup-2026`, click "Run the backtest", watch progress advance, confirm the ranked table and the trust panel render, and confirm the second open is instant (cache hit).

- [ ] **Step 4: Commit any fixes and land**

```bash
git -C /Users/umang/Documents/development/github/Golavo merge --ff-only friendly-helper-claude/work-planning-b8718a
git -C /Users/umang/Documents/development/github/Golavo push origin main
```
