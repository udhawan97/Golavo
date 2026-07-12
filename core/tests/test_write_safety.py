"""Write-path safety for the ledger: atomic writes, corrupt-partial recovery,
concurrent-seal safety, a faithful compute/write split, and integrity-verified
score/void inputs.

These guard the pre-conditions for an in-app seal route. The desktop shell kills
the sidecar on every exit, so a seal can be interrupted mid-write; a double-click
can fire two identical seals at once; and a hand-edited seal must never be able to
launder itself into a scored/voided successor.
"""

from __future__ import annotations

import copy
import json
import threading
from pathlib import Path

import pytest
from golavo_core.artifacts import (
    _write_artifact,
    build_forecast_artifact,
    canonical_bytes,
    load_verified_artifact,
    score_forecast,
    seal_forecast,
    void_forecast,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK = REPO_ROOT / "packs/martj42-internationals"

# Two genuinely-scheduled fixtures in this snapshot, both kicking off after the
# as-of, both well above the abstain floor (so they seal with real probs). The
# default elo family carries no score_matrix, so a transposed-probs tamper stays
# schema-coherent and only the content hash can catch it.
_AS_OF = "2026-07-10T20:00:00Z"
_A = {"date": "2026-07-11", "home_team": "Norway", "away_team": "England"}
_B = {"date": "2026-07-11", "home_team": "Argentina", "away_team": "Switzerland"}


def _seal(output_dir: Path, fixture: dict[str, str]) -> Path:
    return seal_forecast(pack_dir=PACK, output_dir=output_dir, as_of_utc=_AS_OF, **fixture)


def test_build_forecast_artifact_matches_seal_bytes(tmp_path: Path) -> None:
    """The pure compute path and the persist path agree byte-for-byte."""
    built = build_forecast_artifact(pack_dir=PACK, as_of_utc=_AS_OF, **_A)
    path = _seal(tmp_path / "ledger", _A)
    assert path.stem == built["artifact_id"]
    assert path.read_bytes() == canonical_bytes(built) + b"\n"
    # The built dict is a genuine, fully content-addressed artifact.
    assert load_verified_artifact(path)["artifact_id"] == built["artifact_id"]


def test_seal_is_idempotent_and_writes_one_audit_line(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    first = _seal(ledger, _A)
    first_bytes = first.read_bytes()
    second = _seal(ledger, _A)
    assert second == first
    assert second.read_bytes() == first_bytes
    audit = (ledger / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert sum(first.stem in line for line in audit) == 1


def test_seal_repairs_a_truncated_partial_write(tmp_path: Path) -> None:
    """A file left half-written by a killed process must not brick the fixture id.

    Before the atomic-write fix, a truncated fa_*.json whose bytes differ from the
    canonical content tripped the immutable-collision guard on every retry, forever.
    """
    ledger = tmp_path / "ledger"
    path = _seal(ledger, _A)
    good_bytes = path.read_bytes()

    # Simulate a crash mid-write: overwrite the artifact with a truncated prefix.
    path.write_bytes(good_bytes[:20])
    with pytest.raises(ValueError):
        load_verified_artifact(path)  # confirm it is genuinely corrupt now

    repaired = _seal(ledger, _A)  # same inputs → same id → must repair, not raise
    assert repaired == path
    assert repaired.read_bytes() == good_bytes
    assert load_verified_artifact(repaired)["artifact_id"] == path.stem
    audit = (ledger / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert sum(path.stem in line for line in audit) == 1


def test_seal_leaves_no_temp_files(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    _seal(ledger, _A)
    assert not list(ledger.glob("*.tmp"))
    assert not list(ledger.glob(".*.tmp"))


def test_concurrent_identical_seals_are_safe(tmp_path: Path) -> None:
    """N identical writes entering the ledger at once produce one valid artifact
    and exactly one audit line.

    Workers rendezvous on a barrier immediately before ``_write_artifact`` so they
    contend on the real locked section — this would flake (duplicate audit lines,
    torn reads) if ``_WRITE_LOCK`` were removed.
    """
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    artifact = build_forecast_artifact(pack_dir=PACK, as_of_utc=_AS_OF, **_A)
    workers = 12
    barrier = threading.Barrier(workers)
    results: list[Path] = []
    errors: list[BaseException] = []
    guard = threading.Lock()

    def worker() -> None:
        try:
            barrier.wait()
            path = _write_artifact(artifact, ledger)
            with guard:
                results.append(path)
        except BaseException as exc:  # noqa: BLE001 - recorded and re-asserted below
            with guard:
                errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, errors
    assert len(results) == workers
    assert len({p.stem for p in results}) == 1
    path = results[0]
    assert load_verified_artifact(path)["artifact_id"] == path.stem
    audit = (ledger / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert sum(path.stem in line for line in audit) == 1


def test_genuine_collision_still_raises(tmp_path: Path) -> None:
    """A different, VALID artifact already living under a target id is a real content
    collision and must fail loudly — the repair path only rescues corrupt files."""
    ledger = tmp_path / "ledger"
    path_a = _seal(ledger, _A)

    # Forge a distinct, valid artifact and force it onto A's id/path.
    other = build_forecast_artifact(pack_dir=PACK, as_of_utc=_AS_OF, **_B)
    assert other["artifact_id"] != path_a.stem
    imposter = copy.deepcopy(other)
    imposter["artifact_id"] = path_a.stem
    with pytest.raises(FileExistsError, match="immutable artifact collision"):
        _write_artifact(imposter, ledger)
    # A's genuine bytes are untouched.
    assert load_verified_artifact(path_a)["artifact_id"] == path_a.stem


def _tamper_transpose_probs(path: Path) -> None:
    artifact = json.loads(path.read_text(encoding="utf-8"))
    assert artifact["forecast"].get("score_matrix") is None, "elo seal must carry no matrix"
    probs = artifact["forecast"]["probs"]
    probs["home"], probs["away"] = probs["away"], probs["home"]
    # Schema-valid (still sums to 1, no matrix to contradict) but the stored
    # payload_sha256 no longer matches the content.
    path.write_bytes(canonical_bytes(artifact) + b"\n")


def test_score_rejects_a_tampered_input_seal(tmp_path: Path) -> None:
    sealed = _seal(tmp_path / "ledger", _A)
    _tamper_transpose_probs(sealed)
    with pytest.raises(ValueError, match="payload_sha256 mismatch"):
        # The integrity check fires before the newer pack is even read.
        score_forecast(artifact_path=sealed, newer_pack_dir=PACK, output_dir=tmp_path / "scored")


def test_void_rejects_a_tampered_input_seal(tmp_path: Path) -> None:
    sealed = _seal(tmp_path / "ledger", _A)
    _tamper_transpose_probs(sealed)
    with pytest.raises(ValueError, match="payload_sha256 mismatch"):
        void_forecast(
            artifact_path=sealed,
            output_dir=tmp_path / "voided",
            voided_at_utc="2026-07-11T00:00:00Z",
            reason="tampered input must be rejected before voiding",
        )


def test_seal_repairs_a_valid_json_non_artifact_leftover(tmp_path: Path) -> None:
    """A leftover that parses as JSON but is not a valid artifact is still repaired —
    the repair check is content integrity, not mere parseability."""
    ledger = tmp_path / "ledger"
    path = _seal(ledger, _A)
    good_bytes = path.read_bytes()
    path.write_bytes(canonical_bytes({"not": "an artifact"}) + b"\n")
    repaired = _seal(ledger, _A)
    assert repaired.read_bytes() == good_bytes
    assert load_verified_artifact(repaired)["artifact_id"] == path.stem


def test_seal_recovers_a_missing_audit_line(tmp_path: Path) -> None:
    """A crash between writing the artifact and appending its audit event is
    recovered on the next identical seal: the file is byte-identical (no rewrite)
    yet the audit line is still appended."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    artifact = build_forecast_artifact(pack_dir=PACK, as_of_utc=_AS_OF, **_A)
    path = ledger / f"{artifact['artifact_id']}.json"
    path.write_bytes(canonical_bytes(artifact) + b"\n")  # written; audit never appended
    assert not (ledger / "audit.jsonl").exists()
    sealed = _seal(ledger, _A)
    assert sealed == path
    audit = (ledger / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert sum(path.stem in line for line in audit) == 1


def test_score_and_void_reject_a_tampered_matrix_seal(tmp_path: Path) -> None:
    """A dixon_coles seal carries a score_matrix; editing a grid cell breaks its
    coherence, and both score and void must reject it on read (a different guard
    than the payload-hash path the elo tamper tests exercise)."""
    ledger = tmp_path / "ledger"
    sealed = seal_forecast(
        pack_dir=PACK, output_dir=ledger, as_of_utc=_AS_OF, family="dixon_coles", **_A
    )
    artifact = json.loads(sealed.read_text(encoding="utf-8"))
    assert artifact["forecast"]["score_matrix"] is not None
    artifact["forecast"]["score_matrix"]["grid"][0][0] += 0.5  # break coherence
    sealed.write_bytes(canonical_bytes(artifact) + b"\n")
    with pytest.raises(ValueError, match="incoherent score_matrix"):
        score_forecast(artifact_path=sealed, newer_pack_dir=PACK, output_dir=tmp_path / "scored")
    with pytest.raises(ValueError, match="incoherent score_matrix"):
        void_forecast(
            artifact_path=sealed,
            output_dir=tmp_path / "voided",
            voided_at_utc="2026-07-11T00:00:00Z",
            reason="tampered matrix must be rejected before voiding",
        )
