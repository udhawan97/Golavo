/** Presentation helpers. Numbers stay honest: probabilities as percentages
 *  with one decimal, scores at fixed precision, timestamps in explicit UTC. */

/** 0.492 -> "49.2%" */
export function pct(p: number, digits = 1): string {
  return `${(p * 100).toFixed(digits)}%`;
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

/** Truncate a hash for compact display: first 8 … last 6. */
export function shortHash(h: string, head = 10, tail = 6): string {
  if (h.length <= head + tail + 1) return h;
  return `${h.slice(0, head)}…${h.slice(-tail)}`;
}
