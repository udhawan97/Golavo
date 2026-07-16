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

- **Marketing pages** (`index.mdx`): **14 · Narrative Workflow**. Chosen because
  Golavo *is* a sequence — a forecast is sealed before kickoff and scored after
  full time, and that order is irreversible. Narrative Workflow is the one
  macrostructure that requires a genuine sequence, so the numbering lands on
  content where order carries information.
  Variation knobs: stage count, per-stage media treatment.
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
unrelated facts (`01 · 77,000 matches / 02 · Two model voices`) does not get
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
  curve), `--gv-ease-in-out`. Never the browser default `ease`. No bounce.
- Reveal pattern: opacity + ≤16px rise, once, on enter. Quiet.
- The seal press is the **only** motion that draws attention to itself, and it
  fires once.
- Reduced-motion fallback: opacity-only, ≤150ms. The seal lands un-pressed.
- **No scroll-snap.** A ~15,000px page that snaps hijacks the reader's scroll.

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

## Per-page allowances

- Marketing pages MAY use enrichment (Tier-A CSS art, Tier-B hand-built SVG).
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
  --gv-ground:     #101312;
  --gv-paper-2:    #171a19;
  --gv-engine:     #c9a227;  /* dark ground */
  --gv-seal:       #ea5566;  /* dark ground */
  --gv-font-display: "Shippori Mincho", Georgia, serif;
  --gv-font-body:    "Zen Kaku Gothic New", -apple-system, sans-serif;
  --gv-space-sm: 1rem; --gv-space-md: 1.5rem; --gv-space-lg: 2rem;
  --gv-ease-out: cubic-bezier(0.16, 0.7, 0.3, 1);
  --gv-radius-cta: 4px;
}
:root[data-theme="light"] {
  --gv-ground:  #faf7f0;
  --gv-paper-2: #f3eee2;
  --gv-engine:  #8a5e0d;
  --gv-seal:    #bc002d;
}
```
