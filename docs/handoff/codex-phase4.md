# Phase 4 handoff — desktop app (Codex review)

**Base SHA:** `0a3cb72` (Phase 3 tip = `main` = `origin/main` at start).
**Branch:** `lane/phase4`.
**Reviewer:** Codex.

Phase 4 turns Golavo into an installable desktop app: a Tauri 2 shell that
supervises a PyInstaller-frozen FastAPI sidecar. Unsigned builds run locally and
in CI; signing/notarization and signed auto-update are wired and gated on secrets.

## What landed

| Task | Where | State |
|---|---|---|
| Sidecar (PyInstaller onefile + `--smoke`) | `server/golavo_server/sidecar.py`, `packaging/golavo-sidecar.spec` | done, verified |
| Frozen-vs-source resource resolver | `core/golavo_core/resources.py` | done, verified |
| Token gate + Tauri CORS | `server/golavo_server/{main,runtime}.py` | done, verified |
| Tauri 2 shell (port/token → spawn → health gate → window → kill) | `desktop/src-tauri/src/{main,lib,health}.rs` | done, verified |
| UI runtime wiring (injected `apiBase`+token, mock fallback) | `ui/src/lib/api.ts`, `ui/src/vite-env.d.ts` | done, verified |
| Packaging + CI (unsigned dmg/msi/exe + SHA256SUMS + smoke on both OSes) | `packaging/build.sh`, `.github/workflows/{release,ci}.yml` | done (local verified; CI wired) |
| Updater (backup/check/install/rollback), gated | `desktop/src-tauri/src/updater.rs`, `tauri.updater.conf.json` | wired + gated |
| Docs | `README.md`, `docs-site/.../{installation,updates-rollback,architecture}.md` | done |

## Build & run locally (macOS, verified on `aarch64-apple-darwin`)

Prereqs: Rust stable, Node 20+, Python 3.12, Tauri system deps.

```bash
# one command: freeze sidecar -> build UI -> Tauri bundle -> checksums
packaging/build.sh aarch64-apple-darwin
# -> packaging/out/Golavo_0.1.0_aarch64.dmg (+ .app) and SHA256SUMS
```

The sidecar `--smoke` mode (used by CI) boots on an ephemeral port, probes
`/health`, prints the version, and exits 0:

```bash
packaging/out/golavo-sidecar --smoke   # exit 0
```

## Sidecar target-triple naming

PyInstaller emits `packaging/out/golavo-sidecar` (`.exe` on Windows).
`build.sh` copies it to the name Tauri's `externalBin` resolver expects:

```
desktop/src-tauri/binaries/golavo-sidecar-<target-triple>[.exe]
# e.g. golavo-sidecar-aarch64-apple-darwin
#      golavo-sidecar-x86_64-pc-windows-msvc.exe
```

Inside the bundle Tauri strips the triple back to `golavo-sidecar` next to the
shell executable.

## Port + token handshake

1. Shell binds `127.0.0.1:0` → free port; mints a 256-bit hex token
   (`getrandom`).
2. Shell spawns the sidecar: `--host 127.0.0.1 --port <p> --token <t>
   --data-dir <app-data>/ledger --parent-pid <shell-pid>`.
3. Shell blocks on `GET /health` (raw TCP, bounded 90s) before creating a window.
4. Shell creates the window with an init script:
   `window.__GOLAVO_RUNTIME__ = { apiBase: "http://127.0.0.1:<p>", token: "<t>" }`.
5. UI (`ui/src/lib/api.ts`) reads that first, else build-time `VITE_GOLAVO_API`,
   else mocks; it sends `x-golavo-token` on every request.
6. Server rejects `/api/*` without the token (401); `/health` and CORS preflight
   are exempt. Source mode (no `GOLAVO_TOKEN`) stays open, so `make dev`/pytest
   are unchanged.

## Secret-gated steps (nothing faked)

| Step | Secret(s) | Behaviour when unset |
|---|---|---|
| macOS Developer ID signing + notarization | `APPLE_CERTIFICATE(_PASSWORD)`, `APPLE_SIGNING_IDENTITY`, `APPLE_ID`, `APPLE_PASSWORD`, `APPLE_TEAM_ID` | unsigned `.app`/`.dmg`; Gatekeeper warns |
| Windows code signing | SignPath / Azure | unsigned `.msi`/`.exe`; SmartScreen warns |
| Signed auto-update | `TAURI_SIGNING_PRIVATE_KEY(_PASSWORD)` + public key in `tauri.updater.conf.json` | updater plugin not registered; `check_for_update` returns `disabled` |

`build.sh` adds `--features updater --config src-tauri/tauri.updater.conf.json`
only when `TAURI_SIGNING_PRIVATE_KEY` is present.

## Orphan-process test evidence

The sidecar must be gone after quit. **This exposed a real bug first:** the
PyInstaller onefile runs as two processes (a bootloader that forks the Python
child); Tauri's `child.kill()` only killed the bootloader, leaving the child
holding the port. Fixed with a parent-death watchdog (`--parent-pid`); the child
self-exits when reparented or when the shell dies.

Verified on `aarch64-apple-darwin` with the built `Golavo.app`:

```
# launch
[sidecar] golavo-sidecar 0.1.0: serving on http://127.0.0.1:61063
[golavo] sidecar healthy on 127.0.0.1:61063 after 6.9s
$ pgrep -f golavo-sidecar        -> 17437 (bootloader) 17438 (python child)

# graceful quit (osascript 'quit app "Golavo"')
[golavo] sidecar killed on exit
$ pgrep -f golavo-sidecar        -> (none)      # both gone
$ lsof -iTCP:61063               -> port free

# hard case: SIGKILL the shell so the graceful kill can't run
$ kill -9 <golavo-desktop pid watched via --parent-pid>
$ pgrep -f golavo-sidecar        -> (none)      # watchdog self-terminated it
```

Both the graceful path (explicit kill) and the SIGKILL path (watchdog alone)
leave **zero** orphaned sidecar processes and free the port. The workbench was
also confirmed rendering the live evaluation summary (18 folds from the sidecar,
not mocks) via `window.__GOLAVO_RUNTIME__` injection.

## Known gaps / notes

- **Onefile cold boot.** The 73MB onefile self-extracts and, on first launch,
  macOS verifies its many unsigned `.so` files — the health gate took ~12s in
  that state (well within the 90s bound; subsequent launches are faster). Heavy
  numeric imports are deferred and background-warmed so `/health` itself answers
  in <1s. An onedir sidecar would cache verification across launches but is not a
  single-file `externalBin`; revisit if boot latency matters.
- **Binary rollback.** The updater backs up and restores user *data* (the
  ledger); reverting the *executable* still needs reinstalling the prior release.
- **Windows lifecycle** is wired (parent-pid watchdog, installer force-exit note)
  but was not run on Windows here; the CI `--smoke` job exercises the frozen
  bundle on `windows-latest`.
- **Ledger ships empty** (matches Phase 3 reality); the workbench renders the
  live evaluation summary + calibration from the sidecar. The shell points the
  ledger at `<app-data>/com.golavo.app/ledger` (writable) for future sealing.
