---
title: "Design System"
schema_type: common
status: published
owner: core-maintainer
purpose: "Interface design tokens, component language, and the accessibility contract they satisfy."
tags:
  - development
  - frontend
  - accessibility
  - design
---

The frontend design system, introduced in the 2026-09-19 design pass before the F1 family pilot.

Its governing decision is [ADR-014](../planning/adr/adr-014-frontend-e2e-and-accessibility-strategy.md),
which sets **WCAG 2.2 AA** as the conformance target.

## Design intent

The product holds two things at once: a measuring instrument with blind protocols and locked
evidence, and a personal journal of what somebody actually smelled. The interface carries both,
in two registers that are deliberately not interchangeable.

| Register | Where it appears | Treatment |
| :--- | :--- | :--- |
| **Journal** | Ordinary encounters, recommendations, revealed identities, the landing page | Warm paper surfaces, serif display type, brand green |
| **Sealed** | Blind codes, coded samples, anything pre-reveal (ADR-005) | Cool slate, letterspaced monospace, no warm hues |

Keeping the two apart is a data-integrity feature rather than decoration: a coded sample must never
be mistakable for a named one at a glance. `--color-sealed-*` is reserved for the sealed register
and must not be reused for ordinary UI.

## Tokens

All tokens live in `frontend/src/styles/tokens.css`. Nothing outside that file should contain a
literal colour, spacing value, or font stack.

| Group | Prefix | Notes |
| :--- | :--- | :--- |
| Colour | `--color-*` | Light and dark values; every pair is contrast-tested |
| Type family | `--font-display`, `--font-ui`, `--font-mono` | Display is the editorial serif; UI is the instrument sans; mono is for blind codes |
| Type scale | `--text-*` | `display` and `title` are fluid via `clamp()`; the rest are fixed |
| Spacing | `--space-1` … `--space-16` | 4px rhythm |
| Radius | `--radius-sm` … `--radius-pill` | |
| Sizing | `--target-min`, `--measure`, `--shell-max` | `--target-min` is 44px, above the 24px WCAG 2.2 floor |
| Elevation | `--shadow-sm/md/lg` | Re-tuned for dark, where the light values are invisible |
| Motion | `--motion-fast/base/ease` | All transitions are disabled under `prefers-reduced-motion` |

### Stylesheet layers

`frontend/src/index.css` imports four files, in order. The order is load-bearing.

1. `tokens.css` — custom properties only
2. `base.css` — bare HTML elements
3. `layout.css` — page frame and grids
4. `components.css` — component classes

### Themes

Dark mode is automatic from `prefers-color-scheme`, and an explicit choice from the header toggle
pins `data-theme` on the root element and persists in `localStorage`.

The dark palette is therefore declared twice: once under
`@media (prefers-color-scheme: dark) :root:not([data-theme='light'])` and once under
`:root[data-theme='dark']`. Custom properties cannot be aliased across an `@media` boundary and
still remain overridable, so the duplication is deliberate.
`frontend/src/test/contrast.test.ts` asserts the two blocks declare identical colours, which is
what stops them drifting apart.

## Accessibility contract

The target is **WCAG 2.2 AA**, which supersedes the 2.1 AA the original ADR-014 set. It is a
superset, so nothing previously conformant regressed. The US Department of Justice ADA Title II
rule cites WCAG 2.1 AA, so 2.2 AA clears that benchmark with margin.

### What the automated tiers each prove

| Tier | Runs | Catches |
| :--- | :--- | :--- |
| `eslint-plugin-jsx-a11y` | lint | Static markup errors |
| `src/test/contrast.test.ts` | Vitest | Every declared colour pair, both themes, re-derived from the real token values |
| `src/test/documentTitle.test.tsx` | Vitest | 2.4.2, per route and across in-app navigation |
| `e2e/accessibility.spec.ts` | Playwright + axe-core | Six routes × two themes at `wcag22aa`, target size at 360px, focus indicator, keyboard operability |

**A passing axe scan is not a conformance claim.** The design pass that produced this system began
from a suite where axe reported zero violations on all six routes, and still found five real
WCAG failures that axe structurally cannot see:

| Failure | Measured | Guideline |
| :--- | :--- | :--- |
| Focus ring `#b3893e` vs page background | 2.88:1 | 1.4.11, 2.4.11 |
| Focus ring `#b3893e` vs filled brand button | 2.88:1 | 1.4.11, 2.4.11 |
| Input border `#bbc8bf` on white | 1.73:1 | 1.4.11 |
| `aria-pressed` state outline `#9bbcaf` | 1.85:1 | 1.4.11, 1.4.1 |
| `document.title` identical on all six routes | — | 2.4.2 |

axe checks rendered text contrast, not a palette, never focus-indicator contrast, and only the one
theme the browser happens to be in. The contrast and title tests exist precisely to cover that gap.
Manual assistive-technology testing remains outside all of these tiers.

### Focus indicator

A two-tone ring (WCAG technique G195):

```css
:focus-visible {
  outline: 3px solid var(--color-focus-ring);
  outline-offset: 2px;
  box-shadow: 0 0 0 5px var(--color-focus-halo);
}
```

No single colour can clear 3:1 against both a pale paper surface and a filled dark-green button.
The ring carries light surfaces; the halo carries filled buttons. Both tones are asserted against
both surface families in the contrast test. **Do not reduce this to a single-colour outline.**

### Selected state

Pressed toggles must not signal state by colour alone. State is carried by fill, a border that
clears 3:1, a weight change, a border-drawn check mark, and `aria-pressed`.

Two rules protect this and must stay:

- The hovered variants of `[aria-pressed='true']` are listed **explicitly**. A pressed control sets
  its own foreground colour; any hover rule that outranks the pressed rule repaints the background
  underneath that foreground. A hovered, selected sample measured 1.2:1 before this was fixed.
- The check mark is drawn from borders on an empty pseudo-element, not a `content: '✓'` glyph.
  CSS generated content contributes to the accessible name in Chromium, which renamed every pressed
  button to "✓Interested".

### Target size

`--target-min` is 44px, well above the 24px minimum in 2.5.8. The e2e suite asserts no interactive
target falls below 24px in either dimension at a 360px viewport, on every route.

## Calibration scales

The ten perceptual dimensions previously rendered as raw database column names passed through
`text-transform: capitalize` ("Clean Soapy", "Bodily Animalic") above bare 0-5 dropdowns, with no
statement anywhere of what either end of a scale meant.

Display wording now lives in `frontend/src/content/calibrationScales.ts` and renders through
`ScaleField`, a radio group with visible options and both anchors.

> **This wording is draft and needs maintainer sign-off before F1 records any real observation.**
> The response columns are typed and range-bounded in `schemas/calibration.py` (ADR-010) but carry
> no semantic definitions in any accepted document. The anchors therefore describe scale
> *direction* only and deliberately avoid perfumery definitions this project has not established.
> Once approved, the definitions belong in the calibration guide, with that module referencing
> them rather than owning them.

A radio group is one tab stop with arrow-key traversal, so the ten dimensions no longer cost ten
tab stops each to skip. Serialisation is unchanged: the radios share the field `name`, and the
explicit "Not answered" option submits an empty string exactly as the placeholder option did, which
keeps a deliberate zero distinguishable from an unanswered scale.

## Conventions

- **No literal colours outside `tokens.css`.** Add a token instead, and add its pair to the
  contrast test.
- **Eyebrow text is written in sentence case** and uppercased in CSS. Literal all-caps source text
  is read letter-by-letter by some screen readers.
- **Every `<progress>` needs an accessible name.** A bare one is announced only as a percentage.
- **Headings carry hierarchy.** `h3` is `--text-heading`, never body size.
- **New interactive components** get a target-size check and, if they introduce a colour, a
  contrast-test entry.
