"""Canonical, immutable ForecastArtifact sealing and scoring."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import subprocess
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from golavo_core import __version__
from golavo_core.ingest import (
    co_source_descriptors,
    load_matches,
    snapshot_anchor_utc,
    snapshot_descriptor,
    training_rows,
)
from golavo_core.models import FAMILIES, fit_model
from golavo_core.score_matrix import (
    assert_model_coherent,
    assert_stored_coherent,
    build_score_matrix,
)

SCHEMA_VERSION = "0.2.0"
GENERATOR = f"golavo-core/{__version__}"
DECAY_WINDOW_DAYS = 365 * 8
MIN_TEAM_MATCHES = 10

# One in-process lock guards every ledger write. A single sidecar process owns its
# ledger directory, so serialising the collision check + atomic write + audit
# append is enough to make concurrent seals of the same fixture (a double-click, a
# retry storm) safe without a cross-process file lock. Content addressing already
# guarantees repeat writes are byte-identical; the lock only removes the
# interleaving window on the shared audit.jsonl.
_WRITE_LOCK = threading.Lock()


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include a UTC offset: {value}")
    return parsed.astimezone(UTC).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _schema_path() -> Path:
    # Delegated so the schema resolves both in source checkouts and inside the
    # frozen PyInstaller sidecar (see golavo_core.resources).
    from golavo_core.resources import schema_path

    return schema_path()


def validate_artifact(artifact: dict[str, Any], schema_path: Path | None = None) -> None:
    schema = json.loads((schema_path or _schema_path()).read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(artifact)
    probs = artifact["forecast"]["probs"]
    if probs is not None and abs(sum(probs.values()) - 1.0) > 1e-6:
        raise ValueError("forecast probabilities must sum to 1")
    # Enforce the exact-score coherence invariant on every load, from the stored
    # JSON alone: any artifact carrying a score_matrix must have grid + tail
    # marginals that reproduce its sealed 1X2 probabilities. A hand-edited or
    # otherwise incoherent matrix is rejected here, not silently displayed.
    score_matrix = artifact["forecast"].get("score_matrix")
    if score_matrix is not None:
        if probs is None:
            raise ValueError("score_matrix present but forecast has no probs to be coherent with")
        assert_stored_coherent(score_matrix, probs)


def canonical_bytes(value: dict[str, Any]) -> bytes:
    """Return sorted canonical JSON with forecast probabilities rounded to 6 dp."""
    payload = copy.deepcopy(value)
    probs = payload.get("forecast", {}).get("probs")
    if probs is not None:
        rounded = {key: round(float(probs[key]), 6) for key in ("home", "draw", "away")}
        drift = round(1.0 - sum(rounded.values()), 6)
        largest = max(rounded, key=rounded.get)
        rounded[largest] = round(rounded[largest] + drift, 6)
        payload["forecast"]["probs"] = rounded
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def payload_sha256(artifact: dict[str, Any]) -> str:
    """Hash canonical JSON excluding the self-referential digest field."""
    payload = copy.deepcopy(artifact)
    payload["provenance"].pop("payload_sha256", None)
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _code_sha() -> str:
    injected = os.environ.get("GOLAVO_SOURCE_SHA", "").strip().casefold()
    if len(injected) == 40 and all(character in "0123456789abcdef" for character in injected):
        return injected
    try:
        value = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip().casefold()
        if len(value) == 40 and all(character in "0123456789abcdef" for character in value):
            return value
        return "0000000"
    except (OSError, subprocess.CalledProcessError):
        return "0000000"


def _params_hash(params: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes({"params": params})).hexdigest()


def _artifact_id(stable_payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_bytes(stable_payload)).hexdigest()
    return f"fa_{digest[:20]}"


def verify_artifact_integrity(
    artifact: dict[str, Any], *, expected_id: str | None = None
) -> dict[str, Any]:
    """Validate an artifact AND prove its sealed identity still matches its bytes.

    ``validate_artifact`` proves a forecast is well-formed and — if it carries a
    ``score_matrix`` — internally coherent. It does NOT prove the file was left
    untouched after sealing. Any code path that READS an artifact it did not just
    write (the API surface, the calibration aggregator) must additionally recompute
    the content hash and the content-addressed id and reject a mismatch; otherwise
    the "sealed / immutable / auditable" guarantee holds only on the write path and
    a hand-edited ``fa_*.json`` is served as if it were a genuine seal.

    Raises ValueError on a schema/coherence failure, a ``payload_sha256`` that does
    not match the canonical content, an ``artifact_id`` that is not the hash of its
    own stable payload, or (when given) an ``expected_id`` — typically the filename
    stem — that disagrees with the recomputed content id. Because the id is the hash
    of the content, tampering cannot both change a number and keep the same id.
    """
    validate_artifact(artifact)
    stored_hash = artifact.get("provenance", {}).get("payload_sha256")
    recomputed_hash = payload_sha256(artifact)
    if stored_hash != recomputed_hash:
        raise ValueError(
            f"payload_sha256 mismatch: stored {stored_hash!r}, content hashes to "
            f"{recomputed_hash}"
        )
    stable = copy.deepcopy(artifact)
    stable.pop("artifact_id", None)
    stable["provenance"].pop("payload_sha256", None)
    recomputed_id = _artifact_id(stable)
    if artifact.get("artifact_id") != recomputed_id:
        raise ValueError(
            f"artifact_id mismatch: stored {artifact.get('artifact_id')!r}, content "
            f"addresses to {recomputed_id}"
        )
    if expected_id is not None and expected_id != recomputed_id:
        raise ValueError(
            f"artifact filename {expected_id!r} does not match its content id {recomputed_id}"
        )
    return artifact


def load_verified_artifact(path: Path) -> dict[str, Any]:
    """Read a ForecastArtifact JSON file and verify its integrity before use.

    The filename stem must equal the recomputed content id, so a renamed, swapped,
    or edited ``fa_*.json`` is rejected. Use this on every read path — never trust
    an on-disk artifact unverified (see verify_artifact_integrity).
    """
    path = Path(path)
    artifact = json.loads(path.read_text(encoding="utf-8"))
    return verify_artifact_integrity(artifact, expected_id=path.stem)


def _find_match(
    matches: pd.DataFrame,
    date: str,
    home_team: str,
    away_team: str,
    match_id: str | None = None,
) -> pd.Series:
    day = pd.Timestamp(date)
    rows = matches.loc[
        matches["date"].eq(day)
        & matches["home_team"].eq(home_team)
        & matches["away_team"].eq(away_team)
    ]
    if match_id is not None:
        rows = rows.loc[rows["match_id"].eq(match_id)]
    if len(rows) != 1:
        raise ValueError(
            f"expected exactly one match for {date} {home_team} v {away_team}; found {len(rows)}"
        )
    return rows.iloc[0]


def _team_counts(train: pd.DataFrame, as_of: datetime, teams: tuple[str, str]) -> dict[str, int]:
    start = pd.Timestamp(as_of) - pd.Timedelta(days=DECAY_WINDOW_DAYS)
    dates = pd.to_datetime(train["date"], utc=True)
    window = train.loc[dates >= start]
    return {
        team: int((window["home_team"].eq(team) | window["away_team"].eq(team)).sum())
        for team in teams
    }


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically: a temp file in the same directory,
    fsync'd, then ``os.replace``d into place.

    ``Path.write_bytes`` is not atomic — a crash or a kill mid-write (the desktop
    shell kills the sidecar on every exit) can leave a half-written ``fa_*.json``
    whose bytes no longer hash to its content-addressed name. That truncated file
    then makes every retry of the same seal trip the immutable-collision guard
    forever. Writing to a sibling temp file and renaming means a failure can only
    ever leave an orphaned ``*.tmp``, never a corrupt artifact.
    """
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _is_valid_artifact_bytes(data: bytes, expected_id: str) -> bool:
    """True iff ``data`` is a fully-formed artifact whose content id is ``expected_id``.

    Used to distinguish a genuine (hash-collision) artifact already on disk from a
    truncated partial write left by a killed process: a partial write fails to
    parse or fails integrity verification and is therefore safe to overwrite, while
    a valid rival under the same id would be a real content collision that must
    never be silently clobbered.
    """
    try:
        verify_artifact_integrity(json.loads(data), expected_id=expected_id)
    except (ValueError, KeyError, ValidationError):
        # A corrupt/partial file fails to parse (json.JSONDecodeError is a
        # ValueError), fails schema (ValidationError), or fails the hash/id check
        # (ValueError). Any other failure — e.g. an OSError reading the schema — is
        # environmental, not evidence the file is corrupt, so let it propagate
        # rather than silently overwrite a possibly-good artifact.
        return False
    return True


def _append_audit_event(artifact: dict[str, Any], output_dir: Path) -> None:
    event = {
        "artifact_id": artifact["artifact_id"],
        "created_at_utc": artifact["provenance"]["created_at_utc"],
        "payload_sha256": artifact["provenance"]["payload_sha256"],
        "status": artifact["status"],
        "supersedes": artifact.get("supersedes"),
    }
    line = canonical_bytes(event) + b"\n"
    audit_path = output_dir / "audit.jsonl"
    existing = audit_path.read_bytes().splitlines(keepends=True) if audit_path.exists() else []
    if line not in existing:
        with audit_path.open("ab") as stream:
            stream.write(line)


def _write_artifact(artifact: dict[str, Any], output_dir: Path) -> Path:
    validate_artifact(artifact)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{artifact['artifact_id']}.json"
    bytes_to_write = canonical_bytes(artifact) + b"\n"
    with _WRITE_LOCK:
        write_needed = True
        if path.exists():
            existing = path.read_bytes()
            if existing == bytes_to_write:
                write_needed = False  # idempotent: this exact content is already sealed
            elif _is_valid_artifact_bytes(existing, path.stem):
                # A different, *valid* artifact under this id is a genuine content
                # collision (the id is the hash of the content) and must never be
                # silently overwritten.
                raise FileExistsError(f"immutable artifact collision at {path}")
            # else: a corrupt/truncated leftover from a killed write — repair it by
            # falling through to the atomic overwrite below.
        if write_needed:
            _atomic_write_bytes(path, bytes_to_write)
        _append_audit_event(artifact, output_dir)
    return path


def build_forecast_artifact(
    *,
    pack_dir: Path,
    date: str,
    home_team: str,
    away_team: str,
    as_of_utc: str,
    horizon: str = "T-24h",
    family: str = "elo_ordlogit",
    seed: int = 20260710,
    match_id: str | None = None,
) -> dict[str, Any]:
    """Compute a sealed ForecastArtifact WITHOUT writing it to disk.

    The deterministic core of ``seal_forecast`` — it reads the pinned pack and the
    code SHA but never touches the ledger. It enforces every seal invariant — the
    snapshot anchor is not in the future, exactly one fixture
    matches, the fixture has no result yet, ``as_of`` is before kickoff, training
    is cut off leak-free, the abstain floor is applied, and any goal-model score
    matrix is proven coherent — then returns a fully content-addressed artifact
    dict with its ``artifact_id`` and ``payload_sha256`` set. ``seal_forecast`` is
    exactly this plus an atomic write, so an in-app forecast route can run the same
    deterministic engine and persist through the one shared write path. Raises the
    same typed ``ValueError``s as ``seal_forecast`` on any invariant violation.
    """
    if family not in FAMILIES:
        raise ValueError(f"unknown model family: {family}")
    as_of = _utc(as_of_utc)
    snapshot = snapshot_descriptor(pack_dir)
    # A pack may draw fixtures/kickoffs from a second CC0 source; record every source
    # this seal rests on, and require the as-of to be after ALL their data states so no
    # snapshot's availability is overstated.
    co_sources = co_source_descriptors(pack_dir)
    snapshots = [snapshot, *co_sources]
    anchor = max(_utc(snapshot_anchor_utc(descriptor)) for descriptor in snapshots)
    if anchor > as_of:
        raise ValueError(
            "cannot seal as-of a time before the snapshot's data state existed "
            "(upstream commit time, or our retrieval time when no commit time is pinned)"
        )

    matches = load_matches(pack_dir)
    match = _find_match(matches, date, home_team, away_team, match_id)
    if bool(match["is_complete"]):
        raise ValueError(
            "fixture already has a result in this snapshot; a forward seal targets a "
            "scheduled fixture — never re-forecast a played match as if it were upcoming"
        )
    kickoff = pd.Timestamp(match["kickoff_utc"]).to_pydatetime()
    if as_of >= kickoff:
        raise ValueError(
            "sealed_at_utc must be before kickoff_utc (dates-only source: kickoff is "
            "the conservative 00:00 UTC day proxy)"
        )
    cutoff = min(as_of, kickoff - pd.Timedelta(seconds=1).to_pytimedelta())
    train = training_rows(matches, _iso(cutoff))
    train = train.loc[~train["match_id"].eq(match["match_id"])].copy()
    counts = _team_counts(train, as_of, (home_team, away_team))
    abstained = min(counts.values()) < MIN_TEAM_MATCHES

    probs: dict[str, float] | None = None
    expected_goals: dict[str, float] | None = None
    score_matrix: dict[str, Any] | None = None
    params: dict[str, Any] = {"minimum_team_matches": MIN_TEAM_MATCHES}
    if not abstained:
        model = fit_model(family, train, _iso(cutoff))
        prediction = model.predict(home_team, away_team, bool(match["neutral"]))
        probs = dict(zip(("home", "draw", "away"), prediction.probs, strict=True))
        params.update(prediction.params)
        if prediction.expected_goals is not None:
            expected_goals = {
                "home": round(prediction.expected_goals[0], 6),
                "away": round(prediction.expected_goals[1], 6),
            }
        # Goal-based families imply a full exact-score distribution. Seal it, but
        # only after proving it reproduces the sealed 1X2 probs and expected
        # goals — an incoherent matrix aborts the seal rather than being shown.
        if prediction.matrix is not None and expected_goals is not None:
            score_matrix = build_score_matrix(prediction.matrix)
            assert_model_coherent(prediction.matrix, score_matrix, probs, expected_goals)

    minimum_count = min(counts.values())
    uncertainty = "high" if minimum_count < 20 else "medium" if minimum_count < 40 else "low"
    created = _iso(as_of)
    artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": "fa_pending00",
        "status": "abstained" if abstained else "sealed",
        "supersedes": None,
        "match": {
            "match_id": str(match["match_id"]),
            "competition": str(match["tournament"]),
            "stage": None,
            "kickoff_utc": _iso(kickoff),
            "home_team": home_team,
            "away_team": away_team,
            "neutral_venue": bool(match["neutral"]),
            "city": None if pd.isna(match["city"]) else str(match["city"]),
            "country": None if pd.isna(match["country"]) else str(match["country"]),
        },
        "forecast": {
            "market": "1x2_regulation",
            "sealed_at_utc": created,
            "horizon": horizon,
            "probs": probs,
            "expected_goals": expected_goals,
            "abstained": abstained,
            "abstain_reason": (
                f"insufficient data: {home_team}={counts[home_team]}, "
                f"{away_team}={counts[away_team]}; require {MIN_TEAM_MATCHES} each"
                if abstained
                else None
            ),
            "uncertainty": uncertainty,
        },
        "model": {
            "model_id": f"{family}_phase0",
            "family": family,
            "version": __version__,
            "params_hash": _params_hash(params),
            "code_git_sha": _code_sha(),
            "seed": seed,
        },
        "inputs": {"training_cutoff_utc": _iso(cutoff), "snapshots": snapshots},
        "provenance": {
            "created_at_utc": created,
            "generator": GENERATOR,
            "deterministic": True,
            "payload_sha256": "0" * 64,
        },
        "evaluation": None,
    }
    # Additive: present only for goal-based families that yield a coherent grid.
    # Absent for climatological/elo (no goal model) and abstained seals, so the
    # UI can render an honest "no exact-score distribution" state.
    if score_matrix is not None:
        artifact["forecast"]["score_matrix"] = score_matrix
    stable = copy.deepcopy(artifact)
    stable.pop("artifact_id")
    stable["provenance"].pop("payload_sha256")
    artifact["artifact_id"] = _artifact_id(stable)
    artifact["provenance"]["payload_sha256"] = payload_sha256(artifact)
    return artifact


def seal_forecast(
    *,
    pack_dir: Path,
    output_dir: Path,
    date: str,
    home_team: str,
    away_team: str,
    as_of_utc: str,
    horizon: str = "T-24h",
    family: str = "elo_ordlogit",
    seed: int = 20260710,
    match_id: str | None = None,
) -> Path:
    """Seal a deterministic forecast to ``output_dir`` and append one audit event.

    Thin wrapper over ``build_forecast_artifact`` (the deterministic engine) plus
    the shared atomic write — kept as the stable entry point for the CLI and any
    caller that wants compute-and-persist in one step.
    """
    artifact = build_forecast_artifact(
        pack_dir=pack_dir,
        date=date,
        home_team=home_team,
        away_team=away_team,
        as_of_utc=as_of_utc,
        horizon=horizon,
        family=family,
        seed=seed,
        match_id=match_id,
    )
    return _write_artifact(artifact, output_dir)


def _score_snapshot_anchor(
    sealed: dict[str, Any], result_snapshot: dict[str, Any]
) -> datetime:
    """Validate the terminal-state and temporal boundary before result lookup."""
    if sealed["status"] != "sealed" or sealed["forecast"]["probs"] is None:
        raise ValueError("only a non-abstained sealed artifact can be scored")
    old_anchor = max(
        _utc(snapshot_anchor_utc(item)) for item in sealed["inputs"]["snapshots"]
    )
    new_anchor = _utc(snapshot_anchor_utc(result_snapshot))
    if new_anchor <= old_anchor:
        raise ValueError(
            "scoring requires a snapshot whose data state is strictly newer than the seal's"
        )
    return new_anchor


def _score_verified_seal(
    *,
    sealed: dict[str, Any],
    result_snapshot: dict[str, Any],
    home_goals: int,
    away_goals: int,
    output_dir: Path,
) -> Path:
    """Append one scored successor from a trusted, newer result observation.

    Forecast fitting and result publication are separate provenance events.  The
    historical pack scorer below still supplies a validated pack descriptor;
    the desktop settlement service supplies a descriptor for the exact pinned
    result payload it fetched.  Both paths converge here so metric computation,
    immutability, and the strictly-newer-snapshot guard cannot drift.
    """
    new_anchor = _score_snapshot_anchor(sealed, result_snapshot)
    if isinstance(home_goals, bool) or not isinstance(home_goals, int) or home_goals < 0:
        raise ValueError("home_goals must be a non-negative integer")
    if isinstance(away_goals, bool) or not isinstance(away_goals, int) or away_goals < 0:
        raise ValueError("away_goals must be a non-negative integer")

    outcome = "home" if home_goals > away_goals else "draw" if home_goals == away_goals else "away"
    probs = sealed["forecast"]["probs"]
    assigned = float(probs[outcome])
    one_hot = {"home": 0.0, "draw": 0.0, "away": 0.0}
    one_hot[outcome] = 1.0
    brier = sum((float(probs[key]) - one_hot[key]) ** 2 for key in one_hot)

    scored = copy.deepcopy(sealed)
    scored["status"] = "scored"
    scored["supersedes"] = sealed["artifact_id"]
    scored["inputs"]["snapshots"] = [*sealed["inputs"]["snapshots"], copy.deepcopy(result_snapshot)]
    scored["evaluation"] = {
        "actual": {"home_goals": home_goals, "away_goals": away_goals, "outcome": outcome},
        "scored_at_utc": _iso(new_anchor),
        "metrics": {
            "log_loss": round(-math.log(max(assigned, 1e-12)), 6),
            "brier": round(brier, 6),
            "prob_assigned_to_outcome": round(assigned, 6),
        },
    }
    scored["provenance"]["created_at_utc"] = _iso(new_anchor)
    scored["provenance"]["payload_sha256"] = "0" * 64
    stable = copy.deepcopy(scored)
    stable.pop("artifact_id")
    stable["provenance"].pop("payload_sha256")
    scored["artifact_id"] = _artifact_id(stable)
    scored["provenance"]["payload_sha256"] = payload_sha256(scored)
    return _write_artifact(scored, output_dir)


def score_forecast_result(
    *,
    artifact_path: Path,
    result_snapshot: dict[str, Any],
    home_goals: int,
    away_goals: int,
    output_dir: Path,
) -> Path:
    """Score a seal from one pinned trusted result payload.

    The caller owns source-specific fixture matching.  This boundary owns the
    immutable artifact guarantees: it integrity-checks the seal, requires a
    strictly newer snapshot descriptor, validates the resulting artifact against
    the public schema, and appends rather than edits.
    """
    sealed = load_verified_artifact(artifact_path)
    return _score_verified_seal(
        sealed=sealed,
        result_snapshot=result_snapshot,
        home_goals=home_goals,
        away_goals=away_goals,
        output_dir=output_dir,
    )


def score_forecast(*, artifact_path: Path, newer_pack_dir: Path, output_dir: Path) -> Path:
    """Score a seal from a newer snapshot, writing a superseding artifact."""
    # Integrity-verify the input seal, not just its schema: a tampered fa_*.json
    # must be rejected here rather than acquiring a scored successor and only being
    # caught later when the calibration aggregator re-reads the ledger.
    sealed = load_verified_artifact(artifact_path)
    newer_snapshot = snapshot_descriptor(newer_pack_dir)
    # Preserve the fail-fast contract: terminal artifacts and stale snapshots
    # are rejected before loading/searching a potentially large result pack.
    _score_snapshot_anchor(sealed, newer_snapshot)
    match = sealed["match"]
    matches = load_matches(newer_pack_dir)
    actual = _find_match(
        matches,
        match["kickoff_utc"][:10],
        match["home_team"],
        match["away_team"],
        match["match_id"],
    )
    if not bool(actual["is_complete"]):
        raise ValueError("newer snapshot does not contain a completed result for this match")
    return _score_verified_seal(
        sealed=sealed,
        result_snapshot=newer_snapshot,
        home_goals=int(actual["home_score"]),
        away_goals=int(actual["away_score"]),
        output_dir=output_dir,
    )


def void_forecast(
    *, artifact_path: Path, output_dir: Path, voided_at_utc: str, reason: str
) -> Path:
    """Void a seal (postponement, abandonment): an immutable successor, never a result."""
    # Integrity-verify the input seal (see score_forecast): a hand-edited artifact
    # must not be able to spawn a voided successor that launders the tamper.
    sealed = load_verified_artifact(artifact_path)
    if sealed["status"] not in {"sealed", "abstained"}:
        raise ValueError("only a sealed or abstained artifact can be voided")
    if not reason.strip():
        raise ValueError("voiding requires a recorded reason")
    voided = copy.deepcopy(sealed)
    voided["status"] = "voided"
    voided["supersedes"] = sealed["artifact_id"]
    voided["void_reason"] = reason.strip()
    voided["provenance"]["created_at_utc"] = _iso(_utc(voided_at_utc))
    voided["provenance"]["payload_sha256"] = "0" * 64
    stable = copy.deepcopy(voided)
    stable.pop("artifact_id")
    stable["provenance"].pop("payload_sha256")
    voided["artifact_id"] = _artifact_id(stable)
    voided["provenance"]["payload_sha256"] = payload_sha256(voided)
    return _write_artifact(voided, output_dir)
