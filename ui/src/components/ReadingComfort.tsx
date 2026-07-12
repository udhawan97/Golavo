/**
 * Reading-comfort popover — theme (incl. a warm, low-blue palette), text size,
 * line spacing, and contrast. It changes how the page reads, never a number.
 * A single "Aa" control in the header opens it (reachable mid-read); choices
 * persist and apply as data-* on <html>. Copy stays honest: warm tones are for
 * comfort, not eye protection.
 */
import { useEffect, useId, useRef, useState } from "react";
import type { Contrast, Leading, ReadingPrefs, TextSize, Theme } from "../lib/hooks";

export function ReadingComfort({
  prefs,
  onChange,
}: {
  prefs: ReadingPrefs;
  onChange: (patch: Partial<ReadingPrefs>) => void;
}) {
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const panelId = useId();
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="rc" ref={wrap}>
      <button
        type="button"
        className="icon-btn rc__trigger"
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-label="Reading comfort — theme and text"
        title="Reading comfort"
        onClick={() => setOpen((o) => !o)}
      >
        <span aria-hidden>Aa</span>
      </button>
      {open && (
        <div className="rc__panel" id={panelId} role="group" aria-label="Reading comfort">
          <ReadingControls prefs={prefs} onChange={onChange} />
          <p className="rc__note">Warm tones for comfortable evening reading.</p>
        </div>
      )}
    </div>
  );
}

/** The theme / text-size / spacing / contrast controls, shared by the header
 *  popover and the Settings › Appearance section so both stay in sync. */
export function ReadingControls({
  prefs,
  onChange,
}: {
  prefs: ReadingPrefs;
  onChange: (patch: Partial<ReadingPrefs>) => void;
}) {
  return (
    <>
      <Segmented<Theme>
        legend="Theme"
        value={prefs.theme}
        onChange={(theme) => onChange({ theme })}
        options={[["light", "Light"], ["dark", "Dark"], ["warm", "Warm"]]}
      />
      <Segmented<TextSize>
        legend="Text size"
        value={prefs.textSize}
        onChange={(textSize) => onChange({ textSize })}
        options={[["sm", "S"], ["md", "M"], ["lg", "L"], ["xl", "XL"]]}
      />
      <Segmented<Leading>
        legend="Line spacing"
        value={prefs.leading}
        onChange={(leading) => onChange({ leading })}
        options={[["normal", "Normal"], ["relaxed", "Relaxed"]]}
      />
      <Segmented<Contrast>
        legend="Contrast"
        value={prefs.contrast}
        onChange={(contrast) => onChange({ contrast })}
        options={[["normal", "Normal"], ["high", "High"]]}
      />
    </>
  );
}

function Segmented<T extends string>({
  legend,
  value,
  onChange,
  options,
}: {
  legend: string;
  value: T;
  onChange: (v: T) => void;
  options: Array<[T, string]>;
}) {
  return (
    <div className="rc__row" role="group" aria-label={legend}>
      <span className="rc__legend">{legend}</span>
      <div className="rc__seg">
        {options.map(([val, label]) => (
          <button
            key={val}
            type="button"
            className={`rc__seg-btn${value === val ? " is-active" : ""}`}
            aria-pressed={value === val}
            onClick={() => onChange(val)}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}
