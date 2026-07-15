import type { ForecastMode } from "../lib/hooks";

/** Shared Casual ⇄ Expert switch. The persisted mode changes presentation
 * depth only; it never changes or recomputes forecast values. */
export function ModeToggle({
  mode,
  setMode,
}: {
  mode: ForecastMode;
  setMode: (mode: ForecastMode) => void;
}) {
  const modes: Array<[ForecastMode, string]> = [
    ["casual", "Casual"],
    ["expert", "Expert"],
  ];
  return (
    <div className="mode-toggle" role="group" aria-label="Detail level">
      {modes.map(([value, label]) => (
        <button
          key={value}
          type="button"
          className={`mode-toggle__btn${mode === value ? " is-active" : ""}`}
          aria-pressed={mode === value}
          onClick={() => setMode(value)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
