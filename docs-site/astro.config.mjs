// @ts-check
import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";

// GitHub Pages project site: https://udhawan97.github.io/Golavo
// `base` MUST match the repository name for links/assets to resolve.
export default defineConfig({
  site: "https://udhawan97.github.io",
  base: "/Golavo",
  integrations: [
    starlight({
      title: "Golavo",
      favicon: "/favicon.svg",
      description:
        "Local-first, open-source soccer match intelligence. A deterministic engine owns every probability; AI only cites and explains. Every forecast is sealed before kickoff and scored after full time.",
      tagline:
        "The numbers remember everything. The beautiful game still keeps the last word.",
      logo: {
        light: "./src/assets/golavo-lockup-light.svg",
        dark: "./src/assets/golavo-lockup-dark.svg",
        replacesTitle: true,
      },
      // tokens.css must load first — custom.css resolves against its variables.
      customCss: ["./src/styles/tokens.css", "./src/styles/custom.css"],
      // Bespoke animated landing hero (soccer · japan · zen) + expanding search.
      components: {
        Hero: "./src/components/Hero.astro",
        Search: "./src/components/Search.astro",
      },
      head: [
        {
          tag: "link",
          attrs: { rel: "preconnect", href: "https://fonts.googleapis.com" },
        },
        {
          tag: "link",
          attrs: {
            rel: "preconnect",
            href: "https://fonts.gstatic.com",
            crossorigin: true,
          },
        },
        {
          tag: "link",
          attrs: {
            rel: "stylesheet",
            href: "https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@500;600;700&family=Zen+Kaku+Gothic+New:wght@400;500;700&display=swap",
          },
        },
        { tag: "meta", attrs: { name: "theme-color", content: "#101312" } },
        {
          tag: "meta",
          attrs: { property: "og:image", content: "/Golavo/brand/golavo-icon.svg" },
        },
      ],
      social: [
        {
          icon: "github",
          label: "GitHub",
          href: "https://github.com/udhawan97/Golavo",
        },
      ],
      editLink: {
        baseUrl: "https://github.com/udhawan97/Golavo/edit/main/docs-site/",
      },
      sidebar: [
        {
          label: "Start here",
          items: [
            { label: "Introduction", slug: "introduction" },
            { label: "Download & run", slug: "download" },
            { label: "Installation", slug: "installation" },
            { label: "Games & the Match Cockpit", slug: "matchday" },
            { label: "Competition analytics", slug: "competition-analytics" },
            { label: "Picks, points & My Season", slug: "picks-and-points" },
          ],
        },
        {
          label: "Using Golavo",
          items: [
            { label: "Casual vs Expert", slug: "casual-vs-expert" },
            { label: "Local Intelligence", slug: "local-intelligence" },
            { label: "Model Lab & Track record", slug: "prediction-ledger" },
            { label: "Match Notes & enrichment", slug: "match-enrichment" },
          ],
        },
        {
          label: "Methodology",
          items: [
            { label: "Prediction methodology", slug: "methodology/prediction" },
            { label: "Model cards & calibration", slug: "methodology/model-cards" },
            { label: "Fact & Coincidence engine", slug: "methodology/facts" },
          ],
        },
        {
          label: "Data",
          items: [
            { label: "Coverage", slug: "data/coverage" },
            { label: "Sources & licenses", slug: "data/sources" },
          ],
        },
        {
          label: "AI",
          items: [{ label: "AI providers & local models", slug: "ai/providers" }],
        },
        {
          label: "Trust & safety",
          items: [
            { label: "Privacy & security", slug: "privacy-security" },
            { label: "Updates & rollback", slug: "updates-rollback" },
            { label: "Legal & brand use", slug: "legal" },
          ],
        },
        {
          label: "Build & contribute",
          items: [
            { label: "Architecture", slug: "architecture" },
            { label: "Build from source", slug: "build-from-source" },
            { label: "Contributing", slug: "contributing" },
            { label: "Roadmap", slug: "roadmap" },
          ],
        },
      ],
    }),
  ],
});
