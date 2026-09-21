---
title: "Calibration Workflow: Guided Entry, Resume, and Component Retest Design"
schema_type: common
status: draft
owner: core-maintainer
purpose: "Design entry-screen routing for the calibration workflow so first-time evaluators get a guided step-by-step flow, returning evaluators can resume or choose a full baseline versus a specific component, and managers can self-assign new work without a second enroll form."
tags:
  - frontend
  - design
  - architecture
---

Date: 2026-09-20
Related: builds directly on
[2026-09-20-welcome-and-workspace-design.md](2026-09-20-welcome-and-workspace-design.md),
which added `CalibrationPage`'s `initialAssignmentId` deep-link prop; this
design reuses that prop rather than replacing it. Implements the "resume the
next valid calibration step" and "explain progress, lock consequences, and
reveal eligibility" acceptance criteria already stated as P4.3/P4.4 in
[PROJECT-PLAN.md](../../planning/PROJECT-PLAN.md).

## Problem

`CalibrationPage` presents one flat form to every evaluator regardless of
history: pick an assignment from a dropdown, then manually navigate BLOTTER
and SKIN stage tabs. There is no first-time orientation, no "pick up where I
left off," and no way to ask for just the skin component without re-touching
blotter observations that are already locked. `enroll()`
([api/calibration.py:264](../../../src/fragrance_rater/api/calibration.py))
requires manager identity, so a plain participant can never start a new
baseline or component retest themselves; the current UI doesn't route that
request anywhere.

## Constraints that shaped this design

- No schema or migration changes. Given the two calibration-adjacent
  incidents already on record (an Alembic revision id collision and a
  production database that was never migrated at all), adding new
  columns/enums here is unjustified risk for what is fundamentally a UI
  orchestration problem, not a data modeling gap.
- Manager-only enrollment creation is a deliberate part of the controlled,
  blind-testing protocol (ADR-005): a participant choosing to redo "the
  skin component" cannot mean the frontend fabricates a new enrollment on
  the spot. It has to mean either resuming what's already assigned, or
  routing a manager through the one enroll mechanism that already exists.
- `Membership.group_name` (default `"Baseline"`, already entered by managers
  in `ProgramSetupPage`'s member form) is treated as the existing, if
  informal, convention for what a program is *for*. This design formalizes
  reading it, not inventing a new taxonomy field.
- `ProgramSetupPage`'s enrollment form (evaluator picker, recorder
  usernames, session size, gated on `status === 'active'`) already does
  everything a self-assign action needs. This design links to it instead of
  building a second one.

## Design

### 1. Entry routing (`CalibrationPage`)

`CalibrationPage` gains a routing step that runs before rendering the
existing observation form, using an enriched `GET /calibration/enrollments`
response (see §4). It only applies when no `initialAssignmentId` is present;
an explicit deep link (e.g. a "Continue calibration" click from
`WorkspacePage`) always opens that exact assignment directly, unchanged from
today's behavior.

```text
enrollments = GET /calibration/enrollments  // now includes revealed, has_started,
                                             // blotter/skin totals, group_name

incomplete   = enrollments.filter(e => !e.revealed)
inProgress   = incomplete.filter(e => e.has_started)
notStarted   = incomplete.filter(e => !e.has_started)

if inProgress non-empty:      -> Resume flow on the first inProgress enrollment
elif notStarted non-empty:    -> Guided first-timer flow on the first notStarted enrollment
elif enrollments non-empty:   -> Choice screen (all revealed: full baseline vs. component)
else:                         -> Empty state ("nothing assigned yet")
```

`Enrollment` has no creation timestamp and its `id` is a random UUID
(`identifier()`), so there is no true chronological order to pick from
without a new column, which this design's constraints rule out. "First"
here means the same `order_by(Enrollment.id)` tiebreak
`manager_enrollments` already uses: stable and deterministic across
requests, but not a claim about which enrollment is actually older. If a
manager somehow has more than one `inProgress` or `notStarted` enrollment at
once (not expected at this household's scale, but not prevented by the
schema), this picks one of them consistently and does not add a
multi-enrollment chooser for this release; that's an accepted limitation,
not an oversight (see Out of scope).

**`has_started`** comes from the enrichment in §4, not new client-side
state.

### 2. Guided wizard

A new component, `GuidedCalibrationFlow`, replaces manual stage-tab
navigation for the first-timer and resume paths:

- One sample/stage step at a time, a linear progress indicator ("Step 3 of
  9"), Next/Back only: no jump-ahead select.
- The observation form fields themselves are unchanged: it renders the same
  `calibrationScales.ts`-driven inputs the current page already uses, just
  one step's worth at a time instead of all-at-once with manual tab
  switching.
- "Next valid step" ordering is computed the same way
  `CalibrationService.reveal_blocker()` already orders things: skin plan
  decision, then remaining BLOTTER locks, then remaining SKIN locks, then
  the reveal action itself. No new ordering logic is invented; the wizard
  reads the same precedence the reveal gate already enforces.
- The choice screen and the plain "browse my assignments" case both still
  render through the existing dropdown-based view for now; only the
  first-timer and resume paths get the new linear wizard in this iteration
  (see Out of scope).

### 3. Choice screen (all-revealed returning evaluator)

Two actions, both requiring the target program to have open capacity
(status `active`, evaluator not already enrolled):

- **Start a new full baseline**: only surfaced if an active `Program` whose
  memberships are predominantly `group_name = "Baseline"` exists and this
  evaluator isn't enrolled in it yet.
- **Redo a specific component**: same check, but for an active `Program`
  whose memberships are predominantly a non-`"Baseline"` `group_name`
  (e.g. `"Skin Retest"`); the button label uses that `group_name` verbatim
  so the manager's own naming is what the participant sees.

Each action is visible only when `access.manager` is `true` (from the
existing `/calibration/access` response). A non-manager returning evaluator
with nothing new assigned sees only a plain "nothing new assigned right now"
message, never a dead button.

Selecting either action navigates to `/program-setup?program=<id>`.
`ProgramSetupPage` gains an optional `initialProgramId?: string` prop,
following the exact pattern `CalibrationPage.initialAssignmentId` already
established: `App.tsx` reads the `program` query param, validates it against
`appData.programs`, and passes it through; `programId` state
(`ProgramSetupPage.tsx:70`) initializes from that prop instead of `''`. The
manager lands with that program already selected and uses the existing
"2. Enrollment" form to enroll themselves. No new form is built.

### 4. Backend: enrich `GET /calibration/enrollments`

Extends the existing handler
([api/calibration.py:273](../../../src/fragrance_rater/api/calibration.py))
rather than adding a new route. Same permission filter as today
(`admin or username in e.recorder_usernames`); the added fields are exactly
the participant-safe subset `manager_enrollments`
([api/calibration.py:285](../../../src/fragrance_rater/api/calibration.py))
already computes for the manager console, so nothing new is exposed that a
manager-facing endpoint doesn't already compute:

- `revealed: bool` (`item.revealed_at is not None`, already used)
- `has_started: bool`: true if any `Observation` row exists for any
  presentation under this enrollment, regardless of lock state. This is the
  one genuinely new signal; everything else below already exists in
  `manager_enrollments`'s per-enrollment loop.
- `total_presentations`, `blotter_complete`, `skin_planned`, `skin_complete`:
  same computation already used for the manager progress cards.
- `program_name`, `program_version`: already joined for the manager view.
- `group_name_summary: str`: the single dominant `group_name` across this
  enrollment's memberships (its presentations' underlying `Membership`
  rows), or `"Mixed"` if genuinely split. Used only as a display label
  ("Baseline" vs. e.g. "Skin Retest"); it does not change wizard behavior.

No new Pydantic model beyond widening the existing response dict; no schema
or migration change.

## Error handling

- **No active program available for a choice-screen action**: the button
  simply doesn't render for that action rather than rendering disabled with
  an unexplained tooltip, consistent with how `ProgramSetupPage` already
  hides `status !== 'active'` actions.
- **`has_started` query fails or an enrollment has zero presentations
  loaded yet** (e.g. mid-provisioning by a manager): treated as
  `notStarted`, not an error state: worst case a participant re-lands on
  step 1 of a wizard with nothing to show yet, matching today's dropdown
  behavior for the same edge case.
- **Deep link (`initialAssignmentId`) to a revealed or fully-locked
  enrollment**: unchanged from today; the existing page already renders
  read-only post-reveal state for that case.

## Testing

- Extend `frontend/e2e/blind-calibration.spec.ts` with the three new entry
  states: never-started (guided wizard opens on step 1), in-progress
  (wizard opens on the correct next step per `reveal_blocker` ordering), and
  all-revealed (choice screen renders, and only for a manager identity).
- New unit tests for the `has_started` / `group_name_summary` enrichment in
  `tests/unit/test_api/test_calibration.py`, mirroring the existing
  `manager_enrollments` coverage in
  `tests/unit/test_services/test_calibration_service.py`.
- Deep-link regression: `?assignment=<id>` still bypasses routing entirely,
  proving the two features (this design's routing, and the prior
  `initialAssignmentId` work) don't fight each other.

## Out of scope

- A multi-enrollment chooser for the rare case of more than one
  simultaneously in-progress or not-started enrollment; the stable-order
  tiebreak in §1 is accepted for this iteration.
- Converting the choice-screen and plain-browse views to the linear wizard;
  only first-timer and resume get it now.
- Any change to `enroll()`'s manager-only permission, or to the blind
  experimental role system (`RETEST`, `HOLDOUT`, etc.) itself.
- An inline enroll form inside `CalibrationPage`; self-assign always routes
  through `ProgramSetupPage`'s existing form.
