# LICENSES

Full legal texts for every license Golavo carries, matched to entries in
[`data/sources/registry.json`](../data/sources/registry.json) by SPDX id.

| SPDX id | Applies to | Present |
|---|---|---|
| `Apache-2.0` | Golavo's own source code (see the root [`LICENSE`](../LICENSE)) | ✅ `Apache-2.0.txt` |
| `CC0-1.0` | Bundled data packs: martj42 internationals, the five openfootball leagues | ✅ `CC0-1.0.txt` |

Texts for the share-alike and research licenses named in the registry
(`CC-BY-4.0`, `ODbL-1.0`, `CC-BY-SA-4.0`) are vendored here **when the first pack
that carries them ships** — they are not committed speculatively, so this
directory always reflects what the repository actually redistributes.

`THIRD_PARTY_NOTICES.md` at the repository root is generated from the source
registry by `scripts/gen_third_party_notices.py`.
