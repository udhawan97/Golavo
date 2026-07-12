/**
 * Shared external-link constants — the one place off-site URLs live so copy and
 * targets stay consistent across the header banner, Settings, and the match
 * views. Keep these in sync with the real published locations.
 */

// The public documentation site (GitHub Pages). Was previously inlined in
// Settings.tsx; consolidated here so every surface links to the same place.
export const DOCS_URL = "https://udhawan97.github.io/Golavo/";

// RELEASES_URL is authored by the updater module (it drives update prompts too);
// re-exported here so links.ts is the single import surface for external URLs.
export { RELEASES_URL } from "./updater";
