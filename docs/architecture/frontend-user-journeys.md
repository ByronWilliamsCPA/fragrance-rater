---
title: "Frontend User Journeys"
schema_type: common
status: published
owner: core-maintainer
purpose: "Map fragrance-rater's frontend routes to actor flows and current test coverage."
tags:
  - architecture
  - testing
  - documentation
---

## Actors

- **Participant**: family member recording journal encounters, completing blind calibration, and reviewing recommendations.
- **Manager**: a participant with `canManagePrograms: true` (from `GET /calibration/access`), who additionally sets up and administers calibration programs.

## Flows

### Ordinary entry (Participant)

Search the fragrance catalog, record a journal encounter with a 1-5 rating, and correct it later if needed.

Route: `/ratings` (`RatingsPage`).

### Blind calibration and reveal (Participant)

Select an assignment, record blind observations against a coded sample with no visible brand/name/concentration, lock responses, then reveal identity once eligible.

Route: `/calibration` (`CalibrationPage`).

### Recommendation feedback and sampling (Participant)

Request recommendations, mark interest, and record a sampling follow-up.

Route: `/recommendations` (`RecommendationsPage`).

### Program setup (Manager only)

Define, activate, and enroll evaluators into calibration programs. Gated entirely in `App.tsx` (redirect + conditional render on `canManagePrograms`), with the real security boundary at the API (ADR-008), not this client-side check.

Route: `/programs` (`ProgramSetupPage`, `managerOnly: true`).

Routes and page components verified directly against `frontend/src/App.tsx` and
`frontend/src/routing/routes.ts`: all four routes and their page components
(`RatingsPage`, `CalibrationPage`, `RecommendationsPage`, `ProgramSetupPage`)
match the source exactly.

## Route-to-test-status

This table reflects real, current test-run output as of 2026-09-18 on this
worktree (branch `test/frontend-e2e-and-a11y`), not the intent behind any
earlier task in this plan. Commands run:

- `npm run test:run` (Vitest): **4 test files, 40 tests, all passed.**
- `npx playwright test` (mocked e2e, Tasks 5-9): **13 tests, all passed.**
- `npx playwright test --config=playwright.smoke.config.ts` (Task 10 real-backend
  smoke tier): **1 failed, 1 did not run**, both from
  `AggregateError: connect ECONNREFUSED ::1:8000` / `127.0.0.1:8000`. This is a
  connection failure, not a test-assertion failure: this sandbox has no Docker
  access, so no backend is listening on `localhost:8000` (the smoke config's
  corrected default, matching `docker-compose.yml`'s published port, not the
  `8080` the originating task brief guessed). The smoke tier could not be
  exercised here and its status below reflects that, not a claim of coverage.

Note on the smoke tier's shape: `e2e-smoke/disclosure-and-authorization.spec.ts`
uses Playwright's `request` fixture to call backend API endpoints directly
(`POST /api/v1/calibration/...`); it never calls `page.goto()` and does not
render any frontend route. Even when a live backend is available to run it
against, it verifies backend response invariants (no leaked identity fields,
403 on a non-manager activate call), not this frontend's rendering of any of
the four routes below. The "E2E-smoke" column is therefore "not applicable to
this route" for all four rows on route-rendering grounds, in addition to being
unrunnable in this sandbox.

| Route | Page | Unit/component (Vitest) | E2E-mocked (Playwright) | E2E-smoke (real backend) | Accessibility scan (axe-core) |
| --- | --- | --- | --- | --- | --- |
| `/ratings` | `RatingsPage` | Covered: exercised via `src/test/App.test.tsx` (encounter creation, correction, worn-by selection and clearing), 40/40 suite passing | Partially covered: `e2e/ordinary-entry.spec.ts` covers creation only; the correction form (`RatingsPage.tsx:213-259`) is covered at the Vitest tier only | Not run in CI/sandbox; requires live Docker backend, and this route is not exercised by the smoke spec even when a backend is available (see note above) | Covered: `e2e/accessibility.spec.ts` (`/ratings` case) passing, zero axe violations |
| `/calibration` | `CalibrationPage` | Covered: exercised via `App.test.tsx` (assignment progress, retry, non-detection submission, reveal eligibility) and `src/test/accessibility.test.tsx` (landmark/label structural check) | Covered: `e2e/blind-calibration.spec.ts` (reveal flow) and the keyboard-operability test in `e2e/accessibility.spec.ts`, both passing | Not run in CI/sandbox; requires live Docker backend, and this route is not exercised by the smoke spec (see note above) | Covered: `e2e/accessibility.spec.ts` (`/calibration` case) passing, zero axe violations |
| `/recommendations` | `RecommendationsPage` | Covered: exercised via `App.test.tsx` (interest recording, follow-up recording, explanation fallback, run restoration, evaluator-switch history race) | Covered: `e2e/recommendation-feedback.spec.ts` passing | Not run in CI/sandbox; requires live Docker backend, and this route is not exercised by the smoke spec (see note above) | Covered: `e2e/accessibility.spec.ts` (`/recommendations` case) passing, zero axe violations |
| `/programs` | `ProgramSetupPage` | Partially covered: `App.test.tsx` exercises program activation (with confirmation), adding a catalog version (with GTIN), the Fragella manual-check flow, and the manager operations dashboard view; it does **not** exercise creating/enrolling a reviewer into a program | Partially covered: `e2e/manager-authorization.spec.ts` covers only the route-authorization boundary (redirect for non-managers, access for managers, 403-degradation on a rejected manager action); no Playwright spec drives the internal forms (activation, enrollment, catalog-version add, Fragella check) | Not run in CI/sandbox; requires live Docker backend. When runnable, the smoke spec's 403-on-activate case does touch this route's backing endpoint, but only via direct API request, never through this page's UI | Covered: `e2e/accessibility.spec.ts` (`/programs` case) passing, zero axe violations |

## Known gaps

- `RatingsPage`'s correction/edit flow (`RatingsPage.tsx:213-259`) has no Playwright
  coverage: `e2e/ordinary-entry.spec.ts` only exercises creating a new encounter. The
  correction form is covered at the Vitest tier only (`src/test/App.test.tsx`).
- `ProgramSetupPage`'s internal forms have real but partial coverage: Vitest
  (`App.test.tsx`) covers activation, catalog-version addition, and the
  Fragella check; Playwright's mocked e2e covers only the authorization
  boundary (`manager-authorization.spec.ts`) and the one 403-degradation case.
  Reviewer enrollment into a program and the pilot-metrics detail views are
  untested in both tiers.
- The real-backend smoke tier (ADR-014) is not wired into per-PR CI; it must be
  run manually or via a separate, not-yet-built scheduled workflow. It is also
  API-only (no `page.goto()`), so even when it runs against a live backend it
  never exercises this frontend's rendering of any of the four routes above;
  treat it as a backend-invariant check, not frontend route coverage.
- No manual accessibility audit exists; coverage is automated-scan (axe-core,
  all six routes including `/` and `/about`) plus one keyboard journey
  (blind calibration).
- PROJECT-PLAN P1.8's "performance budgets for frontend" criterion is not
  addressed by this plan at all.

## Related

- [`docs/guides/pilot-participant.md`](../guides/pilot-participant.md), [`docs/guides/pilot-manager.md`](../guides/pilot-manager.md) (narrative walkthroughs)
- ADR-014 (e2e and accessibility strategy)
- PROJECT-PLAN.md, P1.8 entry gate
