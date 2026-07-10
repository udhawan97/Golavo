# packs

Golavo ships data as **versioned, signed packs** on GitHub Releases. Each pack is
a semver'd tarball with a license manifest inside, minisign-signed and
hash-verified before the app loads it.

| Pack | Sources | License | Status |
|---|---|---|---|
| `core-cc0` | openfootball, martj42, Wikidata | CC0 (public domain) | primary |
| `overlay-odbl` | OpenLigaDB | ODbL 1.0 | **isolated** optional overlay |

## Isolation is mandatory

`core-cc0` and `overlay-odbl` are **never merged on disk** and never joined into
the same database. ODbL's share-alike would otherwise attach to the entire
combined dataset. `scripts/check_license_isolation.sh` enforces this in CI.

BYOK data (football-data.org, API-Football) is **never** packaged — it stays in
the user's private local session and is purged when the key is removed.
