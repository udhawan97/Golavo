from __future__ import annotations

from pathlib import Path

from golavo_core.ingest.openfootball import load_openfootball_table
from golavo_server import refresh, refresh_sources

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_domestic_refresh_replaces_current_schedule_and_keeps_history(tmp_path: Path) -> None:
    base = REPO_ROOT / "packs/openfootball-eng-pl"
    source_id = refresh_sources.ENGLAND
    ref = "7" * 40
    relative = "2026-27/1-premierleague.txt"
    raw = tmp_path / "raw" / source_id / ref
    (raw / "2026-27").mkdir(parents=True)
    (raw / relative).write_bytes((base / "2026-27.en.1.txt").read_bytes())
    (raw / "LICENSE.md").write_text(
        "CC0 1.0 Universal (CC0 1.0) Public Domain Dedication\n", encoding="utf-8"
    )

    pack, capability = refresh.build_domestic_runtime_pack(
        base,
        tmp_path / "raw",
        source_id=source_id,
        upstream_ref=ref,
        upstream_committed_at="2026-07-21T00:00:00Z",
        season="2026-27",
        relative_path=relative,
        retrieved_at_utc="2026-07-21T01:00:00Z",
        output_dir=tmp_path / "pack",
        as_of_utc="2026-07-21T01:00:00Z",
    )

    frame = load_openfootball_table(pack)
    assert frame["date"].dt.year.min() == 2010
    assert len(frame.loc[frame["date"] >= "2026-07-01"]) == 380
    assert capability["capability"] == "complete"
    assert capability["source_id"] == source_id
    assert not (pack / "manifest.json.sig").exists()
