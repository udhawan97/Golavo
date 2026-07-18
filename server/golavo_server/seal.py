"""Write path for in-app forecasts: eligibility + the single explicit seal.

The rest of the server is read-only; this module adds the one deterministic
write. It runs the SAME engine the CLI does (``golavo_core.artifacts``) and
persists through the SAME atomic, integrity-checked writer, so an in-app seal is
byte-identical to a ``golavo seal``. Three safety properties hold:

* **The client names only a fixture and (optionally) a model family.** The pack,
  the training date, and the as-of are all resolved server-side — the pack from
  the indexed row's source, the as-of from the server clock. A caller can neither
  backdate a seal nor point the engine at an untrusted file or pack path.
* **Forward seals cover men's senior internationals and the bundled domestic
  leagues.** Both map a scheduled row to exactly one pinned CC0 pack — an
  international by its martj42 source, a club by its competition (the OpenFootball
  club source id is shared across leagues, so the competition disambiguates).
  A club prediction is written the same way but is graded only once two
  independent sources agree, so it stays honestly pending until then. Everything
  else returns a typed, honest abstention.
* **One active seal per (fixture, family).** A repeat request returns the existing
  immutable artifact instead of minting a near-duplicate that differs only by the
  as-of second.

pandas/pyarrow and the model stack are imported INSIDE functions to keep the
frozen sidecar's boot and /health readiness fast (see main.py's import note).
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from golavo_core import resources

# Default model for a sealed forecast. dixon_coles is the best matrix-capable
# family on the committed international folds (it produces the exact-score grid the
# UI shows); elo_ordlogit is the stronger pure-1X2 model but seals no grid.
DEFAULT_FAMILY = "dixon_coles"

# Families the route accepts. bivariate_poisson is excluded — it is numerically
# identical to poisson_independent in every recorded evaluation fold.
ALLOWED_FAMILIES = ("dixon_coles", "poisson_independent", "elo_ordlogit", "climatological")

DEFAULT_HORIZON = "T-24h"

# The one international source Golavo can seal from, and the pack name it falls
# back to when no registry is bundled. A map keyed by source id would promise a
# generality that does not exist: a second international source would need its
# own eligibility rules and co-source handling, not another dict entry.
_INTERNATIONAL_SOURCE_ID = "martj42-international-results"
_INTERNATIONAL_PACK_NAME = "martj42-internationals"

# Module global (mirrors matches.INDEX_PATH) so tests can repoint pack resolution
# at a fixture directory. Defaults to the committed packs, bundle-resolved. In a
# frozen build that ships no packs this path will not exist and eligibility
# reports ``pack_unavailable`` rather than pretending it can seal.
PACKS_DIR = resources.resource("packs")

# Serialises the check-existing -> build -> write critical section so a concurrent
# double-request for the same fixture cannot both miss the idempotency scan and
# mint two root seals that differ only by the as-of second. A single sidecar owns
# its ledger and seals are infrequent single-user actions, so one lock is ample.
_SEAL_LOCK = threading.Lock()


class SealError(Exception):
    """A typed seal failure carrying an HTTP status and a machine reason code."""

    def __init__(self, status_code: int, reason_code: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.reason_code = reason_code
        self.detail = detail


def _now(now_utc: datetime | None) -> datetime:
    return (now_utc or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _active_bundled_pack(source_id: str, competition: str | None = None) -> Path | None:
    """The current bundled pack for a source, so search and sealing agree.

    A thin adapter over :func:`golavo_core.packstore.active_pack`, which owns the
    rule; this call site only says where a frozen build keeps its packs — flat in
    ``PACKS_DIR``, not nested as the registry path spells them. The resolver
    declines a pack the build did not ship, so a partial bundle resolves what it
    has instead of failing; an older build with no registry at all resolves None
    and the caller falls back to the pinned canonical pack.
    """
    from golavo_core.packstore import active_pack

    packs_dir = Path(PACKS_DIR)

    def resolve(declared: str) -> Path | None:
        pack = packs_dir / Path(declared).name
        return pack if (pack / "manifest.json").is_file() else None

    return active_pack(
        packs_dir / "snapshots.json",
        resolve=resolve,
        source_id=source_id,
        competition=competition,
    )


def resolve_pack_dir(
    source_id: str | None, source_kind: str | None, competition: str | None = None
) -> Path | None:
    """The pinned CC0 pack a fixture's forward seal must train from, or None.

    Two kinds of fixture resolve to exactly one pack:

    * men's internationals — one martj42 pack (competition is not needed);
    * a club fixture whose ``competition`` names its league — the OpenFootball
      club source id is shared across five leagues, so the competition is what
      picks the one league pack.

    Resolution order, all keeping search and sealing on one source of truth:
    a runtime-refreshed pack (an in-app "pull it in" refresh) first; then the
    greatest-anchor bundled pack (the same one the search index is built from, so a
    bundled refresh that adds fixtures becomes sealable too); then the pinned
    canonical pack as a fallback.
    """
    if source_kind == "club":
        # A club trains only on its own league (leak_safe_training_view scopes to
        # source_id AND competition), and that league is exactly one bundled pack.
        if not source_id or not competition:
            return None
        return _active_bundled_pack(source_id, competition)
    if source_kind != "international":
        return None
    if source_id != _INTERNATIONAL_SOURCE_ID:
        return None
    from golavo_server import runtime  # local: avoid an import cycle at load

    refreshed = runtime.refreshed_pack_dir()
    if refreshed is not None and (refreshed / "manifest.json").is_file():
        return refreshed
    active = _active_bundled_pack(source_id or "")
    if active is not None:
        return active
    pack = Path(PACKS_DIR) / _INTERNATIONAL_PACK_NAME
    return pack if (pack / "manifest.json").is_file() else None


def eligibility(match: dict[str, Any], *, now_utc: datetime | None = None) -> dict[str, Any]:
    """Whether a fixture can be forward-sealed now, with a typed reason.

    Pure over the index-row view ``matches.get_match`` returns — it never fits a
    model, so an ``eligible`` fixture can still become a recorded abstention at
    seal time (the 10-match floor is decided there).
    """
    existing = [f["artifact_id"] for f in match.get("forecasts", []) if "artifact_id" in f]
    base = {"family": DEFAULT_FAMILY, "existing_artifact_ids": existing}

    def verdict(eligible: bool, reason_code: str, detail: str) -> dict[str, Any]:
        return {**base, "eligible": eligible, "reason_code": reason_code, "detail": detail}

    if bool(match.get("is_complete")):
        return verdict(
            False,
            "fixture_complete",
            "this fixture already has a result; a forward seal targets a scheduled fixture",
        )

    source_id = match.get("source_id")
    source_kind = match.get("source_kind")
    competition = match.get("competition")
    if source_kind not in ("international", "club") or (
        source_kind == "international" and source_id != _INTERNATIONAL_SOURCE_ID
    ):
        return verdict(
            False,
            "unsupported_competition",
            "forward seals cover men's senior internationals and the bundled domestic leagues",
        )
    if resolve_pack_dir(source_id, source_kind, competition) is None:
        return verdict(
            False,
            "pack_unavailable",
            "the pinned data pack for this fixture is not available in this build",
        )

    kickoff = match.get("kickoff_utc")
    if kickoff is None:
        return verdict(False, "no_kickoff", "this fixture has no usable kickoff time")
    if _now(now_utc) >= _parse_iso(kickoff):
        return verdict(
            False,
            "kickoff_passed",
            "the seal window closes at kickoff (date-only source: 00:00 UTC on match day)",
        )

    return verdict(True, "eligible", "a local forecast can be sealed for this fixture")


def _reason_for(exc: ValueError) -> str:
    """Map a build_forecast_artifact ValueError to a stable machine reason code."""
    msg = str(exc).lower()
    if "already has a result" in msg:
        return "fixture_complete"
    if "before kickoff" in msg or "must be before kickoff" in msg:
        return "kickoff_passed"
    if "before the snapshot" in msg:
        return "snapshot_anchor"
    if "expected exactly one match" in msg:
        return "fixture_not_in_pack"
    if "unknown model family" in msg:
        return "unsupported_family"
    return "seal_rejected"


def _result_view(artifact: dict[str, Any]) -> dict[str, Any]:
    forecast = artifact.get("forecast", {})
    return {
        "artifact_id": artifact["artifact_id"],
        "status": artifact["status"],
        "family": artifact.get("model", {}).get("family"),
        "abstained": bool(forecast.get("abstained")),
        "abstain_reason": forecast.get("abstain_reason"),
    }


def _existing_seal(forecasts_dir: Path, match_id: str, family: str) -> dict[str, Any] | None:
    """A root seal already recorded for this (fixture, family), or None.

    A cheap navigation scan (no integrity verification — the reopen path
    re-verifies): finds a non-superseded sealed/abstained artifact for this match
    and family so a repeat request is idempotent instead of minting a duplicate.
    """
    import json

    folder = Path(forecasts_dir)
    if not folder.exists():
        return None
    for path in sorted(folder.glob("fa_*.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if not isinstance(obj, dict):
            continue
        if (
            "artifact_id" in obj
            and obj.get("match", {}).get("match_id") == match_id
            and obj.get("model", {}).get("family") == family
            and obj.get("status") in ("sealed", "abstained")
            and obj.get("supersedes") is None
        ):
            return obj
    return None


def _write_notebook_best_effort(artifact: dict[str, Any], pack_dir: Path, ledger: Path) -> None:
    """Precompute the Commentator's Notebook beside the seal. Never blocks the seal.

    Mirrors ``golavo notebook`` so the read-only facts route serves it unchanged.
    A build/validate failure is swallowed: the seal is the product, the notebook
    is context.
    """
    import json

    try:
        from golavo_core.facts import load_side_tables, notebook_for_artifact
        from golavo_core.ingest import load_matches

        matches_df = load_matches(Path(pack_dir))
        goalscorers, shootouts = load_side_tables(Path(pack_dir))
        notebook = notebook_for_artifact(
            artifact, matches_df, goalscorers=goalscorers, shootouts=shootouts
        )
        out = ledger / "notebooks" / f"{artifact['artifact_id']}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(out.name + ".tmp")
        tmp.write_text(json.dumps(notebook, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(out)
    except Exception:  # noqa: BLE001 — notebook is best-effort context, never blocks the seal
        return


def seal_match(
    match_id: str,
    *,
    family: str = DEFAULT_FAMILY,
    forecasts_dir: Path,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Resolve a fixture, check eligibility, and write ONE immutable forward seal.

    Returns ``{created, artifact_id, status, family, abstained, abstain_reason}``.
    Raises ``SealError`` (HTTP status + reason code) for a missing match, an
    ineligible fixture, an unknown family, or an engine-rejected seal. Idempotent
    per (fixture, family): an existing seal is returned with ``created=False``.
    ``now_utc`` is an internal test seam; the route always passes the server clock.
    """
    if family not in ALLOWED_FAMILIES:
        raise SealError(
            422, "unsupported_family", f"family must be one of {', '.join(ALLOWED_FAMILIES)}"
        )

    # Read the clock ONCE: the eligibility gate and the sealed as-of must agree, and
    # a single reading also makes two same-instant requests produce identical bytes.
    resolved_now = _now(now_utc)
    ledger = Path(forecasts_dir)

    from golavo_server import matches  # lazy: pulls pandas/pyarrow

    detail = matches.get_match(match_id, forecasts_dir=ledger)
    if detail is None:
        raise SealError(404, "match_not_found", "no indexed match with that id")
    match = detail["match"]

    verdict = eligibility(match, now_utc=resolved_now)
    if not verdict["eligible"]:
        status = 503 if verdict["reason_code"] == "pack_unavailable" else 422
        raise SealError(status, verdict["reason_code"], verdict["detail"])

    pack = resolve_pack_dir(
        match.get("source_id"), match.get("source_kind"), match.get("competition")
    )
    assert pack is not None  # eligibility proved this; narrows the type for mypy

    from golavo_core.artifacts import load_verified_artifact, seal_forecast

    # Hold the seal lock across the idempotency scan AND the write, so a concurrent
    # duplicate request sees the first seal before deciding to create a new one.
    with _SEAL_LOCK:
        existing = _existing_seal(ledger, match_id, family)
        if existing is not None:
            return {"created": False, **_result_view(existing)}
        try:
            path = seal_forecast(
                pack_dir=Path(pack),
                output_dir=ledger,
                date=str(match["kickoff_utc"])[:10],
                home_team=match["home_team"],
                away_team=match["away_team"],
                as_of_utc=_iso(resolved_now),
                horizon=DEFAULT_HORIZON,
                family=family,
                match_id=match_id,
            )
        except ValueError as exc:
            raise SealError(422, _reason_for(exc), str(exc)) from exc
        except FileExistsError as exc:
            raise SealError(409, "artifact_collision", str(exc)) from exc
        artifact = load_verified_artifact(path)

    _write_notebook_best_effort(artifact, Path(pack), ledger)
    return {"created": True, **_result_view(artifact)}
