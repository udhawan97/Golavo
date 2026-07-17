from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from golavo_server import matches
from golavo_server import retrospective as server_retrospective
from jsonschema import Draft202012Validator, FormatChecker


@pytest.fixture(autouse=True)
def _reset():
    matches.reset_cache()
    server_retrospective.reset_cache()
    yield
    matches.reset_cache()
    server_retrospective.reset_cache()


def _schema() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    return json.loads(
        (root / "docs" / "contracts" / "tournament_retrospective.schema.json").read_text(
            encoding="utf-8"
        )
    )


def _contract_validator() -> Draft202012Validator:
    return Draft202012Validator(_schema(), format_checker=FormatChecker())


def _agreement_validator() -> Draft202012Validator:
    """Validates a snapshot_agreement alone.

    The build() tests below drive a deliberately minimal story stub, which is not
    a contract-valid "available" envelope; pointing the whole-envelope validator
    at one would fail on the stub rather than on the field under test.
    """
    schema = _schema()
    return Draft202012Validator(
        {"$ref": "#/$defs/SnapshotAgreement", "$defs": schema["$defs"]},
        format_checker=FormatChecker(),
    )


def _story_envelope() -> dict[str, Any]:
    """A minimal available story, as the core module shapes it."""
    return {
        "schema_version": "0.1.0",
        "status": "available",
        "coverage": {"status": "complete", "scored": 1, "pending": 0, "note": "n"},
        "biggest_surprises": [],
    }


def _fold(fold_id: str, competition: str, **extra: Any) -> dict[str, Any]:
    """A fold entry shaped as ``evaluation._evaluate_folds`` emits one."""
    return {
        "fold_id": fold_id,
        "competition": competition,
        "window_start": "2026-06-11",
        "window_end": "2026-07-19",
        "training_cutoff_utc": "2026-06-10T23:59:59Z",
        "n_matches": 97,
        "models": [{"family": "dixon_coles", "log_loss": 1.02, "params": {}}],
        **extra,
    }


class _FakeIndex:
    """Drives build() over controlled generations without loading the real index.

    The real story layer costs ~327s and the real evaluate() ~30s; neither is
    ever called from these tests.
    """

    def __init__(self, fingerprint: str = "fp-1", epoch: int = 1) -> None:
        self.fingerprint = fingerprint
        self.epoch = epoch
        self.publishes_are_current = True

    def snapshot(self) -> matches.IndexSnapshot:
        return matches.IndexSnapshot(frame=object(), fingerprint=self.fingerprint, epoch=self.epoch)

    def install(self, monkeypatch: pytest.MonkeyPatch) -> _FakeIndex:
        monkeypatch.setattr(matches, "index_snapshot", self.snapshot)
        monkeypatch.setattr(
            matches,
            "snapshot_is_current",
            lambda snapshot: (
                snapshot.fingerprint == self.fingerprint and snapshot.epoch == self.epoch
            ),
        )

        def apply_if_snapshot_current(snapshot, operation) -> bool:
            if not self.publishes_are_current or snapshot.epoch != self.epoch:
                return False
            operation()
            return True

        monkeypatch.setattr(matches, "apply_if_snapshot_current", apply_if_snapshot_current)
        return self


def _stub_layers(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Stub both expensive layers; return a call counter."""
    calls = {"story": 0, "trust": 0}

    def story(frame, progress, is_cancelled):
        calls["story"] += 1
        return _story_envelope()

    def trust(pack_dir):
        calls["trust"] += 1
        return {**_fold("WC2026", "FIFA World Cup"), "status": "available"}

    monkeypatch.setattr(server_retrospective, "_story", story)
    monkeypatch.setattr(server_retrospective, "_trust", trust)
    return calls


def test_matches_reset_clears_the_retrospective_cache() -> None:
    """A repointed index must never serve a retrospective from the old frame."""
    server_retrospective._CACHE[("probe",)] = {"stale": True}
    matches.reset_cache()
    assert server_retrospective._CACHE == {}


# --- both layers, one pack -------------------------------------------------


def test_build_stamps_the_exact_pack_it_handed_the_trust_layer(monkeypatch) -> None:
    """Story and trust must never describe different packs, and the response must
    stamp the one they shared — auditably, not by a name that cannot tell two
    packs apart."""
    seen: list[Any] = []
    pack_dir = Path("/gen-7/packs/internationals")

    monkeypatch.setattr(server_retrospective.seal, "resolve_pack_dir", lambda *a: pack_dir)
    monkeypatch.setattr(server_retrospective, "_pack_identity", lambda p: (f"stamp::{p}", "d" * 64))
    monkeypatch.setattr(
        server_retrospective,
        "_story",
        lambda frame, progress, is_cancelled: _story_envelope(),
    )

    def trust(handed: Any) -> dict[str, Any]:
        seen.append(handed)
        return {**_fold("WC2026", "FIFA World Cup"), "status": "available"}

    monkeypatch.setattr(server_retrospective, "_trust", trust)
    _FakeIndex().install(monkeypatch)

    result = server_retrospective.build()

    assert seen == [pack_dir]
    assert result["provenance"]["pack"] == f"stamp::{pack_dir}"
    assert result["provenance"]["index_sha256"] == "fp-1"


def test_pack_identity_identifies_the_snapshot_not_the_directory_name(monkeypatch) -> None:
    """Every refreshed generation's pack is named "internationals", so the name is
    inert. Two different generations must stamp differently or the decoupling this
    stamp exists to expose stays invisible."""
    from golavo_core import ingest

    descriptors = {
        Path("/gen-7/packs/internationals"): {"snapshot_id": "sp_aaaaaaaaaaaa", "sha256": "a" * 64},
        Path("/gen-8/packs/internationals"): {"snapshot_id": "sp_bbbbbbbbbbbb", "sha256": "b" * 64},
    }
    monkeypatch.setattr(ingest, "snapshot_descriptor", lambda p: descriptors[p])

    stamps = {server_retrospective._pack_identity(p)[0] for p in descriptors}

    assert len(stamps) == 2
    assert {p.name for p in descriptors} == {"internationals"}  # the names are identical
    assert stamps == {f"sp_aaaaaaaaaaaa@{'a' * 64}", f"sp_bbbbbbbbbbbb@{'b' * 64}"}


def test_pack_identity_never_raises_on_a_corrupt_pack(monkeypatch) -> None:
    """snapshot_descriptor validates the pack off disk; provenance degrading to a
    stated reason is honest, a 500 is not."""
    from golavo_core import ingest

    def boom(pack_dir):
        raise ValueError("manifest.json is not valid JSON")

    monkeypatch.setattr(ingest, "snapshot_descriptor", boom)

    stamp, digest = server_retrospective._pack_identity(Path("/broken"))

    assert stamp.startswith("unidentified: ")
    assert "manifest.json" in stamp
    assert digest is None  # unknown, never a digest that could accidentally match
    assert server_retrospective._pack_identity(None) == (
        "unresolved: no sourcepack resolved for this index",
        None,
    )


# --- the one-snapshot claim, checked not asserted ---------------------------


def _meta(tmp_path: Path, digest: str | None) -> Path:
    """An index meta.json as ingest writes one: one built_from entry per pack.

    The real index carries NINE, the internationals pack among them, so the club
    entry here is load-bearing: reading the wrong one would compare this pack
    against a club pack's digest and cry mismatch on a consistent snapshot.
    """
    built_from = [{"source_id": "openfootball-football-json", "manifest_sha256": "e" * 64}]
    if digest is not None:
        built_from.append(
            {"source_id": server_retrospective._MARTJ42, "manifest_sha256": digest}
        )
    path = tmp_path / "matches_index.meta.json"
    path.write_text(json.dumps({"built_from": built_from, "schema_version": "0.5.0"}))
    return path


def _build_with(monkeypatch, meta_path: Path | None, pack_digest: str | None) -> dict[str, Any]:
    """build() over a controlled (index meta, pack digest) pair."""
    _stub_layers(monkeypatch)
    monkeypatch.setattr(server_retrospective.seal, "resolve_pack_dir", lambda *a: Path("/p"))
    monkeypatch.setattr(
        server_retrospective,
        "_pack_identity",
        lambda p: (f"sp_x@{pack_digest}" if pack_digest else "unidentified: boom", pack_digest),
    )
    index = _FakeIndex().install(monkeypatch)
    # install() hands back a snapshot with no meta_path; this build reads the meta
    # off the snapshot itself, so give it one.
    monkeypatch.setattr(
        matches,
        "index_snapshot",
        lambda: matches.IndexSnapshot(
            frame=object(), fingerprint=index.fingerprint, epoch=index.epoch, meta_path=meta_path
        ),
    )
    server_retrospective.reset_cache()
    return server_retrospective.build()


def test_build_detects_a_pack_the_index_was_not_built_from(monkeypatch, tmp_path) -> None:
    """The exact failure the pack stamp NAMED but could not catch.

    A user refreshes (generation G1); the app upgrades and MATCH_INDEX_SCHEMA_VERSION
    bumps. Next run, _resolve_index_paths() falls back to the committed bundle index
    while resolve_pack_dir() still hands trust G1's pack. After the tournament both
    plausibly carry 104 completed matches, so reconciling coverage.scored against
    trust.n_matches says nothing at all — only the digests can show it.
    """
    result = _build_with(monkeypatch, _meta(tmp_path, "a" * 64), pack_digest="b" * 64)

    agreement = result["provenance"]["snapshot_agreement"]
    assert agreement["status"] == "mismatched"
    assert agreement["cause"] == "pack_index_mismatch"
    # Both digests are stamped, so the verdict is auditable rather than asserted.
    assert agreement["index_pack_sha256"] == "a" * 64
    assert agreement["pack_sha256"] == "b" * 64
    assert "different datasets" in agreement["reason"]
    _agreement_validator().validate(agreement)


def test_build_verifies_one_snapshot_when_the_digests_agree(monkeypatch, tmp_path) -> None:
    """snapshot_descriptor()["sha256"] and the index meta's built_from[].manifest_sha256
    are the same quantity — the sha256 of the pack's manifest.json — which is what
    makes the comparison exact rather than heuristic."""
    result = _build_with(monkeypatch, _meta(tmp_path, "a" * 64), pack_digest="a" * 64)

    agreement = result["provenance"]["snapshot_agreement"]
    assert agreement["status"] == "verified"
    assert agreement["index_pack_sha256"] == agreement["pack_sha256"] == "a" * 64
    assert "cause" not in agreement
    _agreement_validator().validate(agreement)


def test_an_uncheckable_snapshot_never_reads_as_a_verified_one(monkeypatch, tmp_path) -> None:
    """The claim must fail open to "unknown", never to "verified" — and the two
    sides that can go missing stay distinguishable without parsing prose."""
    no_pack = _build_with(monkeypatch, _meta(tmp_path, "a" * 64), pack_digest=None)
    assert no_pack["provenance"]["snapshot_agreement"]["status"] == "unverified"
    assert no_pack["provenance"]["snapshot_agreement"]["cause"] == "pack_unidentified"

    # An index whose meta names every source EXCEPT this one cannot vouch for the pack.
    other = _build_with(monkeypatch, _meta(tmp_path, None), pack_digest="b" * 64)
    assert other["provenance"]["snapshot_agreement"]["status"] == "unverified"
    assert other["provenance"]["snapshot_agreement"]["cause"] == "index_provenance_unreadable"

    # A meta that is absent from disk entirely is the same "unknown", not a crash.
    missing = _build_with(monkeypatch, tmp_path / "gone.json", pack_digest="b" * 64)
    assert missing["provenance"]["snapshot_agreement"]["status"] == "unverified"
    for envelope in (no_pack, other, missing):
        _agreement_validator().validate(envelope["provenance"]["snapshot_agreement"])


def test_index_pack_digest_reads_this_source_entry_not_just_any(tmp_path) -> None:
    """built_from[] carries every pack the index was built from — nine on the real
    index. Reading the wrong entry compares the internationals pack against a club
    pack's digest and cries mismatch on a perfectly consistent snapshot."""
    assert server_retrospective._index_pack_digest(_meta(tmp_path, "a" * 64)) == "a" * 64
    # Every "cannot tell" path is None, never a value a comparison could match on.
    assert server_retrospective._index_pack_digest(None) is None
    assert server_retrospective._index_pack_digest(tmp_path / "absent.json") is None
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json")
    assert server_retrospective._index_pack_digest(corrupt) is None


# --- trust layer -----------------------------------------------------------


def test_trust_selects_the_wc2026_fold_not_the_world_cup_report_card(monkeypatch) -> None:
    """The story layer is exclusively 2026. evaluate() groups report_cards per
    COMPETITION and FOLDS holds two World Cup folds, so a card selected by
    competition == "FIFA World Cup" blends WC2022 into a WC2026 page. Selection is
    by fold_id, out of folds, and must be ordering-independent."""
    from golavo_core import evaluation

    summary = {
        "folds": [
            _fold("WC2022", "FIFA World Cup", n_matches=64, marker="wrong-tournament"),
            _fold("EURO2024", "UEFA Euro", n_matches=51),
            _fold("WC2026", "FIFA World Cup", n_matches=97, marker="the-one-we-want"),
        ],
        # The blended card the old implementation reached for: same competition,
        # two tournaments, 161 matches spanning 2022-11-20..2026-07-19.
        "report_cards": [
            {
                "competition": "FIFA World Cup",
                "window_start": "2022-11-20",
                "window_end": "2026-07-19",
                "models": [{"family": "dixon_coles", "n_matches": 161, "log_loss": 1.0}],
            }
        ],
    }
    monkeypatch.setattr(evaluation, "evaluate", lambda pack_dir: summary)

    trust = server_retrospective._trust(Path("/unused"))

    assert trust["status"] == "available"
    assert trust.get("fold_id") == "WC2026"
    assert trust.get("marker") == "the-one-we-want"
    assert trust.get("n_matches") == 97  # reconciles against coverage.scored, not 161
    assert trust.get("window_start") == "2026-06-11"  # not 2022-11-20


def test_trust_does_not_fall_back_to_the_wc2022_fold(monkeypatch) -> None:
    """A WC2022 fold present in the same summary is never selected — not even when
    it is the only World Cup fold left."""
    from golavo_core import evaluation

    monkeypatch.setattr(
        evaluation,
        "evaluate",
        lambda pack_dir: {"folds": [_fold("WC2022", "FIFA World Cup", n_matches=64)]},
    )

    trust = server_retrospective._trust(Path("/unused"))

    assert trust["status"] == "unavailable"
    assert trust["cause"] == "fold_absent"
    assert "WC2026" in trust["reason"]


def test_trust_is_typed_unavailable_when_evaluate_raises(monkeypatch) -> None:
    """_evaluate_folds raises when a fold's window has no completed rows — exactly
    the pre-tournament state. An unguarded call 500s the request the typed
    envelope was built to answer."""
    from golavo_core import evaluation

    def boom(pack_dir):
        raise ValueError("WC2026 has no rows in the pinned snapshot")

    monkeypatch.setattr(evaluation, "evaluate", boom)

    trust = server_retrospective._trust(Path("/unused"))

    assert trust["status"] == "unavailable"
    assert trust["cause"] == "evaluation_failed"
    assert "no rows in the pinned snapshot" in trust["reason"]


def test_trust_is_typed_unavailable_when_no_pack_resolves() -> None:
    trust = server_retrospective._trust(None)

    assert trust["status"] == "unavailable"
    assert trust["cause"] == "no_pack"
    assert trust["reason"]


def test_the_three_trust_failures_stay_distinguishable(monkeypatch) -> None:
    """No pack, evaluate failed, and no WC2026 fold are different states. Collapsing
    them into one null tells a reader "no skill measured" without saying why."""
    from golavo_core import evaluation

    causes = {server_retrospective._trust(None)["cause"]}

    monkeypatch.setattr(evaluation, "evaluate", lambda pack_dir: {"folds": []})
    causes.add(server_retrospective._trust(Path("/unused"))["cause"])

    def boom(pack_dir):
        raise RuntimeError("pack is corrupt")

    monkeypatch.setattr(evaluation, "evaluate", boom)
    causes.add(server_retrospective._trust(Path("/unused"))["cause"])

    assert causes == {"no_pack", "evaluation_failed", "fold_absent"}


# --- typed unavailable envelope --------------------------------------------


def test_unavailable_story_returns_a_typed_envelope_even_when_trust_blows_up(
    monkeypatch,
) -> None:
    """The production pre-tournament path: the story layer raises, and evaluate()
    raises for the very same reason (an empty WC2026 window). The typed envelope
    must actually be reachable — an unguarded trust layer 500s here instead."""
    from golavo_core import evaluation
    from golavo_core.retrospective import RetrospectiveUnavailable

    def story(frame, progress, is_cancelled):
        raise RetrospectiveUnavailable(
            "This snapshot has no completed 2026 World Cup matches to look back on."
        )

    def evaluate(pack_dir):
        raise ValueError("WC2026 has no rows in the pinned snapshot")

    monkeypatch.setattr(server_retrospective, "_story", story)
    monkeypatch.setattr(evaluation, "evaluate", evaluate)
    monkeypatch.setattr(
        server_retrospective.seal, "resolve_pack_dir", lambda *a: Path("/gen/packs/internationals")
    )
    monkeypatch.setattr(
        server_retrospective, "_pack_identity", lambda p: ("sp_deadbeef@" + "c" * 64, "c" * 64)
    )
    _FakeIndex().install(monkeypatch)

    result = server_retrospective.build()

    assert result["status"] == "unavailable"
    assert "no completed 2026 World Cup matches" in result["reason"]
    assert result["trust"]["status"] == "unavailable"
    assert result["trust"]["cause"] == "evaluation_failed"
    assert result["provenance"]["pack"] == "sp_deadbeef@" + "c" * 64
    _contract_validator().validate(result)


def test_unavailable_envelope_takes_its_version_and_label_from_core() -> None:
    """A core bump moves core and the schema together; a hardcoded copy here would
    silently keep emitting the old version."""
    from golavo_core.retrospective import RETROSPECTIVE_LABEL, RETROSPECTIVE_SCHEMA_VERSION

    envelope = server_retrospective._unavailable_story("nothing to look back on")

    assert envelope["schema_version"] == RETROSPECTIVE_SCHEMA_VERSION
    assert envelope["label"] == RETROSPECTIVE_LABEL


# --- L1 cache --------------------------------------------------------------


def test_a_second_build_on_the_same_generation_is_served_from_the_memo(monkeypatch) -> None:
    calls = _stub_layers(monkeypatch)
    monkeypatch.setattr(server_retrospective.seal, "resolve_pack_dir", lambda *a: Path("/p"))
    monkeypatch.setattr(
        server_retrospective, "_pack_identity", lambda p: ("sp_a@" + "a" * 64, "a" * 64)
    )
    _FakeIndex().install(monkeypatch)

    first = server_retrospective.build()
    second = server_retrospective.build()

    assert first is second
    assert calls["story"] == 1


def test_the_key_self_invalidates_on_an_index_fingerprint_change(monkeypatch) -> None:
    calls = _stub_layers(monkeypatch)
    monkeypatch.setattr(server_retrospective.seal, "resolve_pack_dir", lambda *a: Path("/p"))
    monkeypatch.setattr(
        server_retrospective, "_pack_identity", lambda p: ("sp_a@" + "a" * 64, "a" * 64)
    )
    index = _FakeIndex().install(monkeypatch)

    server_retrospective.build()
    index.fingerprint = "fp-2"
    server_retrospective.build()

    assert calls["story"] == 2


def test_the_key_self_invalidates_on_an_epoch_change(monkeypatch) -> None:
    """The fingerprint can survive a repoint (a bundled-index fallback keeps the
    same bytes); the epoch is what always moves."""
    calls = _stub_layers(monkeypatch)
    monkeypatch.setattr(server_retrospective.seal, "resolve_pack_dir", lambda *a: Path("/p"))
    monkeypatch.setattr(
        server_retrospective, "_pack_identity", lambda p: ("sp_a@" + "a" * 64, "a" * 64)
    )
    index = _FakeIndex().install(monkeypatch)

    server_retrospective.build()
    index.epoch = 2
    server_retrospective.build()

    assert calls["story"] == 2


def test_the_key_self_invalidates_on_a_pack_change_under_an_unchanged_index(
    monkeypatch,
) -> None:
    """Both generations' packs are named "internationals" and the index has not
    moved. Only the pack's digest can tell these two apart — a name-keyed memo
    serves the first generation's trust layer for the second's pack."""
    calls = _stub_layers(monkeypatch)
    packs = [Path("/gen-7/packs/internationals"), Path("/gen-8/packs/internationals")]
    stamps = {packs[0]: "sp_a@" + "a" * 64, packs[1]: "sp_b@" + "b" * 64}
    active = {"pack": packs[0]}

    monkeypatch.setattr(server_retrospective.seal, "resolve_pack_dir", lambda *a: active["pack"])
    monkeypatch.setattr(
        server_retrospective, "_pack_identity", lambda p: (stamps[p], stamps[p][-64:])
    )
    _FakeIndex().install(monkeypatch)

    first = server_retrospective.build()
    active["pack"] = packs[1]
    second = server_retrospective.build()

    assert calls["story"] == 2
    assert first["provenance"]["pack"] != second["provenance"]["pack"]


def test_the_memo_is_bounded(monkeypatch) -> None:
    """Each entry costs minutes to build, but an unbounded memo pins every retired
    generation's frame-derived work in memory."""
    _stub_layers(monkeypatch)
    monkeypatch.setattr(server_retrospective.seal, "resolve_pack_dir", lambda *a: Path("/p"))
    monkeypatch.setattr(
        server_retrospective, "_pack_identity", lambda p: ("sp_a@" + "a" * 64, "a" * 64)
    )
    index = _FakeIndex().install(monkeypatch)

    for generation in range(server_retrospective._CACHE_MAX + 3):
        index.fingerprint = f"fp-{generation}"
        server_retrospective.build()

    assert len(server_retrospective._CACHE) == server_retrospective._CACHE_MAX


def test_a_stale_cache_hit_is_never_served(monkeypatch) -> None:
    """An entry keyed to a generation that is no longer current is skipped, not
    returned — build() retries against the new generation."""
    calls = _stub_layers(monkeypatch)
    monkeypatch.setattr(server_retrospective.seal, "resolve_pack_dir", lambda *a: Path("/p"))
    monkeypatch.setattr(
        server_retrospective, "_pack_identity", lambda p: ("sp_a@" + "a" * 64, "a" * 64)
    )
    index = _FakeIndex().install(monkeypatch)

    server_retrospective.build()
    assert calls["story"] == 1

    # Hand-plant the retired generation's key so build() hits it while the module
    # globals have already moved on: the memo must lose to the epoch check.
    stale_key = ("fp-1", 1, "sp_a@" + "a" * 64)
    server_retrospective._CACHE[stale_key] = {"stale": True}
    index.epoch = 2

    def snapshot() -> matches.IndexSnapshot:
        # An index_snapshot() racing the repoint hands back the retired epoch.
        return matches.IndexSnapshot(frame=object(), fingerprint="fp-1", epoch=1)

    monkeypatch.setattr(matches, "index_snapshot", snapshot)

    result = server_retrospective.build()

    assert result != {"stale": True}
    assert result["status"] == "unavailable"
    assert "retry" in result["reason"]


# --- stale-generation retry ------------------------------------------------


def test_build_retries_rather_than_returning_stale_generation_work(monkeypatch) -> None:
    """A repoint during the story layer's ~5-minute compute must not hand back work
    computed on a retired index generation."""
    calls = _stub_layers(monkeypatch)
    monkeypatch.setattr(server_retrospective.seal, "resolve_pack_dir", lambda *a: Path("/p"))
    monkeypatch.setattr(
        server_retrospective, "_pack_identity", lambda p: ("sp_a@" + "a" * 64, "a" * 64)
    )
    index = _FakeIndex().install(monkeypatch)

    # The first publish is refused (the index moved mid-compute); the retry lands.
    index.publishes_are_current = False

    def apply_if_snapshot_current(snapshot, operation) -> bool:
        if not index.publishes_are_current:
            index.publishes_are_current = True
            return False
        operation()
        return True

    monkeypatch.setattr(matches, "apply_if_snapshot_current", apply_if_snapshot_current)

    result = server_retrospective.build()

    assert calls["story"] == 2
    assert result["status"] == "available"


def test_exhausted_retries_return_a_typed_paused_envelope(monkeypatch) -> None:
    """A pathological repoint loop fails closed to a typed "retry" envelope, never
    to silently-retired work."""
    calls = _stub_layers(monkeypatch)
    monkeypatch.setattr(server_retrospective.seal, "resolve_pack_dir", lambda *a: Path("/p"))
    monkeypatch.setattr(
        server_retrospective, "_pack_identity", lambda p: ("sp_a@" + "a" * 64, "a" * 64)
    )
    index = _FakeIndex().install(monkeypatch)
    index.publishes_are_current = False

    result = server_retrospective.build()

    assert calls["story"] == server_retrospective._MAX_ATTEMPTS
    assert result["status"] == "unavailable"
    assert result["reason"] == (
        "retrospective paused because the verified match index changed; retry"
    )
    assert server_retrospective._CACHE == {}
    # No settled snapshot or pack survives, so none is stamped — a stale stamp
    # would be worse than none.
    assert "provenance" not in result
    assert "trust" not in result
    _contract_validator().validate(result)


# --- HTTP routes -------------------------------------------------------------


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
    # A minimal but conformant "available" envelope — the contract requires
    # "exposure" and at least one row once status is "available", which the
    # task brief's stub (written before Task 3's schema tightening) predates.
    row = {
        "match_id": "m1",
        "kickoff_utc": "2026-06-11T20:00:00Z",
        "kickoff_precision": "exact",
        "information_cutoff_utc": "2026-06-11T19:59:59Z",
        "home_team": "Home",
        "away_team": "Away",
        "home_score": 1,
        "away_score": 0,
        "outcome": "home",
        "families": {
            "dixon_coles": {"probs": {"home": 0.5, "draw": 0.3, "away": 0.2}, "log_loss": 0.69}
        },
        "log_loss": 0.69,
        "training_same_day_proxy_rows": 0,
    }
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
        "coverage": {"status": "complete", "scored": 1, "pending": 0, "note": "n"},
        "exposure": {"rows_with_same_day_proxies": 0, "note": "n"},
        "biggest_surprises": [row],
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


def test_retrospective_route_runs_async_and_a_mid_flight_poll_sees_running(
    monkeypatch,
) -> None:
    """A job_id request returns 202 immediately, and the background task drives
    the same job through to a stamped "done" result — never the AI job route.

    TestClient drains background tasks before ``post()`` returns, so asserting
    ``state == "done"`` only *after* the call returns cannot tell an async
    implementation apart from a synchronous one that also returns 202. This
    test blocks the stub mid-flight (BackgroundTasks runs a sync callable via
    ``run_in_threadpool``, off the event loop) and polls from another thread
    while ``build`` is still running, so "running" is genuinely observed.
    """
    import threading

    from fastapi.testclient import TestClient
    from golavo_server import jobs
    from golavo_server import main as server_main

    stub = {
        "schema_version": "0.1.0",
        "status": "available",
        "label": "n",
        "tournament_id": "worldcup-2026",
        "tournament_name": "2026 FIFA World Cup",
        "biggest_surprises": [],
    }
    release = threading.Event()
    entered = threading.Event()

    def blocking_build(**_: object) -> dict[str, Any]:
        entered.set()
        assert release.wait(timeout=5), "test deadlocked waiting for release"
        return stub

    monkeypatch.setattr(server_retrospective, "build", blocking_build)
    job_id = "rt-job-0001"
    jobs.store()._jobs.pop(job_id, None)

    client = TestClient(server_main.app)
    responses: dict[str, Any] = {}

    def _post() -> None:
        responses["post"] = client.post(
            "/api/v1/tournaments/worldcup-2026/retrospective", json={"job_id": job_id}
        )

    thread = threading.Thread(target=_post)
    thread.start()
    try:
        assert entered.wait(timeout=5), "background task never started"
        mid_flight = client.get(
            f"/api/v1/tournaments/worldcup-2026/retrospective/jobs/{job_id}"
        ).json()
    finally:
        release.set()
        thread.join(timeout=5)

    assert responses["post"].status_code == 202
    assert responses["post"].json() == {"job_id": job_id, "state": "running"}
    assert mid_flight["state"] == "running"

    polled = client.get(
        f"/api/v1/tournaments/worldcup-2026/retrospective/jobs/{job_id}"
    ).json()
    assert polled["job_id"] == job_id
    assert polled["state"] == "done"
    assert polled["result"] == stub
    jobs.store()._jobs.pop(job_id, None)


def test_retrospective_job_seeds_its_own_stage_before_any_progress_tick(
    monkeypatch,
) -> None:
    """A client polling right after the 202, before the worker's first progress
    tick, must see this lane's own stage — never the AI lane's default
    ("assembling_evidence", jobs.Job's dataclass default). Blocks the build stub
    before it calls progress at all, so the poll below observes only the route's
    post-start() seeding, not a tick."""
    import threading

    from fastapi.testclient import TestClient
    from golavo_server import jobs
    from golavo_server import main as server_main

    release = threading.Event()
    entered = threading.Event()

    def blocking_build(**_: object) -> dict[str, Any]:
        entered.set()
        assert release.wait(timeout=5), "test deadlocked waiting for release"
        return {"status": "available", "biggest_surprises": []}

    monkeypatch.setattr(server_retrospective, "build", blocking_build)
    job_id = "rt-seedtest1"
    jobs.store()._jobs.pop(job_id, None)

    client = TestClient(server_main.app)
    thread = threading.Thread(
        target=lambda: client.post(
            "/api/v1/tournaments/worldcup-2026/retrospective", json={"job_id": job_id}
        )
    )
    thread.start()
    try:
        assert entered.wait(timeout=5), "background task never started"
        polled = client.get(
            f"/api/v1/tournaments/worldcup-2026/retrospective/jobs/{job_id}"
        ).json()
    finally:
        release.set()
        thread.join(timeout=5)
        jobs.store()._jobs.pop(job_id, None)

    assert polled["stage"] == "replaying"
    assert polled["stage"] not in jobs.STAGES  # never the AI lane's stage vocabulary
    assert polled["detail"]  # honest, non-null — never the empty default
    assert polled["counts"] == {"completed": 0, "total": 0}  # never {}


def test_retrospective_progress_callback_drives_the_lane_stage_detail_counts(
    monkeypatch,
) -> None:
    """``_progress`` is what a live progress bar renders from and had zero direct
    coverage — partly why the AI-lane leak in the pre-tick window (see the seeding
    test above) shipped unnoticed. Drive it for real and check the exact payload
    shape a client would render."""
    import threading

    from fastapi.testclient import TestClient
    from golavo_server import jobs
    from golavo_server import main as server_main

    release = threading.Event()
    reached = threading.Event()

    def build_with_progress(*, progress=None, is_cancelled=None):
        progress(3, 9)
        reached.set()
        assert release.wait(timeout=5), "test deadlocked waiting for release"
        return {"status": "available", "biggest_surprises": []}

    monkeypatch.setattr(server_retrospective, "build", build_with_progress)
    job_id = "rt-progress01"
    jobs.store()._jobs.pop(job_id, None)

    client = TestClient(server_main.app)
    thread = threading.Thread(
        target=lambda: client.post(
            "/api/v1/tournaments/worldcup-2026/retrospective", json={"job_id": job_id}
        )
    )
    thread.start()
    try:
        assert reached.wait(timeout=5), "progress callback was never reached"
        polled = client.get(
            f"/api/v1/tournaments/worldcup-2026/retrospective/jobs/{job_id}"
        ).json()
    finally:
        release.set()
        thread.join(timeout=5)
        jobs.store()._jobs.pop(job_id, None)

    assert polled["stage"] == "replaying"
    assert polled["detail"] == "Backtesting match 3 of 9"
    assert polled["counts"] == {"completed": 3, "total": 9}


def test_retrospective_route_rejects_a_conflicting_job_id(monkeypatch) -> None:
    """Reusing an id already active is a 409, not a silently dropped second run."""
    from fastapi.testclient import TestClient
    from golavo_server import jobs
    from golavo_server import main as server_main

    monkeypatch.setattr(server_retrospective, "build", lambda **_: {"status": "available"})
    job_id = "rt-conflict1"
    jobs.store()._jobs.pop(job_id, None)
    jobs.store().start(job_id)

    client = TestClient(server_main.app)
    response = client.post(
        "/api/v1/tournaments/worldcup-2026/retrospective", json={"job_id": job_id}
    )

    assert response.status_code == 409
    jobs.store()._jobs.pop(job_id, None)


def test_retrospective_route_maps_match_index_unavailable_to_503(monkeypatch) -> None:
    from fastapi.testclient import TestClient
    from golavo_server import main as server_main

    def boom(**_: object) -> dict[str, Any]:
        raise matches.MatchIndexUnavailable("no index on disk")

    monkeypatch.setattr(server_retrospective, "build", boom)

    response = TestClient(server_main.app).post(
        "/api/v1/tournaments/worldcup-2026/retrospective", json={}
    )

    assert response.status_code == 503


# --- cancellation ------------------------------------------------------------


def test_retrospective_cancel_rejects_a_malformed_job_id() -> None:
    from fastapi.testclient import TestClient
    from golavo_server import main as server_main

    response = TestClient(server_main.app).post(
        "/api/v1/tournaments/worldcup-2026/retrospective/jobs/bad/cancel"
    )

    assert response.status_code == 400


def test_retrospective_cancel_stops_a_running_job_through_its_own_lane() -> None:
    """The lane's own cancel door — a 6-minute compute the user cannot stop is a
    real usability problem, and the only previously-reachable cancel route was
    the AI-named one this lane must not depend on."""
    from fastapi.testclient import TestClient
    from golavo_server import jobs
    from golavo_server import main as server_main

    job_id = "rt-cancel0001"
    jobs.store()._jobs.pop(job_id, None)
    jobs.store().start(job_id)

    client = TestClient(server_main.app)
    response = client.post(
        f"/api/v1/tournaments/worldcup-2026/retrospective/jobs/{job_id}/cancel"
    )

    assert response.status_code == 200
    assert response.json() == {"job_id": job_id, "cancelled": True}
    assert jobs.store().get(job_id).state == "cancelled"
    jobs.store()._jobs.pop(job_id, None)


def test_a_late_fail_never_overwrites_a_cancelled_retrospective_job() -> None:
    """The report's headline decision — cancellation wins over a worker that keeps
    running and eventually calls fail() — had zero coverage. RetrospectiveCancelled
    (raised when the worker notices ``is_cancelled()``) is caught by the same
    broad except in ``_run`` that calls ``fail()`` on any exception, so this is the
    exact path a real cancel-then-still-fails run takes."""
    from golavo_server import jobs

    job_id = "rt-cancelfail1"
    jobs.store()._jobs.pop(job_id, None)
    jobs.store().start(job_id)

    assert jobs.store().cancel(job_id) is True
    # The worker's except-path still runs to completion and calls fail(); it must
    # be refused, not relabel the job "failed".
    assert jobs.store().fail(job_id, "boom") is False

    job = jobs.store().get(job_id)
    payload = job.to_dict()
    assert job.state == "cancelled"
    assert payload["state"] == "cancelled"
    assert "error" not in payload
    jobs.store()._jobs.pop(job_id, None)
