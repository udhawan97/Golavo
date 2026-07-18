"""Pinned sourcepack ingestion and typed match-table construction."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED_RESULT_COLUMNS = {
    "date",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "tournament",
    "city",
    "country",
    "neutral",
}

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_MANIFEST_FIELDS = {
    "source_id",
    "upstream_ref",
    "files",
    "license",
}


def _safe_declared_path(pack_dir: Path, name: object) -> Path:
    """Resolve one manifest file without permitting path escape or symlinks."""
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError(f"{pack_dir}: invalid manifest file name {name!r}")
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{pack_dir}: unsafe manifest file path {name!r}")
    path = pack_dir / relative
    if path.is_symlink():
        raise ValueError(f"{pack_dir}: manifest file must not be a symlink: {name}")
    return path


def validate_pack(pack_dir: Path) -> dict[str, Any]:
    """Validate a complete, path-safe sourcepack and return its manifest.

    The manifest is the provenance boundary for both bundled and runtime packs.
    Unknown auxiliary files are rejected: an undeclared overlay or parser input
    must never influence an index without its bytes being hashed.
    """
    pack_dir = Path(pack_dir)
    manifest_path = pack_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(f"{pack_dir}: missing or invalid manifest.json") from exc
    if not isinstance(manifest, dict):
        raise ValueError(f"{pack_dir}: manifest must be an object")
    missing = _REQUIRED_MANIFEST_FIELDS - set(manifest)
    if missing:
        raise ValueError(f"{pack_dir}: manifest missing fields: {sorted(missing)}")
    if not isinstance(manifest["files"], list) or not manifest["files"]:
        raise ValueError(f"{pack_dir}: manifest files must be a non-empty array")

    declared: set[str] = set()
    for entry in manifest["files"]:
        if not isinstance(entry, dict):
            raise ValueError(f"{pack_dir}: manifest file entry must be an object")
        name = entry.get("name")
        path = _safe_declared_path(pack_dir, name)
        if str(name) in declared:
            raise ValueError(f"{pack_dir}: duplicate manifest file {name!r}")
        declared.add(str(name))
        expected = entry.get("sha256")
        if not isinstance(expected, str) or _SHA256_RE.fullmatch(expected) is None:
            raise ValueError(f"{pack_dir}: invalid sha256 for {name!r}")
        if not path.is_file():
            raise ValueError(f"{pack_dir}: declared file is missing: {name}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"provenance hash mismatch for {path}")

    present = {
        path.relative_to(pack_dir).as_posix()
        for path in pack_dir.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    undeclared = present - declared
    if undeclared:
        raise ValueError(
            f"{pack_dir}: files present but not declared in the manifest: {sorted(undeclared)}"
        )
    return manifest


def snapshot_descriptor(pack_dir: Path) -> dict[str, str]:
    """Return the canonical artifact descriptor for a validated sourcepack."""
    manifest = validate_pack(pack_dir)
    manifest_bytes = (pack_dir / "manifest.json").read_bytes()
    upstream_ref = str(manifest["upstream_ref"])
    descriptor = {
        "snapshot_id": f"sp_{upstream_ref[:12]}",
        "source_id": str(manifest["source_id"]),
        "url": str(manifest["url"]),
        "upstream_ref": upstream_ref,
        "retrieved_at_utc": str(manifest["retrieved_at_utc"]),
        "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "license": str(manifest["license"]),
    }
    if manifest.get("upstream_committed_at_utc"):
        descriptor["upstream_committed_at_utc"] = str(manifest["upstream_committed_at_utc"])
    return descriptor


def co_source_descriptors(pack_dir: Path) -> list[dict[str, str]]:
    """Snapshot descriptors for a pack's declared co-sources (e.g. a fixture/kickoff feed).

    A pack whose match table draws fixtures or kickoff times from a second CC0 source
    records it under manifest ``co_sources``; each entry names the exact file in the
    pack (``sha256_file``) whose bytes are the verifiable provenance digest. These
    descriptors are appended to a seal's ``inputs.snapshots`` so the artifact honestly
    names every source it drew on — the training source AND the fixture source.
    """
    manifest = validate_pack(pack_dir)
    descriptors: list[dict[str, str]] = []
    for entry in manifest.get("co_sources", []):
        ref = str(entry["upstream_ref"])
        digest_file = entry.get("sha256_file")
        sha = (
            hashlib.sha256((pack_dir / str(digest_file)).read_bytes()).hexdigest()
            if digest_file
            else str(entry["sha256"])
        )
        descriptor = {
            "snapshot_id": f"sp_{ref[:12]}",
            "source_id": str(entry["source_id"]),
            "url": str(entry["url"]),
            "upstream_ref": ref,
            "retrieved_at_utc": str(entry["retrieved_at_utc"]),
            "sha256": sha,
            "license": str(entry["license"]),
        }
        if entry.get("upstream_committed_at_utc"):
            descriptor["upstream_committed_at_utc"] = str(entry["upstream_committed_at_utc"])
        descriptors.append(descriptor)
    return descriptors


def snapshot_anchor_utc(descriptor: dict[str, Any]) -> str:
    """Return the time this snapshot's data state verifiably existed.

    The upstream commit time of the pinned ref is the honest anchor: the data
    state was public from that moment, independent of when we fetched it. Packs
    built before the anchor existed fall back to our own retrieval time, which
    is strictly later and therefore never overstates availability.
    """
    return str(descriptor.get("upstream_committed_at_utc") or descriptor["retrieved_at_utc"])


def _canonicalize_former_names(matches: pd.DataFrame, former_names_path: Path) -> pd.DataFrame:
    former = pd.read_csv(
        former_names_path,
        dtype={"current": "string", "former": "string"},
        parse_dates=["start_date", "end_date"],
    )
    result = matches.copy()
    for rename in former.sort_values(["start_date", "former"]).itertuples(index=False):
        active = result["date"].between(rename.start_date, rename.end_date, inclusive="both")
        for column in ("home_team", "away_team"):
            mask = active & result[column].eq(rename.former)
            result.loc[mask, column] = rename.current
    return result


def _match_identity(row: pd.Series) -> str:
    return "|".join(
        [
            row["date"].date().isoformat(),
            str(row["home_team"]),
            str(row["away_team"]),
            str(row["tournament"]),
            str(row["city"]),
            str(row["country"]),
            str(bool(row["neutral"])),
        ]
    )


def load_match_table(pack_dir: Path) -> pd.DataFrame:
    """Load the source snapshot into Golavo's deterministic typed match table."""
    validate_pack(pack_dir)
    matches = pd.read_csv(
        pack_dir / "results.csv",
        dtype={
            "home_team": "string",
            "away_team": "string",
            "home_score": "Int16",
            "away_score": "Int16",
            "tournament": "string",
            "city": "string",
            "country": "string",
            "neutral": "boolean",
        },
        parse_dates=["date"],
    )
    missing = REQUIRED_RESULT_COLUMNS - set(matches.columns)
    if missing:
        raise ValueError(f"results.csv is missing columns: {sorted(missing)}")
    required_non_score = REQUIRED_RESULT_COLUMNS - {"home_score", "away_score"}
    if matches[list(required_non_score)].isna().any().any():
        raise ValueError("results.csv contains nulls in required identity fields")
    if (
        matches[["home_score", "away_score"]]
        .isna()
        .any(axis=1)
        .ne(matches[["home_score", "away_score"]].isna().all(axis=1))
        .any()
    ):
        raise ValueError("a fixture must have both scores or neither score")
    if (matches[["home_score", "away_score"]].dropna() < 0).any().any():
        raise ValueError("results.csv contains a negative score")

    matches = _canonicalize_former_names(matches, pack_dir / "former_names.csv")
    matches = matches.sort_values(
        ["date", "home_team", "away_team", "tournament"], kind="mergesort"
    ).reset_index(drop=True)
    identities = matches.apply(_match_identity, axis=1)
    occurrences = identities.groupby(identities, sort=False).cumcount()
    match_ids = [
        f"m_{hashlib.sha256(f'{identity}|{occurrence}'.encode()).hexdigest()[:16]}"
        for identity, occurrence in zip(identities, occurrences, strict=True)
    ]
    matches.insert(0, "match_id", match_ids)
    matches["ht_home_score"] = pd.Series(pd.NA, index=matches.index, dtype="Int16")
    matches["ht_away_score"] = pd.Series(pd.NA, index=matches.index, dtype="Int16")
    matches["kickoff_utc"] = pd.to_datetime(matches["date"], utc=True)
    matches["kickoff_precision"] = pd.Series("day", index=matches.index, dtype="string")
    matches["is_complete"] = matches[["home_score", "away_score"]].notna().all(axis=1)
    return matches


def order_instants(matches: pd.DataFrame) -> pd.Series:
    """The most precise instant each row can be ordered by.

    ``date`` is calendar-day only, so ordering by it treats every fixture on a
    day as simultaneous and lets a later kickoff sit "before" an earlier one's
    cutoff. ``kickoff_utc`` carries a real time wherever an overlay supplied
    one and otherwise holds that same date's midnight, so preferring it is
    strictly sharper and leaves date-only frames behaving exactly as before.
    """
    if "kickoff_utc" not in matches.columns:
        return pd.to_datetime(matches["date"], utc=True)
    instants = pd.to_datetime(matches["kickoff_utc"], utc=True)
    if "date" in matches.columns and instants.isna().any():
        return instants.fillna(pd.to_datetime(matches["date"], utc=True))
    return instants


def assert_no_future_rows(matches: pd.DataFrame, cutoff_utc: str | pd.Timestamp) -> None:
    """Fail closed if a training frame contains even one row after its cutoff."""
    cutoff = pd.Timestamp(cutoff_utc)
    cutoff = cutoff.tz_localize("UTC") if cutoff.tzinfo is None else cutoff.tz_convert("UTC")
    instants = order_instants(matches)
    offenders = matches.loc[instants > cutoff]
    if not offenders.empty:
        first = offenders.loc[instants.loc[offenders.index].idxmin()]
        stamp = order_instants(offenders.loc[[first.name]]).iloc[0]
        raise ValueError(
            "training leakage: row "
            f"{first.get('match_id', '<unknown>')} kicking off {stamp.isoformat()} exceeds cutoff "
            f"{cutoff.isoformat()}"
        )


def training_rows(matches: pd.DataFrame, cutoff_utc: str | pd.Timestamp) -> pd.DataFrame:
    """Select a chronological training frame and assert the invariant."""
    cutoff = pd.Timestamp(cutoff_utc)
    cutoff = cutoff.tz_localize("UTC") if cutoff.tzinfo is None else cutoff.tz_convert("UTC")
    instants = order_instants(matches)
    eligible = (
        matches["training_eligible"].astype("boolean").fillna(False)
        if "training_eligible" in matches.columns
        else matches["is_complete"].astype("boolean").fillna(False)
    )
    selected = matches.loc[(instants <= cutoff) & matches["is_complete"] & eligible].copy()
    assert_no_future_rows(selected, cutoff)
    return selected


class NoKickoffAnchor(ValueError):
    """The fixture carries no kickoff instant to anchor a leak-safe cutoff."""


# The column ``completed_view`` attaches so a caller can sort or window on the
# same instant the cutoff was applied to, instead of re-deriving one.
ORDER_INSTANT = "order_instant"


def leak_safe_cutoff(kickoff_utc: str | pd.Timestamp) -> pd.Timestamp:
    """The conservative boundary for a fixture: one second before kickoff.

    Deliberately not tightened further. A day-precision (00:00 UTC) row sharing
    the fixture's calendar day cannot be proven to have kicked off first; that
    exposure is disclosed by callers rather than hidden behind a stricter,
    non-app boundary.
    """
    return to_utc(kickoff_utc) - pd.Timedelta(seconds=1)


@dataclass(frozen=True)
class CompletedView:
    """What a board may honestly show at an instant.

    The read-path counterpart to :class:`TrainingView`. ``rows`` holds the
    completed matches at or before ``cutoff_utc``, carrying :data:`ORDER_INSTANT`
    so a caller sorts and windows on the instant the cut was actually made
    against. ``as_of_iso`` is the same instant in the envelope's ``Z`` form, so a
    board cannot filter to one cutoff while publishing another.
    """

    rows: pd.DataFrame
    cutoff_utc: pd.Timestamp

    @property
    def as_of_iso(self) -> str:
        return iso_utc(self.cutoff_utc)


def completed_view(
    matches: pd.DataFrame, *, as_of_utc: str | pd.Timestamp | None
) -> CompletedView:
    """Completed matches at or before ``as_of_utc``, ordered by the sharpest instant.

    Every read-side board — Golavo Ratings, the Golden Boot, competition
    analytics — shares this one rule, because each previously derived its own and
    the copies disagreed on two things that matter:

    * **which instant to cut on.** Cutting on the calendar ``date`` treats a
      21:00 kickoff as already played at 18:00; that shipped once and was fixed
      in 7b5f2d8. :func:`order_instants` prefers the exact kickoff.
    * **what to do with a blank kickoff.** Comparing the raw column drops those
      rows silently (``NaT <= cutoff`` is False); the fit path always kept them
      at their date's midnight. This keeps them.

    ``as_of_utc`` is required: no board may quietly read "everything". Unlike
    :func:`leak_safe_training_view` this applies no source scoping and excludes
    no fixture's own row — a board reports on history, it does not train on it.
    """
    if as_of_utc is None:
        raise ValueError("completed_view requires an explicit as_of_utc cutoff")
    cutoff = to_utc(as_of_utc)
    if matches.empty:
        return CompletedView(rows=matches.copy(), cutoff_utc=cutoff)

    instants = order_instants(matches)
    complete = matches["is_complete"].astype("boolean").fillna(False)
    rows = matches.loc[complete & (instants <= cutoff)].copy()
    rows[ORDER_INSTANT] = instants.loc[rows.index]
    return CompletedView(rows=rows, cutoff_utc=cutoff)


@dataclass(frozen=True)
class TrainingView:
    """One fixture's training history, and the instant it was cut off at.

    ``rows`` has already passed ``assert_no_future_rows`` and excludes the
    fixture's own row. ``cutoff_utc`` is the ISO instant every model fitted on
    ``rows`` must be told, so a caller cannot fit on this frame while quoting a
    different boundary.
    """

    rows: pd.DataFrame
    cutoff_utc: str
    kickoff_utc: pd.Timestamp


def to_utc(value: Any) -> pd.Timestamp:
    """Read an instant as UTC, treating a naive one as already UTC."""
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def iso_utc(value: pd.Timestamp) -> str:
    """The ``...Z`` form every envelope publishes instants in."""
    return to_utc(value).isoformat().replace("+00:00", "Z")


def _str_or_none(value: Any) -> str | None:
    return None if value is None or pd.isna(value) else str(value)


def _scope_to_fixture_source(matches: pd.DataFrame, match_row: Mapping[str, Any]) -> pd.DataFrame:
    """Narrow history to the fixture's own source — never by ``source_kind``.

    Scoping by kind would silently merge a second international source in were one
    ever added, so a shared team string could pull another dataset's results into
    this fixture's history. A club fixture narrows once more, to its own
    competition; an international fixture must not, because its history is
    legitimately cross-competition (a World Cup fit learns from friendlies).
    """
    source_id = _str_or_none(match_row.get("source_id"))
    if source_id is not None and "source_id" in matches.columns:
        matches = matches.loc[matches["source_id"].astype("string").eq(source_id)]
    competition = _str_or_none(match_row.get("competition"))
    if (
        _str_or_none(match_row.get("source_kind")) == "club"
        and competition is not None
        and "competition" in matches.columns
    ):
        matches = matches.loc[matches["competition"].astype("string").eq(competition)]
    return matches


def leak_safe_training_view(
    matches: pd.DataFrame,
    match_row: Mapping[str, Any],
    *,
    as_of_utc: str | pd.Timestamp | None = None,
) -> TrainingView:
    """Everything one fixture may honestly learn from, and nothing else.

    This is the single owner of the app's central invariant. Four facts that were
    previously re-derived per caller are inseparable here:

    * the cutoff is ``kickoff - 1s`` — the conservative boundary the seal, the
      cockpit replay and the retrospective all claim to share;
    * ``as_of_utc`` may only ever *tighten* it (``min(as_of, kickoff - 1s)``), so a
      forward seal can know less than kickoff but never more;
    * history is scoped to the fixture's own source (and, for a club fixture, its
      own competition);
    * the fixture's own row can never train its own forecast, and
      ``assert_no_future_rows`` has run.

    The cutoff is deliberately not tightened further. A day-precision (00:00 UTC)
    row sharing the fixture's calendar day cannot be proven to have kicked off
    first; that exposure is disclosed by callers rather than hidden behind a
    stricter, non-app boundary.
    """
    kickoff_raw = match_row.get("kickoff_utc")
    if kickoff_raw is None or pd.isna(kickoff_raw):
        raise NoKickoffAnchor("fixture has no kickoff timestamp to anchor a leak-safe cutoff")
    kickoff = to_utc(kickoff_raw)

    cutoff = leak_safe_cutoff(kickoff)
    if as_of_utc is not None:
        cutoff = min(to_utc(as_of_utc), cutoff)
    cutoff_utc = iso_utc(cutoff)

    rows = training_rows(_scope_to_fixture_source(matches, match_row), cutoff_utc)
    match_id = str(match_row["match_id"])
    rows = rows.loc[~rows["match_id"].astype("string").eq(match_id)].copy()
    return TrainingView(rows=rows, cutoff_utc=cutoff_utc, kickoff_utc=kickoff)


def write_parquet(pack_dir: Path, output_path: Path) -> Path:
    """Materialize the typed match table as deterministic Parquet."""
    table = load_match_table(pack_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(output_path, index=False, engine="pyarrow", compression="zstd")
    return output_path
