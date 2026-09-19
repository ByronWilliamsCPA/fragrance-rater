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

The interface is modelled on the artifact it replaces: a **sensory-evaluation score sheet**.
That is the whole design, and every rule below follows from it.

The first attempt at this design pass produced a stack of rounded cards on a sage-and-cream
background, with an uppercase kicker above every heading, a pill-tray navigation component and a
three-column feature grid. It was rejected for looking generically generated, which it did. The
specific failures worth not repeating:

- Cards inside cards inside a container, so nothing had a hierarchy of its own.
- Four uppercase letterspaced kickers on one screen, which is a tic rather than a system.
- A marketing feature-grid on a tool five family members will use.
- A decorative gradient that carried no meaning.
- A concept ("two registers") described only in code comments, while both registers rendered as
  the same box in two colours.

What replaced it:

| | |
| :--- | :--- |
| **Surface** | The page is the sheet. There is no card layer at all: no element combines a background, a border and a shadow. Sections are separated by rules and space. |
| **Type** | A humanist sans for the whole interface: the structural discipline of a printed form, without the coldness of Helvetica. Monospace for codes, figures and timings. A serif *only* inside `.prose`, which is the About essay. No webfont, because the repository is REUSE-compliant and shipping a font is a licensing decision. |
| **Colour** | Ink on paper. Colour carries exactly two meanings, below. |
| **Shape** | Squared. `--radius` is 2px, the most a printed control ever gets. |
| **Density** | Dense, but not cramped. The type scale tops out at 1.75rem and there is no hero; the vertical rhythm was opened up in a second pass toward the Wikiparfum/NOSE reference. |

### The two registers

These are now visibly different rather than the same box recoloured.

| Register | Where | Treatment |
| :--- | :--- | :--- |
| **Open** | Encounters, recommendations, revealed identities, every ordinary control | Ink on paper, grotesque, sentence case |
| **Sealed** | Blind codes, coded samples, anything pre-reveal (ADR-005) | Deep blue, monospace, letterspaced, in a ruled box |

Keeping them apart is a data-integrity feature, not decoration: a coded sample must not be
mistakable for a named one at a glance. `--color-sealed-*` belongs to the sealed register and must
not be borrowed for ordinary UI.

Red, amber and green appear only in error, confirmation and success messages. There is no brand
accent. **If a new colour seems necessary, the layout is probably wrong.**

## Tokens

All tokens live in `frontend/src/styles/tokens.css`. Nothing outside that file should contain a
literal colour, spacing value or font stack.

| Group | Prefix | Notes |
| :--- | :--- | :--- |
| Colour | `--color-*` | Light and dark values; every pair is contrast-tested |
| Type family | `--font-ui`, `--font-mono`, `--font-prose` | `--font-prose` is for continuous prose, never for headings |
| Type scale | `--text-masthead`, `--text-title`, `--text-heading`, `--text-body`, `--text-label`, `--text-caption` | Fixed, not fluid |
| Spacing | `--space-1` … `--space-12` | 4px rhythm |
| Radius | `--radius` | One value: 2px |
| Rules | `--rule-hairline`, `--rule-section` | Hairline divides records; section rules sit under headings |
| Sizing | `--target-min`, `--measure`, `--sheet-max`, `--label-column` | `--target-min` is 44px, above the 24px WCAG 2.2 floor |
| Motion | `--motion-fast`, `--motion-ease` | Disabled entirely under `prefers-reduced-motion` |

There is no elevation scale. Shadows were removed with the cards.

### Stylesheet layers

`frontend/src/index.css` imports four files, in order. The order is load-bearing.

1. `tokens.css` — custom properties only
2. `base.css` — bare HTML elements
3. `layout.css` — the sheet, the masthead, the grids
4. `components.css` — component classes

### Themes

Dark mode is automatic from `prefers-color-scheme`, and an explicit choice from the masthead
toggle pins `data-theme` on the root element and persists in `localStorage`.

The dark palette is declared twice: once under
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
| Focus ring `#b3893e` vs filled button | 2.88:1 | 1.4.11, 2.4.11 |
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

No single colour can clear 3:1 against both paper and an ink-filled control. The ring carries the
paper surfaces; the halo carries the filled controls. Both tones are asserted against
both surface families in the contrast test. **Do not reduce this to a single-colour outline.**

### Selected state

Pressed toggles must not signal state by colour alone. State is carried by fill, a border that
clears 3:1, a weight change, a border-drawn check mark, and `aria-pressed`.

The one exception is the scales' "Not answered" option, which is checked on every untouched scale.
It is styled as a ticked box rather than a filled one, so an empty form does not put a heavy mark
on all twelve rows; its rule is scoped through `.scale-field__options` because it otherwise ties
on specificity with the generic checked rule and loses on source order.

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

## Perception, response, and certainty

The Specialty Coffee Association's Coffee Value Assessment separates a **descriptive** judgement
("how much smoke is there") from an **affective** one ("do I like smoke") from an overall
assessment. Collapsing them is the standard failure of consumer sensory forms, and this form
collapsed them: twelve scales ran together with nothing saying which were about the fragrance and
which were about the evaluator.

The calibration form now groups them under headings:

| Group | Holds | Why |
| :--- | :--- | :--- |
| **What you perceived** | intensity, sweetness, freshness, density, dryness, clean or soapy, earthy or rooty, bodily or animalic | Properties of the fragrance, whether or not the evaluator liked them |
| **How you responded** | liking, discomfort | The evaluator's own reaction. `discomfort` is physical, and is not the same as disliking the smell |
| **How sure you are** | confidence, familiarity | How much weight the record should carry |

Skin-test scales split the same way, into performance and response.

**This is presentational only, and it does not close the underlying gap.** The schema
(`schemas/calibration.py`, ADR-010) has perception and overall affect but **no per-dimension
preference**: an evaluator can record "sweetness 5" and "liking 3", but not *that they dislike
sweetness*. That is the signal that would let the model explain itself rather than only rank, and
adding it is a schema decision, not a design one.

The 0-100 recommendation figure is labelled "affinity score" and carries a standing qualification
that it ranks rather than predicts, because ADR-007 forbids labelling it a probability,
confidence, predicted liking, or accuracy.

## Imagery

There is none, and the constraint is not cosmetic. The core flow is blind: showing a bottle before
reveal is what ADR-005 exists to prevent. Imagery can only appear post-reveal, in recommendations,
and in the catalog, so it cannot carry the app's visual identity the way it does on a commercial
perfume site. The fragrance model also has no image field of any kind today.

## The observation log

A sample's saved timepoints render as a table, ordered blotter-then-skin and earliest-first within
each stage. Every professional evaluation sheet this interface is modelled on is laid out this way,
because the point of recording several timepoints is reading the evaporation curve *down a column*:
intensity falling while liking rises is the whole signal, and it is invisible in a list of prose
lines.

This is the one place a real `<table>` is the right structure, and the one place two-dimensional
scrolling is allowed on a narrow screen. WCAG 1.4.10 Reflow exempts content that needs a
two-dimensional layout to be meaningful, and collapsing the log into stacked cards on a phone would
destroy exactly the down-column comparison it exists for.

The API does not guarantee an order, so the component sorts. An out-of-sequence row in an
evaporation curve is actively misleading rather than merely untidy, and
`e2e/accessibility.spec.ts` supplies deliberately unsorted rows to prove the component sorts them
rather than that the fixture arrived sorted.

## Conventions

- **No literal colours outside `tokens.css`.** Add a token, and add its pair to the contrast test.
- **No cards.** If a change adds an element with a background, a border and a shadow together, it
  is reintroducing the layer this design removed. Use a rule.
- **The serif is for `.prose` only.** It is a reading face, not a heading face.
- **Every family in `--font-ui` must be humanist.** The stack degrades across platforms, so a
  neo-grotesque or geometric entry would make the interface read differently depending on the
  machine.
- **Kickers must carry data.** `Sample 1`, `Choice 3` and `Manager` earn their place; `Today`,
  `Discover` and `Journal` above a heading that already says so do not.
- **Every `<progress>` needs an accessible name.** A bare one is announced only as a percentage.
- **New interactive components** get a target-size check and, if they introduce a colour, a
  contrast-test entry.
- **Copy follows the About page's register:** patient, concrete, precisely qualified. No
  aphorisms, no three-item triads, no antithesis-shaped one-liners.
