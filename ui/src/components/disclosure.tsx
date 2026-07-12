/**
 * Progressive-disclosure primitives.
 *
 * `Drawer` wraps native <details>/<summary> so keyboard and screen-reader
 * behaviour come for free, but keeps the open state controlled so the Casual ⇄
 * Expert toggle can open every expert drawer at once (Expert) or collapse them
 * (Casual) while still letting a reader open one individually. It only changes
 * how much is shown — never a number.
 */
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { ChevronDown } from "./icons";

export function Drawer({
  title,
  chip,
  defaultOpen = false,
  children,
}: {
  title: ReactNode;
  chip?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  // Follow the ambient depth (Casual/Expert) when it flips, without freezing an
  // individually-opened drawer: this re-seeds on the mode change only.
  useEffect(() => setOpen(defaultOpen), [defaultOpen]);
  return (
    <details className="drawer" open={open}>
      <summary
        className="drawer__summary"
        onClick={(e) => {
          e.preventDefault();
          setOpen((o) => !o);
        }}
      >
        <ChevronDown className="drawer__chev" size={16} aria-hidden />
        <span className="drawer__title">{title}</span>
        {chip && <span className="drawer__chip">{chip}</span>}
      </summary>
      <div className="drawer__body">{children}</div>
    </details>
  );
}
