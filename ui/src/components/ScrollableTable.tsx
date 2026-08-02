import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";

export function ScrollableTable({
  children,
  label,
  cue,
  className = "",
  style,
}: {
  children: ReactNode;
  label: string;
  cue: string;
  className?: string;
  style?: CSSProperties;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const hintId = useId();
  const [overflow, setOverflow] = useState(false);
  const [atEnd, setAtEnd] = useState(true);
  const [compact, setCompact] = useState(
    () => typeof window !== "undefined" && window.innerWidth <= 768,
  );

  const measure = useCallback(() => {
    const node = scroller.current;
    if (!node) return;
    const nextOverflow = node.scrollWidth > node.clientWidth + 1;
    const nextAtEnd = !nextOverflow || node.scrollLeft + node.clientWidth >= node.scrollWidth - 2;
    setCompact(window.innerWidth <= 768);
    setOverflow((current) => current === nextOverflow ? current : nextOverflow);
    setAtEnd((current) => current === nextAtEnd ? current : nextAtEnd);
  }, []);

  useEffect(() => {
    measure();
    window.addEventListener("resize", measure);
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    if (scroller.current) observer?.observe(scroller.current);
    return () => {
      window.removeEventListener("resize", measure);
      observer?.disconnect();
    };
  }, [measure]);

  const cueVisible = compact && overflow && !atEnd;
  return (
    <div
      className="table-scroll-shell"
      data-overflow={String(overflow)}
      data-at-end={String(atEnd)}
      data-compact={String(compact)}
    >
      <span id={hintId} className="table-scroll__hint" aria-hidden={!cueVisible}>
        {cue} <span aria-hidden>→</span>
      </span>
      <div
        ref={scroller}
        className={`table-wrap${className ? ` ${className}` : ""}`}
        style={style}
        role="region"
        aria-label={overflow ? `${label}. Scroll horizontally for more columns.` : label}
        aria-describedby={cueVisible ? hintId : undefined}
        tabIndex={overflow ? 0 : undefined}
        onScroll={measure}
      >
        {children}
      </div>
    </div>
  );
}
