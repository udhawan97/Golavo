/**
 * Lightweight team identity for dense match lists.
 *
 * National flags are deliberately explicit: guessing a country from a team name
 * would eventually put the wrong flag beside a club or regional side. Everything
 * else falls back to a stable monogram until licensed crest assets are available.
 */
const NATIONAL_FLAGS: Readonly<Record<string, string>> = {
  argentina: "🇦🇷",
  australia: "🇦🇺",
  austria: "🇦🇹",
  belgium: "🇧🇪",
  brazil: "🇧🇷",
  canada: "🇨🇦",
  chile: "🇨🇱",
  china: "🇨🇳",
  colombia: "🇨🇴",
  "costa rica": "🇨🇷",
  croatia: "🇭🇷",
  czechia: "🇨🇿",
  "czech republic": "🇨🇿",
  denmark: "🇩🇰",
  ecuador: "🇪🇨",
  egypt: "🇪🇬",
  england: "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
  france: "🇫🇷",
  germany: "🇩🇪",
  ghana: "🇬🇭",
  greece: "🇬🇷",
  iceland: "🇮🇸",
  india: "🇮🇳",
  iran: "🇮🇷",
  ireland: "🇮🇪",
  italy: "🇮🇹",
  japan: "🇯🇵",
  mexico: "🇲🇽",
  morocco: "🇲🇦",
  netherlands: "🇳🇱",
  "new zealand": "🇳🇿",
  nigeria: "🇳🇬",
  norway: "🇳🇴",
  paraguay: "🇵🇾",
  peru: "🇵🇪",
  poland: "🇵🇱",
  portugal: "🇵🇹",
  qatar: "🇶🇦",
  "republic of ireland": "🇮🇪",
  romania: "🇷🇴",
  "saudi arabia": "🇸🇦",
  scotland: "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
  senegal: "🇸🇳",
  serbia: "🇷🇸",
  "south africa": "🇿🇦",
  "south korea": "🇰🇷",
  "korea republic": "🇰🇷",
  spain: "🇪🇸",
  sweden: "🇸🇪",
  switzerland: "🇨🇭",
  tunisia: "🇹🇳",
  turkey: "🇹🇷",
  türkiye: "🇹🇷",
  ukraine: "🇺🇦",
  "united states": "🇺🇸",
  usa: "🇺🇸",
  uruguay: "🇺🇾",
  wales: "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
};

const NOISE_WORDS = new Set(["afc", "cf", "fc", "sc", "the"]);

export function nationalFlag(team: string): string | null {
  return NATIONAL_FLAGS[team.trim().toLocaleLowerCase("en-US")] ?? null;
}

export function teamMonogram(team: string): string {
  const words = team
    .trim()
    .split(/\s+/)
    .filter((word) => word && !NOISE_WORDS.has(word.toLocaleLowerCase("en-US")));
  const useful = words.length > 0 ? words : [team.trim()];
  if (useful.length === 1) return useful[0].slice(0, 2).toLocaleUpperCase("en-US");
  return `${useful[0][0]}${useful.at(-1)?.[0] ?? ""}`.toLocaleUpperCase("en-US");
}

/** A typography hint, never an abbreviation or mutation of the real name. */
export function teamNameDensity(team: string): "regular" | "compact" | "tight" {
  const longestWord = Math.max(...team.trim().split(/\s+/).map((word) => word.length));
  // Chromium's bundled Linux fonts run wider than macOS for several football
  // names (notably "Wolverhampton"). Step down before a single word can crowd
  // the protected score lane; the visible name is never abbreviated or broken.
  if (longestWord >= 15 || team.length >= 27) return "tight";
  if (longestWord >= 12 || team.length >= 20) return "compact";
  return "regular";
}
