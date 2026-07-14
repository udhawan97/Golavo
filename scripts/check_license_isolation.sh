#!/usr/bin/env bash
# Guard: ODbL (OpenLigaDB) data and code must never be merged into the CC0 core.
# ODbL's share-alike would otherwise attach to the entire combined database.
# Keep the packs and their code paths physically apart. Run in CI.
set -euo pipefail
fail=0

# 1) The CC0 pack must not reference the ODbL source in any way.
if [ -d packs/core-cc0 ]; then
  if grep -riE 'odbl|openligadb|openleaguedb' packs/core-cc0 --exclude='*.md' >/dev/null 2>&1; then
    echo "::error::ODbL/OpenLigaDB reference found inside packs/core-cc0 — must stay isolated."
    fail=1
  fi
fi

# 2) The core modeling library must not import the ODbL overlay module.
if [ -d core ]; then
  if grep -rInE 'from[[:space:]].*overlay_odbl|import[[:space:]].*overlay_odbl' --include='*.py' core >/dev/null 2>&1; then
    echo "::error::core/ imports the ODbL overlay — forbidden."
    fail=1
  fi
fi

# 3) Fjelstul's CC-BY-SA pack is facts-only. It must never enter ingest or the
# bundled match-index builder, even as an optional code path.
if grep -rInE 'fjelstul' core/golavo_core/ingest --include='*.py' >/dev/null 2>&1; then
  echo "::error::fjelstul reference found in core ingest — CC-BY-SA pack must stay facts-only."
  fail=1
fi

# 4) The bundled match index must carry ONLY CC0 sources into the sidecar.
# Its meta records every source's license under built_from[].license; a single
# non-CC0 entry means an ODbL (or otherwise share-alike) pack would ship frozen
# inside the redistributed binary. Assert every source is CC0-1.0.
META="data/index/matches_index.meta.json"
if [ -f "$META" ]; then
  if ! python3 - "$META" <<'PY'
import json, sys
meta = json.load(open(sys.argv[1], encoding="utf-8"))
bad = [b for b in meta.get("built_from", []) if b.get("license") != "CC0-1.0"]
sys.exit(1 if bad else 0)
PY
  then
    echo "::error::match index bundles a non-CC0 source — ODbL must not ship in the sidecar"
    fail=1
  fi
fi

if [ "$fail" -eq 0 ]; then
  echo "license isolation: OK (no ODbL/CC-BY-SA contamination of the CC0 core)."
fi
exit "$fail"
