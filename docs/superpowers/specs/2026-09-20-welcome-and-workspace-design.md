---
title: "Welcome Screen and Role-Aware Workspace Selector Design"
schema_type: common
status: draft
owner: core-maintainer
purpose: "Design a post-auth welcome screen and role-aware workspace selector, replacing HomePage's mixed layout, folding in three UX findings from the prior test round."
tags:
  - frontend
  - design
  - architecture
---

Date: 2026-09-20
Related: prior UX test round (2026-09-20, Manager/Recorder/Participant subagents,
not yet committed to a doc) surfaced the findings this design folds in.

## Problem

`HomePage` mixes three unrelated jobs on one screen: an orientation statement
("your scent journal" plus an explanation of the two record types), a single
computed "next action," and a per-enrollment calibration status list. New
users get no dedicated first-impression screen, and on a phone-width viewport
the mixed layout is harder to scan than a short, role-aware menu would be.

Separately, three findings from the prior desktop UX test round touch the
exact code this work rebuilds, so they're folded in rather than deferred:

1. The same feature is called "Record an encounter" (button), "My Ratings"
   (nav), and "Ordinary encounters" (heading) in different places.
2. Every assignment row's "Continue calibration" button calls
   `navigate('calibration')` with no assignment id
   (`HomePage.tsx:207`), so `/calibration` always opens on an empty
   "Choose assignment" dropdown regardless of which row was clicked.
3. A manager's account has no evaluator enrollment of its own, so nothing
   explains why "My Ratings" looks unusable to that identity: a role-aware
   menu that only lists what an identity can actually do addresses this
   directly.

## Constraint that shaped this design

`docker-compose.prod.yml:82` wires Traefik's forward-auth middleware onto
the frontend router itself, not onto individual app routes. Every request
to this app in production, including the very first request for `/`, is
already authenticated by Authentik before Traefik proxies it here (ADR-008).
There is no request this frontend ever serves that hasn't already passed
that gate. So "pre-authentication landing page" can only mean the first
screen a user sees after that infra-level handoff, not a publicly-reachable
marketing route: that distinction doesn't exist in this app's trust model
the way it does in an app with its own session layer.

A reference pattern was pulled from `CYO_Adventure` (separate `LandingPage`
and `ConsolePage` components, the latter a role-aware list of action rows).
Its component-level separation is worth keeping: a lightweight orientation
screen stays independent of the data-heavy role menu. Its route-level
separation (public vs. authenticated) has no equivalent here, since nothing
in this app is ever unauthenticated.

## Design

### Routing

Two new entries in `routes.ts`'s `Route` union and `navigationItems`:

- `welcome`: path `/`, renders `WelcomePage`
- `workspace`: path `/home`, renders `WorkspacePage` (replaces `HomePage`'s
  slot; `HomePage.tsx` is retired, its three sections redistributed per
  below)

Both remain in `navigationItems` (not `hiddenFromNav`), so both are always
reachable from nav regardless of how a session started, per the decision to
show the welcome screen on every load rather than gating it behind a
first-visit flag.

`navigate()` in `routes.ts:85-90` gains an optional third parameter for a
query string, so a caller can deep-link with state:

```ts
const navigate = useCallback((next: Route, replace = false, query = '') => {
  const path = pathFor(next)
  const search = query ? `?${query}` : window.location.search
  const url = `${path}${search}${window.location.hash}`
  window.history[replace ? 'replaceState' : 'pushState']({}, '', url)
  setRoute(next)
}, [])
```

### WelcomePage (new)

No new API calls. `access` (username, manager flag) is already resolved by
`useAppData` before any page renders (`App.tsx`'s loading gate), so
`WelcomePage` receives it as a prop like every other page does.

Content:

- Hero statement: "Learn your fragrance taste by measuring what you
  actually respond to." (the same sentence already used in `AboutPage.tsx`,
  so the two pages don't drift).
- Identity line: "Welcome, {username}, you're set up as {role}," reusing
  the same `capabilities`-derived role label (`Manager`, `Recorder`, or
  `Participant`) already computed in `AppShell.tsx:19-23`, so the label
  can't drift from what the masthead shows.
- Single primary CTA, "Continue," navigating to `workspace`.
- A link to the existing `/about` page for the full methodology: no
  content duplication; `AboutPage` already tested well in the prior round
  and stays the deep-dive reference.

### WorkspacePage (replaces HomePage)

Role-aware list of interactive rows (mirroring CYO's `console-list`
pattern), built entirely from data `HomePage` already receives
(`assignments`, `programs`, `reviewers`), with no new endpoints:

- **Participant** (baseline, always shown): "Log an encounter" links to
  `ratings`; "See recommendations" links to `recommendations`.
- **Recorder addition** (`assignments.length > 0`): one row per open
  enrollment, each showing program/evaluator and locked-screen count
  exactly as `HomePage.tsx:169-217` does today, but its "Continue
  calibration" button now calls `navigate` with the enrollment's id as a
  query string (`assignment=<id>`), instead of the bare `navigate('calibration')`.
- **Manager addition** (`canManagePrograms`): "Manage programs" links to
  `programs`.

The reassurance copy (`HomePage.tsx:219-230`) moves to a persistent footer
note on `WorkspacePage` rather than sharing top billing with the action
list.

**Terminology fix**: the encounter-logging feature is renamed consistently
to "Log an encounter" everywhere it appears: the nav label (`My Ratings`
becomes `Log an encounter`), the workspace row, and `RatingsPage`'s own
heading. One name, one place it's defined (`navigationItems`'s `label`
field), referenced everywhere else instead of re-typed.

### Deep-link fix (CalibrationPage)

`CalibrationPageProps` gains an optional `initialAssignmentId?: string`.
`App.tsx`'s render of `CalibrationPage` reads an `assignment` query param
from `window.location.search`, validates it's present in
`appData.assignments` (guards against a stale bookmarked link to a
revoked assignment), and passes it through; `CalibrationPage`'s
`assignmentId` state (`CalibrationPage.tsx:78`) initializes from that prop
instead of `''`. An invalid or missing id falls back to today's behavior:
the empty "Choose assignment" placeholder.

### Error handling

No new failure surfaces beyond what exists: `WelcomePage` and
`WorkspacePage` both render only after `useAppData`'s bootstrap already
succeeded (`App.tsx`'s loading/error gate is unchanged), so neither needs
its own loading or error state beyond what `WorkspacePage` already inherits
from `HomePage`'s per-enrollment fetch effect. The one new edge case, a
stale `assignment` query param, degrades to the existing empty-dropdown
state rather than erroring.

### Mobile

No new breakpoint system: `WorkspacePage`'s row list is a vertical list by
default (no grid-reflow rules needed, unlike a card grid), and existing
44px touch targets and the `40rem`/`58rem` breakpoints in `layout.css` and
`components.css` already apply to any new markup built from the same
`.cyo-card`-equivalent row styles.

## Testing

- Extend `frontend/e2e-smoke/disclosure-and-authorization.spec.ts`'s
  header-based role pattern (`X-Authentik-Username` set at context creation)
  with specs for: `WelcomePage` shows the correct name/role and its
  Continue button reaches `WorkspacePage`; `WorkspacePage` shows the correct
  row set per role (reusing `participantAccess`/`managerAccess` fixtures
  from `frontend/e2e/support/mock-api.ts`); the calibration deep link opens
  pre-selected; a stale `assignment` param falls back cleanly.
- After implementation, dispatch the same three role subagents
  (Manager, Recorder, Participant) from the prior UX round, same App Store
  description, this time at a phone-width viewport, against the full
  rebuilt flow (Welcome, then Workspace, then destination pages). This is a
  separate validation step, not part of this implementation plan.

## Out of scope

- Any change to how Authentik/Traefik authenticates requests (ADR-008
  stands unchanged).
- Any per-user "seen the welcome screen" persistence: it's shown every
  load, per explicit decision.
- New backend endpoints or role/capability logic: `WorkspacePage`'s menu
  is built entirely from data already fetched today.
