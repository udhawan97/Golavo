#!/usr/bin/env bash
# Golavo desktop build (Phase 4). Builds the PyInstaller sidecar and the Tauri
# bundle for one target triple. Invoked by the release workflow once the desktop
# shell exists. Until then it is a clearly-failing placeholder.
set -euo pipefail

TARGET="${1:-}"
if [ -z "$TARGET" ]; then
  echo "usage: build.sh <target-triple>   e.g. aarch64-apple-darwin" >&2
  exit 2
fi

if [ ! -f desktop/tauri.conf.json ] && [ ! -f desktop/src-tauri/tauri.conf.json ]; then
  echo "Desktop shell not scaffolded yet (Phase 4). Nothing to build for ${TARGET}." >&2
  exit 1
fi

echo "TODO(Phase 4): build PyInstaller sidecar as golavo-sidecar-${TARGET}, then 'tauri build'."
