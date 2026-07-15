"""Build and read the display-only OpenLigaDB ODbL database.

The module intentionally has no dependency on ``golavo_core`` or the CC0 match
warehouse.  Source ids remain OpenLigaDB-local and every returned field carries
the raw-response receipt that supplied it.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from golavo_server import openligadb_source, openligadb_state

DATABASE_SCHEMA_VERSION = "0.1.0"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(path: Path, context: str) -> Any:
    try:
        return json.loads(path.read_bytes())
    except (OSError, TypeError, ValueError, UnicodeDecodeError) as exc:
        raise openligadb_source.OpenLigaDBError(
            "invalid_schema", f"{context}: raw response is not valid JSON", retryable=False
        ) from exc


def _required_int(value: Any, context: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise openligadb_source.OpenLigaDBError(
            "invalid_schema", f"{context} must be an integer >= {minimum}", retryable=False
        )
    return value


def _required_text(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise openligadb_source.OpenLigaDBError(
            "invalid_schema", f"{context} must be non-empty text", retryable=False
        )
    return value.strip()


def _optional_text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _iso_utc(value: Any, context: str) -> str:
    text = _required_text(value, context)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise openligadb_source.OpenLigaDBError(
            "invalid_schema", f"{context} is not ISO 8601", retryable=False
        ) from exc
    if parsed.tzinfo is None:
        raise openligadb_source.OpenLigaDBError(
            "invalid_schema", f"{context} lacks a UTC offset", retryable=False
        )
    return parsed.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _final_score(match: dict[str, Any], context: str) -> tuple[int | None, int | None]:
    finished = match.get("matchIsFinished")
    if not isinstance(finished, bool):
        raise openligadb_source.OpenLigaDBError(
            "invalid_schema", f"{context}.matchIsFinished must be boolean", retryable=False
        )
    results = match.get("matchResults")
    if not isinstance(results, list):
        raise openligadb_source.OpenLigaDBError(
            "invalid_schema", f"{context}.matchResults must be an array", retryable=False
        )
    if not finished:
        return None, None
    finals = [row for row in results if isinstance(row, dict) and row.get("resultTypeID") == 2]
    if len(finals) != 1:
        raise openligadb_source.OpenLigaDBConflict(
            f"{context} is finished but has {len(finals)} unambiguous final results"
        )
    final = finals[0]
    return (
        _required_int(final.get("pointsTeam1"), f"{context}.final.home"),
        _required_int(final.get("pointsTeam2"), f"{context}.final.away"),
    )


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode=DELETE;
        PRAGMA synchronous=FULL;
        PRAGMA foreign_keys=ON;
        CREATE TABLE metadata (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        ) STRICT;
        CREATE TABLE raw_responses (
          endpoint TEXT PRIMARY KEY,
          sha256 TEXT NOT NULL CHECK(length(sha256) = 64),
          relative_path TEXT NOT NULL UNIQUE,
          captured_at_utc TEXT NOT NULL,
          byte_count INTEGER NOT NULL CHECK(byte_count >= 0),
          content_type TEXT
        ) STRICT;
        CREATE TABLE competitions (
          source_id TEXT NOT NULL CHECK(source_id = 'openligadb'),
          league_id INTEGER NOT NULL,
          shortcut TEXT NOT NULL CHECK(shortcut IN ('bl1','bl2','bl3','dfb')),
          season TEXT NOT NULL CHECK(length(season) = 4),
          name TEXT NOT NULL,
          sport_id INTEGER NOT NULL CHECK(sport_id = 1),
          state TEXT NOT NULL CHECK(state = 'community_unverified'),
          raw_sha256 TEXT NOT NULL CHECK(length(raw_sha256) = 64),
          raw_endpoint TEXT NOT NULL REFERENCES raw_responses(endpoint),
          PRIMARY KEY(shortcut, season)
        ) STRICT;
        CREATE TABLE groups (
          shortcut TEXT NOT NULL,
          season TEXT NOT NULL,
          group_id INTEGER NOT NULL,
          group_order_id INTEGER NOT NULL,
          name TEXT NOT NULL,
          last_change_source_value TEXT NOT NULL,
          raw_sha256 TEXT NOT NULL CHECK(length(raw_sha256) = 64),
          raw_endpoint TEXT NOT NULL REFERENCES raw_responses(endpoint),
          PRIMARY KEY(shortcut, season, group_order_id),
          FOREIGN KEY(shortcut, season) REFERENCES competitions(shortcut, season)
        ) STRICT;
        CREATE TABLE teams (
          source_id TEXT NOT NULL CHECK(source_id = 'openligadb'),
          source_team_id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          short_name TEXT,
          state TEXT NOT NULL CHECK(state = 'source_identity_only'),
          raw_sha256 TEXT NOT NULL CHECK(length(raw_sha256) = 64),
          raw_endpoint TEXT NOT NULL REFERENCES raw_responses(endpoint)
        ) STRICT;
        CREATE TABLE matches (
          source_id TEXT NOT NULL CHECK(source_id = 'openligadb'),
          source_match_id INTEGER PRIMARY KEY,
          league_id INTEGER NOT NULL,
          shortcut TEXT NOT NULL,
          season TEXT NOT NULL,
          group_id INTEGER NOT NULL,
          group_order_id INTEGER NOT NULL,
          group_name TEXT NOT NULL,
          kickoff_utc TEXT NOT NULL,
          kickoff_local TEXT NOT NULL,
          time_zone_id TEXT NOT NULL,
          home_source_team_id INTEGER NOT NULL REFERENCES teams(source_team_id),
          away_source_team_id INTEGER NOT NULL REFERENCES teams(source_team_id),
          home_team_name TEXT NOT NULL,
          away_team_name TEXT NOT NULL,
          is_finished INTEGER NOT NULL CHECK(is_finished IN (0,1)),
          final_home_goals INTEGER,
          final_away_goals INTEGER,
          source_last_updated TEXT,
          state TEXT NOT NULL CHECK(state = 'community_unverified'),
          core_relation TEXT NOT NULL CHECK(core_relation = 'not_compared'),
          raw_sha256 TEXT NOT NULL CHECK(length(raw_sha256) = 64),
          raw_endpoint TEXT NOT NULL REFERENCES raw_responses(endpoint),
          captured_at_utc TEXT NOT NULL,
          FOREIGN KEY(shortcut, season, group_order_id)
            REFERENCES groups(shortcut, season, group_order_id),
          CHECK((is_finished = 0 AND final_home_goals IS NULL AND final_away_goals IS NULL)
             OR (is_finished = 1 AND final_home_goals >= 0 AND final_away_goals >= 0)),
          UNIQUE(shortcut, season, group_order_id, kickoff_utc,
                 home_source_team_id, away_source_team_id)
        ) STRICT;
        CREATE INDEX matches_schedule_idx ON matches(shortcut, kickoff_utc, source_match_id);
        """
    )


def _insert_team(
    connection: sqlite3.Connection,
    team: Any,
    *,
    raw_sha256: str,
    raw_endpoint: str,
    context: str,
) -> tuple[int, str]:
    if not isinstance(team, dict):
        raise openligadb_source.OpenLigaDBError(
            "invalid_schema", f"{context} must be an object", retryable=False
        )
    team_id = _required_int(team.get("teamId"), f"{context}.teamId", minimum=1)
    name = _required_text(team.get("teamName"), f"{context}.teamName")
    short_name = _optional_text(team.get("shortName"))
    existing = connection.execute(
        "SELECT name, short_name FROM teams WHERE source_team_id = ?", (team_id,)
    ).fetchone()
    if existing is not None:
        if (str(existing[0]), existing[1]) != (name, short_name):
            raise openligadb_source.OpenLigaDBConflict(
                f"OpenLigaDB team id {team_id} has conflicting exact identities"
            )
    else:
        connection.execute(
            """INSERT INTO teams
               (source_id, source_team_id, name, short_name, state,
                raw_sha256, raw_endpoint)
               VALUES ('openligadb', ?, ?, ?, 'source_identity_only', ?, ?)""",
            (team_id, name, short_name, raw_sha256, raw_endpoint),
        )
    return team_id, name


def _receipt_by_endpoint(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for receipt in snapshot.get("receipts", []):
        if not isinstance(receipt, dict) or not isinstance(receipt.get("endpoint"), str):
            raise openligadb_source.OpenLigaDBError(
                "invalid_schema", "snapshot contains an invalid raw receipt", retryable=False
            )
        endpoint = str(receipt["endpoint"])
        if endpoint in result:
            raise openligadb_source.OpenLigaDBConflict(
                f"duplicate raw endpoint receipt: {endpoint}"
            )
        result[endpoint] = receipt
    return result


def build_database(staging: Path, snapshot: dict[str, Any]) -> Path:
    """Build a validated, display-only SQLite database from retained responses."""
    target = Path(staging) / "overlay.sqlite3"
    temporary = target.with_suffix(".sqlite3.part")
    temporary.unlink(missing_ok=True)
    receipts = _receipt_by_endpoint(snapshot)
    raw_root = Path(staging) / "raw"
    connection = sqlite3.connect(temporary)
    try:
        _create_schema(connection)
        metadata = {
            "schema_version": DATABASE_SCHEMA_VERSION,
            "source_id": openligadb_source.SOURCE_ID,
            "license": openligadb_source.LICENSE_ID,
            "license_url": openligadb_source.LICENSE_URL,
            "attribution": openligadb_source.ATTRIBUTION,
            "display_only": "true",
            "season": str(snapshot["season"]),
            "content_revision": str(snapshot["content_revision"]),
            "captured_at_utc": str(snapshot["captured_at_utc"]),
        }
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)", sorted(metadata.items())
        )
        for receipt in receipts.values():
            raw_path = raw_root / str(receipt["path"])
            if _sha256(raw_path) != receipt["sha256"]:
                raise openligadb_source.OpenLigaDBConflict(
                    f"raw response hash changed before activation: {receipt['endpoint']}"
                )
            connection.execute(
                """INSERT INTO raw_responses
                   (endpoint, sha256, relative_path, captured_at_utc, byte_count, content_type)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    receipt["endpoint"],
                    receipt["sha256"],
                    receipt["path"],
                    receipt["captured_at_utc"],
                    receipt["bytes"],
                    receipt.get("content_type"),
                ),
            )

        season = str(snapshot["season"])
        leagues_receipt = receipts[f"/getavailableleagues/{season}"]
        seen_match_ids: set[int] = set()
        for competition in snapshot.get("competitions", []):
            shortcut = str(competition["shortcut"])
            league = competition["league"]
            sport = league["sport"]
            connection.execute(
                """INSERT INTO competitions
                   (source_id, league_id, shortcut, season, name, sport_id, state,
                    raw_sha256, raw_endpoint)
                   VALUES ('openligadb', ?, ?, ?, ?, ?, 'community_unverified', ?, ?)""",
                (
                    league["leagueId"],
                    shortcut,
                    season,
                    league["leagueName"],
                    sport["sportId"],
                    leagues_receipt["sha256"],
                    leagues_receipt["endpoint"],
                ),
            )
            league_id = int(league["leagueId"])
            for group in competition["groups"]:
                order = int(group["groupOrderID"])
                changed_endpoint = f"/getlastchangedate/{shortcut}/{season}/{order}"
                matches_endpoint = f"/getmatchdata/{shortcut}/{season}/{order}"
                changed_receipt = receipts[changed_endpoint]
                match_receipt = receipts[matches_endpoint]
                changed_value = _json_bytes(
                    raw_root / changed_receipt["path"], f"{shortcut} group {order} last change"
                )
                connection.execute(
                    """INSERT INTO groups
                       (shortcut, season, group_id, group_order_id, name,
                        last_change_source_value, raw_sha256, raw_endpoint)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        shortcut,
                        season,
                        group["groupID"],
                        order,
                        group["groupName"],
                        str(changed_value),
                        changed_receipt["sha256"],
                        changed_receipt["endpoint"],
                    ),
                )
                rows = _json_bytes(
                    raw_root / match_receipt["path"], f"{shortcut} group {order} matches"
                )
                if not isinstance(rows, list):
                    raise openligadb_source.OpenLigaDBError(
                        "invalid_schema", "match response must be an array", retryable=False
                    )
                for row in rows:
                    if not isinstance(row, dict):
                        raise openligadb_source.OpenLigaDBError(
                            "invalid_schema", "match row must be an object", retryable=False
                        )
                    context = f"{shortcut} group {order} match"
                    match_id = _required_int(row.get("matchID"), f"{context}.matchID", minimum=1)
                    if match_id in seen_match_ids:
                        raise openligadb_source.OpenLigaDBConflict(
                            f"duplicate OpenLigaDB match id {match_id}"
                        )
                    seen_match_ids.add(match_id)
                    group_row = row.get("group")
                    if not isinstance(group_row, dict):
                        raise openligadb_source.OpenLigaDBError(
                            "invalid_schema", f"{context}.group is invalid", retryable=False
                        )
                    if (
                        str(row.get("leagueShortcut") or "").casefold() != shortcut
                        or str(row.get("leagueSeason")) != season
                        or row.get("leagueId") != league_id
                        or group_row.get("groupOrderID") != order
                        or group_row.get("groupID") != group["groupID"]
                    ):
                        raise openligadb_source.OpenLigaDBConflict(
                            f"match {match_id} crosses its declared league/group identity"
                        )
                    home_id, home_name = _insert_team(
                        connection,
                        row.get("team1"),
                        raw_sha256=match_receipt["sha256"],
                        raw_endpoint=matches_endpoint,
                        context=f"{context}.team1",
                    )
                    away_id, away_name = _insert_team(
                        connection,
                        row.get("team2"),
                        raw_sha256=match_receipt["sha256"],
                        raw_endpoint=matches_endpoint,
                        context=f"{context}.team2",
                    )
                    if home_id == away_id:
                        raise openligadb_source.OpenLigaDBConflict(
                            f"match {match_id} assigns the same team to both sides"
                        )
                    final_home, final_away = _final_score(row, f"match {match_id}")
                    try:
                        connection.execute(
                            """INSERT INTO matches
                               (source_id, source_match_id, league_id, shortcut, season,
                                group_id, group_order_id, group_name, kickoff_utc,
                                kickoff_local, time_zone_id, home_source_team_id,
                                away_source_team_id, home_team_name, away_team_name,
                                is_finished, final_home_goals, final_away_goals,
                                source_last_updated, state, core_relation, raw_sha256,
                                raw_endpoint, captured_at_utc)
                               VALUES ('openligadb', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                       ?, ?, ?, ?, 'community_unverified',
                                       'not_compared', ?, ?, ?)""",
                            (
                                match_id,
                                league_id,
                                shortcut,
                                season,
                                group["groupID"],
                                order,
                                group_row.get("groupName") or group["groupName"],
                                _iso_utc(row.get("matchDateTimeUTC"), f"match {match_id}.kickoff"),
                                _required_text(
                                    row.get("matchDateTime"), f"match {match_id}.local kickoff"
                                ),
                                _required_text(
                                    row.get("timeZoneID"), f"match {match_id}.time zone"
                                ),
                                home_id,
                                away_id,
                                home_name,
                                away_name,
                                1 if row.get("matchIsFinished") is True else 0,
                                final_home,
                                final_away,
                                _optional_text(row.get("lastUpdateDateTime")),
                                match_receipt["sha256"],
                                matches_endpoint,
                                match_receipt["captured_at_utc"],
                            ),
                        )
                    except sqlite3.IntegrityError as exc:
                        raise openligadb_source.OpenLigaDBConflict(
                            f"match {match_id} conflicts with another source fixture"
                        ) from exc

        connection.commit()
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise openligadb_source.OpenLigaDBConflict(
                "OpenLigaDB candidate violates an internal source identity"
            )
        if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise openligadb_source.OpenLigaDBError(
                "invalid_database", "OpenLigaDB SQLite integrity check failed", retryable=False
            )
        connection.execute("VACUUM")
    except Exception:
        connection.close()
        temporary.unlink(missing_ok=True)
        raise
    connection.close()
    os.replace(temporary, target)
    return target


def write_generation(staging: Path, snapshot: dict[str, Any]) -> dict[str, Any]:
    database = build_database(staging, snapshot)
    license_notice = {
        "schema_version": "0.1.0",
        "source_id": openligadb_source.SOURCE_ID,
        "source_url": openligadb_source.SOURCE_URL,
        "license": openligadb_source.LICENSE_ID,
        "license_url": openligadb_source.LICENSE_URL,
        "attribution": openligadb_source.ATTRIBUTION,
        "modifications": (
            "Golavo converts retained JSON responses into an isolated, display-only "
            "SQLite database and omits source logo URLs."
        ),
        "distribution_note": (
            "Golavo does not bundle this database. If you redistribute an adapted "
            "database, review and comply with ODbL 1.0."
        ),
    }
    (Path(staging) / "LICENSE.json").write_text(
        json.dumps(license_notice, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    artifacts = []
    for item in sorted(Path(staging).rglob("*")):
        if (
            item.is_file()
            and item.name not in ("generation.json",)
            and not item.name.endswith(".part")
        ):
            artifacts.append(
                {
                    "path": item.relative_to(staging).as_posix(),
                    "sha256": _sha256(item),
                    "bytes": item.stat().st_size,
                }
            )
    basis = {
        "schema_version": openligadb_state.GENERATION_SCHEMA_VERSION,
        "source_id": openligadb_source.SOURCE_ID,
        "license": openligadb_source.LICENSE_ID,
        "season": snapshot["season"],
        "content_revision": snapshot["content_revision"],
        "artifacts": artifacts,
    }
    generation_id = (
        "g_"
        + hashlib.sha256(
            json.dumps(basis, separators=(",", ":"), sort_keys=True).encode("utf-8")
        ).hexdigest()
    )
    manifest = {
        **basis,
        "generation_id": generation_id,
        "created_at_utc": snapshot["captured_at_utc"],
        "display_only": True,
        "selected_competitions": snapshot["selected_competitions"],
        "capabilities": snapshot["capabilities"],
        "raw_response_count": len(snapshot["receipts"]),
        "raw_receipts": snapshot["receipts"],
        "database_sha256": _sha256(database),
    }
    (Path(staging) / "generation.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def _provenance(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "source_id": openligadb_source.SOURCE_ID,
        "license": openligadb_source.LICENSE_ID,
        "raw_sha256": row["raw_sha256"],
        "endpoint": row["raw_endpoint"],
        "captured_at_utc": row["captured_at_utc"],
    }


_MATCH_SELECT = (
    "SELECT source_match_id, shortcut, season, group_name, kickoff_utc, "
    "home_source_team_id, away_source_team_id, home_team_name, away_team_name, "
    "is_finished, final_home_goals, final_away_goals, source_last_updated, "
    "state, core_relation, raw_sha256, raw_endpoint, captured_at_utc FROM matches"
)


def _match_payload(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["is_finished"] = bool(item["is_finished"])
    item["provenance"] = _provenance(row)
    for key in ("raw_sha256", "raw_endpoint", "captured_at_utc"):
        item.pop(key, None)
    return item


def list_competitions() -> dict[str, Any]:
    database = openligadb_state.active_database()
    if database is None:
        return {"schema_version": "0.1.0", "source_id": "openligadb", "competitions": []}
    connection = openligadb_state.open_readonly_database(database)
    try:
        rows = connection.execute(
            """SELECT c.shortcut, c.season, c.league_id, c.name, c.state,
                      COUNT(m.source_match_id) AS match_count,
                      MAX(m.kickoff_utc) AS data_through_utc,
                      c.raw_sha256, c.raw_endpoint, r.captured_at_utc
               FROM competitions c
               JOIN raw_responses r ON r.endpoint = c.raw_endpoint
               LEFT JOIN matches m ON m.shortcut = c.shortcut AND m.season = c.season
               GROUP BY c.shortcut, c.season, c.league_id, c.name, c.state,
                        c.raw_sha256, c.raw_endpoint, r.captured_at_utc
               ORDER BY c.shortcut"""
        ).fetchall()
    finally:
        connection.close()
    competitions = []
    for row in rows:
        item = dict(row)
        item["provenance"] = _provenance(row)
        for key in ("raw_sha256", "raw_endpoint", "captured_at_utc"):
            item.pop(key, None)
        competitions.append(item)
    return {
        "schema_version": "0.1.0",
        "source_id": openligadb_source.SOURCE_ID,
        "license": openligadb_source.LICENSE_ID,
        "attribution": openligadb_source.ATTRIBUTION,
        "display_only": True,
        "identity_policy": "OpenLigaDB source ids only; no automatic core or fuzzy merge",
        "conflict_policy": "a disagreement never overrides a CC0 fact",
        "competitions": competitions,
    }


def list_matches(
    *,
    shortcut: str | None = None,
    from_utc: str | None = None,
    to_utc: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    if shortcut is not None and shortcut not in openligadb_source.COMPETITION_SHORTCUTS:
        raise ValueError("shortcut is not allowlisted")
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    database = openligadb_state.active_database()
    if database is None:
        return {"schema_version": "0.1.0", "source_id": "openligadb", "matches": []}
    clauses: list[str] = []
    params: list[Any] = []
    if shortcut is not None:
        clauses.append("shortcut = ?")
        params.append(shortcut)
    if from_utc is not None:
        clauses.append("kickoff_utc >= ?")
        params.append(_iso_utc(from_utc, "from_utc"))
    if to_utc is not None:
        clauses.append("kickoff_utc <= ?")
        params.append(_iso_utc(to_utc, "to_utc"))
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    sql = _MATCH_SELECT + f"{where} ORDER BY kickoff_utc, source_match_id LIMIT ?"
    params.append(limit)
    connection = openligadb_state.open_readonly_database(database)
    try:
        rows = connection.execute(sql, params).fetchall()
    finally:
        connection.close()
    matches = [_match_payload(row) for row in rows]
    return {
        "schema_version": "0.1.0",
        "source_id": openligadb_source.SOURCE_ID,
        "license": openligadb_source.LICENSE_ID,
        "attribution": openligadb_source.ATTRIBUTION,
        "display_only": True,
        "identity_policy": "OpenLigaDB source ids only; no automatic core or fuzzy merge",
        "conflict_policy": "a disagreement never overrides a CC0 fact",
        "matches": matches,
    }


def get_match(source_match_id: int) -> dict[str, Any] | None:
    if source_match_id < 1:
        raise ValueError("source_match_id must be positive")
    database = openligadb_state.active_database()
    if database is None:
        return None
    connection = openligadb_state.open_readonly_database(database)
    try:
        row = connection.execute(
            _MATCH_SELECT + " WHERE source_match_id = ?", (source_match_id,)
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    return {
        "schema_version": "0.1.0",
        "source_id": openligadb_source.SOURCE_ID,
        "license": openligadb_source.LICENSE_ID,
        "attribution": openligadb_source.ATTRIBUTION,
        "display_only": True,
        "identity_policy": "OpenLigaDB source ids only; no automatic core or fuzzy merge",
        "conflict_policy": "a disagreement never overrides a CC0 fact",
        "matches": [_match_payload(row)],
    }
