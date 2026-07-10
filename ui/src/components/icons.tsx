/** Inline icons — currentColor, no external assets. Decorative by default;
 *  callers add aria-labels where an icon carries meaning. */
import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function base(size: number, props: SVGProps<SVGSVGElement>) {
  return {
    width: size, height: size, viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 1.75, strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const, "aria-hidden": true, focusable: false, ...props,
  };
}

export const SealIcon = ({ size = 20, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <circle cx="12" cy="10" r="6" />
    <path d="M9.5 10l1.8 1.8L15 8.3" />
    <path d="M9 15.4L8 21l4-2 4 2-1-5.6" />
  </svg>
);

export const CopyIcon = ({ size = 15, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M5 15V5a2 2 0 0 1 2-2h8" />
  </svg>
);

export const CheckIcon = ({ size = 15, ...p }: IconProps) => (
  <svg {...base(size, p)}><path d="M4 12l5 5L20 6" /></svg>
);

export const ChevronRight = ({ size = 16, ...p }: IconProps) => (
  <svg {...base(size, p)}><path d="M9 6l6 6-6 6" /></svg>
);

export const ArrowLeft = ({ size = 16, ...p }: IconProps) => (
  <svg {...base(size, p)}><path d="M15 6l-6 6 6 6" /><path d="M9 12h11" /></svg>
);

export const SunIcon = ({ size = 18, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </svg>
);

export const MoonIcon = ({ size = 18, ...p }: IconProps) => (
  <svg {...base(size, p)}><path d="M21 12.8A8.5 8.5 0 1 1 11.2 3a6.6 6.6 0 0 0 9.8 9.8z" /></svg>
);

export const InfoIcon = ({ size = 18, ...p }: IconProps) => (
  <svg {...base(size, p)}><circle cx="12" cy="12" r="9" /><path d="M12 11v5" /><path d="M12 7.5v.5" /></svg>
);

export const AlertIcon = ({ size = 18, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <path d="M12 3.5L21.5 20H2.5L12 3.5z" /><path d="M12 10v4.5" /><path d="M12 17.5v.5" />
  </svg>
);

export const VoidIcon = ({ size = 18, ...p }: IconProps) => (
  <svg {...base(size, p)}><circle cx="12" cy="12" r="9" /><path d="M5.6 5.6l12.8 12.8" /></svg>
);

export const LinkIcon = ({ size = 16, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <path d="M10 14a4 4 0 0 0 5.66 0l2.34-2.34a4 4 0 0 0-5.66-5.66L11 7.34" />
    <path d="M14 10a4 4 0 0 0-5.66 0L6 12.34a4 4 0 0 0 5.66 5.66L13 16.66" />
  </svg>
);

export const ClockIcon = ({ size = 15, ...p }: IconProps) => (
  <svg {...base(size, p)}><circle cx="12" cy="12" r="9" /><path d="M12 7.5V12l3 2" /></svg>
);

export const GlobeIcon = ({ size = 15, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <circle cx="12" cy="12" r="9" /><path d="M3 12h18" />
    <path d="M12 3c2.5 2.4 3.8 5.6 3.8 9s-1.3 6.6-3.8 9c-2.5-2.4-3.8-5.6-3.8-9S9.5 5.4 12 3z" />
  </svg>
);

/** Empty-state glyph: a calm sumi circle (ensō) — nothing sealed yet. */
export const EnsoGlyph = ({ size = 54, ...p }: IconProps) => (
  <svg {...base(size, p)} strokeWidth={2}>
    <path d="M17.5 5.5A9 9 0 1 0 20 12" opacity=".8" />
  </svg>
);
