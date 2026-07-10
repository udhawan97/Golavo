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
      customCss: ["./src/styles/custom.css"],
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
            { label: "Installation", slug: "installation" },
            { label: "Your matchday", slug: "matchday" },
          ],
        },
        {
          label: "Using Golavo",
          items: [
            { label: "Casual vs Expert", slug: "casual-vs-expert" },
            { label: "Local Intelligence", slug: "local-intelligence" },
            { label: "The Prediction Ledger", slug: "prediction-ledger" },
          ],
        },
        {
          label: "Methodology",
          items: [
            { label: "Prediction methodology", slug: "methodology/prediction" },
            { label: "Model cards & calibration", slug: "methodology/model-cards" },
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
