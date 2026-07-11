#!/usr/bin/env bash
# Golavo desktop build (Phase 4). Freezes the PyInstaller sidecar, builds the UI,
# then produces the Tauri bundle for one target triple. Invoked by the release
# workflow and runnable locally.
#
#   packaging/build.sh <target-triple>     e.g. aarch64-apple-darwin
#                                               x86_64-pc-windows-msvc
#
# Signing & the updater are GATED on secrets — absent, an UNSIGNED bundle is
# produced (Gatekeeper/SmartScreen will warn) and no update artifacts are made:
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

echo "==> [2/4] Building UI"
npm --prefix ui ci
npm --prefix ui run build

echo "==> [3/4] Building Tauri bundle"
npm --prefix desktop ci
BUILD_ARGS=(build --target "$TARGET")
if [ -n "${TAURI_SIGNING_PRIVATE_KEY:-}" ]; then
  echo "    updater signing key present -> building signed updater artifacts"
  BUILD_ARGS+=(--features updater --config src-tauri/tauri.updater.conf.json)
else
  echo "    no updater signing key -> UNSIGNED bundle, no updater artifacts"
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
find "$BUNDLE_DIR" -type f \
  \( -name '*.dmg' -o -name '*.app.tar.gz' -o -name '*.msi' -o -name '*.exe' \
     -o -name '*.sig' -o -name '*.AppImage' -o -name '*.deb' -o -name '*.nsis.zip' \) \
  -exec cp {} "$OUT/" \; 2>/dev/null || true

# Checksum exactly those artifact types, deterministically (sorted), bash-safe.
# Named per-target: both platform legs upload into one merged dist in CI, and
# two files both called SHA256SUMS would silently clobber each other there
# (the publish job generates the release-wide SHA256SUMS.txt itself).
SUMS_FILE="SHA256SUMS-${TARGET}"
SUM_TOOL="sha256sum"; command -v sha256sum >/dev/null 2>&1 || SUM_TOOL="shasum -a 256"
(
  cd "$OUT"
  shopt -s nullglob
  files=( *.dmg *.app.tar.gz *.msi *.exe *.sig *.AppImage *.deb *.nsis.zip )
  : > "$SUMS_FILE"
  for f in $(printf '%s\n' "${files[@]}" | sort -u); do
    $SUM_TOOL "$f" >> "$SUMS_FILE"
  done
)
echo "==> Done. Artifacts in ${OUT}:"
ls -la "$OUT"
echo "==> ${SUMS_FILE}:"; cat "$OUT/${SUMS_FILE}"
