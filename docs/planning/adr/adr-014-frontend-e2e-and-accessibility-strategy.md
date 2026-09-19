# ADR-014: Frontend E2E and Accessibility Testing Strategy

> **Status**: Accepted; amended 2026-09-19 (conformance target raised to WCAG 2.2 AA)
>
> **Date**: 2026-09-18

## TL;DR

Adopt Playwright (`@playwright/test`) as the frontend e2e framework with a two-tier strategy: network-mocked specs for the fast per-PR gate, plus a thin real-backend smoke tier for exactly the two invariants a mock cannot prove (pre-reveal identity omission, manager-endpoint rejection of non-managers). Enforce WCAG 2.2 AA (raised from 2.1 AA on 2026-09-19) via an automated axe-core scan in the same mocked suite, plus `eslint-plugin-jsx-a11y` at lint time, plus token-level contrast and document-title tests for the criteria axe cannot evaluate.

## Context

### Problem

PROJECT-PLAN.md's P1.8 entry gate requires e2e coverage of named flows (ordinary entry, blind calibration, recommendation feedback, sampling) and "authorization and disclosure tests cover every manager route." As of 2026-09-18 the frontend has no e2e tests, no e2e framework, and no automated accessibility scanning.

### Constraints

This app is a 6-page personal/family tool (ADR-001), not a multi-tenant production service, but it drives real purchase decisions for family members and handles a controlled-disclosure workflow (ADR-005) where premature identity reveal is a real integrity failure, not just a UX bug. That combination ruled out both extremes: a full CYO_Adventure-scale multi-tier real-backend suite (disproportionate to a 6-page app) and a mocked-only suite (insufficient for the one property, disclosure integrity, that a mock cannot verify by construction, since it only proves the frontend renders what it was told).

### Significance

Sets the pattern every future e2e and accessibility spec follows.

## Decision

**E2E**: `@playwright/test` in `frontend/e2e/`, with a shared `mockApi()` helper (`frontend/e2e/support/mock-api.ts`) intercepting `**/api/v1/**`, mirroring the existing Vitest `vi.mock('axios', ...)` convention at the network layer. Fixtures are pinned to the generated OpenAPI client's types via TypeScript `satisfies` assertions, so a backend schema change that regenerates the client also surfaces any fixture drift as a type error. A second, separate suite (`frontend/e2e-smoke/`, `playwright.smoke.config.ts`) runs against a real `docker compose` stack and asserts exactly two invariants: the API never returns identity data before reveal, and the API rejects non-manager calls to manager-only endpoints. This tier is intended to run nightly or pre-deploy, not on every PR; no such workflow exists yet.

**Accessibility**: WCAG 2.1 AA (superseded by the 2026-09-19 amendment below, which raises this to WCAG 2.2 AA and adds two tiers axe cannot replace), enforced as a single blocking tier inside the mocked e2e suite (`frontend/e2e/accessibility.spec.ts`) using `@axe-core/playwright` against every route with populated fixtures (not empty ones, which would scan a blank shell), plus one keyboard-only journey test, since automated rule scanning does not check keyboard operability. `eslint-plugin-jsx-a11y`'s recommended rules run at lint time.

### Rationale

The committed e2e suite belongs in `frontend/e2e/` using `@playwright/test`, per the Decision above. Network-layer mocking keeps the per-PR CI loop fast and deterministic. The smoke tier exists because this app's controlled-disclosure design (ADR-005) makes premature identity reveal a genuine trust failure for a family-use product, not a cosmetic bug, and only a real backend call can prove the API itself withholds identity, a property the frontend's mocked tests structurally cannot verify. axe-core is the industry-standard automated ruleset and integrates directly with the same Playwright suite, avoiding a second test runner.

## Options Considered

- **Mocked-only e2e, no real-backend tier** (this plan's first-draft position): rejected on review; leaves the disclosure and authorization invariants unproven by anything except "the frontend renders what the mock told it to render."
- **Full real-backend e2e tier for every flow** (CYO_Adventure's pattern): rejected as disproportionate; this app has one deployment target and no staged-environment cadence to support it.
- **Two separate ADRs for e2e and accessibility**: rejected after review; both share one Playwright suite and CI job, and splitting them produced a second ADR with no independent decision of its own.
- **Two-tier accessibility gate (per-PR + weekly), mirroring CYO_Adventure's ADR-029**: rejected for now; this project has no weekly-rehearsal cadence to hang a second tier off of.

## Consequences

### Positive

- Fast, deterministic per-PR CI, with the one property that actually needs a real backend (disclosure/authorization) verified by a real backend, not assumed.
- Fixture-contract check (`tsc -b` against the committed `frontend/src/client/types.gen.ts` snapshot) catches e2e fixtures that drift from that committed snapshot before they silently produce a passing-but-wrong mocked spec. This is narrower than catching live backend schema drift: nothing in this repo or its CI regenerates the snapshot from the running backend, so the check can only prove fixture-to-snapshot consistency, not fixture-to-live-backend consistency.
- Directly closes the e2e portion of PROJECT-PLAN P1.8.

### Trade-offs

- The smoke tier is not wired into per-PR CI (Task 12); it requires a Compose stack in Actions, which is a separate infrastructure decision left open for the user.
- `ProgramSetupPage`'s internal manager actions beyond the route boundary (program definition, enrollment, metrics) remain untested by both tiers; only the authorization boundary and the two named invariants are covered.
- Automated axe-core scanning catches a meaningful but partial subset of real accessibility issues (no manual assistive-technology testing).

### Technical Debt

No CI wiring exists yet for the real-backend smoke tier's cadence (nightly/pre-deploy); no manual accessibility audit process is defined; `ProgramSetupPage`'s internal actions beyond authorization have no test coverage of any kind. The generated API client snapshot (`frontend/src/client/types.gen.ts`) that the fixture-contract check pins against has no automated freshness check against the live backend schema (no CI step runs `generate-client`), so it can silently drift stale over time without anything failing.

## Implementation

`frontend/playwright.config.ts`, `frontend/e2e/support/mock-api.ts`, per-flow specs under `frontend/e2e/`, `frontend/playwright.smoke.config.ts` and `frontend/e2e-smoke/` for the real-backend tier, `frontend/eslint.config.js`'s `jsxA11y.flatConfigs.recommended`. CI wiring in `.github/workflows/ci.yml`'s `frontend` and `frontend-e2e` jobs.

## Validation

Re-review if a production incident traces to a frontend/backend contract mismatch the fixture-contract check should have caught but didn't, if the smoke tier's two invariants prove insufficient after a real incident, or when planning work that adds meaningful new manager-side functionality to `ProgramSetupPage`.

## Amendment, 2026-09-19: WCAG 2.2 AA and the limits of automated scanning

### What changed

The conformance target is **WCAG 2.2 AA**, replacing 2.1 AA. 2.2 is a superset of 2.1, so nothing
previously conformant regressed; the additions that bind this application are 2.4.11 Focus Not
Obscured, 2.5.8 Target Size (Minimum), and 3.3.7 Redundant Entry. The DOJ ADA Title II rule cites
WCAG 2.1 AA, so this target clears that benchmark with margin rather than merely meeting it.

The mocked axe suite now scans with the `wcag22aa` tag, and scans **every route in both colour
schemes**, because the 2026-09-19 design pass introduced a dark theme and a palette scanned in one
theme says nothing about the other.

### Why two non-axe tiers were added

This ADR's original Consequences section conceded that "automated axe-core scanning catches a
meaningful but partial subset of real accessibility issues". The design pass measured how partial.

Starting from a suite in which axe reported **zero violations** on all six routes, widened to
`wcag22aa` and `best-practice` at both 1280px and 360px, five genuine WCAG failures were still
present:

| Failure | Measured | Guideline | Why axe missed it |
| :--- | :--- | :--- | :--- |
| Focus ring vs page background | 2.88:1 | 1.4.11, 2.4.11 | axe does not evaluate focus-indicator contrast |
| Focus ring vs filled brand button | 2.88:1 | 1.4.11, 2.4.11 | as above |
| Input border on white | 1.73:1 | 1.4.11 | axe does not evaluate control-boundary contrast |
| `aria-pressed` state outline | 1.85:1 | 1.4.11, 1.4.1 | as above |
| Identical `document.title` on all six routes | n/a | 2.4.2 | a title was present on every route; axe does not compare them |

Two blocking tiers therefore join the axe scan:

- `frontend/src/test/contrast.test.ts` parses the real token values out of `tokens.css` and
  re-derives every declared pair in both themes, against 4.5:1 for text and 3:1 for UI boundaries
  and state. It also asserts the two dark-theme declaration blocks stay identical, since custom
  properties cannot be aliased across an `@media` boundary and remain overridable.
- `frontend/src/test/documentTitle.test.tsx` asserts a distinct, descriptive title per route and
  across in-app navigation.

The e2e suite additionally asserts no interactive target falls below 24px at a 360px viewport
(2.5.8) and that keyboard focus paints both tones of the indicator.

### Consequence for the focus indicator

No single colour clears 3:1 against both a pale paper surface and a filled dark-green button, so
the indicator is a two-tone ring (technique G195): `--color-focus-ring` carries light surfaces and
`--color-focus-halo` carries filled buttons. Reducing it to a single-colour outline reintroduces
the original failure, and the contrast test is what prevents that.

### Still not covered

No manual assistive-technology testing. Cognitive-load and plain-language review of the calibration
scale wording is a human judgement the maintainer still owes before F1; see
[the design system](../../development/design-system.md) for the sign-off this depends on.

### Re-review triggers

In addition to those in Validation below: re-review if WCAG 2.3 reaches Recommendation, if a manual
assistive-technology audit finds a class of defect none of these tiers covers, or if the design
system gains a second colour theme beyond light and dark.

## Related

- [PROJECT-PLAN.md](../PROJECT-PLAN.md): P1.8 entry gate this ADR closes the e2e portion of
- [ADR-001](adr-001-initial-architecture.md): Docker Compose monolith
- [ADR-005](adr-005-controlled-calibration.md): controlled calibration and disclosure state
- [ADR-008](adr-008-authentication-and-production-boundary.md): Authentik/Traefik trust boundary
- CYO_Adventure ADR-029 (cross-project reference for the two-tier accessibility pattern this ADR deliberately does not adopt yet)
