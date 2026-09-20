---
title: "Welcome Screen and Role-Aware Workspace Implementation Plan"
schema_type: planning
component: Strategy
source: "docs/superpowers/specs/2026-09-20-welcome-and-workspace-design.md"
status: draft
owner: core-maintainer
purpose: "Implement the approved welcome/workspace design: new WelcomePage and WorkspacePage components, routing changes, the calibration deep-link fix, and the encounter-logging terminology rename, each with test coverage."
tags:
  - frontend
  - testing
  - architecture
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Goal

Replace `HomePage` with a `WelcomePage` (post-auth orientation screen) and a
`WorkspacePage` (role-aware menu of what an identity can actually do), fix the
`CalibrationPage` deep-link bug, and rename the encounter-logging feature to one
consistent name everywhere it appears.

## Architecture

All work is in `frontend/`. `routes.ts` gains two routes (`welcome` at `/`,
`workspace` at `/home`, replacing `home`) and an optional query-string
parameter on `navigate()`. `App.tsx` renders the two new pages and reads a
validated `assignment` query param to pre-select `CalibrationPage`'s
dropdown. No backend or API changes; every new page is built from data
`useAppData()` already fetches.

## Tech Stack

React 19, TypeScript strict mode, Vitest + `@testing-library/react` for unit
tests (existing convention: every test renders `<App />` with mocked
`axios`, not isolated component props), Playwright for the mocked `e2e/`
suite.

## Deviation from the source spec

The spec's Testing section says to extend
`frontend/e2e-smoke/disclosure-and-authorization.spec.ts` with the new
UI-level scenarios (welcome→workspace navigation, role-aware rows, the
deep-link). That file has no `page` fixture and never renders anything: it is
a pure API-authorization tier that hits a live backend directly (`request`,
not `page`), reserved for invariants only provable against a real server
(identity disclosure, 403 enforcement). None of this feature's UI behavior
fits that tier or is verifiable there without a running docker-compose stack.
The actual home for mocked UI-level Playwright specs is `frontend/e2e/`
(`playwright.config.ts`, `npm run test:e2e`, `page.route` mocking via
`e2e/support/mock-api.ts`); see `blind-calibration.spec.ts` and
`manager-authorization.spec.ts` for the existing convention this plan follows
instead. Task 8 below targets that suite.

## Content note

The spec's WelcomePage hero statement was to be "drawn from the approved App
Store description," which does not exist anywhere in this repo. Per Byron's
decision (2026-09-20), the hero statement is the same sentence
`AboutPage.tsx:11` already uses: "Learn your fragrance taste by measuring
what you actually respond to."

---

## Task 1: Extract a shared `roleLabelFor` helper

`AppShell.tsx:19-23` computes the Manager/Recorder/Participant label inline.
`WelcomePage` (Task 3) needs the identical label for its identity line, and
the design spec requires the two to share one implementation so they can't
drift. Extract it now, independent of every other task.

**Files:**

- Create: `frontend/src/test/roleLabelFor.test.ts`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/components/AppShell.tsx`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from 'vitest'
import { roleLabelFor } from '../api/types'

describe('roleLabelFor', () => {
  it('returns Manager when canManagePrograms is set', () => {
    expect(roleLabelFor({ canManagePrograms: true, canRecordCalibration: false })).toBe('Manager')
  })

  it('returns Recorder for a non-manager who can record calibration', () => {
    expect(roleLabelFor({ canManagePrograms: false, canRecordCalibration: true })).toBe('Recorder')
  })

  it('returns Participant when neither capability is set', () => {
    expect(roleLabelFor({ canManagePrograms: false, canRecordCalibration: false })).toBe(
      'Participant'
    )
  })
})
```

- [ ] **Step 2: Run it, confirm it fails**

From `frontend/`:

```bash
npm run test:run -- src/test/roleLabelFor.test.ts
```

Expected: FAIL, because `roleLabelFor` is not exported by `../api/types`.

- [ ] **Step 3: Add `roleLabelFor` to `api/types.ts`**

Append immediately after the existing `capabilitiesFor` function (end of the
file, after line 291):

```ts
export function roleLabelFor(capabilities: Capabilities): 'Manager' | 'Recorder' | 'Participant' {
  return capabilities.canManagePrograms
    ? 'Manager'
    : capabilities.canRecordCalibration
      ? 'Recorder'
      : 'Participant'
}
```

- [ ] **Step 4: Run it, confirm it passes**

```bash
npm run test:run -- src/test/roleLabelFor.test.ts
```

Expected: PASS (3 tests).

- [ ] **Step 5: Use it in `AppShell.tsx`**

In `frontend/src/components/AppShell.tsx`, change the import block (lines
1-5):

```tsx
import { useEffect, useRef, type MouseEvent, type ReactNode } from 'react'
import type { Access, Capabilities } from '../api/types'
import { roleLabelFor } from '../api/types'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { navigationItems, type Route } from '../routing/routes'
import { ThemeToggle } from './ThemeToggle'
```

Then replace the inline role computation (lines 19-23):

```tsx
  const role = capabilities.canManagePrograms
    ? 'Manager'
    : capabilities.canRecordCalibration
      ? 'Recorder'
      : 'Participant'
```

with:

```tsx
  const role = roleLabelFor(capabilities)
```

- [ ] **Step 6: Run the existing suite that covers AppShell's role display, confirm no regression**

```bash
npm run test:run -- src/test/App.test.tsx -t "shows manager navigation only from verified access"
```

Expected: PASS. This test asserts `screen.getByText('Manager')`, unchanged
behavior after the refactor.

- [ ] **Step 7: Typecheck and lint**

```bash
npm run typecheck
npm run lint
```

Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/test/roleLabelFor.test.ts frontend/src/api/types.ts frontend/src/components/AppShell.tsx
git commit -m "refactor(frontend): extract roleLabelFor so AppShell and WelcomePage share one role label"
```

---

## Task 2: Restructure routing and rename the encounter-logging feature

Two changes to `routes.ts` land together because they touch the same
`navigationItems` array and leaving either half-done breaks the app: (1) add
`welcome` (`/`) and `workspace` (`/home`, replacing `home`) routes and extend
`navigate()` with an optional query string; (2) rename the `ratings` route's
nav label and `RatingsPage`'s heading from the three inconsistent names
("Record an encounter" / "My Ratings" / "Ordinary encounters") to one:
"Log an encounter".

depends-on: none

**Files:**

- Create: `frontend/src/test/routes.test.ts`
- Modify: `frontend/src/routing/routes.ts`
- Modify: `frontend/src/pages/RatingsPage.tsx:85`
- Modify: `frontend/src/test/App.test.tsx:206`, `:585-586`
- Modify: `frontend/src/test/documentTitle.test.tsx:65-75`

- [ ] **Step 1: Write the failing test**

```ts
import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { navigationItems, pathFor, routeFromPath, useRoute } from '../routing/routes'

describe('routeFromPath', () => {
  it('maps the root path to welcome', () => {
    expect(routeFromPath('/')).toBe('welcome')
  })

  it('maps /home to workspace', () => {
    expect(routeFromPath('/home')).toBe('workspace')
  })

  it('falls back to welcome for an unrecognized path', () => {
    expect(routeFromPath('/nowhere')).toBe('welcome')
  })
})

describe('pathFor', () => {
  it('round-trips every navigation item path', () => {
    for (const item of navigationItems) {
      expect(pathFor(item.route)).toBe(item.path)
    }
  })
})

describe('useRoute navigate', () => {
  it('sets an explicit query string, overriding whatever is already in the URL', () => {
    window.history.replaceState({}, '', '/calibration?stale=1')
    const { result } = renderHook(() => useRoute())

    act(() => result.current.navigate('calibration', false, 'assignment=enr1'))

    expect(window.location.pathname).toBe('/calibration')
    expect(window.location.search).toBe('?assignment=enr1')
  })

  it('preserves the current query string when no query is given', () => {
    window.history.replaceState({}, '', '/recommendations?recommendation_run=run-1')
    const { result } = renderHook(() => useRoute())

    act(() => result.current.navigate('ratings'))

    expect(window.location.pathname).toBe('/ratings')
    expect(window.location.search).toBe('?recommendation_run=run-1')
  })
})
```

- [ ] **Step 2: Run it, confirm it fails**

```bash
npm run test:run -- src/test/routes.test.ts
```

Expected: FAIL, because `routeFromPath('/')` currently returns `'home'`, not
`'welcome'`; `navigate` currently takes only two parameters.

- [ ] **Step 3: Rewrite `routes.ts`**

Replace the full contents of `frontend/src/routing/routes.ts`:

```ts
import { useCallback, useEffect, useState } from 'react'

export type Route =
  | 'welcome'
  | 'workspace'
  | 'calibration'
  | 'recommendations'
  | 'ratings'
  | 'programs'
  | 'about'

export type NavigationItem = {
  route: Route
  label: string
  path: string
  /**
   * Distinct `document.title` for the route.
   *
   * WCAG 2.4.2 (Page Titled) applies per URL, and these are real pushState
   * URLs a family member can bookmark, reload, and hold several of in tabs
   * at once. Every route previously rendered the same "Fragrance Rater"
   * title, which made those tabs indistinguishable and gave a screen-reader
   * user no confirmation that navigation had happened.
   */
  documentTitle: string
  managerOnly?: boolean
  hiddenFromNav?: boolean
}

export const siteName = 'Fragrance Rater'

export const navigationItems: NavigationItem[] = [
  { route: 'welcome', label: 'Welcome', path: '/', documentTitle: 'Welcome' },
  { route: 'workspace', label: 'Workspace', path: '/home', documentTitle: 'Workspace' },
  {
    route: 'calibration',
    label: 'Calibration',
    path: '/calibration',
    documentTitle: 'Blind calibration',
  },
  {
    route: 'recommendations',
    label: 'Recommendations',
    path: '/recommendations',
    documentTitle: 'Recommendations',
  },
  {
    route: 'ratings',
    label: 'Log an encounter',
    path: '/ratings',
    documentTitle: 'Log an encounter',
  },
  {
    route: 'programs',
    label: 'Program setup',
    path: '/programs',
    documentTitle: 'Program setup',
    managerOnly: true,
  },
  {
    route: 'about',
    label: 'About',
    path: '/about',
    documentTitle: 'About this project',
    hiddenFromNav: true,
  },
]

/**
 * The full `document.title` for a route: page name, then the site name.
 *
 * Page-first so the distinguishing part survives truncation in a crowded tab
 * strip, which is the case WCAG 2.4.2 is useful in. Falls back to the site
 * name alone for a route with no navigation entry.
 */
export function documentTitleFor(route: Route): string {
  const item = navigationItems.find((entry) => entry.route === route)
  return item ? `${item.documentTitle} · ${siteName}` : siteName
}

export function routeFromPath(pathname: string): Route {
  return navigationItems.find((item) => item.path === pathname)?.route ?? 'welcome'
}

export function pathFor(route: Route): string {
  return navigationItems.find((item) => item.route === route)?.path ?? '/calibration'
}

export function useRoute() {
  const [route, setRoute] = useState<Route>(() => routeFromPath(window.location.pathname))

  useEffect(() => {
    const onPopState = () => setRoute(routeFromPath(window.location.pathname))
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const navigate = useCallback((next: Route, replace = false, query = '') => {
    const path = pathFor(next)
    const search = query ? `?${query}` : window.location.search
    const url = `${path}${search}${window.location.hash}`
    window.history[replace ? 'replaceState' : 'pushState']({}, '', url)
    setRoute(next)
  }, [])

  return { route, navigate }
}
```

- [ ] **Step 4: Rename `RatingsPage`'s heading**

In `frontend/src/pages/RatingsPage.tsx:85`, change:

```tsx
          <h2>Ordinary encounters</h2>
```

to:

```tsx
          <h2>Log an encounter</h2>
```

- [ ] **Step 5: Run the new test, confirm it passes**

```bash
npm run test:run -- src/test/routes.test.ts
```

Expected: PASS (5 tests).

- [ ] **Step 6: Fix the two existing tests broken by the rename**

In `frontend/src/test/App.test.tsx:206`, change:

```tsx
    fireEvent.click(await screen.findByRole('link', { name: 'My Ratings' }))
```

to:

```tsx
    fireEvent.click(await screen.findByRole('link', { name: 'Log an encounter' }))
```

At `frontend/src/test/App.test.tsx:585-586`, change:

```tsx
    expect(await screen.findByRole('heading', { name: 'Ordinary encounters' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'My Ratings' })).toHaveAttribute('aria-current', 'page')
```

to:

```tsx
    expect(await screen.findByRole('heading', { name: 'Log an encounter' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Log an encounter' })).toHaveAttribute(
      'aria-current',
      'page'
    )
```

- [ ] **Step 7: Fix the one existing test broken by the route restructuring**

In `frontend/src/test/documentTitle.test.tsx:65-75`, replace the whole test:

```tsx
  it('updates the title when navigating without a reload', async () => {
    window.history.replaceState({}, '', '/')
    render(<App />)

    await screen.findByRole('heading', { name: 'Fragrance Rater' })
    await waitFor(() => expect(document.title).toBe('Home · Fragrance Rater'))

    fireEvent.click(screen.getByRole('link', { name: 'My Ratings' }))

    await waitFor(() => expect(document.title).toBe('My ratings · Fragrance Rater'))
  })
```

with:

```tsx
  it('updates the title when navigating without a reload', async () => {
    window.history.replaceState({}, '', '/')
    render(<App />)

    await screen.findByRole('heading', { name: 'Fragrance Rater' })
    await waitFor(() => expect(document.title).toBe('Welcome · Fragrance Rater'))

    fireEvent.click(screen.getByRole('link', { name: 'Log an encounter' }))

    await waitFor(() => expect(document.title).toBe('My ratings · Fragrance Rater'))
  })
```

- [ ] **Step 8: Run both edited files**

```bash
npm run test:run -- src/test/App.test.tsx src/test/documentTitle.test.tsx
```

Expected: these two specific tests now pass. (Several other `App.test.tsx`
tests will still fail at this point because `App.tsx` still imports the
now-retired `home` route indirectly through `HomePage`; that's expected
until Task 6. Confirm only that the tests touched in Steps 6-7 pass, and that
the failures remaining are limited to tests that render `/` expecting
`HomePage` content: `'shows assignment progress and a safe next action on
the home page'`, `'offers reveal from home when only concealed holdout work
remains'`, `'retries assignment progress without reloading the
application'`, plus every test in `revealAndLog.test.tsx`'s `'Landing page
actions'` block. Task 7 handles those.)

- [ ] **Step 9: Typecheck and lint**

```bash
npm run typecheck
npm run lint
```

Expected: `typecheck` fails at this point: `App.tsx:12` still does
`{ route === 'home' && ... }`: actually **`Route` no longer has a `'home'`
member**, so `App.tsx`'s `route === 'home'` comparison is now a TypeScript
error (comparing to a value outside the union). This is expected and
resolved in Task 6, which is why Task 6 depends on this task's output. Do not
attempt to fix `App.tsx` here.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/test/routes.test.ts frontend/src/routing/routes.ts frontend/src/pages/RatingsPage.tsx frontend/src/test/App.test.tsx frontend/src/test/documentTitle.test.tsx
git commit -m "feat(frontend): add welcome/workspace routes and rename encounter logging to one name"
```

---

## Task 3: Create `WelcomePage`

depends-on: Task2 [output] (needs the `welcome`/`workspace` routes and the
renamed "Log an encounter" label)

**Files:**

- Create: `frontend/src/pages/WelcomePage.tsx`
- Create: `frontend/src/test/WelcomePage.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'

const { get, post, patch } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}))

vi.mock('axios', () => ({
  default: { create: () => ({ get, post, patch }), isAxiosError: () => false },
}))

function mockBootstrap(overrides: Record<string, unknown> = {}) {
  get.mockImplementation((path: string) => {
    const responses: Record<string, unknown> = {
      '/reviewers': [{ id: 'r', name: 'Evaluator' }],
      '/calibration/programs': [],
      '/calibration/access': { username: 'family-member', manager: false },
      '/calibration/enrollments': [],
      ...overrides,
    }
    return path in responses
      ? Promise.resolve({ data: responses[path] })
      : Promise.reject(new Error(`Unexpected request: ${path}`))
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  window.history.replaceState({}, '', '/')
  mockBootstrap()
})

describe('WelcomePage', () => {
  it('shows the hero statement, the identity line, and a single continue action', async () => {
    render(<App />)

    expect(
      await screen.findByText(
        'Learn your fragrance taste by measuring what you actually respond to.'
      )
    ).toBeInTheDocument()
    expect(
      screen.getByText("Welcome, family-member, you're set up as Participant.")
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument()
  })

  it('labels a manager identity with the Manager role', async () => {
    mockBootstrap({ '/calibration/access': { username: 'manager-user', manager: true } })
    render(<App />)

    expect(
      await screen.findByText("Welcome, manager-user, you're set up as Manager.")
    ).toBeInTheDocument()
  })

  it('continues into the workspace', async () => {
    render(<App />)

    fireEvent.click(await screen.findByRole('button', { name: 'Continue' }))

    expect(await screen.findByRole('button', { name: 'Log an encounter' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/home')
  })

  it('links to the full methodology page', async () => {
    render(<App />)

    fireEvent.click(await screen.findByRole('button', { name: 'Read the full methodology' }))

    expect(
      await screen.findByRole('heading', { name: 'How this project learns your taste' })
    ).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run it, confirm it fails**

```bash
npm run test:run -- src/test/WelcomePage.test.tsx
```

Expected: FAIL, because `App.tsx` does not yet render anything for `route ===
'welcome'`; `WelcomePage` does not exist.

- [ ] **Step 3: Create `WelcomePage.tsx`**

```tsx
import type { Access, Capabilities } from '../api/types'
import { roleLabelFor } from '../api/types'
import type { Route } from '../routing/routes'

type WelcomePageProps = {
  access: Access
  capabilities: Capabilities
  navigate: (route: Route) => void
}

export function WelcomePage({ access, capabilities, navigate }: WelcomePageProps) {
  return (
    <section>
      <div className="page-heading">
        <div>
          <h2>Welcome</h2>
        </div>
      </div>
      <p className="hero-statement">
        Learn your fragrance taste by measuring what you actually respond to.
      </p>
      <p>
        Welcome, {access.username}, you're set up as {roleLabelFor(capabilities)}.
      </p>
      <div className="button-row">
        <button onClick={() => navigate('workspace')}>Continue</button>
        <button className="secondary" onClick={() => navigate('about')}>
          Read the full methodology
        </button>
      </div>
    </section>
  )
}
```

This intentionally does not yet compile end-to-end: `App.tsx` still needs to
import and render it. Confirming that gap is Step 4.

- [ ] **Step 4: Wire a minimal render into `App.tsx` so the test can run**

This is a temporary, minimal wire-up; Task 6 replaces it with the full,
final `App.tsx` (which also adds `WorkspacePage`, the `CalibrationPage`
deep-link prop, and removes `HomePage`). Add the import and one render
branch without touching anything else yet.

In `frontend/src/App.tsx`, add to the imports (after the `RecommendationsPage`
import on line 10):

```tsx
import { WelcomePage } from './pages/WelcomePage'
```

Add, immediately before the `{route === 'home' && (` block (before line 38):

```tsx
      {route === 'welcome' && (
        <WelcomePage
          access={appData.access}
          capabilities={appData.capabilities}
          navigate={navigate}
        />
      )}
```

Leave the existing `{route === 'home' && <HomePage .../>}` block in place for
now; it is dead code once `routeFromPath('/')` returns `'welcome'` instead
of `'home'`, but removing it here would spill into Task 6's scope. `route ===
'home'` is still a type error per Task 2 Step 9; that resolves in Task 6.

- [ ] **Step 5: Run it, confirm it passes**

```bash
npm run test:run -- src/test/WelcomePage.test.tsx
```

Expected: PASS (4 tests). (`npm run typecheck` will still fail because of the
dangling `route === 'home'` comparison, which is expected until Task 6;
don't run it yet.)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/WelcomePage.tsx frontend/src/test/WelcomePage.test.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add WelcomePage"
```

---

## Task 4: Create `WorkspacePage`

Moves `HomePage`'s enrollment-fetch effect and `nextAction()` helper
verbatim, drops the retired "primary action"/"Calibrations open" summary
(replaced by static role-aware rows), and only renders the calibration
section when `assignments.length > 0`; this is what makes a manager's
account with no evaluator enrollment of its own stop looking broken (UX
finding 3 from the prior test round).

depends-on: Task2 [output]

**Files:**

- Create: `frontend/src/pages/WorkspacePage.tsx`
- Create: `frontend/src/test/WorkspacePage.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'

const { get, post, patch } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}))

vi.mock('axios', () => ({
  default: { create: () => ({ get, post, patch }), isAxiosError: () => false },
}))

const enrollment = {
  id: 'assignment',
  program_id: 'p',
  reviewer_id: 'r',
  revealed: false,
  reveal_eligible: false,
  reveal_blocker: 'BLOTTER',
  skin_plan_locked: true,
  presentations: [
    {
      id: 'sample',
      session_id: 'session',
      blind_code: 'A82F',
      position: 1,
      skin_planned: false,
      blotter_locked: false,
      skin_locked: false,
      observations: [],
    },
  ],
}

function mockBootstrap(overrides: Record<string, unknown> = {}) {
  get.mockImplementation((path: string) => {
    const responses: Record<string, unknown> = {
      '/reviewers': [{ id: 'r', name: 'Evaluator' }],
      '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1' }],
      '/calibration/access': { username: 'family-member', manager: false },
      '/calibration/enrollments': [],
      ...overrides,
    }
    return path in responses
      ? Promise.resolve({ data: responses[path] })
      : Promise.reject(new Error(`Unexpected request: ${path}`))
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  window.history.replaceState({}, '', '/home')
  mockBootstrap()
})

describe('WorkspacePage', () => {
  it('always offers the participant baseline rows', async () => {
    render(<App />)

    expect(await screen.findByRole('button', { name: 'Log an encounter' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'See recommendations' })).toBeInTheDocument()
  })

  it('hides program management from a non-manager', async () => {
    render(<App />)

    await screen.findByRole('button', { name: 'Log an encounter' })
    expect(screen.queryByRole('button', { name: 'Manage programs' })).not.toBeInTheDocument()
  })

  it('offers program management to a manager', async () => {
    mockBootstrap({ '/calibration/access': { username: 'manager-user', manager: true } })
    render(<App />)

    expect(await screen.findByRole('button', { name: 'Manage programs' })).toBeInTheDocument()
  })

  it('hides the calibration section entirely when there are no assignments', async () => {
    render(<App />)

    await screen.findByRole('button', { name: 'Log an encounter' })
    expect(screen.queryByRole('heading', { name: 'Calibration work' })).not.toBeInTheDocument()
  })

  it('shows one row per open enrollment with its own deep-linking action', async () => {
    mockBootstrap({
      '/calibration/enrollments': [{ id: 'assignment', program_id: 'p', reviewer_id: 'r' }],
      '/calibration/enrollments/assignment': enrollment,
    })
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Baseline' })).toBeInTheDocument()
    expect(screen.getByText('Continue required blind blotter screens.')).toBeInTheDocument()
    expect(screen.getByText('0 of 1 blind screens locked')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Continue calibration' }))

    expect(await screen.findByRole('heading', { name: 'Your calibration' })).toBeInTheDocument()
    expect(window.location.search).toBe('?assignment=assignment')
    expect(screen.getByLabelText('Evaluator and program')).toHaveValue('assignment')
    expect(await screen.findByRole('button', { name: /A82F/ })).toBeInTheDocument()
  })

  it('retries assignment progress without reloading the application', async () => {
    let progressUnavailable = true
    get.mockImplementation((path: string) => {
      const responses: Record<string, unknown> = {
        '/reviewers': [{ id: 'r', name: 'Evaluator' }],
        '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1' }],
        '/calibration/access': { username: 'family-member', manager: false },
        '/calibration/enrollments': [{ id: 'assignment', program_id: 'p', reviewer_id: 'r' }],
        '/calibration/enrollments/assignment': enrollment,
      }
      if (path === '/calibration/enrollments/assignment' && progressUnavailable) {
        return Promise.reject(new Error('offline'))
      }
      return Promise.resolve({ data: responses[path] })
    })
    render(<App />)

    expect(
      await screen.findByText('Request failed. Check your connection and try again.')
    ).toBeInTheDocument()
    progressUnavailable = false
    fireEvent.click(screen.getByRole('button', { name: 'Retry assignment progress' }))

    expect(await screen.findByText('Continue required blind blotter screens.')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run it, confirm it fails**

```bash
npm run test:run -- src/test/WorkspacePage.test.tsx
```

Expected: FAIL, because `App.tsx` does not yet render anything for `route ===
'workspace'`; `WorkspacePage` does not exist.

- [ ] **Step 3: Create `WorkspacePage.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { api, requestErrorMessage } from '../api/client'
import type { Assignment, Capabilities, Enrollment, Person, Program } from '../api/types'
import { FeedbackBanner } from '../components/FeedbackBanner'
import { LoadingState } from '../components/PageState'
import type { Route } from '../routing/routes'

type WorkspacePageProps = {
  assignments: Assignment[]
  programs: Program[]
  reviewers: Person[]
  capabilities: Capabilities
  navigate: (route: Route, replace?: boolean, query?: string) => void
}

/**
 * The single next step for one assignment, in the evaluator's terms.
 *
 * Derived from `reveal_blocker`, which the API sets to whichever gate is
 * currently holding the enrollment closed. The strings deliberately name an
 * action rather than the blocker code, because the code is a protocol detail
 * (ADR-005) and the evaluator only needs to know what to do next.
 */
function nextAction(enrollment: Enrollment): string {
  if (enrollment.revealed) return 'Review revealed results or add a post-reveal observation.'
  if (enrollment.reveal_blocker === 'SKIN_PLAN') return 'Finalize the skin-test plan.'
  if (enrollment.reveal_blocker === 'BLOTTER') return 'Continue required blind blotter screens.'
  if (enrollment.reveal_blocker === 'SKIN') return 'Complete the planned blind skin tests.'
  return 'Required blind work is complete. Reveal when ready.'
}

export function WorkspacePage({
  assignments,
  programs,
  reviewers,
  capabilities,
  navigate,
}: WorkspacePageProps) {
  const [enrollments, setEnrollments] = useState<Enrollment[]>([])
  const [loading, setLoading] = useState(assignments.length > 0)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let current = true
    if (!assignments.length) {
      setError('')
      setEnrollments([])
      setLoading(false)
      return
    }
    setLoading(true)
    setError('')
    void Promise.all(
      assignments.map((assignment) =>
        api.get<Enrollment>(`/calibration/enrollments/${assignment.id}`)
      )
    )
      .then((responses) => {
        if (current) setEnrollments(responses.map((response) => response.data))
      })
      .catch((reason: unknown) => {
        if (current) setError(requestErrorMessage(reason))
      })
      .finally(() => {
        if (current) setLoading(false)
      })
    return () => {
      current = false
    }
  }, [assignments, reloadKey])

  return (
    <>
      <section>
        <div className="page-heading">
          <div>
            <h2>Workspace</h2>
          </div>
        </div>
        <div className="button-row">
          <button onClick={() => navigate('ratings')}>Log an encounter</button>
          <button className="secondary" onClick={() => navigate('recommendations')}>
            See recommendations
          </button>
          {capabilities.canManagePrograms && (
            <button className="secondary" onClick={() => navigate('programs')}>
              Manage programs
            </button>
          )}
        </div>
      </section>

      {assignments.length > 0 && (
        <section>
          <h3>Calibration work</h3>
          <FeedbackBanner error={error} />
          {error && (
            <button
              className="secondary"
              disabled={loading}
              onClick={() => setReloadKey((key) => key + 1)}
            >
              Retry assignment progress
            </button>
          )}
          {loading ? (
            <LoadingState label="Loading assignment progress…" />
          ) : (
            enrollments.map((enrollment) => {
              const assignment = assignments.find((item) => item.id === enrollment.id)
              const locked = enrollment.presentations.filter((item) => item.blotter_locked).length
              const total = enrollment.presentations.length
              const evaluator =
                reviewers.find((item) => item.id === assignment?.reviewer_id)?.name || 'Evaluator'
              const program =
                programs.find((item) => item.id === assignment?.program_id)?.name || 'Program'
              return (
                <article className="assignment-row" key={enrollment.id}>
                  <div>
                    <h4>{program}</h4>
                    <p>{evaluator}</p>
                  </div>
                  <div className="assignment-row__meter">
                    <progress
                      value={locked}
                      max={total}
                      aria-label={`Blind screens locked for ${evaluator} on ${program}`}
                    />
                    <small data-numeric>
                      {locked} of {total} blind screens locked
                    </small>
                  </div>
                  <div className="assignment-row__action">
                    <p>
                      <strong>{nextAction(enrollment)}</strong>
                    </p>
                    <button
                      onClick={() =>
                        navigate('calibration', false, `assignment=${enrollment.id}`)
                      }
                    >
                      Continue calibration
                    </button>
                  </div>
                </article>
              )
            })
          )}
        </section>
      )}

      <section>
        <h3>There is nothing here you can get wrong</h3>
        <p>
          Disliking a fragrance, even strongly, is worth as much to the model as liking one. It
          marks where your preferences stop, which is information nothing else in the record
          supplies.
        </p>
        <p>
          The same goes for being unsure. A scale left unanswered is a usable fact about that
          sample; a guess entered to avoid leaving a blank is not.
        </p>
      </section>
    </>
  )
}
```

- [ ] **Step 4: Wire a minimal render into `App.tsx`, same caveat as Task 3**

Add to `App.tsx`'s imports (after the `WelcomePage` import just added):

```tsx
import { WorkspacePage } from './pages/WorkspacePage'
```

Add immediately after the `welcome` block from Task 3:

```tsx
      {route === 'workspace' && (
        <WorkspacePage
          assignments={appData.assignments}
          programs={appData.programs}
          reviewers={appData.reviewers}
          capabilities={appData.capabilities}
          navigate={navigate}
        />
      )}
```

- [ ] **Step 5: Run it, confirm it passes**

```bash
npm run test:run -- src/test/WorkspacePage.test.tsx
```

Expected: PASS (7 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/WorkspacePage.tsx frontend/src/test/WorkspacePage.test.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add WorkspacePage with role-aware rows and calibration deep-link"
```

---

## Task 5: Fix the `CalibrationPage` deep-link bug

`CalibrationPage`'s `assignmentId` state always starts at `''`, so
navigating from a specific enrollment's "Continue calibration" button always
lands on the empty "Choose assignment" dropdown regardless of which row was
clicked (`HomePage.tsx:207`, confirmed present-tense during discovery).
`initialAssignmentId` lets a caller pre-select it.

depends-on: none (this file never calls `navigate` and has no dependency on
Task 2's route changes)

**Files:**

- Modify: `frontend/src/pages/CalibrationPage.tsx:1`, `:17-21`, `:76-107`

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/test/App.test.tsx`, inside the existing `describe('Calibration participant workflow', ...)` block (after the last test, before the closing `})` at line 1314):

```tsx
  it('pre-selects the assignment named in an initial query string', async () => {
    window.history.replaceState({}, '', '/calibration?assignment=assignment')
    render(<App />)

    expect(await screen.findByLabelText('Evaluator and program')).toHaveValue('assignment')
    expect(await screen.findByRole('button', { name: /A82F/ })).toBeInTheDocument()
  })

  it('falls back to the empty dropdown for a stale assignment id in the query string', async () => {
    window.history.replaceState({}, '', '/calibration?assignment=does-not-exist')
    render(<App />)

    await screen.findByRole('option', { name: 'Evaluator · Baseline' })
    expect(screen.getByLabelText('Evaluator and program')).toHaveValue('')
  })
```

- [ ] **Step 2: Run it, confirm it fails**

```bash
npm run test:run -- src/test/App.test.tsx -t "pre-selects the assignment named in an initial query string"
```

Expected: FAIL, because `CalibrationPage` has no `initialAssignmentId` prop yet, and
`App.tsx` does not read the query string yet (this second half lands in
Task 6; for now the test will fail because the dropdown stays empty).

- [ ] **Step 3: Add `initialAssignmentId` to `CalibrationPage.tsx`**

Change the import line (line 1):

```tsx
import { useCallback, useEffect, useRef, useState } from 'react'
```

Change the props type (lines 17-21):

```tsx
type CalibrationPageProps = {
  assignments: Assignment[]
  programs: Program[]
  reviewers: Person[]
  initialAssignmentId?: string
}
```

Change the function signature and the first few lines of the body (lines
76-84), and add the `refresh` `useCallback` wrapper plus the new mount
effect immediately after `enrollmentGuidance` and before `save` (i.e.
replace the existing plain `async function refresh(...)` declaration at
lines 98-107 with the version below):

```tsx
export function CalibrationPage({
  assignments,
  programs,
  reviewers,
  initialAssignmentId,
}: CalibrationPageProps) {
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null)
  const [assignmentId, setAssignmentId] = useState(initialAssignmentId ?? '')
  const requestedAssignment = useRef(initialAssignmentId ?? '')
  const refreshGeneration = useRef(0)
  const [selected, setSelected] = useState('')
  const [stage, setStage] = useState('BLOTTER')
  const [detected, setDetected] = useState('')
  const task = useTask()
  const sample = enrollment?.presentations.find((presentation) => presentation.id === selected)
  function enrollmentGuidance() {
    if (!enrollment) return ''
    if (enrollment.revealed) return 'Identities are revealed. You may add post-reveal observations.'
    if (enrollment.reveal_blocker === 'SKIN_PLAN')
      return 'All blotter screens are locked. Review and finalize the skin-test plan.'
    if (enrollment.reveal_blocker === 'BLOTTER')
      return 'Required blind blotter screens still need to be locked.'
    if (enrollment.reveal_blocker === 'SKIN')
      return 'Planned blind skin tests still need to be locked.'
    return 'All required blind work is locked. The enrollment is eligible to reveal.'
  }

  const refresh = useCallback(async (id = requestedAssignment.current) => {
    const generation = ++refreshGeneration.current
    if (!id) {
      setEnrollment(null)
      return
    }
    const response = await api.get<Enrollment>(`/calibration/enrollments/${id}`)
    if (generation === refreshGeneration.current && requestedAssignment.current === id)
      setEnrollment(response.data)
  }, [])

  useEffect(() => {
    if (!initialAssignmentId) return
    requestedAssignment.current = initialAssignmentId
    void task.run(() => refresh(initialAssignmentId))
    // task is a fresh object every render (useTask isn't memoized), so it is
    // intentionally left out: this effect must fire only when
    // initialAssignmentId (or the stabilized refresh callback) changes, not
    // on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialAssignmentId, refresh])
```

The rest of the component (`save`, the JSX render, the assignment `<select>`
and its `onChange`) is unchanged: it already calls `refresh(id)` and
`refresh()` in ways that work identically against the now-`useCallback`-wrapped
version.

- [ ] **Step 4: Run it, confirm the failure moved (test still fails, but the reason changes)**

```bash
npm run test:run -- src/test/App.test.tsx -t "pre-selects the assignment named in an initial query string"
```

Expected: still FAIL: `CalibrationPage` now supports `initialAssignmentId`,
but nothing in `App.tsx` passes it yet, so the test still sees the empty
dropdown. Confirm the failure is specifically the assertion, not a compile
error; `npm run typecheck` should be clean for this file at this point.

- [ ] **Step 5: Typecheck**

```bash
npm run typecheck
```

Expected: no new errors from `CalibrationPage.tsx` (the pre-existing `route
=== 'home'` error in `App.tsx` from Task 2 is still present and expected
until Task 6).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/CalibrationPage.tsx frontend/src/test/App.test.tsx
git commit -m "feat(frontend): let CalibrationPage accept a pre-selected assignment id"
```

(The two tests added in Step 1 stay red until Task 6 wires `App.tsx` to
supply the prop; that's expected and is why Task 6 depends on this task's
output.)

---

## Task 6: Wire everything together in `App.tsx`, retire `HomePage`

depends-on: Task1 [output], Task2 [output], Task3 [output], Task4 [output],
Task5 [output]: this is the integration point; nothing here compiles
correctly until all five prior tasks' outputs exist.

**Files:**

- Modify: `frontend/src/App.tsx` (full rewrite)
- Delete: `frontend/src/pages/HomePage.tsx`

- [ ] **Step 1: Replace `App.tsx` in full**

```tsx
import { useEffect } from 'react'
import type { Assignment } from './api/types'
import { AppShell } from './components/AppShell'
import { ErrorState, LoadingState } from './components/PageState'
import { useAppData } from './hooks/useAppData'
import { AboutPage } from './pages/AboutPage'
import { CalibrationPage } from './pages/CalibrationPage'
import { ProgramSetupPage } from './pages/ProgramSetupPage'
import { RatingsPage } from './pages/RatingsPage'
import { RecommendationsPage } from './pages/RecommendationsPage'
import { WelcomePage } from './pages/WelcomePage'
import { WorkspacePage } from './pages/WorkspacePage'
import { useRoute } from './routing/routes'

/**
 * Validates the `assignment` query param against the assignments this
 * identity actually has, guarding against a stale bookmarked link to a
 * revoked assignment (which falls back to CalibrationPage's existing empty
 * "Choose assignment" state instead of erroring).
 */
function assignmentIdFromQuery(assignments: Assignment[]): string | undefined {
  const requested = new URLSearchParams(window.location.search).get('assignment')
  return requested && assignments.some((assignment) => assignment.id === requested)
    ? requested
    : undefined
}

function App() {
  const appData = useAppData()
  const { route, navigate } = useRoute()

  useEffect(() => {
    if (
      !appData.loading &&
      !appData.error &&
      route === 'programs' &&
      !appData.capabilities.canManagePrograms
    )
      navigate('calibration', true)
  }, [appData.capabilities.canManagePrograms, appData.error, appData.loading, navigate, route])

  if (appData.loading) return <LoadingState />
  if (appData.error)
    return <ErrorState message={appData.error} retry={() => void appData.reload()} />

  return (
    <AppShell
      access={appData.access}
      capabilities={appData.capabilities}
      route={route}
      navigate={navigate}
    >
      {route === 'welcome' && (
        <WelcomePage
          access={appData.access}
          capabilities={appData.capabilities}
          navigate={navigate}
        />
      )}
      {route === 'workspace' && (
        <WorkspacePage
          assignments={appData.assignments}
          programs={appData.programs}
          reviewers={appData.reviewers}
          capabilities={appData.capabilities}
          navigate={navigate}
        />
      )}
      {route === 'calibration' && (
        <CalibrationPage
          assignments={appData.assignments}
          programs={appData.programs}
          reviewers={appData.reviewers}
          initialAssignmentId={assignmentIdFromQuery(appData.assignments)}
        />
      )}
      {route === 'recommendations' && <RecommendationsPage reviewers={appData.reviewers} />}
      {route === 'ratings' && <RatingsPage reviewers={appData.reviewers} />}
      {route === 'programs' && appData.capabilities.canManagePrograms && (
        <ProgramSetupPage
          programs={appData.programs}
          reviewers={appData.reviewers}
          reload={appData.reload}
        />
      )}
      {route === 'about' && <AboutPage />}
    </AppShell>
  )
}

export default App
```

- [ ] **Step 2: Delete `HomePage.tsx`**

```bash
rm frontend/src/pages/HomePage.tsx
```

- [ ] **Step 3: Run the two tests that were red at the end of Task 5**

```bash
npm run test:run -- src/test/App.test.tsx -t "pre-selects the assignment named in an initial query string"
npm run test:run -- src/test/App.test.tsx -t "falls back to the empty dropdown for a stale assignment id"
```

Expected: both PASS now.

- [ ] **Step 4: Typecheck**

```bash
npm run typecheck
```

Expected: clean. The `route === 'home'` error from Task 2 is gone (no code
references the retired `'home'` member anymore), and `HomePage.tsx` no
longer exists to reference.

- [ ] **Step 5: Run the full unit suite and record what's still red**

```bash
npm run test:run
```

Expected: still FAILING at this point:

- `App.test.tsx`: `'shows assignment progress and a safe next action on the
  home page'`, `'offers reveal from home when only concealed holdout work
  remains'`, `'retries assignment progress without reloading the
  application'`: these three test `HomePage`'s retired hero/primary-action
  mechanism at `/`, which no longer exists. `WorkspacePage.test.tsx` (Task 4)
  already covers the equivalent behavior (role-aware rows, per-enrollment
  progress, and a retry test with an identical assertion) at `/home`, so
  these three are removed rather than rewritten; see Task 7.
- `revealAndLog.test.tsx`: the whole `'Landing page actions'` describe block
  (its premise, a single computed primary-action button, is retired by
  design), rewritten in Task 7.

Everything else in the suite (accessibility, contrast, useTheme, AboutPage,
`api-client`, the rest of `App.test.tsx`, `routes.test.ts`,
`roleLabelFor.test.ts`, `WelcomePage.test.tsx`, `WorkspacePage.test.tsx`)
should already be green.

- [ ] **Step 6: Lint**

```bash
npm run lint
```

Expected: no errors. (`HomePage.tsx` is gone, so nothing references its
removed exports.)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.tsx
git rm frontend/src/pages/HomePage.tsx
git commit -m "feat(frontend): wire Welcome/Workspace into App, retire HomePage"
```

---

## Task 7: Fix the remaining tests broken by retiring `HomePage`

depends-on: Task6 [output]

**Files:**

- Modify: `frontend/src/test/App.test.tsx` (remove 3 obsolete tests)
- Modify: `frontend/src/test/revealAndLog.test.tsx:194-229` (rewrite)

- [ ] **Step 1: Remove the three obsolete `App.test.tsx` tests**

Delete the three tests at `frontend/src/test/App.test.tsx:77-138` in full
(`'shows assignment progress and a safe next action on the home page'`,
`'offers reveal from home when only concealed holdout work remains'`,
`'retries assignment progress without reloading the application'`), keeping
the `describe('Calibration participant workflow', ...)` wrapper and every
other test in the file untouched. Their coverage now lives in
`WorkspacePage.test.tsx` (Task 4): the "next action" text assertions map to
that file's `'shows one row per open enrollment...'` test, and the retry
assertion maps 1:1 to its `'retries assignment progress without reloading
the application'` test.

- [ ] **Step 2: Rewrite `revealAndLog.test.tsx`'s `'Landing page actions'` block**

Replace lines 194-229 in full:

```tsx
describe('Welcome and workspace flow', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/')
  })

  it('continues from the welcome screen into the workspace', async () => {
    mockApi(revealedEnrollment())
    render(<App />)

    expect(
      await screen.findByText("Welcome, family-member, you're set up as Recorder.")
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

    expect(await screen.findByRole('button', { name: 'Log an encounter' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/home')
  })

  it('deep-links from a workspace calibration row directly into that assignment', async () => {
    mockApi(revealedEnrollment())
    window.history.replaceState({}, '', '/home')
    render(<App />)

    fireEvent.click(await screen.findByRole('button', { name: 'Continue calibration' }))

    expect(await screen.findByRole('heading', { name: 'Your calibration' })).toBeInTheDocument()
    expect(window.location.search).toBe('?assignment=assignment')
    expect(screen.getByLabelText('Evaluator and program')).toHaveValue('assignment')
    expect(await screen.findByRole('button', { name: /A82F/ })).toBeInTheDocument()
  })

  it('hides the calibration section for an identity with no assignments', async () => {
    get.mockImplementation((path: string) => {
      const responses: Record<string, unknown> = {
        '/reviewers': [{ id: 'r', name: 'Evaluator' }],
        '/calibration/programs': [],
        '/calibration/access': { username: 'manager-user', manager: true },
        '/calibration/enrollments': [],
      }
      return path in responses
        ? Promise.resolve({ data: responses[path] })
        : Promise.reject(new Error(`Unexpected request: ${path}`))
    })
    window.history.replaceState({}, '', '/home')
    render(<App />)

    await screen.findByRole('button', { name: 'Log an encounter' })
    expect(screen.queryByRole('heading', { name: 'Calibration work' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Manage programs' })).toBeInTheDocument()
  })
})
```

This drops the `import type { Route } from '@playwright/test'`-style unused
import risk: no new imports are needed, since `render`, `screen`,
`fireEvent`, `mockApi`, and `App` are all already imported at the top of this
file.

- [ ] **Step 3: Run the full unit suite**

```bash
npm run test:run
```

Expected: 100% pass, all previously-red tests now green.

- [ ] **Step 4: Coverage check**

```bash
npm run test:coverage
```

Expected: coverage stays at or above the repo's existing baseline. The three
removed `App.test.tsx` tests and the three rewritten `revealAndLog.test.tsx`
tests together exercise a superset of what was covered before (the same
`nextAction()` branches, the same retry path, plus the new deep-link and
role-gating paths), so this should not regress the 80% line / 70% branch
gates from `CLAUDE.md`.

- [ ] **Step 5: Typecheck and lint**

```bash
npm run typecheck
npm run lint
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/test/App.test.tsx frontend/src/test/revealAndLog.test.tsx
git commit -m "test(frontend): replace HomePage-era tests with Welcome/Workspace coverage"
```

---

## Task 8: Add a mocked Playwright spec for the new flow

depends-on: Task6 [completion] (exercises the fully-wired app in a real
browser; does not consume Task7's output, so this can run in parallel with
Task 7)

**Files:**

- Create: `frontend/e2e/welcome-and-workspace.spec.ts`

- [ ] **Step 1: Write the spec**

```ts
import { test, expect, type Route } from '@playwright/test'
import { bootstrapRoutes, enrollmentFixture, managerAccess, mockApi } from './support/mock-api'

// #ASSUME: data-integrity: bootstrapRoutes()'s fixed '/calibration/enrollments'
// fixture always seeds one assignment (id 'enr1'), regardless of which access
// fixture is passed, so every test here also mocks
// '/calibration/enrollments/enr1' to avoid an unmocked-501 request, matching
// the convention in blind-calibration.spec.ts and manager-authorization.spec.ts.
function withEnrollment(overrides: Parameters<typeof bootstrapRoutes>[0] = undefined) {
  return {
    ...bootstrapRoutes(overrides),
    '/calibration/enrollments/enr1': (route: Route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(enrollmentFixture(false)),
      }),
  }
}

test.describe('Welcome and workspace', () => {
  test('continues from welcome into a role-aware workspace', async ({ page }) => {
    await mockApi(page, withEnrollment())

    await page.goto('/')
    await expect(
      page.getByText('Learn your fragrance taste by measuring what you actually respond to.')
    ).toBeVisible()
    await page.getByRole('button', { name: 'Continue' }).click()

    await expect(page).toHaveURL('/home')
    await expect(page.getByRole('button', { name: 'Log an encounter' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Manage programs' })).toHaveCount(0)
  })

  test('offers program management from the workspace to a manager', async ({ page }) => {
    await mockApi(page, withEnrollment(managerAccess))

    await page.goto('/home')

    await expect(page.getByRole('button', { name: 'Manage programs' })).toBeVisible()
  })

  test('deep-links a calibration row directly into its assignment', async ({ page }) => {
    await mockApi(page, withEnrollment())

    await page.goto('/home')
    await page.getByRole('button', { name: 'Continue calibration' }).click()

    await expect(page).toHaveURL('/calibration?assignment=enr1')
    await expect(page.getByLabel('Evaluator and program')).toHaveValue('enr1')
    await expect(page.getByRole('button', { name: 'ABC-123' })).toBeVisible()
  })
})
```

- [ ] **Step 2: Run it**

From `frontend/`:

```bash
npm run test:e2e -- e2e/welcome-and-workspace.spec.ts
```

Expected: PASS (3 tests). This builds and previews the app first
(`playwright.config.ts`'s `webServer`), so the first run takes roughly a
minute.

- [ ] **Step 3: Run the full mocked e2e suite to confirm no regression**

```bash
npm run test:e2e
```

Expected: all specs pass, including the pre-existing
`manager-authorization.spec.ts`, `blind-calibration.spec.ts`,
`log-an-encounter.spec.ts`, `recommendation-feedback.spec.ts`, and
`accessibility.spec.ts`.

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/welcome-and-workspace.spec.ts
git commit -m "test(frontend): add mocked e2e coverage for welcome/workspace and the calibration deep link"
```

---

## Self-Review

**1. Spec coverage (clause-level).** Every clause of the design's "Design"
section maps to a task: routing changes → Task 2; `WelcomePage` content →
Task 3; `WorkspacePage` rows and terminology fix → Tasks 2 and 4;
`CalibrationPage` deep-link fix → Tasks 5-6; error handling (stale query
param falls back to the empty dropdown) → Task 5's second test; mobile (no
new breakpoint system) → no code changes required, nothing to implement.
Testing section: the e2e-smoke citation was corrected (see "Deviation from
the source spec" above) and retargeted to the mocked `e2e/` suite (Task 8);
the deferred mobile-viewport UX subagent re-test is explicitly out of this
plan's scope, as the spec itself says.

**2. Placeholder scan.** No TBD/TODO/"add error handling" language anywhere
in the tasks above; every step shows literal, complete code.

**3. Type consistency.** `Route`, `Capabilities`, `Access`, `Assignment`,
`Enrollment`, `Person`, `Program` are used identically to their existing
definitions in `api/types.ts` across every new file. `navigate`'s signature
`(route: Route, replace?: boolean, query?: string) => void` is consistent
between `routes.ts`'s `useRoute()` return value, `WorkspacePageProps`, and
every call site.

**4. Shell command environment.** All commands are plain `npm run` scripts
run from `frontend/`; none import their own package or need `PYTHONPATH`-style
setup.

**5. Capability probe.** Not applicable; no managed cloud API involved.

**6. Test-helper consistency.** Every new Vitest file reuses the exact
`vi.hoisted`/`vi.mock('axios', ...)` bootstrap pattern already used in
`App.test.tsx`, `documentTitle.test.tsx`, and `revealAndLog.test.tsx`
(verified by reading all three in full during discovery), rather than
inventing new mocking infrastructure. Every new Playwright spec reuses
`mockApi`/`bootstrapRoutes`/`enrollmentFixture`/`managerAccess` from
`e2e/support/mock-api.ts` exactly as `blind-calibration.spec.ts` and
`manager-authorization.spec.ts` already do.

**7. Tool-replacement coupling table.** Not applicable; no tool is being
replaced.

**8. Nox/pytest session names.** Not applicable; this is a frontend-only
plan (no Python/nox involved).

**9. pytest config sanity.** Not applicable.

**10. Cross-requirement consistency sweep.** The plan touches routing
(Task 2), two new page components (Tasks 3-4), one existing page's prop
contract (Task 5), and the integration point (Task 6): four interacting
pieces, enough to warrant the pairwise check:

| Pair | Compatible? |
| --- | --- |
| `welcome`/`workspace` routes (Task 2) × `WelcomePage`'s `navigate('workspace')` (Task 3) | Compatible: `workspace` exists in the `Route` union before `WelcomePage` references it (Task 3 depends on Task 2). |
| `navigate()`'s query param (Task 2) × `WorkspacePage`'s `navigate('calibration', false, ...)` (Task 4) | Compatible: same dependency ordering. |
| `CalibrationPage`'s `initialAssignmentId` (Task 5) × `App.tsx`'s `assignmentIdFromQuery` (Task 6) | Compatible: Task 6 depends on Task 5's output; the prop and its caller are written in the same integration step. |
| Encounter-logging rename (Task 2) × `WorkspacePage`'s "Log an encounter" row (Task 4) | Compatible: both use the identical string; Task 4 depends on Task 2. |
| `roleLabelFor` (Task 1) × `WelcomePage`'s identity line (Task 3) | Compatible: independent tasks, but `WelcomePage`'s code imports `roleLabelFor` from `api/types`, which Task 1 must land first for that import to resolve. **Task 3's dependency list is corrected to also include Task1 [output]** (it was omitted above; add it before starting Task 3). |
| Calibration section's conditional render (`assignments.length > 0`, Task 4) × the "hides calibration section" UX finding (spec's folded-in finding 3) | Compatible: this is exactly what resolves that finding; verified by Task 4's and Task 7's dedicated tests. |

No unresolved conflicts. One correction was found and is folded into the
task list above: **Task 3 depends on Task 1 [output] in addition to Task 2
[output]** (its `import { roleLabelFor } from '../api/types'` requires
Task 1's export to exist).

**11. Assertion discrimination check.** The deep-link tests
(`WorkspacePage.test.tsx`'s `'shows one row per open enrollment...'`,
`App.test.tsx`'s two new `initialAssignmentId` tests, and the Playwright
spec's `'deep-links a calibration row...'`) all assert
`toHaveValue('assignment' | 'enr1')` on the actual `<select>` element, which
fails against the pre-fix code (state always initializes to `''`) and passes
only once `initialAssignmentId` is threaded through: a real revert-probe,
not a vacuous check. The "hides calibration section" tests assert
`.not.toBeInTheDocument()` on the heading itself (not a substring or count
check on a compound value), which fails against the pre-fix
always-rendered-with-EmptyState behavior.

**12. Blast-radius sweep.** The only shared surface touched is
`navigationItems` and the `Route` union (Task 2), both exported from
`routes.ts`. Every consumer was enumerated during discovery
(`AppShell.tsx`, `App.tsx`, `useDocumentTitle` via `documentTitleFor`, and
every test file that renders `<App />`) and each one's necessary update is
covered by an explicit task step above. No other file references `Route` or
`navigationItems`.

---

## Execution Handoff

Plan complete and saved to
`docs/superpowers/plans/2026-09-20-welcome-and-workspace-implementation.md`.

Two execution options:

1. **Subagent-Driven (recommended)**: dispatch each task to a fresh
   subagent per this plan's dependency graph (Tasks 1, 2, and 5 can start in
   parallel; Tasks 3 and 4 start once Task 2 lands, and per the Self-Review
   correction, Task 3 also waits on Task 1; Task 6 waits on all of Tasks
   1-5; Tasks 7 and 8 both wait on Task 6 and can run in parallel with each
   other).
2. **Inline Execution**: work through the tasks yourself in this session,
   in dependency order.

Which approach?
