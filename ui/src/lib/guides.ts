/**
 * Contextual page guides.
 *
 * These are deliberately about orientation and next actions, never about
 * changing a forecast. Keeping the definitions as data makes the header
 * popover predictable and easy to verify across every route family.
 */
export interface PageGuideLink {
  label: string;
  href: string;
}

export interface PageGuide {
  eyebrow: string;
  title: string;
  summary: string;
  steps: [string, string, string];
  links: PageGuideLink[];
}

const GUIDES = {
  matchday: {
    eyebrow: "Matchday guide",
    title: "Predict the next match, then keep score",
    summary: "Upcoming current-season fixtures lead; older results stay in the model and recent-result tabs.",
    steps: [
      "Open an upcoming card and read the two model voices.",
      "Inspect the exact-score view and margin-free model fair line.",
      "Save your score call before kickoff, then track it in My Season.",
    ],
    links: [
      { label: "Search matches", href: "#/matches" },
      { label: "How Golavo earns trust", href: "#/trust" },
    ],
  },
  search: {
    eyebrow: "Search guide",
    title: "Find the fixture before choosing the depth",
    summary: "Search narrows the catalogue; opening a result moves you into its source-backed cockpit.",
    steps: [
      "Search by either team or competition.",
      "Open the exact fixture and confirm its kickoff or result state.",
      "Use Casual for the story or Expert for the full audit trail.",
    ],
    links: [
      { label: "Browse Matchday", href: "#/" },
      { label: "Browse leagues", href: "#/leagues" },
    ],
  },
  match: {
    eyebrow: "Match cockpit guide",
    title: "Read the match from headline to source",
    summary: "The cockpit separates Golavo's sealed numbers, source-backed context, and optional outside signals.",
    steps: [
      "Begin with the score or three-way probability line.",
      "Read the fair decimal as 1 ÷ model probability—not a bookmaker recommendation.",
      "Open the notebook and optional Player Lens, then make your own score call.",
    ],
    links: [
      { label: "Your season", href: "#/season" },
      { label: "Model methods", href: "#/lab/methods" },
    ],
  },
  forecast: {
    eyebrow: "Forecast record guide",
    title: "Audit what was known when the forecast sealed",
    summary: "This view is a record: later results may score it, but never rewrite its original probabilities.",
    steps: [
      "Confirm the seal time and immutable digest.",
      "Read each model voice separately instead of averaging them.",
      "Use cited facts and the track record to judge the forecast in context.",
    ],
    links: [
      { label: "Open the track record", href: "#/lab/track-record" },
      { label: "Read the methods", href: "#/lab/methods" },
    ],
  },
  leagues: {
    eyebrow: "Competition guide",
    title: "Move from the season table into a match",
    summary: "League views combine current-season fixtures with honest source capability and provenance.",
    steps: [
      "Start with the live table, current form, scoring rates, and remaining fixtures.",
      "Use season probabilities for the forward view; history is labelled below as model context.",
      "Open a fixture to predict a score or fetch optional top-five Player Lens data.",
    ],
    links: [
      { label: "All leagues", href: "#/leagues" },
      { label: "Search matches", href: "#/matches" },
    ],
  },
  season: {
    eyebrow: "My Season guide",
    title: "Make your call before kickoff",
    summary: "Your score picks stay local, lock at kickoff, and are compared with deterministic model families.",
    steps: [
      "Pick an upcoming score from a match cockpit.",
      "Return here to see open, locked, and scored picks.",
      "Compare points without changing the model's sealed record.",
    ],
    links: [
      { label: "Find an upcoming match", href: "#/matches" },
      { label: "Scoring guide", href: "#/guide/picks" },
    ],
  },
  teams: {
    eyebrow: "My Teams guide",
    title: "Keep a local view of the clubs you follow",
    summary: "Your list is stored on this device and only shapes what Golavo brings forward for you.",
    steps: [
      "Add or import the clubs you want close at hand.",
      "Review identity matches before accepting an import.",
      "Open a club's fixture without changing source or model data.",
    ],
    links: [
      { label: "Browse leagues", href: "#/leagues" },
      { label: "Manage local data", href: "#/settings" },
    ],
  },
  lab: {
    eyebrow: "Model Lab guide",
    title: "Judge the methods before trusting the headline",
    summary: "The Lab exposes backtests, track records, ratings, and the rules behind every sealed forecast.",
    steps: [
      "Start with the track record for observed performance.",
      "Use backtests to compare methods on the same historical windows.",
      "Read the methodology before interpreting a model difference.",
    ],
    links: [
      { label: "Track record", href: "#/lab/track-record" },
      { label: "Methodology", href: "#/lab/methods" },
    ],
  },
  trust: {
    eyebrow: "Trust Center guide",
    title: "Trace a claim back to its local proof",
    summary: "The Trust Center is the maintenance and recovery surface for Golavo's local evidence.",
    steps: [
      "Inspect the active data and forecast checkpoints.",
      "Export or verify a proof before changing local state.",
      "Use Settings for opt-in refresh, overlays, and removal controls.",
    ],
    links: [
      { label: "Open Settings", href: "#/settings" },
      { label: "Read model methods", href: "#/lab/methods" },
    ],
  },
  settings: {
    eyebrow: "Control-room guide",
    title: "Tune Golavo without crossing a boundary",
    summary: "Reading choices are local. Network, provider, and AI lanes stay optional and clearly separated.",
    steps: [
      "Set theme, text size, spacing, and contrast first.",
      "Choose if approved sources may check or refresh while Golavo is open.",
      "Enable outside data or AI only after reading its exact boundary.",
    ],
    links: [
      { label: "Open the Trust Center", href: "#/trust" },
      { label: "Return to Matchday", href: "#/" },
    ],
  },
} satisfies Record<string, PageGuide>;

export const GUIDE_OPEN_EVENT = "golavo-guide-open";

export function openPageGuide(): void {
  window.dispatchEvent(new Event(GUIDE_OPEN_EVENT));
}

export function guideForPath(path: string): PageGuide {
  if (path === "/settings") return GUIDES.settings;
  if (path === "/trust") return GUIDES.trust;
  if (path === "/teams") return GUIDES.teams;
  if (path.startsWith("/season")) return GUIDES.season;
  if (path.startsWith("/match/")) return GUIDES.match;
  if (path.startsWith("/forecast/")) return GUIDES.forecast;
  if (path === "/matches") return GUIDES.search;
  if (path === "/leagues" || path.startsWith("/league/")) return GUIDES.leagues;
  if (path.startsWith("/lab") || path.startsWith("/ledger") || path.startsWith("/eval")) return GUIDES.lab;
  return GUIDES.matchday;
}
