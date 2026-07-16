/** Presentation helpers. Numbers stay honest: probabilities as percentages
 *  with one decimal, scores at fixed precision, timestamps in explicit UTC. */

/** 0.492 -> "49.2%" */
export function pct(p: number, digits = 1): string {
  return `${(p * 100).toFixed(digits)}%`;
}

/** 0.492 -> "49%". Whole numbers only — used in casual bars and verdicts so the
 *  UI never implies precision the model doesn't have. Expert tables keep pct(). */
export function pctWhole(p: number): string {
  return `${Math.round(p * 100)}%`;
}

/** Round a set of proportions to integers that still sum to `total` (default
 *  100), via largest-remainder. Keeps the three 1X2 labels honest: they add up.
 *  Returns integers in the input order. */
export function largestRemainder(values: number[], total = 100): number[] {
  const scaled = values.map((v) => v * total);
  const floors = scaled.map((v) => Math.floor(v));
  let remainder = total - floors.reduce((a, b) => a + b, 0);
  // Hand the leftover units to the largest fractional parts, one at a time.
  const order = scaled
    .map((v, i) => ({ i, frac: v - Math.floor(v) }))
    .sort((a, b) => b.frac - a.frac);
  const out = [...floors];
  for (let k = 0; k < order.length && remainder > 0; k++, remainder--) out[order[k].i] += 1;
  return out;
}

/** A lay-reader frequency for a probability: 0.62 -> "about 3 in 5". Restricted
 *  to small, legible denominators; picks the least-error fraction. For headline
 *  comprehension only — never a substitute for the percentage. */
export function inWords(p: number): string {
  if (p <= 0 || p >= 1) return p >= 1 ? "a near certainty" : "very unlikely";
  // Small, legible denominators only — "3 in 5" reads better than "5 in 8".
  const denoms = [2, 3, 4, 5, 6, 10];
  let best = { n: 1, d: 2, err: Infinity };
  for (const d of denoms) {
    const n = Math.round(p * d);
    if (n <= 0 || n >= d) continue;
    const err = Math.abs(n / d - p);
    if (err < best.err - 1e-9) best = { n, d, err };
  }
  return `about ${best.n} in ${best.d}`;
}

/** A [start, end] ISO/date range -> "since 1930" for casual context lines. */
export function sinceYear(range: [string, string]): string {
  const y = range[0]?.slice(0, 4);
  return /^\d{4}$/.test(y ?? "") ? `since ${y}` : "";
}

/** A [start, end] range -> "1930–2026" (or a single year), for compact meta. */
export function yearSpan(range: [string, string]): string {
  const a = range[0]?.slice(0, 4);
  const b = range[1]?.slice(0, 4);
  if (!/^\d{4}$/.test(a ?? "")) return "";
  if (!/^\d{4}$/.test(b ?? "") || a === b) return a;
  return `${a}–${b}`;
}

/** Fixed-precision number for metric display. */
export function num(x: number, digits = 3): string {
  return x.toFixed(digits);
}

/** ISO instant -> "9 Jul 2026, 20:00 UTC" (always UTC — forecasts are UTC-anchored). */
export function utc(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const date = d.toLocaleDateString("en-GB", {
    day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
  });
  const time = d.toLocaleTimeString("en-GB", {
    hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC",
  });
  return `${date}, ${time} UTC`;
}

/** ISO instant -> "9 Jul 2026" (date only, UTC). */
export function utcDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", {
    day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
  });
}

/** Exact display derived from the immutable kickoff and seal timestamps. The
 * legacy horizon enum is intentionally not used: old artifacts treated it as a
 * coarse audit tag rather than the actual elapsed duration. */
export function sealLeadTime(kickoffUtc: string, sealedAtUtc: string): string | null {
  const kickoff = Date.parse(kickoffUtc);
  const sealed = Date.parse(sealedAtUtc);
  if (!Number.isFinite(kickoff) || !Number.isFinite(sealed) || sealed > kickoff) return null;
  const totalMinutes = Math.max(0, Math.floor((kickoff - sealed) / 60_000));
  const days = Math.floor(totalMinutes / (24 * 60));
  const hours = Math.floor((totalMinutes % (24 * 60)) / 60);
  const minutes = totalMinutes % 60;
  if (days > 0) return hours > 0 ? `${days}d ${hours}h` : `${days}d`;
  if (hours > 0) return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
  return `${minutes}m`;
}

/** Relative label anchored to a reference instant: "in 2 days" / "4 days ago". */
export function relative(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const diffMs = d.getTime() - now.getTime();
  const abs = Math.abs(diffMs);
  const mins = Math.round(abs / 60000);
  const hours = Math.round(abs / 3_600_000);
  const days = Math.round(abs / 86_400_000);
  let mag: string;
  if (mins < 60) mag = `${mins} min`;
  else if (hours < 48) mag = `${hours} h`;
  else mag = `${days} day${days === 1 ? "" : "s"}`;
  return diffMs >= 0 ? `in ${mag}` : `${mag} ago`;
}

/** Like relative(), but only within a sane window around now, so a far-future
 *  fixture or an ancient result never renders an absurd "in 1282 days" next to
 *  a "Played" chip. Returns "" outside the window — the explicit date already
 *  carries it. Keeps near-term context in both directions. */
export function kickoffRelative(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const days = (d.getTime() - now.getTime()) / 86_400_000;
  if (days > 60 || days < -14) return "";
  return relative(iso, now);
}

/** Truncate a hash for compact display: first 8 … last 6. */
export function shortHash(h: string, head = 10, tail = 6): string {
  if (h.length <= head + tail + 1) return h;
  return `${h.slice(0, head)}…${h.slice(-tail)}`;
}
