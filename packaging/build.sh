#!/usr/bin/env bash
# Golavo desktop build (Phase 4). Freezes the PyInstaller sidecar, builds the UI,
# then produces the Tauri bundle for one target triple. Invoked by the release
# workflow and runnable locally.
#
#   packaging/build.sh <target-triple>     e.g. aarch64-apple-darwin
#                                               x86_64-pc-windows-msvc
#
# Distribution signing & the updater are GATED on secrets. Without an Apple
# certificate, macOS receives only a local ad-hoc bundle seal (Gatekeeper will
# still warn); without the updater key, no update artifacts are made:
#   TAURI_SIGNING_PRIVATE_KEY (+ _PASSWORD)  -> sign + emit updater artifacts
#   APPLE_CERTIFICATE / APPLE_SIGNING_IDENTITY / APPLE_ID / APPLE_PASSWORD /
#   APPLE_TEAM_ID                            -> macOS Developer ID + notarization
# None of these are fabricated here; Tauri simply skips the step when unset.
set -euo pipefail

TARGET="${1:-}"
if [ -z "$TARGET" ]; then
  echo "usage: build.sh <target-triple>   e.g. aarch64-apple-darwin" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Pin every layer of the packaged app to the exact checkout being built. Cargo
# can otherwise reuse a prior build-script result after a same-branch commit
# because .git/HEAD still contains the same symbolic ref. The environment value
# is tracked by build.rs, forwarded to the sidecar, exposed by /meta, and stored
# in newly sealed forecast artifacts.
CHECKOUT_SOURCE_SHA="$(git rev-parse HEAD)"
if [[ -n "${GOLAVO_SOURCE_SHA:-}" && "$GOLAVO_SOURCE_SHA" != "$CHECKOUT_SOURCE_SHA" ]]; then
  echo "GOLAVO_SOURCE_SHA does not match the checkout being packaged" >&2
  exit 2
fi
export GOLAVO_SOURCE_SHA="$CHECKOUT_SOURCE_SHA"

# Always freeze the checkout being built. Developer machines can have editable
# installs pointing at an older worktree; without an explicit front-of-path
# override PyInstaller's collect_submodules step can silently package that stale
# golavo_core/golavo_server instead of this repository.
export PYTHONPATH="$REPO_ROOT/server:$REPO_ROOT/core${PYTHONPATH:+:$PYTHONPATH}"

# Fail before freezing if local correction state can reach any authoritative,
# model, data-pack, or redistributable sink. The spec ships contracts/code only.
python scripts/validate_correction_isolation.py
python scripts/validate_research_isolation.py

# macOS Developer ID signing is optional and gated on APPLE_CERTIFICATE. In CI
# the env is populated from secrets, so an ABSENT secret arrives as an EMPTY
# string — and Tauri, seeing APPLE_CERTIFICATE "set", still runs `security
# import` on the empty cert and fails the whole build ("failed to import
# keychain certificate"). Unset the entire Apple group when the cert is empty so
# Tauri skips Developer ID signing cleanly. For macOS targets we then select a
# separate ad-hoc overlay so the bundle is internally sealed while remaining
# honestly undistributed/unnotarized (the updater signature is independent).
ADHOC_MACOS=0
if [ -z "${APPLE_CERTIFICATE:-}" ]; then
  unset APPLE_CERTIFICATE APPLE_CERTIFICATE_PASSWORD APPLE_SIGNING_IDENTITY \
    APPLE_ID APPLE_PASSWORD APPLE_TEAM_ID 2>/dev/null || true
  case "$TARGET" in
    *apple-darwin*) ADHOC_MACOS=1 ;;
  esac
fi

EXT=""
case "$TARGET" in
  *windows*) EXT=".exe" ;;
esac

echo "==> [1/4] Freezing sidecar (PyInstaller) for ${TARGET}"
python -m PyInstaller --clean --noconfirm packaging/golavo-sidecar.spec \
  --distpath packaging/out --workpath packaging/build
SIDECAR_SRC="packaging/out/golavo-sidecar${EXT}"
SIDECAR_DST="desktop/src-tauri/binaries/golavo-sidecar-${TARGET}${EXT}"
mkdir -p desktop/src-tauri/binaries
cp "$SIDECAR_SRC" "$SIDECAR_DST"
chmod +x "$SIDECAR_DST" || true
echo "    sidecar -> ${SIDECAR_DST}"
# The frozen executable is an internal app resource, not a standalone release
# download. Keep only the target-named copy staged for Tauri so upload-artifact
# cannot leak the raw 80+ MB sidecar into the public release.
rm -f "$SIDECAR_SRC"

echo "==> [2/4] Building UI"
npm --prefix ui ci
npm --prefix ui run build

echo "==> [3/4] Building Tauri bundle"
npm --prefix desktop ci
BUILD_ARGS=(build --target "$TARGET")
if [ "$ADHOC_MACOS" -eq 1 ]; then
  # Rust's linker adds only an executable-level ad-hoc signature. An unsigned
  # .app needs an outer ad-hoc signature too so Info.plist, resources and the
  # sidecar are sealed and `codesign --verify --deep --strict` succeeds. Tauri
  # applies this overlay before it creates the DMG. Real Developer ID builds do
  # not use the overlay and continue to take their identity from CI secrets.
  BUILD_ARGS+=(--config src-tauri/tauri.adhoc.conf.json)
fi
if [ -n "${TAURI_SIGNING_PRIVATE_KEY:-}" ]; then
  echo "    updater signing key present -> building signed updater artifacts"
  BUILD_ARGS+=(--features updater --config src-tauri/tauri.updater.conf.json)
  # The local E2E harness (scripts/test-updater-local.sh) stacks one more
  # overlay to point the endpoint at 127.0.0.1. Only meaningful with the
  # updater feature, so it lives inside this branch.
  if [ -n "${GOLAVO_UPDATER_ENDPOINT_OVERLAY:-}" ]; then
    echo "    endpoint overlay -> ${GOLAVO_UPDATER_ENDPOINT_OVERLAY}"
    BUILD_ARGS+=(--config "$GOLAVO_UPDATER_ENDPOINT_OVERLAY")
  fi
else
  echo "    no updater signing key -> no updater artifacts"
fi
( cd desktop && npx tauri "${BUILD_ARGS[@]}" )

echo "==> [4/4] Collecting artifacts + checksums"
OUT="packaging/out"
# Tauri may namespace the bundle dir by target; handle both layouts.
BUNDLE_DIR="desktop/src-tauri/target/${TARGET}/release/bundle"
[ -d "$BUNDLE_DIR" ] || BUNDLE_DIR="desktop/src-tauri/target/release/bundle"
mkdir -p "$OUT"
# Copy only the installer/update artifacts (NOT the raw ~73MB sidecar that
# PyInstaller left in $OUT — it is already staged under desktop/.../binaries/).
COLLECTED=()
while IFS= read -r -d '' artifact; do
  cp "$artifact" "$OUT/"
  COLLECTED+=("$(basename "$artifact")")
done < <(find "$BUNDLE_DIR" -type f \
  \( -name '*.dmg' -o -name '*.app.tar.gz' -o -name '*.msi' -o -name '*.exe' \
     -o -name '*.sig' -o -name '*.AppImage' -o -name '*.deb' -o -name '*.nsis.zip' \) \
  ! -name 'rw.*' -print0 2>/dev/null)

# Checksum exactly those artifact types, deterministically (sorted), bash-safe.
# Named per-target: both platform legs upload into one merged dist in CI, and
# two files both called SHA256SUMS would silently clobber each other there
# (the publish job generates the release-wide SHA256SUMS.txt itself).
SUMS_FILE="SHA256SUMS-${TARGET}"
SUM_TOOL="sha256sum"; command -v sha256sum >/dev/null 2>&1 || SUM_TOOL="shasum -a 256"
(
  cd "$OUT"
  : > "$SUMS_FILE"
  for f in $(printf '%s\n' "${COLLECTED[@]}" | sort -u); do
    [ -n "$f" ] || continue
    $SUM_TOOL "$f" >> "$SUMS_FILE"
  done
)
echo "==> Done. Artifacts in ${OUT}:"
ls -la "$OUT"
echo "==> ${SUMS_FILE}:"; cat "$OUT/${SUMS_FILE}"
