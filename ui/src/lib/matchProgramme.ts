import type { FormEntry } from "./contract";

const NUMBER_WORDS = ["Zero", "One", "Two", "Three", "Four", "Five"];

export function formVenue(entry: FormEntry): "home" | "away" | "neutral" {
  if (entry.neutral) return "neutral";
  return entry.is_home ? "home" : "away";
}

/** The form payload is oldest-first. A streak is the uninterrupted run ending
 * with the newest result; venue is named only when every result in that run was
 * played in the same role. */
export function formStreakSentence(entries: FormEntry[]): string | null {
  if (entries.length < 2) return null;
  const newest = entries.at(-1)!;
  let start = entries.length - 1;
  while (start > 0 && entries[start - 1].result === newest.result) start -= 1;
  const run = entries.slice(start);
  if (run.length < 2) return null;

  const venues = new Set(run.map(formVenue));
  const venue = venues.size === 1 ? `${formVenue(newest)} ` : "";
  const result = newest.result === "W" ? "wins" : newest.result === "D" ? "draws" : "losses";
  const count = NUMBER_WORDS[run.length] ?? String(run.length);
  return `${count} ${venue}${result} in a row.`;
}

export function goalDifferenceTrend(entries: FormEntry[]): number[] {
  return entries.map((entry) => entry.gf - entry.ga);
}

export function signedGoalDifference(value: number): string {
  if (value > 0) return `+${value}`;
  if (value < 0) return `−${Math.abs(value)}`;
  return "0";
}
