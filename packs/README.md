# packs

Golavo ships data as **versioned, signed packs** on GitHub Releases. Each pack is
a semver'd tarball with a license manifest inside, minisign-signed and
hash-verified before the app loads it.

| Pack | Sources | License | Status |
|---|---|---|---|
| `core-cc0` | openfootball, martj42, Wikidata | CC0 (public domain) | primary |
| `overlay-odbl` | OpenLigaDB | ODbL 1.0 | **isolated** optional overlay |

## Vendored sourcepacks (in this repository)

Pinned, byte-exact snapshots with per-file SHA-256 manifests, validated by
`scripts/validate_provenance.py`. One pack per competition source; the
openfootball packs share a single pinned upstream ref and are **historical
only** — see `docs/handoff/openfootball-audit.md` for each league's gate verdict.

| Directory | Coverage | License |
|---|---|---|
| `martj42-internationals/` | men's senior full internationals (Phase 0) | CC0-1.0 |
| `openfootball-eng-pl/` | English Premier League seasons 2010-11 → 2025-26 (Phase 1) | CC0-1.0 |
| `openfootball-esp-ll/` | La Liga seasons 2012-13 → 2025-26 (Phase 2) | CC0-1.0 |
| `openfootball-deu-bl/` | Bundesliga seasons 2010-11 → 2025-26 (Phase 2) | CC0-1.0 |
| `openfootball-ita-sa/` | Serie A seasons 2013-14 → 2025-26 (Phase 2) | CC0-1.0 |
| `openfootball-fra-l1/` | Ligue 1 seasons 2014-15 → 2025-26 (Phase 2) | CC0-1.0 |

Vendored season files include flagged partial captures (e.g. every league's
2025-26); the audit gate — not the pack contents — decides which seasons the
engine may treat as clean.

## Isolation is mandatory

`core-cc0` and `overlay-odbl` are **never merged on disk** and never joined into
the same database. ODbL's share-alike would otherwise attach to the entire
combined dataset. `scripts/check_license_isolation.sh` enforces this in CI.

BYOK data (football-data.org, API-Football) is **never** packaged — it stays in
the user's private local session and is purged when the key is removed.
