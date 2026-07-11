# packaging

Build and release tooling. Active as of **Phase 4**.

- `build.sh <target-triple>` — freeze the PyInstaller sidecar, build the UI, then
  the Tauri bundle for one platform. Invoked by `.github/workflows/release.yml`
  and runnable locally. Emits artifacts + `SHA256SUMS` into `packaging/out/`.
- `golavo-sidecar.spec` — PyInstaller **onefile** spec for the FastAPI sidecar.
  Bundles the read-only resources (JSON schema + evaluation summaries) so the
  frozen server resolves them under `sys._MEIPASS`. Excludes heavy unused libs;
  numpy/pandas/scipy/pyarrow are required by the calibration path and included.
- **Signing** — macOS Developer ID + notarization (Apple Developer Program,
  $99/yr); Windows via SignPath Foundation (free OSS) or Azure Trusted Signing.
  All gated on secrets; `build.sh` skips signing when they are unset.
- **Updater** — signed Tauri artifacts + a static `latest.json` on GitHub
  Releases. Enabled only when `TAURI_SIGNING_PRIVATE_KEY` is present (then
  `build.sh` adds `--features updater --config src-tauri/tauri.updater.conf.json`).

Outputs land in `packaging/out/` (gitignored) and are uploaded as release assets.

## Notes

- The sidecar is a ~73MB onefile (it embeds numpy/pandas/scipy/pyarrow). It
  self-extracts on first launch; heavy imports are deferred and warmed in the
  background so the shell's `/health` gate passes in well under a second.
- `build.sh` copies the frozen sidecar to
  `desktop/src-tauri/binaries/golavo-sidecar-<target-triple>` (with `.exe` on
  Windows) — the name Tauri's `externalBin` resolver expects.
