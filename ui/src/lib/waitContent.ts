/**
 * Copy shown while the engine warms — the splash and the home warming card share
 * this deck. Three interleaved kinds:
 *   - FACTS      : genuinely-true, obscure football trivia (kept factual on
 *                  purpose — even the loading screen shouldn't make things up).
 *   - WAIT_WHY   : an honest, witty-professional explanation of why a cold launch
 *                  takes a beat (self-extracting engine, a 75k-match library).
 *   - APP_GEMS   : hidden-feature tips, so the wait doubles as onboarding.
 *
 * Tone: calm, honest, a little playful — never hype, never a claim we can't back.
 * Each entry is ONE sentence so it fits a card without reflow.
 */

/** Genuinely true, genuinely obscure football facts. */
export const FACTS: readonly string[] = [
  "“Soccer” is British slang — short for as-SOC-iation football, coined to tell it apart from rugby.",
  "Brazil is the only country to appear at every men's World Cup since the tournament began in 1930.",
  "The most lopsided professional match ever finished 149–0 — every goal an own goal, scored in protest, in Madagascar in 2002.",
  "Denmark won Euro 1992 without qualifying: they were called up at the last minute to replace Yugoslavia.",
  "Vatican City fields its own national team, drawn mostly from Swiss Guards and clergy.",
  "Only three people have won the World Cup as both player and manager: Zagallo, Beckenbauer, and Deschamps.",
  "The fastest World Cup goal came after 11 seconds — Hakan Şükür for Turkey in 2002.",
  "The goal net was patented in 1891 by a Liverpool engineer, John Brodie.",
  "A regulation match ball must measure 68–70 cm around — the same spec used at the World Cup.",
  "Nearly 200,000 fans packed the Maracanã for the 1950 World Cup final, still a record crowd.",
  "The oldest club in the world, Sheffield FC, was founded in 1857 — before the modern rules even existed.",
  "A single Law of the Game — Law 11, offside — has been rewritten more than any other in football's history.",
];

/** Why a cold launch takes a moment — honest, and a little witty. */
export const WAIT_WHY: readonly string[] = [
  "Golavo runs entirely on your machine — no cloud shortcuts. The first minute is the price of owning the whole stadium.",
  "The engine ships as one sealed bundle and unpacks itself at every launch. Think of it as the groundskeeper unrolling the pitch.",
  "Seventy-five thousand matches are taking their seats in the library. They arrive in order; nobody queue-jumps.",
  "Five model families are lacing up. Each one fits on demand, at kickoff minus one second — never after.",
  "Nothing is phoning home while you wait. There is no home to phone.",
  "Now loading pandas — the data kind, not the bears. The slowest member of an otherwise punctual squad.",
  "A calm start beats a fast guess: the engine checks its bundled data before it shows you a single number.",
  "The match library is one frozen snapshot — it reads once, then answers all session long without touching a network.",
  "First launches take the scenic route. After this, pages answer in the time it takes to blink.",
  "Your forecasts, your disk, your rules. Independence has a short warm-up.",
];

/** Hidden features — the wait doubles as a guided tour. */
export const APP_GEMS: readonly string[] = [
  "Opening any match — even one from 1950 — compares two voices, a baseline, and disclosed goal-model variants.",
  "Expert mode reveals the full exact-score grid: every scoreline the models weigh, the most likely one ringed in gold.",
  "Seal a forecast before kickoff and it becomes immutable — scored after full time in Model Lab, misses included.",
  "The Commentator's Notebook gathers source-backed facts for a match — and labels coincidences as coincidences.",
  "The models are allowed to disagree. Golavo shows the council's spread instead of averaging it into false confidence.",
  "Late kickoff? The warm theme under the header's “Aa” is tuned for calm night-time reading.",
  "Everything works offline. The one route that can reach the network — fixture freshness — stays off until you switch it on.",
  "Every sealed forecast carries a SHA-256 fingerprint. Change one byte and Golavo refuses to show it.",
  "Search forgives accents: “sao paulo” finds São Paulo, “munchen” finds München.",
  "AI Deep Read is optional and checked against the engine's own numbers — it may narrate; it may never invent.",
];

export interface WaitCard {
  label: string;
  text: string;
}

/**
 * Short editorial notes for the full-screen launch experience. The larger
 * warming card can carry the longer deck above; the splash deliberately uses
 * one compact line so its hierarchy never collapses while the engine starts.
 */
export const LAUNCH_NOTES: readonly WaitCard[] = [
  {
    label: "Local-first",
    text: "Your match library stays on this Mac — never in the cloud.",
  },
  {
    label: "Football fact",
    text: "Liverpool engineer John Brodie patented the goal net in 1891.",
  },
  {
    label: "Built for trust",
    text: "The engine owns every number; AI may explain, never edit.",
  },
  {
    label: "Football fact",
    text: "Brazil has played at every men's World Cup since 1930.",
  },
  {
    label: "Private by design",
    text: "Nothing phones home while Golavo prepares your workspace.",
  },
  {
    label: "Football fact",
    text: "Denmark entered Euro 1992 late — then won the tournament.",
  },
] as const;

export function buildLaunchDeck(seed = 0): WaitCard[] {
  const offset = ((seed % LAUNCH_NOTES.length) + LAUNCH_NOTES.length) % LAUNCH_NOTES.length;
  return [...LAUNCH_NOTES.slice(offset), ...LAUNCH_NOTES.slice(0, offset)];
}

/**
 * A round-robin interleave of the three decks, so consecutive cards vary in kind
 * (why → gem → fact → why …). Each deck is offset by `seed` so two surfaces
 * (splash + home) don't march in lockstep. Deterministic for a given seed.
 */
export function buildWaitDeck(seed = 0): WaitCard[] {
  const decks: { label: string; items: readonly string[] }[] = [
    { label: "While you wait", items: WAIT_WHY },
    { label: "Did you know", items: APP_GEMS },
    { label: "Football fact", items: FACTS },
  ];
  const cards: WaitCard[] = [];
  const max = Math.max(...decks.map((d) => d.items.length));
  for (let i = 0; i < max; i++) {
    for (const deck of decks) {
      const item = deck.items[(i + seed) % deck.items.length];
      cards.push({ label: deck.label, text: item });
    }
  }
  return cards;
}
