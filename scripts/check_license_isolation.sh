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

if [ "$fail" -eq 0 ]; then
  echo "license isolation: OK (no ODbL contamination of the CC0 core)."
fi
exit "$fail"
