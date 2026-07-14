# ADR-0001: Desktop architecture

- **Status:** Accepted
- **Date:** 2026-07-09
- **Deciders:** @udhawan97

## Context

Golavo is a local-first, offline-capable desktop app with a Python statistical
core (Dixon-Coles / bivariate Poisson, Parquet warehouse via pandas/pyarrow), a rich UI, an
optional AI layer, and a requirement for signed auto-updates with backup and
rollback on macOS and Windows.

## Options considered

| Option | Pros | Cons | Effort |
|---|---|---|---|
| **A. Tauri 2 + React + FastAPI/Python (PyInstaller) sidecar** | signed updater with static GitHub manifest; small shell; full Python stats stack; strong sandboxing | two runtimes; sidecar lifecycle is DIY; dual signing; target-triple builds | High |
| B. pywebview + PyInstaller (FolioOrb pattern) | proven in-house updater/backup/rollback; lowest effort | hand-rolled updater; weaker sandboxing; hard-exit hacks | Lowest |
| C. PWA / browser-first | zero packaging/signing | no sidecar; rewrite stats in JS/WASM; storage eviction; CORS walls for BYOK | Medium |
| D. Pure Rust / Tauri | single runtime; tiny/fast | rewrite the entire modeling stack in Rust; slow science iteration | Highest |
| E. Electron + Python | familiar | largest bundle, worst memory, weakest security story | Medium |

## Decision

**Option A** — Tauri 2 shell with a FastAPI/Python sidecar — is the shipped
desktop architecture. The FastAPI + Vite source-mode web app remains available
for local browser use without the shell.

Rationale: it keeps the Python scientific stack (fastest iteration on the models
that are the whole point), gives the strongest security posture (capabilities,
CSP, signed updater), and supports a zero-server update path via GitHub Releases.

## Consequences

- The PyInstaller sidecar binary must be renamed to `<name>-<target-triple>` per
  platform, and the shell must **kill the sidecar on exit** (and before update on
  Windows, where the installer force-exits the app) — Tauri does not manage
  sidecar lifecycle.
- The updater signing key is **fatal if lost** (installed users are stranded), so
  it is escrowed offline in two locations before any public release.
- macOS distribution requires the Apple Developer Program ($99/yr) for Developer
  ID signing + notarization; Windows uses SignPath Foundation (free OSS) or Azure
  Artifact Signing.

## Kill / reconsider triggers

- Sidecar orphan-process or Windows file-lock bugs unresolved after two focused
  weeks → fall back to **Option B** (FolioOrb's updater is a proven fallback).
- Python numerical core stabilizes under ~3k LoC by v2 → reconsider **Option D**
  and delete the sidecar.
- Source-mode web app fully satisfies the audience → pause desktop investment and
  reconsider **C**.
