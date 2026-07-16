"""Exact identity, typed-field, provenance and conflict validation."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from golavo_server import (
    correction_policy,
    correction_sanitize,
    correction_store,
    refresh_state,
)

_PLACEHOLDER_RE = re.compile(r"^[WL][0-9]{1,4}$", re.IGNORECASE)


def normalize_proposed(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        raise correction_store.CorrectionStoreError(
            "proposed_value_too_deep", "proposed value is too deeply nested", 422
        )
    if isinstance(value, str):
        if len(value) > 500:
            raise correction_store.CorrectionStoreError(
                "proposed_text_too_long", "proposed text fields are limited to 500 characters", 422
            )
        try:
            _raw, display = correction_sanitize.sanitize(value)
        except correction_sanitize.EvidenceError as exc:
            raise correction_store.CorrectionStoreError(exc.reason_code, exc.detail, 422) from exc
        return display
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not value.is_integer():
            raise correction_store.CorrectionStoreError(
                "invalid_proposed_number", "proposed numeric fields must be integers", 422
            )
        return int(value)
    if isinstance(value, list):
        if len(value) > 20:
            raise correction_store.CorrectionStoreError(
                "proposed_value_too_large", "proposed arrays are limited to 20 items", 422
            )
        return [normalize_proposed(item, depth=depth + 1) for item in value]
    if isinstance(value, dict):
        if len(value) > 20 or not all(isinstance(key, str) for key in value):
            raise correction_store.CorrectionStoreError(
                "invalid_proposed_value", "proposed values must use small string-keyed objects", 422
            )
        return {key: normalize_proposed(item, depth=depth + 1) for key, item in value.items()}
    raise correction_store.CorrectionStoreError(
        "invalid_proposed_value", "proposed value contains an unsupported type", 422
    )


def derive_original(correction_type: str, match: dict[str, Any] | None) -> dict[str, Any] | None:
    if correction_type == "missing_fixture":
        return None
    if match is None:
        raise correction_store.CorrectionStoreError(
            "exact_identity_required", "this correction type requires an exact indexed match", 422
        )
    provenance = match.get("provenance") if isinstance(match.get("provenance"), dict) else {}
    if correction_type == "kickoff_time":
        return {
            "kickoff_utc": match.get("kickoff_utc"),
            "kickoff_precision": match.get("kickoff_precision"),
            "source_id": provenance.get("kickoff") or match.get("source_id"),
        }
    if correction_type == "venue":
        return {
            "city": match.get("city"),
            "country": match.get("country"),
            "source_id": provenance.get("venue") or match.get("source_id"),
        }
    if correction_type == "final_score":
        return {
            "home_score": match.get("home_score"),
            "away_score": match.get("away_score"),
            "is_complete": bool(match.get("is_complete")),
            "source_id": provenance.get("result") or match.get("source_id"),
        }
    if correction_type == "team_alias":
        return {
            "home_team": match.get("home_team"),
            "away_team": match.get("away_team"),
            "competition": match.get("competition"),
            "country": match.get("country"),
            "source_id": provenance.get("identity") or match.get("source_id"),
        }
    raise correction_store.CorrectionStoreError(
        "unknown_correction_type", "unsupported correction type", 422
    )


def _parse_aware(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _required_string(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and bool(value.strip()) else None


def _typed_reasons(
    correction_type: str,
    proposed: dict[str, Any],
    *,
    original: dict[str, Any] | None,
    source_id: str | None,
) -> list[str]:
    reasons: list[str] = []
    if correction_type == "kickoff_time":
        if not _parse_aware(proposed.get("kickoff_utc")):
            reasons.append("kickoff_requires_rfc3339_offset")
        if proposed.get("kickoff_precision") not in {"day", "minute", "exact"}:
            reasons.append("invalid_kickoff_precision")
    elif correction_type == "team_alias":
        alias = _required_string(proposed, "alias")
        canonical = _required_string(proposed, "canonical_team")
        scope = proposed.get("scope")
        if not alias or not canonical or alias.casefold() == canonical.casefold():
            reasons.append("alias_requires_distinct_exact_names")
        if not isinstance(scope, dict) or not _required_string(scope, "source_id"):
            reasons.append("alias_requires_source_scope")
        elif scope.get("source_id") != source_id:
            reasons.append("alias_source_scope_mismatch")
        exact_teams = {
            value
            for value in (
                original.get("home_team") if original else None,
                original.get("away_team") if original else None,
            )
            if isinstance(value, str)
        }
        if not canonical or canonical not in exact_teams:
            reasons.append("alias_requires_exact_indexed_team")
        if isinstance(scope, dict) and original:
            for key in ("competition", "country"):
                supplied = scope.get(key)
                expected = original.get(key)
                if supplied is not None and supplied != expected:
                    reasons.append(f"alias_{key}_scope_mismatch")
    elif correction_type == "venue":
        if not _required_string(proposed, "venue_name"):
            reasons.append("venue_name_required")
        if not _required_string(proposed, "city") or not _required_string(proposed, "country"):
            reasons.append("venue_city_country_required")
    elif correction_type == "final_score":
        home, away = proposed.get("home_score"), proposed.get("away_score")
        if (
            isinstance(home, bool)
            or isinstance(away, bool)
            or not isinstance(home, int)
            or not isinstance(away, int)
            or home < 0
            or away < 0
            or home > 99
            or away > 99
        ):
            reasons.append("invalid_final_score")
        if proposed.get("score_basis") != "regulation_plus_extra_time":
            reasons.append("score_basis_required")
        penalties = proposed.get("penalties")
        if penalties is not None and not (
            isinstance(penalties, dict)
            and all(
                isinstance(penalties.get(key), int)
                and not isinstance(penalties.get(key), bool)
                and penalties[key] >= 0
                for key in ("home", "away")
            )
        ):
            reasons.append("invalid_penalty_score")
    elif correction_type == "missing_fixture":
        home = _required_string(proposed, "home_team")
        away = _required_string(proposed, "away_team")
        if not home or not away or home.casefold() == away.casefold():
            reasons.append("fixture_requires_distinct_teams")
        if home and _PLACEHOLDER_RE.fullmatch(home):
            reasons.append("placeholder_team_not_allowed")
        if away and _PLACEHOLDER_RE.fullmatch(away):
            reasons.append("placeholder_team_not_allowed")
        if not _required_string(proposed, "competition"):
            reasons.append("fixture_competition_required")
        if not _parse_aware(proposed.get("kickoff_utc")):
            reasons.append("kickoff_requires_rfc3339_offset")
        if proposed.get("kickoff_precision") not in {"day", "minute", "exact"}:
            reasons.append("invalid_kickoff_precision")
        if not _required_string(proposed, "upstream_record_key"):
            reasons.append("upstream_record_key_required")
    return sorted(set(reasons))


def _proposed_tokens(correction_type: str, proposed: dict[str, Any]) -> list[str]:
    if correction_type == "missing_fixture":
        kickoff = str(proposed.get("kickoff_utc") or "")
        return [
            str(proposed.get("home_team") or ""),
            str(proposed.get("away_team") or ""),
            kickoff[:10],
        ]
    if correction_type == "kickoff_time":
        kickoff = str(proposed.get("kickoff_utc") or "")
        return [kickoff[:10], kickoff[11:16]]
    if correction_type == "team_alias":
        return [str(proposed.get("alias") or ""), str(proposed.get("canonical_team") or "")]
    if correction_type == "venue":
        return [str(proposed.get("venue_name") or ""), str(proposed.get("city") or "")]
    if correction_type == "final_score":
        return [str(proposed.get("home_score")), str(proposed.get("away_score"))]
    return []


def _snapshot_evidence_ids(root: Path, proposal: dict[str, Any]) -> list[str]:
    source_id = proposal.get("source_id")
    policy = correction_policy.policy_for(source_id)
    if policy is None or policy["license_namespace"] != "core-cc0":
        return []
    try:
        active, _using_previous = refresh_state.active_generation()
        if active is None:
            return []
        manifest = refresh_state.verify_generation(active)
    except (OSError, RuntimeError, ValueError):
        return []
    receipts = {
        str(item.get("upstream_ref")): item
        for item in manifest.get("source_snapshots", [])
        if item.get("source_id") == source_id
    }
    tokens = [
        token.casefold()
        for token in _proposed_tokens(proposal["correction_type"], proposal["proposed"])
        if token
    ]
    verified: list[str] = []
    for evidence, raw in correction_store.raw_evidence(root, proposal["proposal_id"]):
        revision = evidence.get("source_revision")
        receipt = receipts.get(str(revision))
        if receipt is None:
            continue
        excerpt = raw.lower()
        if tokens and not all(token.encode().lower() in excerpt for token in tokens):
            continue
        for file_receipt in receipt.get("files", []):
            relative = Path(str(file_receipt.get("path", "")))
            if relative.is_absolute() or ".." in relative.parts:
                continue
            source_path = active / "raw" / str(source_id) / str(revision) / relative
            try:
                source_bytes = source_path.read_bytes()
            except OSError:
                continue
            if raw in source_bytes:
                verified.append(str(evidence["evidence_id"]))
                break
    return sorted(set(verified))


def validate(
    root: Path,
    proposal_id: str,
    *,
    current_match: dict[str, Any] | None,
) -> dict[str, Any]:
    proposal = correction_store.get_proposal(root, proposal_id)
    reason_codes = _typed_reasons(
        proposal["correction_type"],
        proposal["proposed"],
        original=proposal["original"],
        source_id=proposal.get("source_id"),
    )
    conflicts: list[dict[str, Any]] = []
    try:
        correction_policy.validate_type(proposal.get("source_id"), proposal["correction_type"])
    except correction_policy.CorrectionPolicyError as exc:
        reason_codes.append(exc.reason_code)
    if not proposal["evidence"] or all(item["redacted"] for item in proposal["evidence"]):
        reason_codes.append("source_url_and_captured_evidence_required")
    if proposal["correction_type"] != "missing_fixture":
        if current_match is None:
            conflicts.append({"reason_code": "target_match_missing"})
        else:
            current_original = derive_original(proposal["correction_type"], current_match)
            if current_original != proposal["original"]:
                conflicts.append(
                    {
                        "reason_code": "authoritative_base_changed",
                        "original": proposal["original"],
                        "current": current_original,
                    }
                )
    elif current_match is not None:
        conflicts.append(
            {
                "reason_code": "authoritative_fixture_already_exists",
                "match_id": current_match.get("match_id"),
            }
        )
    conflicts.extend(correction_store.competing_proposals(root, proposal))
    snapshot_ids = _snapshot_evidence_ids(root, proposal) if not reason_codes else []
    verification = "snapshot_verified" if snapshot_ids else "structural_only"
    if conflicts:
        state = "conflict"
        reason_codes.append("conflict_fails_closed")
    elif reason_codes:
        state = "evidence_attached" if proposal["evidence"] else "draft"
        verification = "none"
    else:
        state = "validated_candidate"
    return correction_store.apply_validation(
        root,
        proposal_id,
        state=state,
        verification_level=verification,
        reason_codes=sorted(set(reason_codes)),
        conflicts=conflicts,
        snapshot_evidence_ids=snapshot_ids,
        expected_head_event_id=proposal["head_event_id"],
    )
