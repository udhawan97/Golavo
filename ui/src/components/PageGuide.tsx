import { useEffect, useId, useRef, useState } from "react";
import { BookIcon, ChevronRight } from "./icons";
import { GUIDE_OPEN_EVENT, guideForPath } from "../lib/guides";

export function PageGuide({ path }: { path: string }) {
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const panelId = useId();
  const guide = guideForPath(path);
  const close = () => {
    setOpen(false);
    trigger.current?.focus();
  };

  useEffect(() => setOpen(false), [path]);

  useEffect(() => {
    const openFromPage = () => setOpen(true);
    window.addEventListener(GUIDE_OPEN_EVENT, openFromPage);
    return () => window.removeEventListener(GUIDE_OPEN_EVENT, openFromPage);
  }, []);

  useEffect(() => {
    if (!open) return;
    panel.current?.focus();
    const onDown = (event: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      trigger.current?.focus();
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="page-guide" ref={wrap}>
      <button
        ref={trigger}
        type="button"
        className="icon-btn page-guide__trigger"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-label={`Guide for this page — ${guide.eyebrow}`}
        title="Guide for this page"
        onClick={() => setOpen((value) => !value)}
      >
        <BookIcon size={18} />
      </button>
      {open && (
        <div
          ref={panel}
          id={panelId}
          className="page-guide__panel"
          role="dialog"
          aria-labelledby={titleId}
          tabIndex={-1}
        >
          <button
            type="button"
            className="page-guide__close"
            aria-label="Close page guide"
            onClick={close}
          >
            <span aria-hidden>×</span>
          </button>
          <p className="page-guide__eyebrow">{guide.eyebrow}</p>
          <h2 id={titleId}>{guide.title}</h2>
          <p className="page-guide__summary">{guide.summary}</p>
          <ol className="page-guide__steps">
            {guide.steps.map((step, index) => (
              <li key={step}>
                <span aria-hidden>{index + 1}</span>
                <p>{step}</p>
              </li>
            ))}
          </ol>
          <nav className="page-guide__links" aria-label="Guide destinations">
            {guide.links.map((link) => (
              <a key={link.href} href={link.href} onClick={() => setOpen(false)}>
                {link.label}<ChevronRight size={14} />
              </a>
            ))}
          </nav>
        </div>
      )}
    </div>
  );
}
