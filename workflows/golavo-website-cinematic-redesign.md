# Golavo cinematic website redesign

## Goal

Turn Golavo's existing landing page into a cinematic, product-led experience that
makes a strong first impression and drives visitors to **Download or run locally**.
The page should impress an experienced frontend developer through composition,
motion discipline, accessibility, and implementation craft—not through a heavy
runtime or ornamental effects.

## Trigger

Run this workflow when the owner explicitly asks to redesign, enhance, or visually
polish Golavo's public website.

## Inputs

- The current `docs-site/` implementation and `docs-site/design.md`.
- The current product screenshots, animated match-programme GIF, brand SVGs, and
  explanatory SVG artifacts under `docs-site/public/`.
- The current product/version/release language already present in the page.
- The Golavo product-trust contract.

## Locked decisions

- **Primary action:** Download or run Golavo locally.
- **Audience:** curious football supporters first; analytical users, researchers,
  and frontend/developer visitors as a second layer.
- **Tone:** cinematic luxury filtered through Golavo's Japanese editorial system.
- **Macrostructure:** Feature Stack—three real app scenes with a strong linear
  mobile fallback—followed by the genuine before kickoff → at kickoff → after
  full time lifecycle.
- **Visual system:** preserve Shippori Mincho, Zen Kaku Gothic New, sumi/washi
  grounds, gold for engine/data, and hanko red for commitment.
- **Enrichment:** real product media with Tier-A CSS perspective/depth and Tier-B
  inline SVG craft. Do not add Three.js, a motion library, stock art, fake browser
  chrome, glassmorphism, decorative floating orbs, or ambient infinite animation.
- **Information architecture:** preserve existing routes, documentation ownership,
  factual copy intent, and download behavior.

## Implementation workflow

1. Confirm `main` and `origin/main` alignment and work from a scoped branch.
2. Render the current site at desktop and mobile widths to establish a visual
   baseline.
3. Extend `docs-site/design.md` before using any new depth or motion language.
4. Upgrade the hero into a split, product-led composition:
   - concise left-biased copy and primary download CTA;
   - an orbit-of-three arrangement made only from real screenshots;
   - a hand-built SVG trajectory/seal motif that communicates preview → seal →
     score;
   - one orchestrated entrance, optional pointer response on fine pointers, and a
     static reduced-motion fallback.
5. Add one cinematic product stage below the hero:
   - sticky desktop media with three scroll-selected scenes;
   - actual Games, Match Cockpit/GIF, and Model Lab/My Season media;
   - IntersectionObserver state changes that animate only transform/opacity;
   - linear static media/text pairs below 60rem and all reduced-motion contexts.
6. Preserve and refine the existing numbered forecast lifecycle, trust substrate,
   download chooser, and statement close. The cinematic stage previews the product;
   it does not duplicate or replace the trust story.
7. Add a restrained scroll-progress cue to the existing docs/search shell without
   changing Starlight's navigation or keyboard search model.
8. Update Hallmark preflight/log records and keep every colour/font behind named
   tokens.

## Motion budget

Use at most three expressive motion primitives:

1. A single hero entrance.
2. Scene crossfade/perspective shift in the product stage.
3. The one-shot forecast-seal press.

Functional scroll progress and brief CTA hover/press feedback stay transform-only
and do not introduce another narrative timeline. All motion uses named easings and
transform/opacity only. No scroll-event listener, parallax, bounce, auto-rotating
carousel, layout animation, or non-functional loop. `prefers-reduced-motion`
renders a complete static experience with no missing media or content.

## Acceptance criteria

- The primary CTA is visible in the first viewport at 800px-high desktop and at
  375×812 mobile.
- The hero uses real product media and contains no fake OS/browser/device chrome.
- The product stage communicates Games → Match Cockpit → immutable record/Model
  Lab with an accessible, keyboard-independent reading order.
- Every image has meaningful alt text plus width/height; below-fold assets are
  lazy-loaded; the hero's primary image is eager/high-priority.
- No horizontal scroll at 320, 375, 414, or 768px.
- Clickable labels stay on one line; touch targets are at least 44×44px.
- Light and dark themes remain legible; gold remains data-only and red remains
  commitment/primary-action-only.
- `prefers-reduced-motion` disables spatial motion and substitutes the GIF with a
  still image.
- The deterministic engine remains the only numeric authority; the page makes no
  invented metrics, forecasts, testimonials, or product claims.
- Astro typecheck and production build pass.
- Browser QA passes at 320, 375, 414, 768, 1024, and 1440px with zero console
  errors and screenshots inspected in both light and dark themes.
- The final two-axis review reports no unresolved Standards or Spec findings.
- The scoped commit is merged to `main`, pushed to `origin/main`, and the live
  GitHub Pages site is rechecked after deployment.

## Checkpoint

Push the human checkpoint to the end. Present one decision-ready brief containing:

- what changed and why;
- the verification matrix and any limitations;
- before/after screenshots;
- commit SHA, `main`/`origin/main` alignment, and live-site URL.
