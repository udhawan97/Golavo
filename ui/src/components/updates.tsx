/**
 * In-app update surfaces: the passive header pill, the morphing update sheet
 * (modeled on the macOS Software Update pane), the one-time auto-check consent
 * card, and the honest post-update toast.
 *
 * Nothing here renders outside the desktop shell — every entry point guards on
 * the shared controller (see lib/updater.ts).
 */
import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { useUpdater } from "../lib/updater-context";
import {
  ERROR_HINTS,
  ERROR_TITLES,
  RELEASES_URL,
  formatBytes,
  formatWhen,
} from "../lib/updater";
import type { UpdaterPhase } from "../lib/updater";
import { DownloadIcon } from "./icons";

// ---------------------------------------------------------------- pill ------

/** Passive "Update available" affordance — a real, focusable button. Hidden
 *  while the sheet is open, after "Skip this version", and everywhere that is
 *  not an updater-enabled desktop build. */
export function UpdatePill() {
  const u = useUpdater();
  if (!u.pillVisible) return null;
  const { phase } = u;
  const version = "info" in phase && phase.info ? phase.info.version : "";
  const label =
    phase.kind === "downloading" ? "Downloading update…"
    : phase.kind === "ready" ? "Update ready"
    : "Update available";
  return (
    <button
      type="button"
      className="update-pill"
      onClick={u.openSheet}
      aria-label={`${label}${version ? `: Golavo ${version}` : ""}. Open software update.`}
    >
      <DownloadIcon size={14} />
      {label}
    </button>
  );
}

// ---------------------------------------------------------------- sheet -----

/** Focus containment: send focus in on open, keep Tab cycling inside, restore
 *  on close. Small and dependency-free rather than exhaustive.
 *
 *  The effect keys ONLY on `active`, so it does not tear down and re-`focus()`
 *  on every render — critical during a download, where the sheet re-renders on
 *  each progress tick and would otherwise yank focus off Cancel every ~2 MB.
 *  `onEscape` is read through a ref so its changing identity never re-runs the
 *  effect. */
function useFocusTrap(active: boolean, onEscape: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  const onEscapeRef = useRef(onEscape);
  useEffect(() => { onEscapeRef.current = onEscape; }, [onEscape]);
  useEffect(() => {
    if (!active || !ref.current) return;
    const container = ref.current;
    const previous = document.activeElement as HTMLElement | null;
    container.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onEscapeRef.current();
        return;
      }
      if (e.key !== "Tab") return;
      const focusables = container.querySelectorAll<HTMLElement>(
        'button, [href], input, select, [tabindex]:not([tabindex="-1"])',
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    container.addEventListener("keydown", onKey);
    return () => {
      container.removeEventListener("keydown", onKey);
      previous?.focus?.();
    };
  }, [active]);
  return ref;
}

/** Release notes, rendered safely: plain text only, bullets recognised, never
 *  raw HTML. Long bodies are capped — the release page has the rest. */
function ReleaseNotes({ notes }: { notes: string }) {
  const capped = notes.length > 2400 ? `${notes.slice(0, 2400)}…` : notes;
  const lines = capped.split(/\r?\n/);
  const blocks: ReactNode[] = [];
  let bullets: string[] = [];
  const flush = () => {
    if (bullets.length) {
      blocks.push(
        <ul key={`ul-${blocks.length}`} className="update-notes__list">
          {bullets.map((b, i) => <li key={i}>{b}</li>)}
        </ul>,
      );
      bullets = [];
    }
  };
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) { flush(); continue; }
    const bullet = line.match(/^[-*•]\s+(.*)$/);
    if (bullet) bullets.push(bullet[1]);
    else { flush(); blocks.push(<p key={`p-${blocks.length}`}>{line}</p>); }
  }
  flush();
  return <div className="update-notes">{blocks}</div>;
}

function ReleasesLink({ children = "releases page" }: { children?: ReactNode }) {
  return (
    <a href={RELEASES_URL} target="_blank" rel="noreferrer">
      {children}
    </a>
  );
}

function ProgressBar({ downloaded, total }: { downloaded: number; total: number | null }) {
  const pct = total ? Math.min(100, Math.round((downloaded / total) * 100)) : null;
  // Announce at coarse steps only — per-chunk aria-live would spam screen readers.
  const coarse = pct === null ? null : Math.floor(pct / 25) * 25;
  return (
    <div className="update-progress">
      <div
        className="update-progress__track"
        role="progressbar"
        aria-label="Download progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct ?? undefined}
      >
        <div
          className={`update-progress__fill${pct === null ? " update-progress__fill--indeterminate" : ""}`}
          style={pct === null ? undefined : { width: `${pct}%` }}
        />
      </div>
      <p className="dim update-progress__label">
        {total ? `${formatBytes(downloaded)} of ${formatBytes(total)}` : formatBytes(downloaded)}
      </p>
      <span className="visually-hidden" role="status" aria-live="polite">
        {coarse !== null && coarse > 0 ? `Downloaded ${coarse} percent` : ""}
      </span>
    </div>
  );
}

function sheetBody(u: ReturnType<typeof useUpdater>, phase: UpdaterPhase): ReactNode {
  const current = u.status?.appVersion ?? "";
  const platform = u.status?.platform ?? "other";
  switch (phase.kind) {
    case "checking":
      return (
        <>
          <p role="status" aria-live="polite">Checking for updates…</p>
          <div className="update-sheet__actions">
            <button type="button" className="btn btn--ghost" onClick={u.closeSheet}>
              Close
            </button>
          </div>
        </>
      );

    case "upToDate":
      return (
        <>
          <p>You’re on the latest version{current ? ` — Golavo ${current}` : ""}.</p>
          {u.lastCheckedAt && (
            <p className="dim">Last checked {formatWhen(u.lastCheckedAt)}.</p>
          )}
          <div className="update-sheet__actions">
            <button type="button" className="btn" onClick={() => void u.check({ manual: true })}>
              Check again
            </button>
          </div>
        </>
      );

    case "available":
      return (
        <>
          <p>
            <strong>Golavo {phase.info.version}</strong> is available
            {current ? <> — you have {current}</> : null}. Requires a restart to install.
          </p>
          {phase.skipped && (
            <p className="update-sheet__note">
              You previously skipped this version, so it isn’t showing reminders.{" "}
              <button type="button" className="link-btn" onClick={u.unskip}>
                Show reminders again
              </button>
            </p>
          )}
          {phase.info.notes && <ReleaseNotes notes={phase.info.notes} />}
          <p className="dim">
            Downloads come signed from GitHub and are verified before anything installs.
            Your ledger is backed up first. <ReleasesLink>Release page ›</ReleasesLink>
          </p>
          <div className="update-sheet__actions">
            <button type="button" className="btn btn--primary" onClick={() => void u.download()}>
              Update now
            </button>
            {!phase.skipped && (
              <button type="button" className="btn btn--ghost" onClick={u.skipOffered}>
                Skip this version
              </button>
            )}
            <button type="button" className="btn btn--ghost" onClick={u.closeSheet}>
              Later
            </button>
          </div>
        </>
      );

    case "downloading":
      return (
        <>
          <p>Downloading Golavo {phase.info.version}…</p>
          <ProgressBar downloaded={phase.downloaded} total={phase.total} />
          <div className="update-sheet__actions">
            <button type="button" className="btn" onClick={() => void u.cancel()}>
              Cancel
            </button>
            <button type="button" className="btn btn--ghost" onClick={u.closeSheet}>
              Hide
            </button>
          </div>
        </>
      );

    case "ready":
      return (
        <>
          <p>
            <strong>Golavo {phase.info.version}</strong> is downloaded and verified.
          </p>
          <p className="dim">
            Your ledger is backed up before anything is touched.{" "}
            {platform === "windows"
              ? "Golavo will close, update itself, and reopen — usually under a minute."
              : "Golavo will restart into the new version."}
          </p>
          <div className="update-sheet__actions">
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => void u.installAndRestart()}
            >
              {platform === "windows" ? "Quit & install" : "Restart Golavo"}
            </button>
            <button type="button" className="btn btn--ghost" onClick={u.closeSheet}>
              Later
            </button>
          </div>
        </>
      );

    case "installing":
      return (
        <p role="status" aria-live="polite">
          Installing Golavo {phase.info.version}… Golavo will restart itself.
        </p>
      );

    case "error": {
      const { error } = phase;
      const hint = ERROR_HINTS[error.kind] ?? ERROR_HINTS.other;
      return (
        <>
          <p>
            <strong>{ERROR_TITLES[error.kind] ?? ERROR_TITLES.other}</strong>
          </p>
          {error.kind === "needs_move" ? (
            <p>{error.message}</p>
          ) : (
            <>
              {hint && <p>{hint}</p>}
              <p className="dim update-sheet__detail">{error.message}</p>
            </>
          )}
          <p className="dim">
            Manual downloads always work: <ReleasesLink />.
          </p>
          <div className="update-sheet__actions">
            {error.kind === "install_failed" || error.kind === "install_stalled" ? (
              <button
                type="button"
                className="btn btn--primary"
                onClick={() => void u.relaunch()}
              >
                Restart Golavo
              </button>
            ) : (
              <button
                type="button"
                className="btn"
                onClick={() => void u.check({ manual: true })}
              >
                Try again
              </button>
            )}
            {/* A stalled install already stopped the sidecar, so the app is
                degraded — relaunch is the only sensible path, no "Close". */}
            {error.kind !== "install_stalled" && (
              <button type="button" className="btn btn--ghost" onClick={u.dismissError}>
                Close
              </button>
            )}
          </div>
        </>
      );
    }

    case "idle":
    default:
      return (
        <>
          <p>Check GitHub for a newer version of Golavo.</p>
          {u.lastCheckedAt && (
            <p className="dim">Last checked {formatWhen(u.lastCheckedAt)}.</p>
          )}
          <div className="update-sheet__actions">
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => void u.check({ manual: true })}
            >
              Check for updates
            </button>
          </div>
        </>
      );
  }
}

export function UpdateSheet() {
  const u = useUpdater();
  const closable = u.phase.kind !== "installing";
  const onEscape = () => { if (closable) u.closeSheet(); };
  const trapRef = useFocusTrap(u.sheetOpen, onEscape);
  if (!u.sheetOpen) return null;
  return (
    <div
      className="update-backdrop"
      onClick={(e) => { if (e.target === e.currentTarget && closable) u.closeSheet(); }}
    >
      <div
        ref={trapRef}
        className="update-sheet card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="update-sheet-title"
        tabIndex={-1}
      >
        <h2 id="update-sheet-title" className="update-sheet__title">Software Update</h2>
        {sheetBody(u, u.phase)}
      </div>
    </div>
  );
}

// ------------------------------------------------------------- consent ------

/** One-time, non-blocking card honoring the "no network unless you opt in"
 *  promise: auto-checks stay off until the user answers. Both answers are
 *  remembered; "Not now" keeps a visible path back via Settings. */
export function UpdateConsentCard() {
  const u = useUpdater();
  if (!u.consentNeeded || u.sheetOpen) return null;
  return (
    <div className="consent-card card" role="region" aria-label="Automatic update checks">
      <p className="consent-card__title">Keep Golavo up to date?</p>
      <p className="dim">
        Golavo can ask GitHub once a day whether a newer version exists. Nothing else
        leaves your machine, and downloads only start when you click.
      </p>
      <div className="update-sheet__actions">
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => { u.setAutoCheck("on"); void u.check(); }}
        >
          Enable checks
        </button>
        <button type="button" className="btn btn--ghost" onClick={() => u.setAutoCheck("off")}>
          Not now
        </button>
      </div>
      <p className="dim consent-card__hint">You can change this anytime in Settings.</p>
    </div>
  );
}

// --------------------------------------------------------------- toast ------

const TOAST_MS = 8000;

/** Post-update confirmation, driven by the shell's just-updated record — the
 *  backup claim appears only when a backup was actually taken. */
export function UpdatedToast() {
  const u = useUpdater();
  const toast = u.freshUpdateToast;
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(u.ackToast, TOAST_MS);
    return () => window.clearTimeout(timer);
  }, [toast, u.ackToast]);
  if (!toast) return null;
  return (
    <div className="update-toast card" role="status" aria-live="polite">
      <span>
        Updated to Golavo {toast.to}
        {toast.backupTaken ? " — your ledger was backed up before installing." : "."}
      </span>
      <button type="button" className="icon-btn update-toast__close" onClick={u.ackToast} aria-label="Dismiss">
        ✕
      </button>
    </div>
  );
}
