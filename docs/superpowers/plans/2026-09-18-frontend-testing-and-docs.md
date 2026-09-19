---
title: "Frontend Testing and Documentation Improvement Plan"
schema_type: planning
component: Strategy
source: "docs/planning/PROJECT-PLAN.md#P1.8"
status: draft
owner: core-maintainer
purpose: "Close the PROJECT-PLAN P1.8 frontend test-strategy gate with e2e tests, CI wiring, accessibility scanning, and journey/ADR documentation."
tags:
  - testing
  - architecture
  - adr
  - ci_cd
  - quality_assurance
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Goal

Close the frontend half of PROJECT-PLAN's P1.8 entry gate: give fragrance-rater's frontend an e2e test suite covering its named flows, wire all frontend tests into CI, add automated accessibility scanning, and document the frontend's user journeys and the architectural decisions this plan makes.

## Architecture

Add `@playwright/test` as a committed e2e suite under `frontend/e2e/`, mocking the backend at the network layer (`page.route()`) for the fast per-PR tier, backed by a thin real-backend smoke tier for the two security-load-bearing invariants a mock cannot prove. Wire Vitest unit tests, typecheck, lint, build, and the mocked Playwright suite into a new frontend CI job. Add `@axe-core/playwright` for automated WCAG 2.1 AA scanning and `eslint-plugin-jsx-a11y` at lint time, applied *before* the flow specs pin selectors to the current DOM. Document decisions in a single ADR and consolidate the two existing prose user guides into a single developer-facing journey doc with a route-to-test-status table generated from the actual passing suite, not asserted in advance.

## Tech Stack

Playwright (`@playwright/test`) for e2e, `@axe-core/playwright` for automated accessibility scanning, `eslint-plugin-jsx-a11y` for lint-time accessibility checks, added to the existing Vite + React 19 + TypeScript + Vitest + React Testing Library stack. No new runtime dependencies.

---

## Revision Note

This plan was reviewed by a principal-level architecture reviewer (opus) before implementation. Verdict: NEEDS_REVISION, applied here. Key changes from the reviewer's findings, each addressed by a specific task below:

1. **Mocked-only e2e cannot prove the disclosure/authorization invariants P1.8 actually cares about** (the API omitting `identity` pre-reveal; the API rejecting non-manager calls to manager endpoints) because a mock only proves the frontend renders what it was told to render. Added Task 10 (real-backend smoke tier, 2 invariants only, not a full second suite).
2. **A fixture-contract check was missing**, so nothing would catch `mock-api.ts` fixtures drifting from the real API shape (which happened in this plan's first draft: `RecommendationRun.items` should be `.impressions`, `Enrollment.samples` should be `.presentations`). Added Task 3.
3. **Several flow specs had concrete shape/selector bugs** verified against the real components. Fixed in Tasks 6-9 below.
4. **Task sequencing had two real conflicts**: three tasks editing the same CI file need serializing (not "independent"), and the accessibility tasks were scheduled after the flow specs, meaning a11y fixes would break the selectors the flow specs already pinned. Reordered: accessibility (Tasks 4-5) now precedes the flow specs (Tasks 6-9).
5. **ADR-015 was a section pretending to be an ADR.** Folded into ADR-014 as a section (Task 14).
6. **Task 16 (now 17) cannot claim P1.8 is fully closed**: performance budgets remain explicitly out of scope, and even with Task 10's smoke tier, `ProgramSetupPage`'s internal manager actions beyond the route boundary remain untested. Task 17 records partial closure with both gaps named, not a blanket "closed."

---

## Decisions Locked By This Plan

1. **E2E backend strategy = network-layer mocking for the fast per-PR tier, plus a thin real-backend smoke tier for exactly two disclosure/authorization invariants** (not a full duplicate real-backend suite). Documented in ADR-014.
2. **Coverage mechanism = a single `frontend` Codecov surface flag**, per `.claude/standards/testing.md` §16.2's exception for a Vitest frontend that can't split by test type in one run.
3. **Accessibility target = WCAG 2.1 AA, single blocking CI tier**, documented as a section within ADR-014 rather than a separate ADR, since it shares the same Playwright suite and CI job as the e2e strategy.

---

## Codebase Discovery (already performed)

Confirmed via direct file reads and a scoped Explore subagent pass (re-verified by the opus review pass against `App.tsx`, `routing/routes.ts`, `hooks/useAppData.ts`, `api/client.ts`, `api/types.ts`, `RatingsPage.tsx`, `CalibrationPage.tsx`, `RecommendationsPage.tsx`, `vite.config.ts`, `package.json` as of 2026-09-18). Treat as current at plan-authoring time; re-check any file a task quotes before editing it, since implementation may take place days or weeks later.

- Dev server port: `3000` (`frontend/vite.config.ts`). Production API base URL: `/api/v1` (`frontend/src/api/client.ts`, `apiV1BaseUrl()`).
- **`useAppData` fetches on mount for every route**: `/reviewers`, `/calibration/access`, `/calibration/programs`, `/calibration/enrollments`. Any e2e spec that doesn't mock all four gets an `ErrorState` render instead of the target page. This is the root cause of two spec bugs the opus review caught; fixed via a shared `bootstrapRoutes()` fixture in Task 2.
- Routes and paths (`frontend/src/routing/routes.ts`, `frontend/src/App.tsx`): `home`→`/`, `calibration`→`/calibration`, `ratings`→`/ratings`, `recommendations`→`/recommendations`, `programs`→`/programs` (`managerOnly: true`), `about`→`/about`.
- The **only** manager-gated route is `/programs` (`ProgramSetupPage`). Gating is entirely in `App.tsx`: a redirect for non-managers plus a conditional render on `appData.capabilities.canManagePrograms`. `ProgramSetupPage` itself performs no internal capability check, and the real security boundary is the API (per ADR-008's Authentik/Traefik trust boundary), not this client-side redirect.
- `Enrollment` has a `presentations` array (not `samples`); each entry needs `session_id`, `skin_planned`, `observations: []` alongside `blind_code`/`blotter_locked`/`skin_locked`/`identity`. `reveal_blocker` is `null` when absent, not `undefined`.
- `RecommendationRun` is `{ id, reviewer_id, created_at, impressions: [...] }` (not `items`); each impression needs `fragrance_name`, `fragrance_brand`, `match_percent`, `shown_at`, `responses: []`.
- PROJECT-PLAN P1.8's named e2e flows map to real pages: "ordinary entry" → `RatingsPage`; "blind calibration" → `CalibrationPage`; "recommendation feedback" and "sampling" → `RecommendationsPage`.
- Existing Vitest/RTL convention (`frontend/src/test/App.test.tsx`, `accessibility.test.tsx`): `vi.hoisted()` + `vi.mock('axios', ...)`, `beforeEach` resets `window.history` and mock responses, async assertions via `await screen.findByRole(...)`.
- `.pre-commit-config.yaml`'s `validate-front-matter` hook runs on `^docs/(?!planning/).*\.md$`. ADRs live under `docs/planning/adr/` and are **exempt** (confirmed: `adr-001-initial-architecture.md` has no YAML frontmatter). The next available ADR number is `adr-014`.
- Allowed frontmatter tags (`docs/_data/tags.yml`) confirmed to include: `testing`, `architecture`, `adr`, `ci_cd`, `documentation`, `quality_assurance`, `planning`. There is no `frontend` or `accessibility` tag; do not invent one.
- `codecov.yml` currently defines `unit`/`integration`/`security` flags pointed at `src/fragrance_rater/` only. No frontend flag exists yet.
- `.github/workflows/ci.yml` calls the org's reusable `python-ci.yml` workflow only; it has no frontend job at all.
- `frontend/src/client/` is the `@hey-api/openapi-ts`-generated client (`npm run generate-client`), excluded from Vitest coverage but importable for its generated types (conventionally `types.gen.ts`; confirm the exact export names at implementation time by grepping the generated file, since they're derived from the live backend's OpenAPI schema, not fixed by this plan).

---

## Task 1: Install and configure Playwright

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/playwright.config.ts`
- Modify: `frontend/.gitignore` (create the file if it doesn't already exist as a nested gitignore; otherwise the repo root `.gitignore` is the right target; check which convention `frontend/` already uses before choosing)

- [ ] **Step 1: Install Playwright**

Run (from `frontend/`):
```bash
npm install -D @playwright/test
npx playwright install --with-deps chromium
```
Expected: `@playwright/test` appears in `frontend/package.json` devDependencies and `frontend/package-lock.json`; Chromium binaries installed.

- [ ] **Step 2: Add e2e scripts**

Modify `frontend/package.json` `scripts` block (add these entries, keep all existing ones):
```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint \"src/**/*.{ts,tsx}\"",
    "lint:fix": "eslint \"src/**/*.{ts,tsx}\" --fix",
    "preview": "vite preview",
    "test": "vitest",
    "test:run": "vitest run",
    "test:coverage": "vitest run --coverage",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui",
    "format": "prettier --write \"src/**/*.{ts,tsx,css,json}\"",
    "format:check": "prettier --check \"src/**/*.{ts,tsx,css,json}\"",
    "typecheck": "tsc --noEmit",
    "generate-client": "openapi-ts --input http://localhost:8000/openapi.json --output ./src/client --client axios"
  }
}
```

- [ ] **Step 3: Create the Playwright config**

Create `frontend/playwright.config.ts`:
```typescript
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: 'npm run build && npm run preview -- --port 3000',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
```

- [ ] **Step 4: Ignore Playwright's local run artifacts**

Add to `.gitignore` (whichever file governs `frontend/`, per Step 0's check):
```
playwright-report/
test-results/
blob-report/
```

- [ ] **Step 5: Verify the config loads**

Run: `npx playwright test --list`
Expected: exits 0 with `Total: 0 tests in 0 files`. If the webServer fails to start, run `npm run build && npm run preview -- --port 3000` manually first to see the real error.

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/playwright.config.ts frontend/.gitignore
git commit -S -m "test(frontend): add Playwright e2e infrastructure"
```

---

## Task 2: Shared e2e mock-API helper

**depends-on: Task1 [output]**

**Files:**
- Create: `frontend/e2e/support/mock-api.ts`

- [ ] **Step 1: Write the shared route-mocking helper with correct API shapes**

Fixes two shape bugs the opus review caught in this plan's first draft (`RecommendationRun.items` should be `.impressions`, `Enrollment.samples` should be `.presentations`), and adds `bootstrapRoutes()` so every spec mocks the four endpoints `useAppData` fetches on mount, instead of each spec rediscovering that requirement independently.

Create `frontend/e2e/support/mock-api.ts`:
```typescript
import type { Page, Route } from '@playwright/test'

export interface MockRoutes {
  [path: string]: unknown | ((route: Route) => Promise<void> | void)
}

/**
 * Intercepts every /api/v1/* request and resolves it from a path -> response
 * map. Unmatched paths reject with 501 so a missing fixture fails loudly
 * instead of hanging on a real network call.
 */
export async function mockApi(page: Page, routes: MockRoutes): Promise<void> {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname.replace(/^.*\/api\/v1/, '')
    const handler = routes[path]

    if (handler === undefined) {
      await route.fulfill({ status: 501, body: `No mock for ${route.request().method()} ${path}` })
      return
    }
    if (typeof handler === 'function') {
      await handler(route)
      return
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(handler) })
  })
}

export const reviewers = [{ id: 'r1', name: 'Evaluator One' }]
export const participantAccess = { username: 'family-member', manager: false }
export const managerAccess = { username: 'manager', manager: true }

/**
 * useAppData fetches these four endpoints on mount for EVERY route. Any
 * spec that omits one gets an ErrorState render instead of its target page.
 */
export function bootstrapRoutes(access: typeof participantAccess | typeof managerAccess = participantAccess): MockRoutes {
  return {
    '/reviewers': reviewers,
    '/calibration/access': access,
    '/calibration/programs': [{ id: 'p1', name: 'Baseline', version: '1' }],
    '/calibration/enrollments': [{ id: 'enr1', program_id: 'p1', reviewer_id: 'r1' }],
  }
}

export const fragranceCatalog = [
  { id: 'f1', brand: 'House', name: 'Signature', concentration: 'EDP', version_key: '1' },
]

export function enrollmentFixture(revealed: boolean) {
  return {
    id: 'enr1',
    revealed,
    reveal_eligible: true,
    reveal_blocker: null,
    presentations: [
      {
        id: 'samp1',
        session_id: 'sess1',
        position: 1,
        blind_code: 'ABC-123',
        blotter_locked: revealed,
        skin_locked: false,
        skin_planned: false,
        identity: revealed ? { brand: 'House', name: 'Signature', concentration: 'EDP' } : null,
        observations: [],
      },
    ],
  }
}

export function recommendationRunFixture(interested = false) {
  return {
    id: 'run1',
    reviewer_id: 'r1',
    created_at: '2026-09-18T00:00:00Z',
    impressions: [
      {
        id: 'imp1',
        rank: 1,
        fragrance_name: 'Signature',
        fragrance_brand: 'House',
        match_percent: 87,
        shown_at: '2026-09-18T00:00:00Z',
        responses: interested ? [{ id: 'resp1', impression_id: 'imp1', interested: true, sampling_state: null, created_at: '2026-09-18T00:00:01Z' }] : [],
      },
    ],
  }
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit -p .`
Expected: no new type errors. If `tsc` reports `e2e/` is outside `tsconfig`'s `include`, read `frontend/tsconfig.json` first and add `"e2e"` to its `include` array before proceeding.

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/support/mock-api.ts
git commit -S -m "test(frontend): add shared e2e API mocking helper"
```

---

## Task 3: Fixture-contract check against the generated API client

**depends-on: Task2 [output]**

**Files:**
- Modify: `frontend/e2e/support/mock-api.ts`

This is the guardrail the opus review flagged as missing: nothing currently catches `mock-api.ts`'s fixtures drifting from the real API shape when the backend changes and `npm run generate-client` regenerates `frontend/src/client/`. A compile-time `satisfies` check is cheaper than a runtime schema validator and fits this app's scale.

- [ ] **Step 1: Find the generated type names**

Run: `grep -n "^export (type|interface)" frontend/src/client/types.gen.ts | head -30`
Expected: a list including the types backing `Enrollment`, `RecommendationRun`, `RecommendationResponse`, and `CalibrationAccess` (exact names vary by what `@hey-api/openapi-ts` generated from the live backend schema; use whatever names actually appear).

- [ ] **Step 2: Add `satisfies` assertions to the fixtures**

Modify `frontend/e2e/support/mock-api.ts`: import the real generated types found in Step 1 and add `satisfies` to each fixture function's return value, e.g.:
```typescript
import type { EnrollmentRead, RecommendationRunRead } from '../../src/client/types.gen'

export function enrollmentFixture(revealed: boolean) {
  return {
    // ...unchanged body from Task 2...
  } satisfies EnrollmentRead
}

export function recommendationRunFixture(interested = false) {
  return {
    // ...unchanged body from Task 2...
  } satisfies RecommendationRunRead
}
```
Use the exact type names from Step 1's grep output; they will not literally be `EnrollmentRead`/`RecommendationRunRead` unless the backend schema happens to name them that.

- [ ] **Step 3: Run typecheck and fix any mismatch**

Run: `cd frontend && npx tsc --noEmit -p .`
Expected: PASS. Any mismatch here means a fixture shape is wrong relative to the real API right now, before any spec is written against it, catching exactly the class of bug the opus review found in this plan's own first draft.

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/support/mock-api.ts
git commit -S -m "test(frontend): pin e2e fixtures to the generated API client types"
```

---

## Task 4: Lint-time accessibility rules

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/eslint.config.js`

Independent of Tasks 1-3. Placed *before* the flow specs (Tasks 6-9) so any component change this task requires happens before those specs pin selectors to the current DOM, per the opus review's sequencing finding.

- [ ] **Step 1: Install the plugin**

Run (from `frontend/`): `npm install -D eslint-plugin-jsx-a11y`

- [ ] **Step 2: Wire it into the flat config**

Modify `frontend/eslint.config.js` (full new contents):
```javascript
import js from '@eslint/js'
import globals from 'globals'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist', 'node_modules', 'src/client'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended, jsxA11y.flatConfigs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
    },
  },
)
```

- [ ] **Step 3: Run lint and fix any findings in the real components**

Run: `cd frontend && npm run lint`
Expected: may surface new warnings/errors against existing components (missing labels, redundant roles, etc). Fix them directly in the component files; don't disable rules to pass. If a page component changes here (e.g. an added `aria-label`), note it, since Task 6-9's specs must select against the post-fix DOM, not the pre-fix one.

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/eslint.config.js
git commit -S -m "chore(frontend): add eslint-plugin-jsx-a11y"
```

---

## Task 5: Automated accessibility scan (axe-core)

**depends-on: Task2 [output], Task4 [completion]**

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/e2e/accessibility.spec.ts`

Placed before the flow specs, per the same sequencing fix as Task 4. Fixes the opus review's finding that scanning with empty fixtures effectively scans blank pages; this version scans populated pages and adds one keyboard-only journey, since automated axe-core rules don't cover keyboard/focus behavior at all.

- [ ] **Step 1: Install axe-core's Playwright integration**

Run (from `frontend/`): `npm install -D @axe-core/playwright`

- [ ] **Step 2: Write a scan across every route with populated data**

Create `frontend/e2e/accessibility.spec.ts`:
```typescript
import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import {
  mockApi,
  bootstrapRoutes,
  managerAccess,
  fragranceCatalog,
  enrollmentFixture,
  recommendationRunFixture,
} from './support/mock-api'

const routeChecks: { path: string; heading: string | RegExp }[] = [
  { path: '/', heading: /fragrance/i },
  { path: '/calibration', heading: 'ABC-123' },
  { path: '/ratings', heading: 'Ordinary encounters' },
  { path: '/recommendations', heading: 'Signature' },
  { path: '/about', heading: /about/i },
  { path: '/programs', heading: 'Program setup' },
]

test.describe('Accessibility (WCAG 2.1 AA)', () => {
  for (const { path, heading } of routeChecks) {
    test(`${path} has no automatically detectable violations`, async ({ page }) => {
      await mockApi(page, {
        ...bootstrapRoutes(managerAccess),
        [`/calibration/enrollments/enr1`]: enrollmentFixture(false),
        '/fragrances': fragranceCatalog,
        '/evaluations': [],
        '/recommendation-measurement/runs': recommendationRunFixture(),
      })

      await page.goto(path)
      await expect(page.getByRole('heading', { name: heading })).toBeVisible()

      const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()

      expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([])
    })
  }
})
```

Waits on a real heading instead of `networkidle`, so the scan runs against rendered content, not a loading shell.

- [ ] **Step 3: Add a keyboard-only journey through blind calibration**

Automated axe-core rules do not check keyboard operability or focus management; append to the same file:
```typescript
test.describe('Keyboard operability', () => {
  test('blind calibration is fully operable via keyboard', async ({ page }) => {
    await mockApi(page, {
      ...bootstrapRoutes(),
      '/calibration/enrollments/enr1': enrollmentFixture(false),
    })

    await page.goto('/calibration')
    await page.keyboard.press('Tab')
    await page.keyboard.press('Tab')
    await page.keyboard.press('Enter')

    await expect(page.getByRole('heading', { name: 'ABC-123' })).toBeVisible()
    await expect(page.getByText('Blind observation')).toBeVisible()
  })
})
```
Adjust the exact number of `Tab` presses once run against the real page; the point of this test is that some keyboard-only path reaches the blind-observation view, not this specific press count.

- [ ] **Step 4: Run it and fix real violations, don't suppress them**

Run: `cd frontend && npx playwright test e2e/accessibility.spec.ts`
Expected: may legitimately FAIL on first run. Fix violations in the actual page components; do not loosen `withTags` or add exceptions.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/e2e/accessibility.spec.ts
git commit -S -m "test(frontend): add automated WCAG 2.1 AA scan and a keyboard-only journey"
```

---

## Task 6: E2E spec: ordinary entry (RatingsPage)

**depends-on: Task3 [completion]** (parallelizable with Tasks 7, 8, 9)

**Files:**
- Create: `frontend/e2e/ordinary-entry.spec.ts`

Fixes the opus review's finding that the first draft never triggered a catalog search before selecting a fragrance version, leaving the select empty.

- [ ] **Step 1: Write the spec**

```typescript
import { test, expect } from '@playwright/test'
import { mockApi, bootstrapRoutes, fragranceCatalog } from './support/mock-api'

test.describe('Ordinary entry (journal encounters)', () => {
  test('records and corrects a journal encounter', async ({ page }) => {
    let savedEncounter: Record<string, unknown> | null = null

    await mockApi(page, {
      ...bootstrapRoutes(),
      '/fragrances': fragranceCatalog,
      '/evaluations': (route) => {
        if (route.request().method() === 'GET') {
          return route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(savedEncounter ? [savedEncounter] : []),
          })
        }
        const body = route.request().postDataJSON()
        savedEncounter = { id: 'e1', ...body }
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(savedEncounter) })
      },
    })

    await page.goto('/ratings')
    await expect(page.getByRole('heading', { name: 'Ordinary encounters' })).toBeVisible()

    await page.getByLabel('Evaluator').selectOption('r1')
    await page.getByLabel('Search fragrances').fill('Signature')
    await page.getByRole('button', { name: 'Search catalog' }).click()
    await expect(page.getByRole('option', { name: /Signature/ })).toBeVisible()

    await page.getByLabel('Fragrance version').selectOption('f1')
    await page.getByLabel('Rating (1–5)').fill('4')
    await page.getByRole('button', { name: 'Save new encounter' }).click()

    await expect(page.getByText('Encounter history')).toBeVisible()
  })
})
```

- [ ] **Step 2: Run it**

Run: `cd frontend && npx playwright test e2e/ordinary-entry.spec.ts`
Expected: PASS. If "Search catalog" isn't the real button text, or search results render some other way than an `<option>`, re-read `frontend/src/pages/RatingsPage.tsx`'s catalog-search JSX and adjust the two lines that reference it; this is the one part of this spec not independently re-verified during the opus review pass.

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/ordinary-entry.spec.ts
git commit -S -m "test(frontend): add e2e coverage for ordinary journal entries"
```

---

## Task 7: E2E spec: blind calibration and reveal

**depends-on: Task3 [completion]** (parallelizable with Tasks 6, 8, 9)

**Files:**
- Create: `frontend/e2e/blind-calibration.spec.ts`

Fixes the opus review's two concrete shape/API bugs: `Enrollment.presentations` (not `.samples`), `reveal_blocker: null` (not `undefined`), and the `selectOption({ label: /Baseline/ })` regex misuse (Playwright's `label` matcher is `string`-only).

- [ ] **Step 1: Write the spec**

```typescript
import { test, expect } from '@playwright/test'
import { mockApi, bootstrapRoutes, enrollmentFixture } from './support/mock-api'

test.describe('Blind calibration', () => {
  test('hides identity until reveal, then discloses it', async ({ page }) => {
    let revealed = false

    await mockApi(page, {
      ...bootstrapRoutes(),
      '/calibration/enrollments/enr1': (route) => {
        if (route.request().method() === 'POST') {
          revealed = true
          return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
        }
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(enrollmentFixture(revealed)),
        })
      },
      '/calibration/enrollments/enr1/reveal': (route) => {
        revealed = true
        return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
      },
      '/calibration/presentations/samp1/lock/BLOTTER': { status: 'locked' },
    })

    await page.goto('/calibration')
    await page.getByLabel('Evaluator and program').selectOption({ label: 'Baseline' })
    await page.getByRole('button', { name: 'ABC-123' }).click()

    await expect(page.getByRole('heading', { name: 'ABC-123' })).toBeVisible()
    await expect(page.getByText('House')).toHaveCount(0)
    await expect(page.getByText('Signature')).toHaveCount(0)
    await expect(page.getByText('Blind observation')).toBeVisible()

    await page.getByRole('button', { name: 'Lock blotter responses' }).click()
    await page.getByRole('button', { name: 'Confirm blotter lock' }).click()

    await page.getByRole('button', { name: 'Reveal completed baseline' }).click()
    await page.getByRole('button', { name: 'Confirm reveal' }).click()

    await expect(page.getByText('House · Signature · EDP')).toBeVisible()
    await expect(page.getByText('Post-reveal observation')).toBeVisible()
  })
})
```

- [ ] **Step 2: Run it**

Run: `cd frontend && npx playwright test e2e/blind-calibration.spec.ts`
Expected: PASS. If the confirm-dialog button labels (`Confirm blotter lock`, `Confirm reveal`) don't match, re-read the `ConfirmAction` usages in `CalibrationPage.tsx`.

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/blind-calibration.spec.ts
git commit -S -m "test(frontend): add e2e coverage for blind calibration and reveal"
```

---

## Task 8: E2E spec: recommendation feedback and sampling

**depends-on: Task3 [completion]** (parallelizable with Tasks 6, 7, 9)

**Files:**
- Create: `frontend/e2e/recommendation-feedback.spec.ts`

Fixes the opus review's findings: the run fixture must use `impressions` (not `items`) or `.map` throws, and the POST response must return a real `RecommendationResponse` with `interested: true` or the `aria-pressed` assertion never flips.

- [ ] **Step 1: Write the spec**

```typescript
import { test, expect } from '@playwright/test'
import { mockApi, bootstrapRoutes, recommendationRunFixture } from './support/mock-api'

test.describe('Recommendation feedback and sampling', () => {
  test('records interest and a sampling follow-up', async ({ page }) => {
    const responses: Record<string, unknown>[] = []

    await mockApi(page, {
      ...bootstrapRoutes(),
      '/recommendation-measurement/runs': recommendationRunFixture(),
      '/recommendation-measurement/impressions/imp1/responses': (route) => {
        const body = route.request().postDataJSON()
        responses.push(body)
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 'resp1', impression_id: 'imp1', interested: true, sampling_state: null, created_at: '2026-09-18T00:00:02Z' }),
        })
      },
      '/calibration/history/r1': [],
    })

    await page.goto('/recommendations')
    await page.getByLabel('Evaluator').selectOption('r1')
    await page.getByRole('button', { name: 'Get recommendations' }).click()

    await expect(page.getByRole('heading', { name: 'Signature' })).toBeVisible()

    await page.getByRole('button', { name: 'Interested' }).click()
    await expect(page.getByRole('button', { name: 'Interested' })).toHaveAttribute('aria-pressed', 'true')

    await page.getByRole('button', { name: 'Update sampling and outcome' }).click()
    await page.getByLabel('Sampling status').selectOption({ label: 'Plan to sample' })
    await page.getByRole('button', { name: 'Save follow-up' }).click()

    await expect
      .poll(() => responses.some((r) => r.sampling_state === 'PLANNED'))
      .toBe(true)
  })
})
```

- [ ] **Step 2: Run it**

Run: `cd frontend && npx playwright test e2e/recommendation-feedback.spec.ts`
Expected: PASS. If "Sampling status" option labels don't match `{ label: 'Plan to sample' }`, re-check `RecommendationsPage.tsx`'s label-to-`sampling_state` mapping.

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/recommendation-feedback.spec.ts
git commit -S -m "test(frontend): add e2e coverage for recommendation feedback and sampling"
```

---

## Task 9: E2E spec: manager route authorization

**depends-on: Task3 [completion]** (parallelizable with Tasks 6, 7, 8)

**Files:**
- Create: `frontend/e2e/manager-authorization.spec.ts`

Adds the 403-degradation case the opus review flagged as missing: the redirect-on-non-manager case only tests the happy client-side gate, not what happens when the API itself rejects a call.

- [ ] **Step 1: Write the spec**

```typescript
import { test, expect } from '@playwright/test'
import { mockApi, bootstrapRoutes, participantAccess, managerAccess } from './support/mock-api'

test.describe('Manager route authorization', () => {
  test('redirects a non-manager away from /programs', async ({ page }) => {
    await mockApi(page, bootstrapRoutes(participantAccess))

    await page.goto('/programs')

    await expect(page).toHaveURL('/calibration')
    await expect(page.getByRole('heading', { name: 'Program setup' })).toHaveCount(0)
  })

  test('allows a manager to reach /programs', async ({ page }) => {
    await mockApi(page, bootstrapRoutes(managerAccess))

    await page.goto('/programs')

    await expect(page).toHaveURL('/programs')
    await expect(page.getByRole('heading', { name: 'Program setup' })).toBeVisible()
  })

  test('degrades gracefully when the API rejects a manager action with 403', async ({ page }) => {
    await mockApi(page, {
      ...bootstrapRoutes(managerAccess),
      '/calibration/programs/p1/activate': (route) =>
        route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'forbidden' }) }),
    })

    await page.goto('/programs')
    await page.getByRole('button', { name: /activate/i }).first().click()

    await expect(page.getByText('You do not have access to this action.')).toBeVisible()
  })
})
```

The third case's exact button name and trigger flow depend on `ProgramSetupPage.tsx`'s activation control; verify the selector against the real component before treating this test as passing.

- [ ] **Step 2: Run it**

Run: `cd frontend && npx playwright test e2e/manager-authorization.spec.ts`
Expected: PASS for the first two cases without modification; the third may need its selector adjusted per Step 1's note.

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/manager-authorization.spec.ts
git commit -S -m "test(frontend): add e2e coverage for manager route authorization"
```

---

## Task 10: Real-backend smoke tier for disclosure and authorization invariants

**depends-on: Task9 [completion]**

**Files:**
- Create: `frontend/e2e-smoke/disclosure-and-authorization.spec.ts`
- Create: `frontend/playwright.smoke.config.ts`

The opus review's central finding: Tasks 5, 7, and 9 mock the API, so they only prove the frontend renders what it's told. The two invariants that actually matter for a family-trust product are (1) the API never sends `identity` before reveal, and (2) the API rejects non-manager calls to manager-only endpoints. Only a real backend can prove either. This tier is a Playwright suite of exactly these two assertions against a running `docker compose` stack, run nightly or pre-deploy, not on every PR.

- [ ] **Step 1: Discover the backend's test-seeding convention**

Dispatch an Explore subagent with this exact prompt: "In the fragrance-rater backend (src/fragrance_rater/ and tests/), find how pytest tests seed a calibration enrollment and program, and how they authenticate as a manager vs a non-manager user for API tests. Report the exact fixture names/functions and the auth mechanism (header, cookie, or token) used in existing integration tests." This grounds Steps 2-3 in the backend's actual conventions rather than assumptions; this plan's frontend-only exploration didn't cover it.

- [ ] **Step 2: Write the smoke config**

Create `frontend/playwright.smoke.config.ts` (separate from `playwright.config.ts` so this tier never runs as part of the default `npm run test:e2e`):
```typescript
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e-smoke',
  fullyParallel: false,
  retries: 1,
  workers: 1,
  reporter: [['github'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.SMOKE_BASE_URL || 'http://localhost:8080',
  },
})
```

- [ ] **Step 3: Write the two-invariant spec**

Using Step 1's findings for exact seeding/auth details, create `frontend/e2e-smoke/disclosure-and-authorization.spec.ts` with two tests: one that calls the real `GET /api/v1/calibration/enrollments/{id}` for a seeded, unrevealed enrollment and asserts the response body contains no `identity` field with real brand/name data; one that calls a real manager-only endpoint (e.g. `POST /api/v1/calibration/programs/{id}/activate`) as a seeded non-manager user and asserts a 403. Use Playwright's `request` fixture (API testing, no browser) rather than `page`, since these are API-contract assertions, not UI assertions.

- [ ] **Step 4: Add an npm script and document how to run it**

Modify `frontend/package.json`, add: `"test:e2e:smoke": "playwright test --config=playwright.smoke.config.ts"`.

- [ ] **Step 5: Run it against a local stack**

Run: `docker compose up -d && cd frontend && SMOKE_BASE_URL=http://localhost:8080 npm run test:e2e:smoke`
Expected: PASS. This tier is intentionally not wired into the per-PR CI job (Task 12); Task 12's step 3 documents that a separate, less-frequent workflow (nightly or pre-deploy) is a follow-up decision for the user, since it requires CI infrastructure (a running Compose stack in Actions) beyond this plan's frontend scope.

- [ ] **Step 6: Commit**

```bash
git add frontend/playwright.smoke.config.ts frontend/e2e-smoke/ frontend/package.json
git commit -S -m "test(frontend): add real-backend smoke tier for disclosure and authorization invariants"
```

---

## Task 11: Frontend CI job (lint, typecheck, unit tests, build)

**Files:**
- Modify: `.github/workflows/ci.yml`

Independent of Tasks 1-10; can run first, in parallel. **Serializes with Tasks 12 and 13**, which also edit this file; do not parallelize those three.

- [ ] **Step 1: Resolve the exact Action SHAs to pin**

The opus review caught a malformed SHA (39 hex chars) in this plan's first draft; resolve real ones instead of copying a guessed value. Run:
```bash
gh api repos/actions/checkout/commits/v4 --jq .sha
gh api repos/actions/setup-node/commits/v4 --jq .sha
```
Expected: two 40-character hex strings. Use these exact values in Step 2, with the resolved tag as a trailing comment.

- [ ] **Step 2: Add a `frontend` job alongside the existing `ci` job**

Modify `.github/workflows/ci.yml`: add a new top-level job (do not remove the existing `ci` job):
```yaml
jobs:
  ci:
    name: CI Pipeline
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@cb0742cf00832b4e640a47dfca222047c2b70c1c  # main
    with:
      python-version: '3.12'
      coverage-threshold: 80
      source-directory: 'src'
      test-directory: 'tests'
      run-integration-tests: true
      run-security-tests: true
      fail-on-llm-tags: false
      no-build: false

  frontend:
    name: Frontend CI
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@<SHA_FROM_STEP_1>  # v4
      - uses: actions/setup-node@<SHA_FROM_STEP_1>  # v4
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck
      - run: npm run test:coverage
      - run: npm run build

  ci-gate:
    name: CI Gate
    needs: [ci, frontend]
    runs-on: ubuntu-latest
    if: always()
    permissions:
      contents: read
    steps:
      - name: Aggregate CI result
        env:
          CI_RESULT: ${{ needs.ci.result }}
          FRONTEND_RESULT: ${{ needs.frontend.result }}
        run: |
          if [ "$CI_RESULT" != "success" ] || [ "$FRONTEND_RESULT" != "success" ]; then
            echo "::error::CI did not succeed (backend=$CI_RESULT, frontend=$FRONTEND_RESULT)"
            exit 1
          fi
          echo "CI Gate: all upstream checks succeeded."
```
Replace `<SHA_FROM_STEP_1>` with the two real values resolved in Step 1.

- [ ] **Step 3: Verify locally before pushing**

Run (from `frontend/`): `npm ci && npm run lint && npm run typecheck && npm run test:coverage && npm run build`
Expected: all four succeed.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -S -m "ci(frontend): add frontend lint/typecheck/test/build job"
```

---

## Task 12: Add Playwright e2e job to CI

**depends-on: Task1 [output], Task9 [completion], Task11 [completion]**

**Files:**
- Modify: `.github/workflows/ci.yml`

Explicitly serialized after Task 11 (same file, both edit the `jobs:` block and `ci-gate`'s `needs`/aggregate check).

- [ ] **Step 1: Add an e2e job with browser caching, and wire it into the gate**

`workers: 1` plus `retries: 2` (from Task 1's config) makes this the slowest CI job as specs accumulate; cache the Playwright browser install by its version to avoid re-downloading Chromium every run.

Modify `.github/workflows/ci.yml`, add a new job (reuse the SHAs resolved in Task 11 Step 1):
```yaml
  frontend-e2e:
    name: Frontend E2E
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@<SHA_FROM_TASK11_STEP1>  # v4
      - uses: actions/setup-node@<SHA_FROM_TASK11_STEP1>  # v4
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - name: Get installed Playwright version
        id: playwright-version
        run: echo "version=$(node -p "require('./package-lock.json').packages['node_modules/@playwright/test'].version")" >> "$GITHUB_OUTPUT"
      - uses: actions/cache@<RESOLVE_VIA_GH_API>  # v4
        id: playwright-cache
        with:
          path: ~/.cache/ms-playwright
          key: playwright-${{ steps.playwright-version.outputs.version }}
      - run: npx playwright install --with-deps chromium
        if: steps.playwright-cache.outputs.cache-hit != 'true'
      - run: npx playwright install-deps chromium
        if: steps.playwright-cache.outputs.cache-hit == 'true'
      - run: npm run test:e2e
      - if: failure()
        uses: actions/upload-artifact@<RESOLVE_VIA_GH_API>  # v4
        with:
          name: playwright-report
          path: frontend/playwright-report/
          retention-days: 7
```
Resolve both `<RESOLVE_VIA_GH_API>` placeholders the same way Task 11 Step 1 did: `gh api repos/actions/cache/commits/v4 --jq .sha` and `gh api repos/actions/upload-artifact/commits/v4 --jq .sha`. Do not hand-type a SHA; that is exactly the mistake the opus review caught in this plan's first draft.

Update `ci-gate`'s `needs: [ci, frontend, frontend-e2e]` and add `FRONTEND_E2E_RESULT: ${{ needs.frontend-e2e.result }}` to the aggregate check, following Task 11's pattern.

Note: the real-backend smoke tier from Task 10 is intentionally NOT added here; it requires a running Compose stack in CI and belongs in a separate, less-frequent workflow (nightly or pre-deploy). Surface that as an open decision to the user rather than silently building it into this plan's CI-wiring scope.

- [ ] **Step 2: Verify locally**

Run (from `frontend/`): `npm run build && npx playwright test`
Expected: all specs from Tasks 6-9 pass against the production build.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -S -m "ci(frontend): add Playwright e2e job"
```

---

## Task 13: Frontend coverage flag in Codecov

**depends-on: Task11 [completion], Task12 [completion]**

**Files:**
- Modify: `codecov.yml`
- Modify: `.github/workflows/ci.yml`

Explicitly serialized after Tasks 11 and 12 (same CI file).

- [ ] **Step 1: Confirm the coverage output path**

Run: `cd frontend && npm run test:coverage && ls coverage/lcov.info`
Expected: file exists (`frontend/vite.config.ts`'s `test.coverage.reporter` already includes `lcov`).

- [ ] **Step 2: Add the `frontend` flag to `codecov.yml`**

Read the current `codecov.yml` in full first, then add a `frontend` entry alongside the existing `unit`/`integration`/`security` flags, per the single-surface-flag exception in `.claude/standards/testing.md` §16.2:
```yaml
flags:
  frontend:
    paths:
      - frontend/src/
    carryforward: true

coverage:
  status:
    project:
      frontend: { target: auto, flags: [frontend], threshold: 2% }
```
Do not add per-test-type flags (no `frontend-unit`, `frontend-e2e`).

- [ ] **Step 3: Upload from CI**

Modify Task 11's `frontend` job in `.github/workflows/ci.yml`, adding a step after `npm run test:coverage`:
```yaml
      - uses: codecov/codecov-action@<RESOLVE_VIA_GH_API>  # v5
        with:
          files: frontend/coverage/lcov.info
          flags: frontend
          token: ${{ secrets.CODECOV_TOKEN }}
```
Resolve the SHA via `gh api repos/codecov/codecov-action/commits/v5 --jq .sha`, the same way as Task 11 Step 1.

- [ ] **Step 4: Commit**

```bash
git add codecov.yml .github/workflows/ci.yml
git commit -S -m "ci(frontend): add frontend coverage flag and upload"
```

---

## Task 14: ADR-014: Frontend e2e and accessibility testing strategy

**depends-on: Task9 [completion], Task5 [completion]** (written after the real specs and scan exist, and after the specs have run, not before)

**Files:**
- Create: `docs/planning/adr/adr-014-frontend-e2e-and-accessibility-strategy.md`

Folds what would have been a separate ADR-015 into a section of this one, per the opus review's finding that a two-ADR split was over-built for a decision that shares one Playwright suite and one CI job.

- [ ] **Step 1: Write the ADR**

No frontmatter (ADRs are exempt from `validate-front-matter`; follow the plain-markdown template from `adr-001-initial-architecture.md`).

```markdown
# ADR-014: Frontend E2E and Accessibility Testing Strategy

> **Status**: Accepted
>
> **Date**: 2026-09-18

## TL;DR

Adopt Playwright (`@playwright/test`) as the frontend e2e framework with a two-tier strategy: network-mocked specs for the fast per-PR gate, plus a thin real-backend smoke tier for exactly the two invariants a mock cannot prove (pre-reveal identity omission, manager-endpoint rejection of non-managers). Enforce WCAG 2.1 AA via an automated axe-core scan in the same mocked suite, plus `eslint-plugin-jsx-a11y` at lint time.

## Context

### Problem

PROJECT-PLAN.md's P1.8 entry gate requires e2e coverage of named flows (ordinary entry, blind calibration, recommendation feedback, sampling) and "authorization and disclosure tests cover every manager route." As of 2026-09-18 the frontend has no e2e tests, no e2e framework, and no automated accessibility scanning.

### Constraints

This app is a 6-page personal/family tool (ADR-001), not a multi-tenant production service, but it drives real purchase decisions for family members and handles a controlled-disclosure workflow (ADR-005) where premature identity reveal is a real integrity failure, not just a UX bug. That combination ruled out both extremes: a full CYO_Adventure-scale multi-tier real-backend suite (disproportionate to a 6-page app) and a mocked-only suite (insufficient for the one property, disclosure integrity, that a mock cannot verify by construction, since it only proves the frontend renders what it was told).

### Significance

Sets the pattern every future e2e and accessibility spec follows.

## Decision

**E2E**: `@playwright/test` in `frontend/e2e/`, with a shared `mockApi()` helper (`frontend/e2e/support/mock-api.ts`) intercepting `**/api/v1/**`, mirroring the existing Vitest `vi.mock('axios', ...)` convention at the network layer. Fixtures are pinned to the generated OpenAPI client's types via TypeScript `satisfies` assertions, so a backend schema change that regenerates the client also surfaces any fixture drift as a type error. A second, separate suite (`frontend/e2e-smoke/`, `playwright.smoke.config.ts`) runs against a real `docker compose` stack and asserts exactly two invariants: the API never returns identity data before reveal, and the API rejects non-manager calls to manager-only endpoints. This tier runs nightly or pre-deploy, not on every PR.

**Accessibility**: WCAG 2.1 AA, enforced as a single blocking tier inside the mocked e2e suite (`frontend/e2e/accessibility.spec.ts`) using `@axe-core/playwright` against every route with populated fixtures (not empty ones, which would scan a blank shell), plus one keyboard-only journey test, since automated rule scanning does not check keyboard operability. `eslint-plugin-jsx-a11y`'s recommended rules run at lint time.

### Rationale

Per `.claude/rules/design.md`, the committed e2e suite belongs in `frontend/e2e/` using `@playwright/test`. Network-layer mocking keeps the per-PR CI loop fast and deterministic. The smoke tier exists because this app's controlled-disclosure design (ADR-005) makes premature identity reveal a genuine trust failure for a family-use product, not a cosmetic bug, and only a real backend call can prove the API itself withholds identity, a property the frontend's mocked tests structurally cannot verify. axe-core is the industry-standard automated ruleset and integrates directly with the same Playwright suite, avoiding a second test runner.

## Options Considered

- **Mocked-only e2e, no real-backend tier** (this plan's first-draft position): rejected on review; leaves the disclosure and authorization invariants unproven by anything except "the frontend renders what the mock told it to render."
- **Full real-backend e2e tier for every flow** (CYO_Adventure's pattern): rejected as disproportionate; this app has one deployment target and no staged-environment cadence to support it.
- **Two separate ADRs for e2e and accessibility**: rejected after review; both share one Playwright suite and CI job, and splitting them produced a second ADR with no independent decision of its own.
- **Two-tier accessibility gate (per-PR + weekly), mirroring CYO_Adventure's ADR-029**: rejected for now; this project has no weekly-rehearsal cadence to hang a second tier off of.

## Consequences

### Positive

- Fast, deterministic per-PR CI, with the one property that actually needs a real backend (disclosure/authorization) verified by a real backend, not assumed.
- Fixture-contract check catches API drift before it silently produces a passing-but-wrong mocked spec.
- Directly closes the e2e portion of PROJECT-PLAN P1.8.

### Trade-offs

- The smoke tier is not wired into per-PR CI (Task 12); it requires a Compose stack in Actions, which is a separate infrastructure decision left open for the user.
- `ProgramSetupPage`'s internal manager actions beyond the route boundary (program definition, enrollment, metrics) remain untested by both tiers; only the authorization boundary and the two named invariants are covered.
- Automated axe-core scanning catches a meaningful but partial subset of real accessibility issues (no manual assistive-technology testing).

### Technical Debt

No CI wiring exists yet for the real-backend smoke tier's cadence (nightly/pre-deploy); no manual accessibility audit process is defined; `ProgramSetupPage`'s internal actions beyond authorization have no test coverage of any kind.

## Implementation

`frontend/playwright.config.ts`, `frontend/e2e/support/mock-api.ts`, per-flow specs under `frontend/e2e/`, `frontend/playwright.smoke.config.ts` and `frontend/e2e-smoke/` for the real-backend tier, `frontend/eslint.config.js`'s `jsxA11y.flatConfigs.recommended`. CI wiring in `.github/workflows/ci.yml`'s `frontend` and `frontend-e2e` jobs.

## Validation

Re-review if a production incident traces to a frontend/backend contract mismatch the fixture-contract check should have caught but didn't, if the smoke tier's two invariants prove insufficient after a real incident, or when planning work that adds meaningful new manager-side functionality to `ProgramSetupPage`.

## Related

- PROJECT-PLAN.md, P1.8 entry gate
- ADR-001 (Docker Compose monolith), ADR-005 (controlled calibration and disclosure state), ADR-008 (Authentik/Traefik trust boundary)
- CYO_Adventure ADR-029 (cross-project reference for the two-tier accessibility pattern this ADR deliberately does not adopt yet)
```

- [ ] **Step 2: Commit**

```bash
git add docs/planning/adr/adr-014-frontend-e2e-and-accessibility-strategy.md
git commit -S -m "docs(adr): add ADR-014 frontend e2e and accessibility strategy"
```

---

## Task 15: Frontend user-journey documentation

**depends-on: Task6 [completion], Task7 [completion], Task8 [completion], Task9 [completion], Task10 [completion], Task5 [completion]**

**Files:**
- Create: `docs/architecture/frontend-user-journeys.md`

The route-to-test-status table is generated from the actual state of the suite after all specs have run, not asserted in advance, per the opus review's finding that pre-writing "Covered" everywhere is a claim, not a record.

- [ ] **Step 1: Confirm the actual test state before writing the table**

Run: `cd frontend && npm run test:run && npx playwright test && npx playwright test --config=playwright.smoke.config.ts`
Expected: note the real pass/fail state of each. Only mark a cell "Covered" in Step 2's table if the corresponding spec is passing right now, not because a task in this plan intended it to pass.

- [ ] **Step 2: Write the doc**

```markdown
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

## Route-to-test-status

(Fill this table from Step 1's actual run output, not from intent. Columns: Route, Page, Unit/component (Vitest), E2E-mocked (Playwright), E2E-smoke (real backend), Accessibility scan.)

## Known gaps

- `ProgramSetupPage`'s internal forms (program definition, enrollment, pilot operations, metrics) have coverage only at the authorization boundary (`manager-authorization.spec.ts`) and the one 403-degradation case; internal action correctness is untested.
- The real-backend smoke tier (ADR-014) is not wired into per-PR CI; it must be run manually or via a separate, not-yet-built scheduled workflow.
- No manual accessibility audit exists; coverage is automated-scan plus one keyboard journey.
- PROJECT-PLAN P1.8's "performance budgets for frontend" criterion is not addressed by this plan at all.

## Related

- `docs/guides/pilot-participant.md`, `docs/guides/pilot-manager.md` (narrative walkthroughs)
- ADR-014 (e2e and accessibility strategy)
- PROJECT-PLAN.md, P1.8 entry gate
```

- [ ] **Step 3: Verify frontmatter passes the validator**

Run: `python tools/validate_front_matter.py docs`
Expected: no errors for this file.

- [ ] **Step 4: Commit**

```bash
git add docs/architecture/frontend-user-journeys.md
git commit -S -m "docs(architecture): add frontend user-journey and test-status doc"
```

---

## Task 16: Update tech-spec.md frontend section

**depends-on: Task14 [output]**

**Files:**
- Modify: `docs/planning/tech-spec.md`

- [ ] **Step 1: Read the current architecture layer section**

Run: `grep -n "React 19" docs/planning/tech-spec.md` to find the exact current line; re-confirm before editing.

- [ ] **Step 2: Expand the frontend entry**

Insert immediately after the existing one-line frontend stack mention (do not remove it):
```markdown
State management: local component state only, no external state-management library. Routing: a custom type-safe route union (`frontend/src/routing/routes.ts`), not React Router. Testing: Vitest + React Testing Library for unit/component tests, Playwright for mocked e2e plus a real-backend smoke tier (ADR-014), `@axe-core/playwright` + `eslint-plugin-jsx-a11y` for accessibility (ADR-014).
```

- [ ] **Step 3: Commit**

```bash
git add docs/planning/tech-spec.md
git commit -S -m "docs(tech-spec): document frontend state/routing/testing approach"
```

---

## Task 17: Record PROJECT-PLAN P1.8 gate evidence (partial closure)

**depends-on: Task1 [completion] through Task16 [completion]**

**Files:**
- Modify: `docs/planning/PROJECT-PLAN.md`

Per the opus review: this task must not claim P1.8 is fully closed. Two gaps remain regardless of everything else in this plan: performance budgets for the frontend are entirely out of scope here, and `ProgramSetupPage`'s internal manager actions beyond the authorization boundary have no test coverage. Record both explicitly rather than letting the gate read as closed when it isn't.

- [ ] **Step 1: Confirm the full suite passes together**

Run:
```bash
cd frontend
npm run lint && npm run typecheck && npm run test:coverage && npm run build && npx playwright test
```
Expected: all pass. This is the first point all sixteen prior tasks' output runs together; passing individual task-level checks is not sufficient evidence on its own.

- [ ] **Step 2: Update PROJECT-PLAN.md's P1.8 evidence with named residual gaps**

Read the current P1.8 section first, then update its evidence/status fields to reflect: e2e coverage for the four named flows (closed, evidence: ADR-014 and the passing `frontend/e2e/` suite), authorization/disclosure testing (closed for the one manager route and the two invariants named in ADR-014's real-backend smoke tier; explicitly note `ProgramSetupPage`'s internal actions beyond the boundary are NOT covered), performance budgets for frontend (explicitly NOT addressed by this plan, open). Link ADR-014 and `docs/architecture/frontend-user-journeys.md` as evidence.

- [ ] **Step 3: Commit**

```bash
git add docs/planning/PROJECT-PLAN.md
git commit -S -m "docs(planning): record P1.8 frontend test-strategy evidence, with residual gaps named"
```

---

## Self-Review

**Spec coverage**: PROJECT-PLAN P1.8's four named e2e flows map to Tasks 6-8. "Authorization and disclosure tests cover every manager route" is covered by Task 9 (the one real route, plus a 403-degradation case) and Task 10 (the two invariants a mock cannot prove). "Backend and frontend lint, type, test, and build checks pass" is covered by Task 11. "Performance budgets for frontend" is explicitly NOT covered; Task 17 records this as an open gap rather than silently dropping it.

**Placeholder scan**: no TBD/TODO markers. Task 10 Step 1 and Task 15 Step 1/2's table are structured as discovery-then-fill steps (an accepted pattern for gaps this plan's frontend-only exploration didn't cover), not vague placeholders; both name exactly what to discover and how to act on it. The `<SHA_FROM_STEP_1>` and `<RESOLVE_VIA_GH_API>` markers in Tasks 11-13 are resolved by an explicit, named `gh api` command in the same task, not left to guesswork.

**Type consistency**: `mockApi()`, `bootstrapRoutes()`, `enrollmentFixture()`, `recommendationRunFixture()` signatures and shapes are used identically across Tasks 5-9, corrected to match the real `Enrollment`/`RecommendationRun` shapes, and pinned by Task 3's `satisfies` check.

**Post-opus-review status**: this revision addressed all six of the opus review's numbered findings: (1) added Task 10's real-backend smoke tier instead of relying on mocks alone for disclosure/authorization; (2) fixed the concrete shape/selector bugs in Tasks 6-9; (3) reordered accessibility (Tasks 4-5) before the flow specs (Tasks 6-9); (4) serialized Tasks 11-13's shared-file edits and replaced the malformed hand-typed SHA with an explicit `gh api` resolution step; (5) folded ADR-015 into ADR-014; (6) changed Task 17 to record partial closure with both residual gaps (performance budgets, `ProgramSetupPage` internal actions) named rather than claiming the gate is fully closed.

**Remaining open decision for the user**: whether to build CI wiring for the real-backend smoke tier's cadence (nightly/pre-deploy) as a follow-up to this plan, since Task 12 deliberately does not add it to the per-PR job. This is a real scope boundary this plan draws, not an oversight, but it is a judgment call the user should confirm before Task 17 is treated as this effort's true end point.
