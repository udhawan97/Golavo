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


def _contract_validator() -> Draft202012Validator:
    root = Path(__file__).resolve().parents[2]
    schema = json.loads(
        (root / "docs" / "contracts" / "tournament_retrospective.schema.json").read_text(
            encoding="utf-8"
        )
    )
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _story_envelope() -> dict[str, Any]:
    """A minimal available story, as the core module shapes it."""
    return {
        "schema_version": "0.1.0",
        "status": "available",
        "coverage": {"status": "complete", "scored": 1, "pending": 0, "note": "n"},
        "matches": [],
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
    monkeypatch.setattr(server_retrospective, "_pack_stamp", lambda p: f"stamp::{p}")
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


def test_pack_stamp_identifies_the_snapshot_not_the_directory_name(monkeypatch) -> None:
    """Every refreshed generation's pack is named "internationals", so the name is
    inert. Two different generations must stamp differently or the decoupling this
    stamp exists to expose stays invisible."""
    from golavo_core import ingest

    descriptors = {
        Path("/gen-7/packs/internationals"): {"snapshot_id": "sp_aaaaaaaaaaaa", "sha256": "a" * 64},
        Path("/gen-8/packs/internationals"): {"snapshot_id": "sp_bbbbbbbbbbbb", "sha256": "b" * 64},
    }
    monkeypatch.setattr(ingest, "snapshot_descriptor", lambda p: descriptors[p])

    stamps = {server_retrospective._pack_stamp(p) for p in descriptors}

    assert len(stamps) == 2
    assert {p.name for p in descriptors} == {"internationals"}  # the names are identical
    assert stamps == {f"sp_aaaaaaaaaaaa@{'a' * 64}", f"sp_bbbbbbbbbbbb@{'b' * 64}"}


def test_pack_stamp_never_raises_on_a_corrupt_pack(monkeypatch) -> None:
    """snapshot_descriptor validates the pack off disk; provenance degrading to a
    stated reason is honest, a 500 is not."""
    from golavo_core import ingest

    def boom(pack_dir):
        raise ValueError("manifest.json is not valid JSON")

    monkeypatch.setattr(ingest, "snapshot_descriptor", boom)

    stamp = server_retrospective._pack_stamp(Path("/broken"))

    assert stamp.startswith("unidentified: ")
    assert "manifest.json" in stamp
    assert server_retrospective._pack_stamp(None).startswith("unresolved: ")


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
    monkeypatch.setattr(server_retrospective, "_pack_stamp", lambda p: "sp_deadbeef@" + "c" * 64)
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
    monkeypatch.setattr(server_retrospective, "_pack_stamp", lambda p: "sp_a@" + "a" * 64)
    _FakeIndex().install(monkeypatch)

    first = server_retrospective.build()
    second = server_retrospective.build()

    assert first is second
    assert calls["story"] == 1


def test_the_key_self_invalidates_on_an_index_fingerprint_change(monkeypatch) -> None:
    calls = _stub_layers(monkeypatch)
    monkeypatch.setattr(server_retrospective.seal, "resolve_pack_dir", lambda *a: Path("/p"))
    monkeypatch.setattr(server_retrospective, "_pack_stamp", lambda p: "sp_a@" + "a" * 64)
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
    monkeypatch.setattr(server_retrospective, "_pack_stamp", lambda p: "sp_a@" + "a" * 64)
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
    monkeypatch.setattr(server_retrospective, "_pack_stamp", lambda p: stamps[p])
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
    monkeypatch.setattr(server_retrospective, "_pack_stamp", lambda p: "sp_a@" + "a" * 64)
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
    monkeypatch.setattr(server_retrospective, "_pack_stamp", lambda p: "sp_a@" + "a" * 64)
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
    monkeypatch.setattr(server_retrospective, "_pack_stamp", lambda p: "sp_a@" + "a" * 64)
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
    monkeypatch.setattr(server_retrospective, "_pack_stamp", lambda p: "sp_a@" + "a" * 64)
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
