#!/usr/bin/env bash
# Local end-to-end exercise of the in-app updater (macOS arm64).
#
# What it does:
#   1. builds the CURRENT version with the update endpoint pointed at
#      http://127.0.0.1:$PORT (signed with the real updater key);
#   2. bumps a throwaway PATCH version, builds it too, then restores the tree;
#   3. serves the new version's updater tarball + latest.json over loopback;
#   4. opens the current-version app so you can walk the real flow end to end:
#
#        consent card -> Check now -> sheet offers the new version ->
#        Update now -> progress bar -> Restart Golavo -> post-update toast ->
#        Settings shows the update record -> ledger intact
#
# Tamper test (run after the happy path): corrupt the served tarball and check
# the download is REJECTED (signature verification) —
#     printf 'x' >> <workdir>/serve/Golavo_*_aarch64.app.tar.gz
#   then Check now -> Update now must fail with a signature error and the old
#   version must keep running.
#
# Prereqs:
#   - updater private key: TAURI_SIGNING_PRIVATE_KEY, TAURI_SIGNING_PRIVATE_KEY_PATH,
#     or the default escrow file (see KEY_DEFAULT below)
#   - a Python 3.12 env with `pip install -e core -e server pyinstaller`
#   - Rust stable + Node 20+
#   - a CLEAN git tree (the script bumps versions in place, builds, restores)
#
# Expect ~two full desktop builds of wall-clock time.
set -euo pipefail

PORT="${GOLAVO_UPDATE_TEST_PORT:-8199}"
TARGET="aarch64-apple-darwin"
KEY_DEFAULT="$HOME/Documents/development/security/golavo-updater-keys/golavo-updater.key"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [ "$(uname -sm)" != "Darwin arm64" ]; then
  echo "this harness drives the macOS arm64 flow; run it on Apple Silicon" >&2
  exit 2
fi
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "git tree is not clean — commit or stash first (the script bumps versions in place)" >&2
  exit 2
fi
if [ -z "${TAURI_SIGNING_PRIVATE_KEY:-}" ]; then
  KEY_FILE="${TAURI_SIGNING_PRIVATE_KEY_PATH:-$KEY_DEFAULT}"
  [ -f "$KEY_FILE" ] || { echo "updater private key not found at $KEY_FILE" >&2; exit 2; }
  TAURI_SIGNING_PRIVATE_KEY="$(cat "$KEY_FILE")"
fi
export TAURI_SIGNING_PRIVATE_KEY
export TAURI_SIGNING_PRIVATE_KEY_PASSWORD="${TAURI_SIGNING_PRIVATE_KEY_PASSWORD:-}"

CURRENT="$(python3 scripts/bump_version.py --check | sed 's/.*: //')"
NEXT="$(python3 - "$CURRENT" <<'PY'
import sys
major, minor, patch = sys.argv[1].split("-")[0].split(".")
print(f"{major}.{minor}.{int(patch) + 1}")
PY
)"

WORK="$(mktemp -d /tmp/golavo-updater-e2e.XXXXXX)"
SERVE="$WORK/serve"
mkdir -p "$SERVE" "$WORK/installed"
echo "==> workdir: $WORK   (current $CURRENT -> offered $NEXT)"

# Endpoint overlay: stacked on top of tauri.updater.conf.json, so the committed
# pubkey still applies — only the endpoint (and the http allowance the release
# build otherwise refuses) differ from production.
OVERLAY="$WORK/dev-endpoint.json"
cat > "$OVERLAY" <<EOF
{
  "plugins": {
    "updater": {
      "endpoints": ["http://127.0.0.1:${PORT}/latest.json"],
      "dangerousInsecureTransportProtocol": true
    }
  }
}
EOF

BUNDLE_DIR="desktop/src-tauri/target/${TARGET}/release/bundle"

echo "==> [A] building Golavo ${CURRENT} (loopback endpoint)"
GOLAVO_UPDATER_ENDPOINT_OVERLAY="$OVERLAY" bash packaging/build.sh "$TARGET"
cp -R "${BUNDLE_DIR}/macos/Golavo.app" "$WORK/installed/Golavo.app"

echo "==> [B] building Golavo ${NEXT} (the offered update)"
python3 scripts/bump_version.py "$NEXT"
GOLAVO_UPDATER_ENDPOINT_OVERLAY="$OVERLAY" bash packaging/build.sh "$TARGET"
cp "${BUNDLE_DIR}/macos/"Golavo*.app.tar.gz "$SERVE/Golavo_${NEXT}_aarch64.app.tar.gz"
cp "${BUNDLE_DIR}/macos/"Golavo*.app.tar.gz.sig "$SERVE/Golavo_${NEXT}_aarch64.app.tar.gz.sig"

echo "==> restoring the version bump"
git restore desktop/src-tauri/tauri.conf.json desktop/src-tauri/Cargo.toml \
  desktop/src-tauri/Cargo.lock desktop/package.json ui/package.json \
  core/pyproject.toml server/pyproject.toml core/golavo_core/__init__.py \
  server/golavo_server/__init__.py CITATION.cff

echo "==> writing latest.json (mac-only manifest for the local harness)"
python3 - "$SERVE" "$NEXT" "$PORT" <<'PY'
import datetime, json, pathlib, sys

serve, version, port = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
tarball = next(p for p in serve.glob("*.app.tar.gz"))
signature = (serve / (tarball.name + ".sig")).read_text().strip()
manifest = {
    "version": version,
    "notes": f"Local E2E test build {version}.\n- exercised by scripts/test-updater-local.sh",
    "pub_date": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "platforms": {
        "darwin-aarch64": {
            "signature": signature,
            "url": f"http://127.0.0.1:{port}/{tarball.name}",
        }
    },
}
(serve / "latest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(f"    latest.json -> offers {version}")
PY

echo "==> serving updates on http://127.0.0.1:${PORT} (ctrl-c when done)"
(cd "$SERVE" && exec python3 -m http.server "$PORT" --bind 127.0.0.1) &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT

echo "==> opening Golavo ${CURRENT} from $WORK/installed"
open "$WORK/installed/Golavo.app"

cat <<EOF

Walk this checklist in the app:
  [ ] first launch shows the consent card ("Keep Golavo up to date?")
  [ ] Enable checks -> the header pill appears within ~30s (or use
      Settings -> Check now)
  [ ] sheet offers Golavo ${NEXT} with release notes
  [ ] Update now -> progress bar counts up -> "Restart Golavo"
  [ ] restart -> app reopens as ${NEXT} -> toast "Updated to Golavo ${NEXT} —
      your ledger was backed up before installing."
  [ ] Settings shows the ${CURRENT} -> ${NEXT} record; ledger data intact
  [ ] Skip this version: silences the pill; a manual check still shows the
      version with "you previously skipped this"
  [ ] Cancel mid-download returns cleanly to the offer
  [ ] tamper test (see header comment) -> download REJECTED, old app fine
  [ ] offline test: kill this server (ctrl-c), manual check shows the
      "Couldn't reach GitHub" copy with the releases link

The server keeps running until you ctrl-c this script.
EOF
wait "$SERVER_PID"
