# Golavo v0.2.0 — hardening handoff

**Base SHA:** `30dd644` (v0.1.0 + 8 commits, tagged release + Phase 7–8) · **Release:** `v0.2.0`, unsigned pre-alpha · **Scope:** harden the shipped product — no new features. Full findings: [`v0.2-review.md`](v0.2-review.md).

## What this release is

A hardening capstone over the released v0.1.0 product. I reviewed the whole shipped system as a skeptical principal engineer + open-data lawyer + adversarial critic, verified every candidate finding against the code (and empirically where it mattered), fixed the confirmed **High** findings each with a regression test, and cut v0.2.0. **No Critical defect survived verification** — reported honestly rather than invented.

## Review summary

- **Critical: none.** The guarantees that matter held: no chronological leakage in the seal path; machine-checked coherence between the sealed 1X2, expected goals, and exact-score matrix (all from one fitted joint distribution); an AI numeric whitelist that cannot emit an *unsupported* number; BYOK keys that never enter a prompt; SSRF-safe provider config; score-matrix determinism robust to ±128-ULP per-element perturbation. Most ✅/coverage/accuracy claims reproduce exactly — the repo is unusually honest.
- **High: 3 — all fixed with regression tests** (below).
- **Medium: 6, Low: 8 — deferred**, tracked in [`v0.2-review.md`](v0.2-review.md) (§ Deferred). L1 (updater doc drift) and L2 (docs-site version) were corrected opportunistically; M4's misleading wording was corrected as part of H2.

## Fixed (with the test that proves it)

| ID | Finding | Fix | Regression test |
|----|---------|-----|-----------------|
| **H1** | Read-only API + calibration served on-disk artifacts with no schema/coherence/hash validation → tamper & incoherence passed the API and could skew calibration; contradicted "coherence enforced on every load / immutable, auditable". | `verify_artifact_integrity` + `load_verified_artifact` in `core/golavo_core/artifacts.py` recompute `payload_sha256` and the content-addressed `artifact_id` (filename stem must match content); wired into `server/golavo_server/main.py` (`list_forecasts` omits, `get_forecast`/`narrative` → 500) and `calibration._load_ledger`. Fail closed. | `core/tests/test_v0_2_hardening_core.py` (transposed-prob tamper, wrong-filename, tampered-ledger, accepts-every-genuine-sample) · `server/tests/test_v0_2_hardening_api.py::test_api_fails_closed_on_a_tampered_artifact` |
| **H2** | `SECURITY.md`/`packs/README.md`/`README.md` claimed minisign **signature-verified** packs + "unsigned packs require override" — no such code (only per-file sha256). Release "sign checksums" step was an `echo` stub that still flipped a keyed release to a full release. | Reworded all three docs to the true mechanism, marking signature verification **planned (ADR-0001), not yet implemented**; release step now fails if a key is set (signing unimplemented) and the notes stop implying `SHA256SUMS.txt` authenticates a download; corrected `SECURITY.md`'s stale "Phase 0 has no updater". | `core/tests/test_v0_2_hardening_core.py::test_docs_do_not_overclaim_pack_signature_verification` |
| **H3** | Desktop sidecar parent-watch was POSIX-only; on Windows (a shipped target) `os.kill(pid,0)` signals/terminates rather than probes and raised an uncaught `OSError`, and reparent-detection never fires → orphaned sidecar holding its loopback port every session. | `server/golavo_server/sidecar.py`: `_pid_alive` dispatches by platform (Windows: non-destructive `OpenProcess`/`WaitForSingleObject`); the orphan decision is factored into a pure `_orphaned(...)` with the reparent heuristic disabled on Windows; `except` broadened to `OSError`. POSIX path unchanged. | `server/tests/test_v0_2_hardening_api.py` (`_pid_alive` self/reaped-child/Windows-dispatch-without-killing; `_orphaned` POSIX vs Windows) |

**Verification note (H3):** the Windows branch is unit-tested by platform dispatch + non-killing-probe selection (mocked `os.name`), since no Windows runtime is available in this environment. A real Windows integration test (and the CI `sidecar-smoke` job exercising `--parent-pid`) is recommended follow-up — the POSIX path, which CI does exercise, is unchanged.

## Deferred (Medium/Low — tracked, not fixed per the fix-only-High rule)

See [`v0.2-review.md`](v0.2-review.md) § "Deferred items". Highlights:
- **M1–M3 (provenance, latent):** the license-isolation guard is a bypassable name-grep; no manifest-completeness check; the runtime pack loader has no license gate. **No active violation** — there is no ODbL data in the tree, all seven packs' declared files hash-match, and no shipped code reads ODbL. These are barriers to build before the first ODbL byte lands.
- **M4:** implement real minisign checksum signing (wording already corrected).
- **M5:** the whitelist blocks *unsupported* numbers but not wrong *semantic role* — inherent to numeric whitelisting; document in the AI methodology page.
- **M6:** Casual mode should surface the calibration/ledger pointer for parity of certainty.
- **L3–L8:** updater pubkey placeholder guard, health-gate fast-fail, PID-reuse reaping, keychain portability, a cross-OS determinism CI matrix, and the Starlette `TestClient` deprecation.

## Evidence

- **Determinism.** Regenerating the sample artifacts on macOS produced a byte-identical tree (`git status` clean). Empirically, no stored 9-dp score-matrix value flips under ±128-ULP per-element perturbation across 120 fixture rates × 3 goal families — far beyond any realistic cross-platform libm delta (≤~4 ULP). Determinism is robust; the residual (L7) is only that byte-identity is not *asserted* across OSes in CI.
- **Security.** The served-narration numeric gate exact-matches trusted `display` strings (value+unit+citation bound); spelled-out numbers, fractions, betting lexicon, and credential shapes hard-reject. BYOK keys go only in a request header (never the prompt/body); cloud `base_url` cannot be overridden; local providers are loopback-validated and keyless. I could construct neither an unsupported-number leak nor a key-exfiltration path. New: on-disk artifacts are integrity-verified before serving (H1).
- **Provenance.** From a clean checkout: `validate_provenance.py` OK (7 packs, registry consistent), `validate_artifacts.py` OK (8 samples, hashes match), `check_license_isolation.sh` OK. All packs contain only manifest-declared files today.

## Honest state of the product

- **What it is:** an open-source, local-first, deterministic 1X2 forecaster for men's senior full internationals (forward seal→score→void loop + real calibration record) and a historical backtest of the top-5 European leagues; a machine-checked-coherent exact-score matrix on goal-based seals; a deterministic Fact & Coincidence engine; an optional, off-by-default local-first AI narration layer that cites — never owns — numbers; a Tauri 2 desktop app that builds **unsigned**.
- **What it deliberately is not:** a betting product (no odds/picks/locks/bankroll), a livescore app, a redistributor of licensed feeds, or an "AI predictor" (the statistics own every number). Signed releases/updater and typed-feature→rerun remain gated/planned.
- **Blocked by data (verified, not fixable here):** confirmed lineups, injuries, corners, shots, xG, club-level goalscorers, a club forward loop, and cups have **no lawful open source**. They are correctly out of scope — not added, scraped, or fabricated.

## Reproduce the verification

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e "core[dev]" -e "server[dev]" ruff
ruff check .
pytest -q                                   # core + server (incl. e2e, red-team, hardening)
python scripts/validate_provenance.py       # 7 packs + registry, from a clean checkout
python scripts/validate_artifacts.py        # 8 sample artifacts, payload hashes
cd ui && npm ci && npm run build            # tsc --noEmit + vite build
```
