# packaging

Build and release tooling. Activates in **Phase 4**.

- `build.sh <target-triple>` — build the PyInstaller sidecar, then the Tauri
  bundle, for one platform. Invoked by `.github/workflows/release.yml`.
- **PyInstaller** — onedir build of the Python sidecar; ship `certifi` for TLS;
  exclude heavy ML libs to avoid bloat.
- **Signing** — macOS Developer ID + notarization (Apple Developer Program,
  $99/yr); Windows via SignPath Foundation (free OSS) or Azure Artifact Signing.
- **Updater** — Tauri signed artifacts + a static `latest.json` on GitHub
  Releases; separate from OS code signing.
- **SBOM** — a CycloneDX SBOM and `SHA256SUMS` accompany every release.

Outputs land in `packaging/out/` and are uploaded as release assets.
