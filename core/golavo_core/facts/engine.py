"""Build a deterministic Commentator's Notebook for one fixture.

Pure function of (match table, side tables, fixture descriptor). No wall clock,
no network, no model. Build it twice from the same vendored pack and you get a
byte-identical notebook. The information horizon is ``as_of_utc`` — usually a
seal's training cutoff — so the notebook never reads a result the forecast could
not.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd

from golavo_core import __version__

from ._history import TemplateContext, as_utc_iso
from .guardrails import apply_guardrails
from .registry import COINCIDENCE_CAP, REGISTRY, REGISTRY_VERSION, family_size

NOTEBOOK_SCHEMA_VERSION = "0.1.0"
GENERATOR = f"golavo-core/{__version__}"


def _to_utc(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _facts_schema() -> dict[str, Any]:
    from golavo_core.resources import facts_schema_path

    return json.loads(facts_schema_path().read_text(encoding="utf-8"))


def _as_of_history(matches: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    completed = matches.loc[matches["is_complete"].astype("boolean").fillna(False).astype(bool)]
    kickoff = pd.to_datetime(completed["kickoff_utc"], utc=True)
    return completed.loc[kickoff <= as_of].copy()


def _as_of_events(table: pd.DataFrame | None, as_of: pd.Timestamp) -> pd.DataFrame | None:
    if table is None:
        return None
    dates = pd.to_datetime(table["date"], utc=True)
    return table.loc[dates <= as_of].copy()


def build_notebook(
    *,
    matches: pd.DataFrame,
    home_team: str,
    away_team: str,
    competition: str,
    neutral: bool,
    as_of_utc: str,
    kickoff_utc: str,
    source_ids: list[str],
    goalscorers: pd.DataFrame | None = None,
    shootouts: pd.DataFrame | None = None,
    wc_history: Any = None,
    validate: bool = True,
) -> dict[str, Any]:
    """Compute the notebook for one fixture. See module docstring for the contract."""
    as_of = _to_utc(as_of_utc)
    kickoff = _to_utc(kickoff_utc)
    ids = tuple(str(sid) for sid in source_ids)

    history = _as_of_history(matches, as_of)
    ctx = TemplateContext(
        matches=history,
        home_team=str(home_team),
        away_team=str(away_team),
        competition=str(competition),
        neutral=bool(neutral),
        as_of=as_of,
        kickoff=kickoff,
        source_ids=ids,
        goalscorers=_as_of_events(goalscorers, as_of),
        shootouts=_as_of_events(shootouts, as_of),
        wc_history=wc_history,
    )

    proposals = [(tmpl, cand) for tmpl in REGISTRY for cand in tmpl.fn(ctx)]
    facts, suppressed = apply_guardrails(
        proposals, source_ids=ids, as_of=as_of, coincidence_cap=COINCIDENCE_CAP
    )
    notebook_source_ids = list(ids)
    for fact in facts:
        for source_id in fact["source_ids"]:
            if source_id not in notebook_source_ids:
                notebook_source_ids.append(source_id)

    notebook: dict[str, Any] = {
        "schema_version": NOTEBOOK_SCHEMA_VERSION,
        "notebook_id": "nb_pending00",
        "registry_version": REGISTRY_VERSION,
        "as_of_utc": as_utc_iso(as_of),
        "match": {
            "home_team": str(home_team),
            "away_team": str(away_team),
            "competition": str(competition),
            "neutral_venue": bool(neutral),
            "kickoff_utc": as_utc_iso(kickoff),
        },
        "source_ids": notebook_source_ids,
        "family_size": family_size(),
        "coincidence_cap": COINCIDENCE_CAP,
        "facts": facts,
        "suppressed": suppressed,
        "generator": GENERATOR,
    }

    stable = dict(notebook)
    stable.pop("notebook_id")
    digest = hashlib.sha256(_canonical_bytes(stable)).hexdigest()
    notebook["notebook_id"] = f"nb_{digest[:20]}"

    if validate:
        validate_notebook(notebook)
    return notebook


def notebook_for_artifact(
    artifact: dict[str, Any],
    matches: pd.DataFrame,
    *,
    goalscorers: pd.DataFrame | None = None,
    shootouts: pd.DataFrame | None = None,
    wc_history: Any = None,
    source_ids: list[str] | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    """Build the notebook for a ForecastArtifact from its own pack's match table.

    Reads only artifact fields (no import of the forecast writer). The as-of
    horizon is the artifact's training cutoff, so the notebook and the sealed
    forecast see the same information.
    """
    match = artifact["match"]
    if source_ids is None:
        source_ids = [snap["snapshot_id"] for snap in artifact["inputs"]["snapshots"]]
    return build_notebook(
        matches=matches,
        home_team=match["home_team"],
        away_team=match["away_team"],
        competition=match["competition"],
        neutral=match["neutral_venue"],
        as_of_utc=artifact["inputs"]["training_cutoff_utc"],
        kickoff_utc=match["kickoff_utc"],
        source_ids=source_ids,
        goalscorers=goalscorers,
        shootouts=shootouts,
        wc_history=wc_history,
        validate=validate,
    )


def validate_notebook(notebook: dict[str, Any]) -> None:
    """Validate against the JSON schema and enforce the guardrail invariants."""
    from jsonschema import Draft202012Validator, FormatChecker

    Draft202012Validator(_facts_schema(), format_checker=FormatChecker()).validate(notebook)

    if notebook["registry_version"] != REGISTRY_VERSION:
        raise ValueError("notebook registry_version does not match the loaded registry")
    if notebook["family_size"] != family_size():
        raise ValueError("notebook family_size does not match the registry (MC bound drift)")
    if notebook["coincidence_cap"] != COINCIDENCE_CAP:
        raise ValueError("notebook coincidence_cap does not match the registry")

    source_ids = set(notebook["source_ids"])
    coincidences = 0
    for fact in notebook["facts"]:
        if not set(fact["source_ids"]) <= source_ids:
            raise ValueError(f"fact {fact['id']!r} cites a source not in the notebook")
        if fact["sample_n"] < fact["min_sample"]:
            raise ValueError(f"fact {fact['id']!r} is below its own min_sample floor")
        if not fact["source_ids"]:
            raise ValueError(f"fact {fact['id']!r} carries no source")
        if fact["freshness"]["stale"]:
            raise ValueError(f"stale fact {fact['id']!r} was not suppressed")
        if fact["label"] == "coincidence":
            coincidences += 1
    if coincidences > notebook["coincidence_cap"]:
        raise ValueError("coincidence cap exceeded")
