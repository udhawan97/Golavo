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

/** A calm activity/pulse glyph — a dot with a heartbeat trace. Used for the
 *  header activity center trigger, and the "form" fact category. */
export const PulseIcon = ({ size = 18, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <path d="M3 12h4l2-5 3 10 2-7 2 2h5" />
  </svg>
);

/** Head-to-head glyph — two opposing arrows. */
export const VersusIcon = ({ size = 16, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <path d="M14 4l4 4-4 4" /><path d="M18 8H8" />
    <path d="M10 20l-4-4 4-4" /><path d="M6 16h10" />
  </svg>
);

/** Signature-stats glyph — a fingerprint-like set of arcs. */
export const FingerprintIcon = ({ size = 16, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <path d="M12 11a2 2 0 0 1 2 2c0 2-.5 4-1.5 6" />
    <path d="M8.5 6.5A6 6 0 0 1 18 12c0 1.5-.2 3-.6 4.5" />
    <path d="M6 12a6 6 0 0 1 3-5.2" />
    <path d="M9.5 13c0-1.4 1.1-2.5 2.5-2.5" />
  </svg>
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

export const GearIcon = ({ size = 18, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);

export const DownloadIcon = ({ size = 16, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <path d="M12 4v10" /><path d="M7.5 10.5L12 15l4.5-4.5" /><path d="M4.5 19h15" />
  </svg>
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

export const LockIcon = ({ size = 16, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <rect x="5" y="10" width="14" height="11" rx="2.5" />
    <path d="M8.5 10V7.5a3.5 3.5 0 0 1 7 0V10" />
  </svg>
);

export const PlusIcon = ({ size = 18, ...p }: IconProps) => (
  <svg {...base(size, p)}><path d="M12 5v14M5 12h14" /></svg>
);

export const MinusIcon = ({ size = 18, ...p }: IconProps) => (
  <svg {...base(size, p)}><path d="M5 12h14" /></svg>
);

export const PitchIcon = ({ size = 18, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <rect x="3" y="4" width="18" height="16" rx="1.5" />
    <path d="M12 4v16" /><circle cx="12" cy="12" r="2.5" />
    <path d="M3 8h3v8H3M21 8h-3v8h3" />
  </svg>
);

export const SearchIcon = ({ size = 18, ...p }: IconProps) => (
  <svg {...base(size, p)}><circle cx="11" cy="11" r="7" /><path d="M20 20l-4.3-4.3" /></svg>
);

export const GlobeIcon = ({ size = 15, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <circle cx="12" cy="12" r="9" /><path d="M3 12h18" />
    <path d="M12 3c2.5 2.4 3.8 5.6 3.8 9s-1.3 6.6-3.8 9c-2.5-2.4-3.8-5.6-3.8-9S9.5 5.4 12 3z" />
  </svg>
);

export const CalendarIcon = ({ size = 15, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <rect x="3.5" y="4.5" width="17" height="16" rx="2.5" /><path d="M3.5 9h17" />
    <path d="M8 3v3M16 3v3" />
  </svg>
);

export const PinIcon = ({ size = 15, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <path d="M12 21c4.5-4.2 7-7.6 7-11a7 7 0 1 0-14 0c0 3.4 2.5 6.8 7 11z" />
    <circle cx="12" cy="10" r="2.4" />
  </svg>
);

export const BookIcon = ({ size = 16, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <path d="M4 4.5A2 2 0 0 1 6 3h13v15H6a2 2 0 0 0-2 2z" /><path d="M4 20.5V4.5" /><path d="M19 18v3H6" />
  </svg>
);

export const ScaleIcon = ({ size = 16, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <path d="M12 4v16" /><path d="M6 20h12" /><path d="M5 7h14" /><path d="M5 7l-2.5 5a2.5 2.5 0 0 0 5 0z" />
    <path d="M19 7l-2.5 5a2.5 2.5 0 0 0 5 0z" />
  </svg>
);

/** Compact distribution bars — used where a chart is the visual, not an action. */
export const DistributionIcon = ({ size = 16, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <path d="M4 20V12h3v8M10.5 20V5h3v15M17 20v-6h3v6" />
    <path d="M3 20.5h18" />
  </svg>
);

/** Matrix cells — the exact-score table disclosure. */
export const MatrixIcon = ({ size = 16, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <rect x="3.5" y="3.5" width="17" height="17" rx="2.5" />
    <path d="M9 3.5v17M15 3.5v17M3.5 9h17M3.5 15h17" />
  </svg>
);

export const SparkIcon = ({ size = 16, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z" />
  </svg>
);

export const StarIcon = ({
  size = 24,
  filled = false,
  ...p
}: IconProps & { filled?: boolean }) => (
  <svg {...base(size, { ...p, fill: filled ? "currentColor" : "none" })}>
    <path d="M12 3.2l2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9L6.6 20l1-6.1-4.4-4.3 6.1-.9z" />
  </svg>
);

export const ShieldCheckIcon = ({ size = 16, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <path d="M12 3l7 2.5v5.5c0 4.3-3 7.6-7 9-4-1.4-7-4.7-7-9V5.5z" /><path d="M9 11.5l2 2 4-4" />
  </svg>
);

export const ChevronDown = ({ size = 16, ...p }: IconProps) => (
  <svg {...base(size, p)}><path d="M6 9l6 6 6-6" /></svg>
);

export const TrophyIcon = ({ size = 16, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <path d="M7 4h10v4a5 5 0 0 1-10 0z" /><path d="M7 6H4v1a3 3 0 0 0 3 3M17 6h3v1a3 3 0 0 1-3 3" />
    <path d="M12 13v3M9 20h6M10 20l.5-4M14 20l-.5-4" />
  </svg>
);

/** Empty-state glyph: a calm sumi circle (ensō) — nothing sealed yet. */
export const EnsoGlyph = ({ size = 54, ...p }: IconProps) => (
  <svg {...base(size, p)} strokeWidth={2}>
    <path d="M17.5 5.5A9 9 0 1 0 20 12" opacity=".8" />
  </svg>
);

/** Writing glyph — a quill sweeping to a baseline. The AI "writing" stage. */
export const QuillIcon = ({ size = 16, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <path d="M20 4c-5 .4-9.2 2.8-11.7 6.9L6 16" />
    <path d="M19 8.5c-2.6 1-4.8 2.6-6.6 4.8" />
    <path d="M6 16l-1 4" />
    <path d="M4 20h7" />
  </svg>
);

/** Evidence-bundle glyph — an isometric parcel. The "assembling" stage. */
export const BundleIcon = ({ size = 16, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <path d="M12 3l7.5 4.3v9.4L12 21l-7.5-4.3V7.3z" />
    <path d="M12 12v9" />
    <path d="M4.5 7.3L12 12l7.5-4.7" />
  </svg>
);

/** Deep-analysis flavor — a telescope aimed at a small star. */
export const TelescopeIcon = ({ size = 16, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <path d="M4 13.5L18 7" />
    <path d="M15.5 5.5l2 4.5" />
    <circle cx="6" cy="14.5" r="2" />
    <path d="M9 15.5l-2 5.5M6.5 16.5l2.5 4.5" />
    <path d="M20.5 12.5v2M19.5 13.5h2" />
  </svg>
);

/** Erlenmeyer flask — the advanced/model-override disclosure. */
export const FlaskIcon = ({ size = 16, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <path d="M10 3v5l-5.5 10a2 2 0 0 0 1.8 3h11.4a2 2 0 0 0 1.8-3L14 8V3" />
    <path d="M9 3h6" />
    <path d="M7.5 15.5h9" />
  </svg>
);

/** A checked list — the "verifying" stage and the evidence legend. */
export const ChecklistIcon = ({ size = 16, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <rect x="4" y="3.5" width="16" height="17" rx="2.5" />
    <path d="M7.5 9l1.5 1.5L12 7.5" />
    <path d="M7.5 15l1.5 1.5L12 13.5" />
    <path d="M14.5 9.5h3M14.5 15.5h3" />
  </svg>
);

/** Outbound-link marker for web sources. */
export const ExternalLinkIcon = ({ size = 12, ...p }: IconProps) => (
  <svg {...base(size, p)}>
    <path d="M19 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h5" />
    <path d="M14 4h6v6" />
    <path d="M20 4l-9 9" />
  </svg>
);
