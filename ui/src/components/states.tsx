import type { ReactNode } from "react";
import { AlertIcon, EnsoGlyph } from "./icons";

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state" role="status">
      <EnsoGlyph className="state__glyph" />
      <p className="state__title">{title}</p>
      {children && <p className="state__body">{children}</p>}
    </div>
  );
}

export function ErrorState({
  title = "Something went sideways",
  error,
  onRetry,
}: {
  title?: string;
  error: Error;
  onRetry?: () => void;
}) {
  return (
    <div className="state" role="alert">
      <AlertIcon size={48} className="state__glyph" style={{ color: "var(--orange)" }} />
      <p className="state__title">{title}</p>
      <p className="state__body">{error.message}</p>
      {onRetry && (
        <button
          type="button"
          className="btn btn--ghost"
          onClick={onRetry}
          style={{ marginTop: ".75rem" }}
        >
          Try again
        </button>
      )}
    </div>
  );
}

/** Skeleton list for the matchday view while artifacts load. */
export function ListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="md-grid" aria-hidden>
      {Array.from({ length: rows }, (_, i) => <div key={i} className="skeleton sk-card" />)}
    </div>
  );
}

/** Generic block skeleton for detail/eval views. */
export function BlockSkeleton({ lines = 6 }: { lines?: number }) {
  return (
    <div className="card card--pad stack" aria-hidden>
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="skeleton sk-line" style={{ width: `${90 - i * 8}%` }} />
      ))}
    </div>
  );
}

export function Loading({ label }: { label: string }) {
  return <span className="visually-hidden" role="status" aria-live="polite">{label}</span>;
}
