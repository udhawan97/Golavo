# desktop

The Golavo desktop shell (**Tauri 2**). **AGPL-3.0.** Lands in **Phase 4** — see
[ADR-0001](../docs/adr/0001-architecture.md).

Responsibilities when built:

- Spawn the FastAPI/Python sidecar (PyInstaller) on an ephemeral loopback port
  with a per-launch token; kill it on exit (and before update on Windows).
- Wait for `/health` before showing the window.
- Signed auto-updates (stable + beta channels), pre-update backup, health check,
  and one-click rollback.
- Native menus, file dialogs, and OS keychain access for BYOK secrets.

Sidecar binaries must be named `<name>-<target-triple>` per platform. The updater
signing key is fatal-if-lost and is escrowed offline before any public release.
