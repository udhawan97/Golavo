"""User-authorized post-match result ingestion and immutable forecast settlement.

The forecasting ledger is local-first: this module reaches only two fixed CC0
repositories, and only when the UI explicitly calls the settlement route (or the
user has enabled the existing keep-data-fresh preference).  Remote bytes are
resolved through an immutable Git commit, hashed, matched to an exact fixture,
and recorded as a new snapshot on the scored successor.  The original seal is
never edited.

martj42 remains the general men's-international result source.  OpenFootball's
World Cup JSON is an independent World Cup result source and closes the common
publication gap where martj42 still carries a scheduled ``NA/NA`` row after the
final whistle.  If both sources publish a result and disagree, settlement fails
closed for that fixture.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from golavo_core.artifacts import score_forecast_result
from golavo_core.calibration import calibration_summary
from golavo_core.identity import fixture_key
from golavo_core.ingest.snapshot import snapshot_anchor_utc
from golavo_core.ingest.worldcup import final_score

SCHEMA_VERSION = "0.2.0"
RESULT_GRACE = timedelta(hours=3)
MAX_PAYLOAD_BYTES = 25 * 1024 * 1024

_MARTJ_REPO = "martj42/international_results"
_MARTJ_SOURCE = "martj42-international-results"
_MARTJ_URL = "https://github.com/martj42/international_results"
_WORLD_CUP_REPO = "openfootball/worldcup.json"
_WORLD_CUP_SOURCE = "openfootball-worldcup-json"
_WORLD_CUP_URL = "https://github.com/openfootball/worldcup.json"
_COMMIT_API = "https://api.github.com/repos/{repo}/commits/master"
_RAW = "https://raw.githubusercontent.com/{repo}/{ref}/{path}"

# A club prediction is graded only when two independent trusted sources agree on
# the score. Golavo has fewer than two free club-result sources today, so a club
# seal is deferred with this reason — never graded on a single unverified result.
_CLUB_PENDING_REASON = "awaiting_independent_confirmation"


def _requires_independent_confirmation(competition: str) -> bool:
    """True for a club competition, which needs multi-source agreement to settle.

    Internationals settle from martj42 (with a World Cup cross-check); a club
    competition has no such trusted forward-result source wired, so it is held
    until two independent sources can confirm the score. The sealed artifact
    stores the source competition NAME, so it is resolved to a catalog id first.
    """
    from golavo_core.competitions import competition_by_id, competition_id_for_source_name

    competition_id = competition_id_for_source_name(competition)
    if competition_id is None:
        return False
    entry = competition_by_id(competition_id)
    return entry is not None and entry.get("team_scope") == "club"


# Two simultaneous UI requests must not observe the same unresolved root and
# write two different successors with different retrieval timestamps.
_SETTLEMENT_LOCK = threading.Lock()


class SettlementError(Exception):
    """A trusted result source could not be read or safely interpreted."""


class ResultConflict(SettlementError):
    """Two trusted sources published different scores for the same fixture."""


@dataclass(frozen=True)
class SourceResults:
    source_id: str
    snapshot: dict[str, Any]
    results: dict[tuple[str, str, str, str], tuple[int, int]]


FetchBytes = Callable[[str], bytes]
MatchKey = tuple[str, str, str, str]


def _key(date: str, home: str, away: str, competition: str) -> MatchKey:
    """This fixture's identity, scoped to its competition.

    Grading requires two sources to agree on a fixture, so this key must be the
    same one the index was built with — hence the shared fold.
    """
    day, home_norm, away_norm, competition_norm = fixture_key(date, home, away, competition)
    return day, home_norm, away_norm, competition_norm


def _fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Golavo-result-settlement/1"})
    try:
        with urlopen(request, timeout=20) as response:  # noqa: S310 (fixed HTTPS allowlist)
            payload = response.read(MAX_PAYLOAD_BYTES + 1)
    except Exception as exc:  # noqa: BLE001 (transport failures share one typed boundary)
        raise SettlementError(f"could not reach the result source: {exc}") from exc
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise SettlementError("result source response exceeded the 25 MB safety limit")
    return payload


def _commit(repo: str, fetch: FetchBytes) -> tuple[str, str]:
    try:
        body = json.loads(fetch(_COMMIT_API.format(repo=repo)).decode("utf-8"))
        ref = str(body["sha"])
        committed_at = str(body["commit"]["committer"]["date"])
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SettlementError("unexpected repository commit response") from exc
    if len(ref) < 12 or not committed_at:
        raise SettlementError("repository commit response was incomplete")
    return ref, committed_at


def _descriptor(
    *,
    source_id: str,
    source_url: str,
    ref: str,
    committed_at: str,
    retrieved_at: str,
    payload: bytes,
) -> dict[str, Any]:
    return {
        "snapshot_id": f"sp_{ref[:12]}",
        "source_id": source_id,
        "url": source_url,
        "upstream_ref": ref,
        "upstream_committed_at_utc": committed_at,
        "retrieved_at_utc": retrieved_at,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "license": "CC0-1.0",
    }


def _insert_result(
    results: dict[MatchKey, tuple[int, int]],
    key: MatchKey,
    score: tuple[int, int],
) -> None:
    previous = results.get(key)
    if previous is not None and previous != score:
        raise SettlementError(f"result source contains conflicting duplicate rows for {key[0]}")
    results[key] = score


def martj42_results(
    csv_text: str, target_keys: set[MatchKey] | None = None
) -> dict[MatchKey, tuple[int, int]]:
    """Parse completed result rows from martj42's canonical CSV."""
    results: dict[MatchKey, tuple[int, int]] = {}
    try:
        rows = csv.DictReader(io.StringIO(csv_text))
        required = {
            "date",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
            "tournament",
        }
        if rows.fieldnames is None or not required.issubset(rows.fieldnames):
            raise SettlementError("martj42 results header changed")
        for row in rows:
            home_score = row.get("home_score")
            away_score = row.get("away_score")
            if home_score in (None, "", "NA") or away_score in (None, "", "NA"):
                continue
            score = int(home_score), int(away_score)
            if score[0] < 0 or score[1] < 0:
                raise ValueError("negative score")
            key = _key(
                str(row["date"]),
                str(row["home_team"]),
                str(row["away_team"]),
                str(row.get("tournament") or ""),
            )
            if target_keys is None or key in target_keys:
                _insert_result(results, key, score)
    except (TypeError, ValueError) as exc:
        raise SettlementError("martj42 results contained an invalid score") from exc
    return results


def world_cup_results(
    data: dict[str, Any], target_keys: set[MatchKey] | None = None
) -> dict[MatchKey, tuple[int, int]]:
    """Parse completed regulation/extra-time results from worldcup.json."""
    matches = data.get("matches")
    if not isinstance(matches, list):
        raise SettlementError("worldcup.json response has no matches array")
    results: dict[MatchKey, tuple[int, int]] = {}
    for match in matches:
        if not isinstance(match, dict):
            continue
        date, home, away = match.get("date"), match.get("team1"), match.get("team2")
        score = final_score(match.get("score"))
        if not all(isinstance(value, str) and value for value in (date, home, away)):
            continue
        if score is not None:
            key = _key(date, home, away, "FIFA World Cup")
            if target_keys is None or key in target_keys:
                _insert_result(results, key, score)
    return results


def fetch_martj42(
    *,
    retrieved_at: str,
    target_keys: set[MatchKey] | None = None,
    fetch: FetchBytes = _fetch,
) -> SourceResults:
    ref, committed_at = _commit(_MARTJ_REPO, fetch)
    payload = fetch(_RAW.format(repo=_MARTJ_REPO, ref=ref, path="results.csv"))
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SettlementError("martj42 results were not UTF-8") from exc
    return SourceResults(
        source_id=_MARTJ_SOURCE,
        snapshot=_descriptor(
            source_id=_MARTJ_SOURCE,
            source_url=_MARTJ_URL,
            ref=ref,
            committed_at=committed_at,
            retrieved_at=retrieved_at,
            payload=payload,
        ),
        results=martj42_results(text, target_keys),
    )


def fetch_world_cup(
    year: str,
    *,
    retrieved_at: str,
    target_keys: set[MatchKey] | None = None,
    fetch: FetchBytes = _fetch,
) -> SourceResults:
    if len(year) != 4 or not year.isdigit():
        raise SettlementError(f"invalid World Cup year {year!r}")
    ref, committed_at = _commit(_WORLD_CUP_REPO, fetch)
    payload = fetch(_RAW.format(repo=_WORLD_CUP_REPO, ref=ref, path=f"{year}/worldcup.json"))
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SettlementError("worldcup.json result payload was invalid") from exc
    return SourceResults(
        source_id=_WORLD_CUP_SOURCE,
        snapshot=_descriptor(
            source_id=_WORLD_CUP_SOURCE,
            source_url=_WORLD_CUP_URL,
            ref=ref,
            committed_at=committed_at,
            retrieved_at=retrieved_at,
            payload=payload,
        ),
        results=world_cup_results(data, target_keys),
    )


def _is_world_cup(chain: dict[str, Any]) -> bool:
    return chain["match"]["competition"] == "FIFA World Cup"


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def settle_pending_forecasts(
    artifact_dir: Path,
    *,
    now: datetime | None = None,
    martj_loader: Callable[..., SourceResults] = fetch_martj42,
    world_cup_loader: Callable[..., SourceResults] = fetch_world_cup,
) -> dict[str, Any]:
    """Check trusted sources and append scored successors for completed seals.

    Network/source failures are isolated per provider.  A report is always
    returned so the UI can distinguish "still playing", "source has not
    published", and "source check failed" instead of calling all three
    "awaiting full time".
    """
    now = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    artifact_dir = Path(artifact_dir)
    with _SETTLEMENT_LOCK:
        summary = calibration_summary(artifact_dir)
        unresolved = [
            chain
            for chain in summary["chains"]
            if chain["resolution"]["status"] == "pending"
            and not chain["abstained"]
            and chain["probs"] is not None
        ]
        eligible: list[dict[str, Any]] = []
        deferred: list[str] = []
        club_pending: list[dict[str, Any]] = []
        for chain in unresolved:
            kickoff = datetime.fromisoformat(
                chain["match"]["kickoff_utc"].replace("Z", "+00:00")
            ).astimezone(UTC)
            if now < kickoff + RESULT_GRACE:
                deferred.append(chain["sealed_artifact_id"])
            elif _requires_independent_confirmation(chain["match"]["competition"]):
                # Past kickoff, but a club seal is never graded on a single source;
                # it waits for two independent sources rather than joining the
                # internationals settlement below.
                club_pending.append(chain)
            else:
                eligible.append(chain)

        retrieved_at = _iso(now)
        sources: dict[str, SourceResults] = {}
        errors: list[dict[str, str]] = []
        target_keys = {
            _key(
                chain["match"]["kickoff_utc"][:10],
                chain["match"]["home_team"],
                chain["match"]["away_team"],
                chain["match"]["competition"],
            )
            for chain in eligible
        }
        if eligible:
            try:
                source = martj_loader(retrieved_at=retrieved_at, target_keys=target_keys)
                sources[source.source_id] = source
            except SettlementError as exc:
                errors.append({"source_id": _MARTJ_SOURCE, "message": str(exc)})

        world_cup_years = sorted(
            {chain["match"]["kickoff_utc"][:4] for chain in eligible if _is_world_cup(chain)}
        )
        world_cup_sources: dict[str, SourceResults] = {}
        for year in world_cup_years:
            try:
                year_keys = {key for key in target_keys if key[0].startswith(year)}
                source = world_cup_loader(
                    year, retrieved_at=retrieved_at, target_keys=year_keys
                )
                world_cup_sources[year] = source
            except SettlementError as exc:
                errors.append({"source_id": _WORLD_CUP_SOURCE, "message": str(exc)})

        scored: list[dict[str, Any]] = []
        still_pending: list[dict[str, str]] = [
            {"artifact_id": chain["sealed_artifact_id"], "reason": _CLUB_PENDING_REASON}
            for chain in club_pending
        ]
        for chain in eligible:
            match = chain["match"]
            match_key = _key(
                match["kickoff_utc"][:10],
                match["home_team"],
                match["away_team"],
                match["competition"],
            )
            observations: list[tuple[tuple[int, int], dict[str, Any]]] = []
            martj = sources.get(_MARTJ_SOURCE)
            if martj is not None and match_key in martj.results:
                observations.append((martj.results[match_key], martj.snapshot))
            if _is_world_cup(chain):
                world_cup = world_cup_sources.get(match["kickoff_utc"][:4])
                if world_cup is not None and match_key in world_cup.results:
                    observations.append((world_cup.results[match_key], world_cup.snapshot))

            distinct = {score for score, _snapshot in observations}
            if len(distinct) > 1:
                errors.append(
                    {
                        "source_id": "consensus",
                        "message": (
                            f"trusted sources disagree for {match['home_team']} v "
                            f"{match['away_team']}; settlement was refused"
                        ),
                    }
                )
                still_pending.append(
                    {"artifact_id": chain["sealed_artifact_id"], "reason": "source_conflict"}
                )
                continue
            if not observations:
                still_pending.append(
                    {"artifact_id": chain["sealed_artifact_id"], "reason": "result_not_published"}
                )
                continue

            score = observations[0][0]
            # When both agree, record the newest verifiable observation.  This
            # also satisfies the core's strict post-seal snapshot boundary.
            snapshot = max(observations, key=lambda item: snapshot_anchor_utc(item[1]))[1]
            try:
                output = score_forecast_result(
                    artifact_path=artifact_dir / f"{chain['sealed_artifact_id']}.json",
                    result_snapshot=snapshot,
                    home_goals=score[0],
                    away_goals=score[1],
                    output_dir=artifact_dir,
                )
            except (OSError, ValueError) as exc:
                errors.append(
                    {
                        "source_id": snapshot["source_id"],
                        "message": f"could not score {chain['sealed_artifact_id']}: {exc}",
                    }
                )
                still_pending.append(
                    {"artifact_id": chain["sealed_artifact_id"], "reason": "scoring_refused"}
                )
                continue
            scored.append(
                {
                    "sealed_artifact_id": chain["sealed_artifact_id"],
                    "scored_artifact_id": output.stem,
                    "home_team": match["home_team"],
                    "away_team": match["away_team"],
                    "home_goals": score[0],
                    "away_goals": score[1],
                    "source_id": snapshot["source_id"],
                }
            )

        return {
            "schema_version": SCHEMA_VERSION,
            "checked_at_utc": retrieved_at,
            "pending_before_check": len(unresolved),
            "eligible": len(eligible),
            "awaiting_independent_confirmation": len(club_pending),
            "deferred_in_progress": deferred,
            "sources_checked": sorted(
                {*sources.keys(), *(source.source_id for source in world_cup_sources.values())}
            ),
            "scored": scored,
            "still_pending": still_pending,
            "errors": errors,
        }
