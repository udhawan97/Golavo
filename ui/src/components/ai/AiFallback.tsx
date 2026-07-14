import { AlertIcon, InfoIcon } from "../icons";

/** Turn a raw transport error ("AI narrative → HTTP 503") into a calm, honest
 *  user-facing line. 503 means the local engine is still warming; other codes get
 *  a generic recoverable message instead of leaking the wire status text. */
export function humanizeError(error: Error): string {
  const msg = error.message || "";
  if (/HTTP 503/.test(msg))
    return "The local engine is still warming up. Give it a moment, then try again.";
  if (/HTTP 422/.test(msg))
    return "Golavo couldn’t assemble enough verified evidence for this match, so the model was not called. Refresh the match, then try again.";
  if (/HTTP \d{3}/.test(msg))
    return "The AI request couldn’t be completed. The analysis above is unaffected — try again in a moment.";
  return msg || "The AI request failed. The analysis above is unaffected.";
}

export function FallbackCard({
  reason, unavailable = false, onRetry, onSwitchFast, notes,
}: {
  reason: string | null;
  unavailable?: boolean;
  onRetry?: () => void;
  onSwitchFast?: () => void;
  notes?: string[];
}) {
  // Surface the real, de-duplicated failure reasons (timeout vs unreachable vs a
  // specific guard rejection) so a user staring at "Try again" can see WHY it
  // failed instead of looping blindly.
  const details = Array.from(new Set((notes ?? []).filter((n) => n && n.trim())));
  return (
    <div className="callout callout--info ai-fallback">
      {unavailable ? <InfoIcon size={18} /> : <AlertIcon size={18} />}
      <div>
        <div className="callout__title">
          {unavailable ? "AI unavailable" : "Showing the deterministic analysis only"}
        </div>
        {reason ??
          "AI output could not be verified against the engine's numbers, so it was discarded. " +
          "The analysis above is unaffected."}
        {details.length > 0 && (
          <details className="ai-fallback__details" style={{ marginTop: ".4rem" }}>
            <summary className="small dim">What happened</summary>
            <ul className="small dim" style={{ margin: ".3rem 0 0", paddingLeft: "1.1rem" }}>
              {details.map((d, i) => <li key={i}>{d}</li>)}
            </ul>
          </details>
        )}
        {(onRetry || onSwitchFast) && (
          <div className="ai-fallback__actions" style={{ marginTop: ".5rem", display: "flex", gap: ".5rem" }}>
            {onRetry && (
              <button type="button" className="ai-refresh" onClick={onRetry}>Try again</button>
            )}
            {onSwitchFast && (
              <button type="button" className="ai-refresh" onClick={onSwitchFast}>
                Switch to Fast
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/** Shown when AI is off — the honest default. */
export function OffCard() {
  return (
    <p className="ai-note">
      AI is <b>off</b> — the default. The analysis above stands entirely on its own.
      Choose a local model or your own key from the selector (or the AI toggle in the header)
      to add an optional, cited reading.
    </p>
  );
}
