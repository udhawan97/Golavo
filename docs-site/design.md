# Design — Golavo docs-site

A locked design system for this site. Every page redesign reads this file before
emitting code. Do not regenerate per page — extend or amend this file when the
system needs to grow.

The brand (palette, typefaces, motifs) predates this file and is **preserved**.
What this system adds is *job separation* for colour, a structural spine for the
landing page, and a contrast floor that both themes actually meet.

## Genre

**editorial.** Shippori Mincho on washi is already an editorial voice; the system
commits to it rather than fighting it. This bans, per genre: gradient-filled pill
buttons, centred-everything heroes, glassmorphism, pure black/white grounds.

## Macrostructure family

- **Marketing pages** (`index.mdx`): **16 · Feature Stack**, anchored to Golavo's
  real forecast lifecycle. The page opens with an unnumbered **H8 floating
  no-frame** product theater, then an **F2 sticky-scroll stack** walks through
  three real app states. The existing before-kickoff → at-kickoff → after-full-
  time sequence follows as the product contract beneath the visual tour. This
  changes the structural fingerprint from the earlier Narrative Workflow build
  without inventing a fake product story.
  Variation knobs: pinned side=right, scenes=3, product media=real, lifecycle
  continuation=numbered. The cinematic prologue is a tour, not a fourth stage.
- **Content pages** (~25 Starlight markdown docs): **02 · Long Document**.
  Starlight owns these templates. The system reaches them through tokens only —
  no restructuring.
- **Utility pages** (`download.mdx`): Long Document + the platform catalogue grid.
  The 3-up grid is legitimate here: three real platforms, not three invented
  features.

### The timeline / substrate split

The landing page has two registers, and the difference is load-bearing:

- **Numbered stages** — `1.0 BEFORE KICKOFF` → `2.0 AT KICKOFF` → `3.0 AFTER FULL TIME`.
  These are ordinal because the product is ordinal.
- **Unnumbered substrate** — architecture, the AI boundary, local data,
  competition analytics. These are *always true*, not steps. They must never
  take a stage number.

Numbering anywhere else is decoration and is banned. In particular: a rail of
unrelated facts (`01 · 100,000 matches / 02 · Two model voices`) does not get
numbers, because that list has no order.

## Theme

Palette is the existing Golavo brand, unchanged. What changes is that each
accent now has **one job** and **one value per ground**.

Two accents, split by what the material physically does:

- **Engine (gold)** — numbers, data, the deterministic core. Gold leaf reads on
  lacquer, so gold belongs on ink.
- **Seal (hanko red)** — commitment, the immutable record. Vermilion seal ink
  reads on washi, so red belongs on paper.

```
--gv-ground-ink    oklch(18.8% 0.006 164)   /* #101312 sumi   */
--gv-ground-paper  oklch(97.4% 0.009 89)    /* #faf7f0 washi  */
```

Each value is measured against **both** surfaces it can sit on — the base ground
and `--gv-paper-2` — and must clear **4.5** (WCAG AA, normal text) on the worse
of the two. Measuring against the base ground alone is not sufficient: `paper-2`
is the lower-contrast surface and is where cards, install tiles and the search
pill live.

| token | value | on ground | on paper-2 | worst |
| --- | --- | --- | --- | --- |
| `--gv-engine` dark | `#c9a227` | 7.72 | 7.24 | 7.24 |
| `--gv-engine` light | `#8a5e0d` | 5.32 | 4.92 | 4.92 |
| `--gv-seal` dark | `#ea5566` | 5.33 | 5.00 | 5.00 |
| `--gv-seal` light | `#bc002d` | 6.18 | 5.71 | 5.71 |

Three values needed correcting against the naive first pass, and the reasons are
worth keeping:

- The previous system hard-coded `#c9a227` on both grounds. On paper it measures
  **2.26** and failed every kicker and accented heading in light mode.
- Starlight's own light accent `#9a6b12` measures **4.38** — under the 4.5 floor.
  It clears AA Large only, so it cannot carry a 14px kicker. Hence `#8a5e0d`.
- The brand hinomaru `#bc002d` measures **2.83** on ink and cannot carry text in
  the dark theme, so the dark seal is lightened to `#ea5566` (same hue family).

`--gv-seal-ink` is the glyph colour *on* a seal fill, and flips per theme: near-black
on the light-red dark-theme fill, near-white on the deep-red light-theme fill.

Brand constants (unchanged, still available):

```
--golavo-ink #101312 · --golavo-paper #f4efe6 · --golavo-gold #c9a227
--golavo-red #bc002d · --golavo-orange #d9622b · --golavo-green #0b6e4f
--golavo-wave #6082b8
```

Accent budget: engine + seal together stay under 5% of any viewport. The seal is
spent almost entirely in one place (see Signature).

## Typography

- Display: **Shippori Mincho**, weight 600, style **normal**. Roman always.
- Body: **Zen Kaku Gothic New**, weight 400.
- Mono: system stack (`ui-monospace`, SF Mono, JetBrains Mono), weight 400–600.
- Display tracking: `-0.035em` at display sizes, `-0.012em` at heading sizes.
- Type scale anchor: `--text-display: clamp(2.45rem, 7vw, 5.8rem)`.

**Italic is body-copy emphasis only.** No italic in any heading or display
string. An italicised word inside a roman heading is banned outright — it is the
single most reliable AI tell in this codebase's prior output.

## Spacing

4-point named scale. Values live in `src/styles/tokens.css`. Pages must use named
tokens (`var(--gv-space-md)`), never raw values.

## Motion

- Easings: `--gv-ease-out: cubic-bezier(0.16, 0.7, 0.3, 1)` (the existing house
  curve), `--gv-ease-in`, `--gv-ease-in-out`. Never the browser default `ease`.
  No bounce.
- The hero gets one orchestrated opacity + ≤12px entrance and then stops.
- The product theater may crossfade and change perspective between three real
  screenshots as each scene becomes current. It uses `IntersectionObserver`, not
  a scroll listener, and never scrubs or parallax-shifts the page.
- The seal press remains the **only** motion that draws attention to itself, and
  it fires once.
- A two-pixel header progress line is functional orientation, not decoration. It
  may use the native scroll timeline where supported.
- Reduced-motion fallback: opacity-only, ≤150ms. The seal lands un-pressed.
- **No scroll-snap.** A ~15,000px page that snaps hijacks the reader's scroll.
- No infinite ambient loops. The seigaiha field is a still substrate.

## Microinteractions stance

- Silent success. No celebratory toasts.
- Hover delay 800ms; focus delay 0ms.
- `:focus-visible` ring at ≥3:1, never animated, always instant.
- Animate `transform`/`opacity` only.

## CTA voice

- **Primary**: flat `--gv-seal` fill, ink-or-paper text, 4px radius. **No
  gradient.** The primary action is a stamp, not a lozenge.
- **Secondary**: 1px `--gv-rule` outline on the bare ground, same radius.
- **Tertiary**: text + arrow, no chrome.
- Copy pattern: active verb naming exactly what happens ("Download or run
  locally"), and the same word survives to the destination.

## Surfaces

**Paper, never glass.** No `backdrop-filter` anywhere. Surfaces are solid ground
or `--gv-paper-2`, separated by hairlines, not blur. The brand's medium is washi
and sumi; glassmorphism contradicts it.

The rising sun is a **hard-edged disc**, never a blurred radial bloom. The
hinomaru has an edge; a soft gold gradient glow is the generic dark-page default
and reads as AI-generated.

Product media may use static CSS perspective and the single
`--gv-shadow-media` token. It must be a real Golavo screenshot with at most a
hairline frame—never fake browser, phone, window, or IDE chrome. Below 60rem the
tilt drops and media returns to normal document flow.

## Per-page allowances

- Marketing pages MAY use enrichment (Tier-A CSS art/perspective, Tier-B
  hand-built SVG, and real product screenshots or recordings).
- Content pages: typography only.
- Utility pages: typography + the platform catalogue grid.

## Signature — the hanko

One vermilion seal, pressed **once**, at stage `2.0 AT KICKOFF`.

A hanko is the Japanese artifact for making a thing official and unalterable —
which is exactly what Golavo's seal does to a forecast. Its glyph is the
forecast's own SHA-256 prefix, always labelled as an example digest, never
presented as a live value.

This is the page's one loud moment. Everything around it stays quiet so it can
land. If a future page wants a second signature, it replaces this one — it does
not join it.

## What pages MUST share

- The wordmark / lockup.
- The two accents and their jobs — engine never marks a commitment, seal never
  marks a number.
- Shippori Mincho display + Zen Kaku Gothic New body, both roman in headings.
- The CTA voice (flat fill, 4px radius, active verb).
- Hairline rules as the divider language.

## What pages MAY differ on

- Macrostructure within the page-type family.
- Stage count and per-stage media treatment on marketing pages.
- Enrichment — marketing pages only, Tier-A or Tier-B.

## Exports

See `src/styles/tokens.css` for the live values. That file is the single source
of truth; this section mirrors it.

### tokens.css

```css
:root {
  --gv-ground:     oklch(18.3% 0.0052 173.7);
  --gv-paper-2:    oklch(21.42% 0.005 173.9);
  --gv-ink-1:      oklch(96.45% 0.0098 87.5);
  --gv-ink-2:      oklch(78.64% 0.0133 86.8);
  --gv-rule:       oklch(26.13% 0.0062 134.9);
  --gv-engine:     oklch(72.8% 0.138 89.7);
  --gv-seal:       oklch(65.23% 0.1836 17.2);
  --gv-focus:      oklch(82.72% 0.139 91.8);
  --gv-font-display: "Shippori Mincho", Georgia, serif;
  --gv-font-body:    "Zen Kaku Gothic New", -apple-system, sans-serif;
  --gv-space-sm: 1rem; --gv-space-md: 1.5rem; --gv-space-lg: 2rem;
  --gv-ease-out: cubic-bezier(0.16, 0.7, 0.3, 1);
  --gv-radius-cta: 4px;
  --gv-radius-media: 10px;
  --gv-perspective: 1400px;
}
:root[data-theme="light"] {
  --gv-ground:  oklch(97.65% 0.0098 87.5);
  --gv-paper-2: oklch(94.97% 0.0168 88);
  --gv-ink-1:   oklch(20.05% 0.005 84.6);
  --gv-ink-2:   oklch(38.69% 0.0087 88.7);
  --gv-rule:    oklch(89.54% 0.0241 88.2);
  --gv-engine:  oklch(51.64% 0.1042 75.5);
  --gv-seal:    oklch(50.28% 0.2021 20.7);
  --gv-focus:   oklch(51.64% 0.1042 75.5);
}
```

### Tailwind v4 `@theme`

```css
@theme {
  --color-paper: oklch(97.65% 0.0098 87.5);
  --color-paper-2: oklch(94.97% 0.0168 88);
  --color-ink: oklch(20.05% 0.005 84.6);
  --color-ink-2: oklch(38.69% 0.0087 88.7);
  --color-rule: oklch(89.54% 0.0241 88.2);
  --color-engine: oklch(51.64% 0.1042 75.5);
  --color-seal: oklch(50.28% 0.2021 20.7);
  --color-focus: oklch(51.64% 0.1042 75.5);
  --font-display: "Shippori Mincho", Georgia, serif;
  --font-body: "Zen Kaku Gothic New", ui-sans-serif, sans-serif;
  --font-outlier: ui-monospace, "SF Mono", monospace;
  --spacing-sm: 1rem;
  --spacing-md: 1.5rem;
  --spacing-lg: 2rem;
  --spacing-xl: 3rem;
  --spacing-2xl: 4.5rem;
  --text-md: 1rem;
  --text-lg: 1.18rem;
  --ease-out: cubic-bezier(0.16, 0.7, 0.3, 1);
  --ease-in: cubic-bezier(0.7, 0, 0.84, 0);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --radius-card: 6px;
}
```

### DTCG `tokens.json`

```json
{
  "$schema": "https://design-tokens.github.io/community-group/format/",
  "color": {
    "paper": { "$value": "oklch(97.65% 0.0098 87.5)", "$type": "color" },
    "paper-2": { "$value": "oklch(94.97% 0.0168 88)", "$type": "color" },
    "ink": { "$value": "oklch(20.05% 0.005 84.6)", "$type": "color" },
    "ink-2": { "$value": "oklch(38.69% 0.0087 88.7)", "$type": "color" },
    "rule": { "$value": "oklch(89.54% 0.0241 88.2)", "$type": "color" },
    "engine": { "$value": "oklch(51.64% 0.1042 75.5)", "$type": "color" },
    "seal": { "$value": "oklch(50.28% 0.2021 20.7)", "$type": "color" },
    "focus": { "$value": "oklch(51.64% 0.1042 75.5)", "$type": "color" }
  },
  "font": {
    "display": { "$value": "Shippori Mincho, Georgia, serif", "$type": "fontFamily" },
    "body": { "$value": "Zen Kaku Gothic New, ui-sans-serif, sans-serif", "$type": "fontFamily" },
    "outlier": { "$value": "SF Mono, ui-monospace, monospace", "$type": "fontFamily" }
  },
  "space": {
    "sm": { "$value": "1rem", "$type": "dimension" },
    "md": { "$value": "1.5rem", "$type": "dimension" },
    "lg": { "$value": "2rem", "$type": "dimension" },
    "xl": { "$value": "3rem", "$type": "dimension" },
    "2xl": { "$value": "4.5rem", "$type": "dimension" }
  },
  "duration": {
    "micro": { "$value": "120ms", "$type": "duration" },
    "short": { "$value": "220ms", "$type": "duration" },
    "major": { "$value": "500ms", "$type": "duration" }
  }
}
```

### shadcn/ui CSS variables

```css
:root {
  --background: 97.65% 0.0098 87.5;
  --foreground: 20.05% 0.0042 84.6;
  --card: 94.97% 0.0168 88;
  --card-foreground: 20.05% 0.0042 84.6;
  --popover: 94.97% 0.0168 88;
  --popover-foreground: 20.05% 0.0042 84.6;
  --primary: 50.28% 0.2021 20.7;
  --primary-foreground: 97.9% 0.0111 45.7;
  --secondary: 89.54% 0.0241 88.2;
  --secondary-foreground: 38.69% 0.0087 88.7;
  --muted: 89.54% 0.0241 88.2;
  --muted-foreground: 49.19% 0.0127 95.3;
  --accent: 51.64% 0.1042 75.5;
  --accent-foreground: 97.9% 0.0111 45.7;
  --border: 89.54% 0.0241 88.2;
  --input: 89.54% 0.0241 88.2;
  --ring: 51.64% 0.1042 75.5;
  --radius: 6px;
}
```
