# packs

Golavo vendors data as **pinned, hash-verified packs**. Each pack carries a
license manifest with a per-file SHA-256 list, and every retained snapshot's
manifest hash is pinned in `snapshots.json`; the app re-hashes every declared file
before load. Minisign **signature** verification (authenticity) and release-tarball
distribution are **planned (ADR-0001), not yet implemented** — because the manifest
lives inside the pack, the current check catches corruption, not a forged pack.

| Pack | Sources | License | Status |
|---|---|---|---|
| `core-cc0` | openfootball, martj42, Wikidata | CC0 (public domain) | primary |
| `overlay-odbl` | OpenLigaDB | ODbL 1.0 | **isolated** optional overlay |
| `fjelstul-worldcup-f942c6b` | Fjelstul World Cup Database | CC-BY-SA-4.0 | **vendored, isolated facts-only pack** |
| `pappalardo-wyscout-research-2019` | Pappalardo/Wyscout public event corpus | CC-BY-4.0 | **bundled compact team-only research artifacts; raw events excluded** |

The Pappalardo/Wyscout pack contains seven competition-and-era summaries
(2017/18 big-five leagues, Euro 2016, World Cup 2018). Its generated artifacts
cover the published 1,941 matches and 3,251,294 events in about 100 KB. Player
identities and the 74 MB compressed raw event archive are not redistributed.

## Vendored sourcepacks (in this repository)

Pinned, byte-exact snapshots with per-file SHA-256 manifests, validated by
`scripts/validate_provenance.py`. One pack per competition source; the
openfootball packs share a single pinned upstream ref and are **historical
only** — see `docs/handoff/openfootball-audit.md` for each league's gate verdict.

| Directory | Coverage | License |
|---|---|---|
| `martj42-internationals/` | men's senior full internationals (current primary snapshot; ref `ddd7249…`) | CC0-1.0 |
| `martj42-internationals-273c731492df/` | retained older internationals snapshot (forward-loop T0; `core` file set) | CC0-1.0 |
| `openfootball-eng-pl/` | English Premier League seasons 2010-11 → 2025-26 (historical only) | CC0-1.0 |
| `openfootball-esp-ll/` | La Liga seasons 2012-13 → 2025-26 (historical only) | CC0-1.0 |
| `openfootball-deu-bl/` | Bundesliga seasons 2010-11 → 2025-26 (historical only) | CC0-1.0 |
| `openfootball-ita-sa/` | Serie A seasons 2013-14 → 2025-26 (historical only) | CC0-1.0 |
| `openfootball-fra-l1/` | Ligue 1 seasons 2014-15 → 2025-26 (historical only) | CC0-1.0 |

Vendored season files include flagged partial captures (e.g. every league's
2025-26); the audit gate — not the pack contents — decides which seasons the
engine may treat as clean.

## Snapshot retention

Snapshots are **immutable and retained**. `scripts/build_sourcepack.py --ref
<full-sha> [--files core|full]` vendors one pinned upstream ref into a new
directory (`martj42-internationals-<ref12>` by default), records the upstream
commit time (`upstream_committed_at_utc` — the data-state anchor that seals
validate against) alongside the honest retrieval time, and registers the pack
in `packs/snapshots.json`. A ref that is already registered is never
re-fetched; an existing directory or registry entry is never rewritten.
`validate_provenance.py` re-verifies every pack byte and the registry on every
CI run. The `core` file set (`results.csv`, `former_names.csv`, license) is the
minimum the match table reads and keeps retained snapshots small; `full` also
vendors goalscorers and shootouts.

## Isolation is mandatory

`core-cc0` and `overlay-odbl` are **never merged on disk** and never joined into
the same database. ODbL's share-alike would otherwise attach to the entire
combined dataset. `scripts/check_license_isolation.sh` enforces this in CI.

BYOK data (football-data.org, API-Football) is **never** packaged — it stays in
the user's private local session and is purged when the key is removed.
