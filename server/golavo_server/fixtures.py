"""Opt-in fixture freshness: check the CC0 upstream for a genuinely-new fixture.

Golavo is local-first and makes **no** automatic network calls; this module is the
one exception, and it runs only when the user turns on "keep fixtures up to date"
and the UI calls the check endpoint. It fetches martj42's ``results.csv`` (the same
CC0 source the packs are pinned from), finds scheduled fixtures whose kickoff is
still ahead, and reports those NOT already in the committed index — i.e. genuinely
new upcoming games the user could forecast once the data is refreshed. It never
writes, seals, or rebuilds anything: it is a read-only awareness check.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any
from urllib.request import urlopen

SCHEMA_VERSION = "0.2.0"
_COMMIT_API = "https://api.github.com/repos/martj42/international_results/commits/master"
_RESULTS_RAW = "https://raw.githubusercontent.com/martj42/international_results/{ref}/results.csv"


class FixtureCheckError(Exception):
    """The upstream check could not complete (offline, rate-limited, changed)."""


def future_fixtures_from_csv(csv_text: str, now: datetime) -> list[dict[str, str]]:
    """Scheduled (no-score) fixtures dated strictly after today.

    kickoff is the conservative 00:00 UTC day proxy, so a fixture dated today has
    already passed its proxy (now > 00:00) and is not forecastable — only a
    strictly-later date is genuinely ahead. Pure over the CSV text (network-free,
    unit testable).
    """
    today = now.strftime("%Y-%m-%d")
    out: list[dict[str, str]] = []
    for row in csv.DictReader(io.StringIO(csv_text)):
        no_score = (row.get("home_score") or "NA") in ("", "NA") and (
            row.get("away_score") or "NA"
        ) in ("", "NA")
        if no_score and row.get("date", "") > today:
            out.append(
                {
                    "date": row["date"],
                    "home_team": row["home_team"],
                    "away_team": row["away_team"],
                    "competition": row.get("tournament", ""),
                }
            )
    return out


def _fetch(url: str) -> bytes:
    try:
        with urlopen(url, timeout=20) as response:  # noqa: S310 (pinned https URLs)
            return response.read()
    except Exception as exc:  # noqa: BLE001 (any transport failure => an honest 503)
        raise FixtureCheckError(f"could not reach the fixture source: {exc}") from exc


def _fetch_latest() -> tuple[str, str]:
    ref = str(json.loads(_fetch(_COMMIT_API).decode("utf-8"))["sha"])
    return ref, _fetch(_RESULTS_RAW.format(ref=ref)).decode("utf-8")


def _normalize(text: str) -> str:
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", str(text))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold().strip()


def check_new_fixtures(
    index_frame: Any, now: datetime | None = None, fetch: Any = None
) -> dict[str, Any]:
    """Upcoming fixtures upstream that are NOT already in the committed index.

    ``fetch`` is injectable so the network round-trip can be stubbed in tests;
    it resolves to ``_fetch_latest`` at call time (so a monkeypatch on the module
    attribute takes effect). ``index_frame`` is the loaded match index; a fixture
    already present (matched by date + normalized team names) is filtered out, so
    the result is exactly the genuinely-new games — the ones a refresh would add.
    """
    now = now or datetime.now(UTC)
    ref, results_csv = (fetch or _fetch_latest)()
    scheduled = future_fixtures_from_csv(results_csv, now)

    existing: set[tuple[str, str, str]] = set()
    if index_frame is not None and len(index_frame) > 0:
        import pandas as pd

        for _, row in index_frame.iterrows():
            date = pd.Timestamp(row["date"]).date().isoformat() if row["date"] is not None else ""
            existing.add((date, str(row["home_norm"]), str(row["away_norm"])))

    new = [
        f
        for f in scheduled
        if (f["date"], _normalize(f["home_team"]), _normalize(f["away_team"])) not in existing
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "source_ref": ref,
        "checked_at_utc": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "new_fixtures": new,
    }
