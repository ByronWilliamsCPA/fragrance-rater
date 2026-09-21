---
title: "Calibration Workflow: Guided Entry, Resume, and Component Retest Implementation Plan"
schema_type: planning
component: Strategy
source: "docs/superpowers/specs/2026-09-20-calibration-workflow-design.md"
status: draft
owner: core-maintainer
purpose: "Implement the approved entry-routing design: backend enrichment of GET /calibration/enrollments, a pure routing decision, a linear guided wizard for first-timer/resume evaluators, a manager-only choice screen for redo/self-assign, and the ProgramSetupPage deep-link wiring, each with test coverage."
tags:
  - frontend
  - testing
  - architecture
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Goal

Replace `CalibrationPage`'s always-visible manual dropdown with routing that
opens a linear guided wizard for a first-timer or in-progress evaluator, a
manager-only choice screen for a returning evaluator whose work is all
revealed, and leaves the existing manual dropdown reachable as an explicit
fallback. Backed by an enrichment of the existing `GET /calibration/enrollments`
list (no new route), and a deep-link wiring on `ProgramSetupPage` so a
self-assign action lands on the right program's enrollment form.

## Architecture

Backend: `enrollments()` in `api/calibration.py` gains the same per-enrollment
computation `manager_enrollments()` already does, plus one genuinely new
signal (`has_started`, from `CalibrationService`) and one new pure label
helper (`group_name_summary`, also on `CalibrationService`). No schema change.

Frontend: a new pure function (`calibrationEntryFor`) decides, from the
enriched list, whether to show the wizard, the choice screen, or fall through
to the existing dropocratic view. The existing ~200-line sample-detail-and-form
JSX in `CalibrationPage` is extracted into `SampleObservationPanel` first (a
pure refactor, no behavior change) so the new `GuidedCalibrationFlow` wizard
can reuse it instead of duplicating it. `CalibrationChoiceScreen` is new and
manager-gated. `ProgramSetupPage` gains an `initialProgramId` prop mirroring
`CalibrationPage.initialAssignmentId`, wired through `App.tsx` the same way
`assignmentLinkFor` already is.

## Tech Stack

React 19, TypeScript strict mode, Vitest + `@testing-library/react` (existing
convention: tests render `<App />` with mocked `axios`), Playwright for the
mocked `e2e/` suite, FastAPI + SQLAlchemy async for the backend, pytest +
pytest-asyncio.

## Spec clarifications resolved during planning

The approved spec ([2026-09-20-calibration-workflow-design.md](../specs/2026-09-20-calibration-workflow-design.md))
left two implementation-level gaps; both are resolved here rather than left
ambiguous, per the source-of-truth review already fixing the spec's
`ProgramSetupPage.tsx:70` citation to the verified `:59`.

1. **Where the choice screen's per-program `group_name` comes from.** §3
   requires distinguishing an active program whose memberships are
   predominantly `"Baseline"` from one that is predominantly some other
   `group_name`, but §4's backend enrichment only touches
   `GET /calibration/enrollments` (existing enrollments), not
   `GET /calibration/programs` (candidate programs the evaluator is *not yet*
   enrolled in). Adding a second backend enrichment was rejected: it would
   widen `/calibration/programs`'s payload for every identity (including
   non-managers, who cannot see membership data at all per `manager()` on
   `members()`, `api/calibration.py:138-143`), which is a bigger blast radius
   than the spec's own "no new routes" framing intended. Instead, since §3's
   actions are manager-gated already (`access.manager === true`), the choice
   screen re-uses the existing manager-only
   `GET /calibration/programs/{id}/members` endpoint client-side, exactly as
   `ProgramSetupPage` already does, scoped to the small set of active
   programs the evaluator isn't yet enrolled in (household-scale, per the
   spec's own "not expected at this household's scale" framing).
2. **What "this evaluator isn't enrolled in it yet" means**, given
   `GET /calibration/enrollments` returns every enrollment a manager identity
   can see (all reviewers, not just "self": Reviewer records have no
   explicit link to the signed-in Authentik identity anywhere in the data
   model). Resolved as a program-level check across all assignments visible
   to the signed-in identity, not a per-reviewer check: a program is a
   self-assign candidate only if none of `assignments` already names it. This
   matches the spec's own Error Handling framing for this exact button
   ("the button simply doesn't render" is explicitly tolerated as best-effort,
   not a data-integrity guarantee); the real protocol invariants remain
   enforced server-side by `enroll()`, unchanged by this plan.

## Codebase discovery (verified against the worktree, 2026-09-20)

- `api/calibration.py:273-281` is the current `enrollments()` handler (bare
  `{id, program_id, reviewer_id}` list comprehension). `api/calibration.py:284-327`
  is `manager_enrollments()`, whose per-enrollment loop (fetch `program`,
  `reviewer`, `presentations`, `members`, then compute `blotter_complete`,
  `skin_planned`, `skin_complete`, call `service.reveal_blocker(...)`) is the
  pattern this plan's Task 3 extends.
- `services/calibration_service.py:470-487` is the existing static
  `reveal_blocker()`; `:316-329` is `presentations()`. Both are reused
  unchanged.
- `frontend/src/api/types.ts:14-18` (`Assignment`), `:101-107` (`Enrollment`,
  the *detail* shape from `GET /calibration/enrollments/{id}`, not the list),
  `:143-155` (`ProgramMember`) are the types this plan extends or reuses.
  `useAppData.ts:12,25,55` fetches the *list* endpoint typed as `Assignment[]`
  today; this is what gains the new fields, via a new `EnrollmentSummary`
  type, not `Enrollment`.
- `frontend/src/pages/CalibrationPage.tsx` (543 lines) is read in full for
  this plan. Its sample-detail-and-form JSX (lines 332-537) plus the `save()`
  function (lines 178-206) is what Task 6 extracts. Its deep-link `useEffect`
  (lines 147-176) and its dropdown/workspace section (lines 208-542) are
  reused unchanged inside the new `manualBrowse` fallback path.
- `frontend/src/pages/ProgramSetupPage.tsx:58-70`: `programId` state is at
  line 59 (`const [programId, setProgramId] = useState('')`); line 70 is the
  derived `selectedProgram`, confirming the spec fix above. The "2. Enrollment"
  form is lines 450-481.
- `frontend/src/App.tsx:81-90` (`CalibrationPage` render) and `:94-100`
  (`ProgramSetupPage` render, currently no query-param wiring) are both
  modified. `frontend/src/routing/routes.ts:123-145` (`assignmentQuery`,
  `assignmentLinkFor`) is the exact pattern Task 10 mirrors for `program`.
- **Blast radius, confirmed by grep, not guessed:** `App.test.tsx:60`
  (top-level `beforeEach` for the whole "Calibration participant workflow"
  describe block, feeding tests at lines 78/85/101/114) and
  `revealAndLog.test.tsx:103` both set `window.location` to `/calibration`
  with **no** `?assignment=` query and then immediately interact with the
  `Evaluator and program` dropdown. Once routing is live, a single
  not-yet-revealed, not-yet-started enrollment (exactly what these fixtures
  describe) resolves to `{ kind: 'guided' }`, not the dropdown, so both break
  without an explicit fix. `App.test.tsx:1265,1273,1292,1303` already use
  `?assignment=assignment` (the deep-link regression tests from the prior,
  already-merged welcome/workspace plan) and need no change: they are the
  existing proof that a deep link bypasses routing. `accessibility.test.tsx:28`
  also sets bare `/calibration`; Task 11 triages it by running the suite,
  not by guessing its assertions. `frontend/e2e/support/mock-api.ts:54-68`
  (`bootstrapRoutes()`) is the shared fixture every e2e spec inherits; its
  `/calibration/enrollments` entry needs the new fields so a spec that
  navigates to `/calibration` without a query still exercises intentional
  behavior instead of accidentally landing on the new wizard.
- `frontend/package.json` scripts: `"test:run": "vitest run"`,
  `"typecheck": "tsc -b"`, `"test:e2e": "playwright test"`. Backend:
  `uv run pytest`, per root `CLAUDE.md`.
- `docs/_data/tags.yml` allows `frontend`, `testing`, `architecture` (already
  used by the sibling `2026-09-20-welcome-and-workspace-implementation.md`
  plan, whose frontmatter shape this plan copies exactly:
  `schema_type: planning`, `component: Strategy`, `source: <spec path>`).
  `docs/superpowers/plans/` is not gitignored.

## File Structure

- Modify: `src/fragrance_rater/services/calibration_service.py` (add
  `has_started`, `group_name_summary`)
- Modify: `src/fragrance_rater/api/calibration.py` (rewrite `enrollments()`)
- Modify: `tests/unit/test_services/test_calibration_service.py`
- Modify: `tests/unit/test_api/test_calibration.py`
- Modify: `frontend/src/api/types.ts` (add `EnrollmentSummary`)
- Modify: `frontend/src/hooks/useAppData.ts` (fetch as `EnrollmentSummary[]`)
- Create: `frontend/src/routing/calibrationEntry.ts` (pure routing decision)
- Create: `frontend/src/test/calibrationEntry.test.ts`
- Create: `frontend/src/pages/SampleObservationPanel.tsx` (extracted from
  `CalibrationPage`)
- Create: `frontend/src/pages/GuidedCalibrationFlow.tsx`
- Create: `frontend/src/test/GuidedCalibrationFlow.test.tsx`
- Create: `frontend/src/pages/CalibrationChoiceScreen.tsx`
- Create: `frontend/src/test/CalibrationChoiceScreen.test.tsx`
- Modify: `frontend/src/pages/CalibrationPage.tsx` (routing wiring, `access`
  prop, extraction of `SampleObservationPanel`/`save()`)
- Modify: `frontend/src/pages/ProgramSetupPage.tsx` (`initialProgramId` prop)
- Modify: `frontend/src/routing/routes.ts` (`programQuery`, `programLinkFor`)
- Modify: `frontend/src/App.tsx` (pass `access` to `CalibrationPage`, wire
  `programLinkFor` to `ProgramSetupPage`)
- Modify: `frontend/src/test/App.test.tsx`, `frontend/src/test/revealAndLog.test.tsx`,
  `frontend/src/test/accessibility.test.tsx` (blast-radius fixes)
- Modify: `frontend/e2e/support/mock-api.ts` (`bootstrapRoutes()` fixture)
- Modify: `frontend/e2e/blind-calibration.spec.ts` (bypass routing via
  `?assignment=`)
- Create: new states in `frontend/e2e/blind-calibration.spec.ts` (or a new
  `frontend/e2e/calibration-entry.spec.ts`) for guided/choice/deep-link states

---

## Task 1: `CalibrationService.has_started`

**Files:**
- Modify: `src/fragrance_rater/services/calibration_service.py:329` (insert
  after `presentations()`)
- Test: `tests/unit/test_services/test_calibration_service.py`

depends-on: none

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_services/test_calibration_service.py`:

```python
@pytest.mark.asyncio
async def test_has_started_false_until_first_observation(protocol):
    service, *_ = protocol
    enrollment = await enroll(protocol)
    presentations = await service.presentations(enrollment.id)
    assert await service.has_started({p.id for p in presentations}) is False
    await service.observe(
        presentations[0].id,
        ResponseInput(stage="BLOTTER", detected=True, intensity=2, liking=5),
        "family-recorder",
        admin=False,
    )
    assert await service.has_started({p.id for p in presentations}) is True


@pytest.mark.asyncio
async def test_has_started_false_for_empty_presentation_set(protocol):
    service, *_ = protocol
    assert await service.has_started(set()) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_services/test_calibration_service.py -k has_started -v`
Expected: FAIL with `AttributeError: 'CalibrationService' object has no attribute 'has_started'`

- [ ] **Step 3: Write minimal implementation**

Insert into `src/fragrance_rater/services/calibration_service.py` immediately
after `presentations()` (after line 329, before `async def target(...)`):

```python
    async def has_started(self, presentation_ids: set[str]) -> bool:
        """True if any Observation exists for any of the given presentations.

        Reports raw participation regardless of lock state, distinct from
        `blotter_locked_at`/`skin_locked_at`: an evaluator who has answered
        but not yet locked a sample has still "started."
        """
        if not presentation_ids:
            return False
        return (
            await self.db.scalar(
                select(Observation.id).where(
                    Observation.presentation_id.in_(presentation_ids)
                )
            )
        ) is not None
```

This needs `select` (already imported at the top of the file) and
`Observation` (already imported at the top of the file); no new imports.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_services/test_calibration_service.py -k has_started -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/fragrance_rater/services/calibration_service.py tests/unit/test_services/test_calibration_service.py
git commit -S -m "feat(calibration): add CalibrationService.has_started"
```

---

## Task 2: `CalibrationService.group_name_summary`

**Files:**
- Modify: `src/fragrance_rater/services/calibration_service.py` (insert after
  `has_started`, from Task 1)
- Test: `tests/unit/test_services/test_calibration_service.py`

depends-on: Task1 [completion]

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_services/test_calibration_service.py`:

```python
@pytest.mark.asyncio
async def test_group_name_summary_single_value(protocol):
    service, program, base, repeat, holdout = protocol
    enrollment = await enroll(protocol)
    presentations = await service.presentations(enrollment.id)
    members = {
        m.id: m
        for m in [base, repeat, holdout]
    }
    assert service.group_name_summary(members, presentations) == "Baseline"


@pytest.mark.asyncio
async def test_group_name_summary_mixed_when_split(protocol):
    service, program, base, repeat, holdout = protocol
    enrollment = await enroll(protocol)
    presentations = await service.presentations(enrollment.id)
    holdout.group_name = "Retest"
    await service.db.flush()
    members = {m.id: m for m in [base, repeat, holdout]}
    assert service.group_name_summary(members, presentations) == "Mixed"


def test_group_name_summary_empty_presentations():
    from fragrance_rater.services.calibration_service import CalibrationService

    assert CalibrationService.group_name_summary({}, []) == "Mixed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_services/test_calibration_service.py -k group_name_summary -v`
Expected: FAIL with `AttributeError: type object 'CalibrationService' has no attribute 'group_name_summary'`

- [ ] **Step 3: Write minimal implementation**

Insert into `src/fragrance_rater/services/calibration_service.py`, immediately
after the `has_started` method added in Task 1:

```python
    @staticmethod
    def group_name_summary(
        members: dict[str, Membership], presentations: list[Presentation]
    ) -> str:
        """The single group_name shared by every presentation's membership.

        Returns "Mixed" when presentations span more than one group_name, or
        when there is nothing to summarize (no presentations yet, mirroring
        the has_started "not started" edge case). Display label only; never
        used to decide wizard behavior (see the design doc's ADR-005
        constraint against inventing a new taxonomy).
        """
        if not presentations:
            return "Mixed"
        names = {members[obj.membership_id].group_name for obj in presentations}
        return names.pop() if len(names) == 1 else "Mixed"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_services/test_calibration_service.py -k group_name_summary -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/fragrance_rater/services/calibration_service.py tests/unit/test_services/test_calibration_service.py
git commit -S -m "feat(calibration): add CalibrationService.group_name_summary"
```

---

## Task 3: Enrich `GET /calibration/enrollments`

**Files:**
- Modify: `src/fragrance_rater/api/calibration.py:273-281`
- Test: `tests/unit/test_api/test_calibration.py`

depends-on: Task1 [output], Task2 [output]

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_api/test_calibration.py` (reuses the same
program/enrollment fixture as `test_controlled_lifecycle_authorization_and_reveal`,
built inline since that test's locals aren't shared across tests):

```python
@pytest.mark.asyncio
async def test_enrollments_list_is_enriched_for_the_recorder(test_app):
    reviewer = await test_app.post(
        "/api/v1/reviewers", json={"name": "Evaluator"}, headers=MANAGER
    )
    fragrance = await test_app.post(
        "/api/v1/fragrances",
        json={
            "name": "Enriched identity",
            "brand": "Enriched house",
            "concentration": "EDT",
            "gender_target": "Unisex",
            "primary_family": "woody",
            "subfamily": "aromatic",
        },
        headers=MANAGER,
    )
    program = await test_app.post(
        f"{PREFIX}/programs", json={"name": "Enrich", "version": "1"}, headers=MANAGER
    )
    program_id = program.json()["id"]
    member = await test_app.post(
        f"{PREFIX}/programs/{program_id}/members",
        json={
            "fragrance_id": fragrance.json()["id"],
            "role": "UNIVERSAL_BASELINE",
            "identity_evidence": "Label verified",
        },
        headers=MANAGER,
    )
    assert member.status_code == 201
    await test_app.post(f"{PREFIX}/programs/{program_id}/activate", headers=MANAGER)
    enrollment = await test_app.post(
        f"{PREFIX}/programs/{program_id}/enroll",
        json={
            "reviewer_id": reviewer.json()["id"],
            "recorder_usernames": ["recorder"],
        },
        headers=MANAGER,
    )
    enrollment_id = enrollment.json()["id"]

    before = await test_app.get(f"{PREFIX}/enrollments", headers=RECORDER)
    assert before.status_code == 200
    row = next(item for item in before.json() if item["id"] == enrollment_id)
    assert row["has_started"] is False
    assert row["revealed"] is False
    assert row["program_name"] == "Enrich"
    assert row["program_version"] == "1"
    assert row["group_name_summary"] == "Baseline"
    assert row["total_presentations"] > 0
    assert row["blotter_complete"] == 0
    assert row["skin_planned"] == 0
    assert row["skin_complete"] == 0

    detail = await test_app.get(f"{PREFIX}/enrollments/{enrollment_id}", headers=RECORDER)
    presentation_id = detail.json()["presentations"][0]["id"]
    await test_app.post(
        f"{PREFIX}/presentations/{presentation_id}/observations",
        json={"stage": "BLOTTER", "detected": True, "intensity": 3, "liking": 6},
        headers=RECORDER,
    )

    after = await test_app.get(f"{PREFIX}/enrollments", headers=RECORDER)
    row = next(item for item in after.json() if item["id"] == enrollment_id)
    assert row["has_started"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_api/test_calibration.py -k test_enrollments_list_is_enriched_for_the_recorder -v`
Expected: FAIL with `KeyError: 'has_started'`

- [ ] **Step 3: Write minimal implementation**

Replace `api/calibration.py:273-281` (the current `enrollments()` handler)
with:

```python
@router.get("/enrollments")
async def enrollments(db: DB, identity: Identity) -> list[dict[str, object]]:
    """List evaluator assignments the recorder can access, enriched for routing.

    Enriches the same participant-safe fields manager_enrollments already
    computes for the pilot-operations console (see that handler below), plus
    one new signal: has_started. Same permission filter as before.
    """
    username, admin = actor(identity)
    service = CalibrationService(db)
    result: list[dict[str, object]] = []
    for item in await db.scalars(select(Enrollment).order_by(Enrollment.id)):
        if not (admin or username in item.recorder_usernames):
            continue
        program = await db.get(Program, item.program_id)
        assert program is not None
        presentations = await service.presentations(item.id)
        members = {
            member.id: member
            for member in await db.scalars(
                select(Membership).where(
                    Membership.id.in_({p.membership_id for p in presentations})
                )
            )
        }
        skin_planned = [p for p in presentations if p.skin_reason is not None]
        result.append(
            {
                "id": item.id,
                "program_id": item.program_id,
                "reviewer_id": item.reviewer_id,
                "revealed": item.revealed_at is not None,
                "has_started": await service.has_started(
                    {p.id for p in presentations}
                ),
                "total_presentations": len(presentations),
                "blotter_complete": sum(
                    p.blotter_locked_at is not None for p in presentations
                ),
                "skin_planned": len(skin_planned),
                "skin_complete": sum(
                    p.skin_locked_at is not None for p in skin_planned
                ),
                "program_name": program.name,
                "program_version": program.version,
                "group_name_summary": CalibrationService.group_name_summary(
                    members, presentations
                ),
            }
        )
    return result
```

This adds no new imports: `Program` and `Membership` are already imported at
the top of `api/calibration.py` (confirmed: `Membership` is used by
`add_member`, `Program` by `programs()`), and `CalibrationService` is already
imported.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_api/test_calibration.py -k test_enrollments_list_is_enriched_for_the_recorder -v`
Expected: PASS

- [ ] **Step 5: Run the full backend suite to confirm no regression**

Run: `uv run pytest tests/unit/test_api/test_calibration.py tests/unit/test_services/test_calibration_service.py -v`
Expected: PASS, all tests (the pre-existing
`test_controlled_lifecycle_authorization_and_reveal` does not assert on
`/enrollments`'s shape directly, only `/manager/enrollments`, so it is
unaffected)

- [ ] **Step 6: Commit**

```bash
git add src/fragrance_rater/api/calibration.py tests/unit/test_api/test_calibration.py
git commit -S -m "feat(calibration): enrich GET /calibration/enrollments for entry routing"
```

---

## Task 4: `EnrollmentSummary` frontend type

**Files:**
- Modify: `frontend/src/api/types.ts` (insert after `Assignment`, line 18)
- Modify: `frontend/src/hooks/useAppData.ts:12,25,55`
- Modify: `frontend/src/pages/CalibrationPage.tsx:3,19`

depends-on: Task3 [output]

- [ ] **Step 1: Add the type**

Insert into `frontend/src/api/types.ts`, immediately after the `Assignment`
type (line 18):

```typescript
/**
 * The GET /calibration/enrollments list response: `Assignment` plus the
 * routing signals CalibrationPage's entry decision needs. Kept distinct from
 * `Enrollment` (the GET /calibration/enrollments/{id} DETAIL shape,
 * line 101 below): the two endpoints return different fields, and
 * conflating them previously caused a spec citation error.
 */
export type EnrollmentSummary = Assignment & {
  revealed: boolean
  has_started: boolean
  total_presentations: number
  blotter_complete: number
  skin_planned: number
  skin_complete: number
  program_name: string
  program_version: string
  group_name_summary: string
}
```

- [ ] **Step 2: Widen `useAppData`**

In `frontend/src/hooks/useAppData.ts`, change the import (line 3) and the two
usages:

```typescript
import type { Access, Assignment, EnrollmentSummary, Person, Program } from '../api/types'
```

Line 12: `const [assignments, setAssignments] = useState<EnrollmentSummary[]>([])`

Line 25: `api.get<EnrollmentSummary[]>('/calibration/enrollments'),`

`Assignment` stays imported: `capabilitiesFor` (line 4, from `types.ts`) still
takes `Assignment[]`, and `EnrollmentSummary[]` is assignable to it since
`EnrollmentSummary extends Assignment` (structural typing, no cast needed).

- [ ] **Step 3: Widen `CalibrationPageProps`**

In `frontend/src/pages/CalibrationPage.tsx`, change the type import (line 3)
and the prop type (line 19):

```typescript
import type { Assignment, Enrollment, EnrollmentSummary, Person, Program } from '../api/types'
```

Line 19: `assignments: EnrollmentSummary[]`

`Assignment` stays imported for now: it is still used for the dropdown's
`.find((assignment) => ...)` calls elsewhere in the file, which read only the
fields `Assignment` already declares.

- [ ] **Step 4: Type-check**

Run: `npm run typecheck` (from `frontend/`)
Expected: PASS, no new errors. (`App.tsx` still passes `assignments`, typed
`EnrollmentSummary[]` after Task 3/4's backend and `useAppData` changes flow
through, to `CalibrationPage`, so the prop type now matches exactly.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/hooks/useAppData.ts frontend/src/pages/CalibrationPage.tsx
git commit -S -m "feat(frontend): add EnrollmentSummary type for calibration entry routing"
```

---

## Task 5: `calibrationEntryFor` pure routing decision

**Files:**
- Create: `frontend/src/routing/calibrationEntry.ts`
- Create: `frontend/src/test/calibrationEntry.test.ts`

depends-on: Task4 [output]

- [ ] **Step 1: Write the failing test**

Create `frontend/src/test/calibrationEntry.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { calibrationEntryFor } from '../routing/calibrationEntry'
import type { EnrollmentSummary } from '../api/types'

function summary(overrides: Partial<EnrollmentSummary>): EnrollmentSummary {
  return {
    id: 'e1',
    program_id: 'p1',
    reviewer_id: 'r1',
    revealed: false,
    has_started: false,
    total_presentations: 3,
    blotter_complete: 0,
    skin_planned: 0,
    skin_complete: 0,
    program_name: 'Baseline',
    program_version: '1',
    group_name_summary: 'Baseline',
    ...overrides,
  }
}

describe('calibrationEntryFor', () => {
  it('routes to empty when there are no assignments', () => {
    expect(calibrationEntryFor([])).toEqual({ kind: 'empty' })
  })

  it('routes to guided for a single not-started enrollment', () => {
    const entry = summary({ id: 'e1' })
    expect(calibrationEntryFor([entry])).toEqual({ kind: 'guided', enrollmentId: 'e1' })
  })

  it('prefers resume over guided when both exist', () => {
    const notStarted = summary({ id: 'e1', has_started: false })
    const inProgress = summary({ id: 'e2', has_started: true })
    expect(calibrationEntryFor([notStarted, inProgress])).toEqual({
      kind: 'resume',
      enrollmentId: 'e2',
    })
  })

  it('routes to choice when every assignment is revealed', () => {
    const entry = summary({ id: 'e1', revealed: true, has_started: true })
    expect(calibrationEntryFor([entry])).toEqual({ kind: 'choice' })
  })

  it('picks the id-order tiebreak deterministically among multiple in-progress', () => {
    const first = summary({ id: 'a-first', has_started: true })
    const second = summary({ id: 'b-second', has_started: true })
    expect(calibrationEntryFor([second, first])).toEqual({
      kind: 'resume',
      enrollmentId: 'b-second',
    })
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:run -- src/test/calibrationEntry.test.ts` (from `frontend/`)
Expected: FAIL with a module-not-found error for `../routing/calibrationEntry`

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/routing/calibrationEntry.ts`:

```typescript
import type { EnrollmentSummary } from '../api/types'

/**
 * The calibration entry-routing decision, computed once from the enriched
 * enrollment list.
 *
 * "resume" and "guided" both open the same GuidedCalibrationFlow wizard,
 * distinguished only by which enrollment they open; the wizard itself
 * computes its own starting step from that enrollment's current state
 * (see nextWizardStep in GuidedCalibrationFlow.tsx). "First" among multiple
 * candidates is the array's own order, which callers get from the API's
 * `order_by(Enrollment.id)` tiebreak: stable across requests, not a claim
 * about creation order (see the design doc's §1 note).
 */
export type CalibrationEntryDecision =
  | { kind: 'resume'; enrollmentId: string }
  | { kind: 'guided'; enrollmentId: string }
  | { kind: 'choice' }
  | { kind: 'empty' }

export function calibrationEntryFor(
  assignments: readonly EnrollmentSummary[]
): CalibrationEntryDecision {
  if (assignments.length === 0) return { kind: 'empty' }
  const incomplete = assignments.filter((entry) => !entry.revealed)
  const inProgress = incomplete.find((entry) => entry.has_started)
  if (inProgress) return { kind: 'resume', enrollmentId: inProgress.id }
  const notStarted = incomplete.find((entry) => !entry.has_started)
  if (notStarted) return { kind: 'guided', enrollmentId: notStarted.id }
  return { kind: 'choice' }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test:run -- src/test/calibrationEntry.test.ts`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/routing/calibrationEntry.ts frontend/src/test/calibrationEntry.test.ts
git commit -S -m "feat(frontend): add calibrationEntryFor routing decision"
```

---

## Task 6: Extract `SampleObservationPanel` from `CalibrationPage` (pure refactor)

**Files:**
- Create: `frontend/src/pages/SampleObservationPanel.tsx`
- Modify: `frontend/src/pages/CalibrationPage.tsx`

depends-on: Task4 [output]. Parallelizable with Task 5 (different files).

This is a behavior-preserving extraction, verified by the *existing* test
suite staying green, not a new test. `GuidedCalibrationFlow` (Task 7) needs
this component to avoid duplicating ~200 lines of form/lock/observation-log
JSX and its `save()` closure.

- [ ] **Step 1: Confirm the pre-extraction baseline is green**

Run: `npm run test:run -- src/test/App.test.tsx src/test/revealAndLog.test.tsx` (from `frontend/`)
Expected: PASS (baseline, before any change in this task)

- [ ] **Step 2: Create `SampleObservationPanel.tsx`**

Create `frontend/src/pages/SampleObservationPanel.tsx`, moving
`CalibrationPage.tsx`'s `ScaleGroupFields`, `disabledOnNonDetection`,
`timeOrdered`, `save()`, and the `sample ? (...) : (...)` JSX block
(lines 52-96 and 178-206 and 332-537 of the current file) here verbatim,
adapted to take its former closure variables as props:

```typescript
import { api } from '../api/client'
import type { Enrollment, Sample } from '../api/types'
import { ConfirmAction } from '../components/ConfirmAction'
import { EmptyState } from '../components/PageState'
import { ScaleField } from '../components/ScaleField'
import {
  blotterGroups,
  numericFieldNames,
  observationNotes,
  skinGroups,
  type ScaleGroup,
} from '../content/calibrationScales'
import type { useTask } from '../hooks/useTask'

/**
 * Renders one group of scales under a shared heading.
 *
 * The heading is what carries the descriptive/affective separation: without
 * it the twelve scales read as one undifferentiated run, and an evaluator has
 * no cue that "Discomfort" is a fact about them rather than about the scent.
 */
function ScaleGroupFields({
  group,
  isDisabled,
}: {
  group: ScaleGroup
  isDisabled?: (name: string) => boolean
}) {
  return (
    <div className="scale-group">
      <h3 className="scale-group__legend">{group.legend}</h3>
      <p className="scale-group__description">{group.description}</p>
      <div className="scale-stack">
        {group.scales.map((item) => (
          <ScaleField key={item.name} scale={item} disabled={isDisabled?.(item.name)} />
        ))}
      </div>
    </div>
  )
}

/**
 * Non-detection forces intensity to 0 and clears liking, so those two must not
 * accept input. The perceptual dimensions stay enabled, which is the behaviour
 * this form already had: whether they should also be closed off when nothing
 * was smelled is a data-model question, not a presentational one.
 */
function disabledOnNonDetection(name: string) {
  return name === 'intensity' || name === 'liking'
}

/**
 * Orders a sample's observations into a readable log.
 *
 * Blotter screens precede skin tests, and within a stage the timepoints run
 * earliest first. The API does not guarantee an order, and an out-of-sequence
 * row in an evaporation curve is actively misleading rather than merely untidy.
 */
function timeOrdered(observations: Enrollment['presentations'][number]['observations']) {
  const stageRank = (stage: string) => (stage === 'SKIN' ? 1 : 0)
  return [...observations].sort(
    (first, second) =>
      stageRank(first.stage) - stageRank(second.stage) ||
      first.elapsed_minutes - second.elapsed_minutes
  )
}

export type SampleObservationPanelProps = {
  enrollment: Enrollment
  sample: Sample
  stage: string
  setStage: (stage: string) => void
  detected: string
  setDetected: (detected: string) => void
  task: ReturnType<typeof useTask>
  refresh: () => Promise<void>
}

export function SampleObservationPanel({
  enrollment,
  sample,
  stage,
  setStage,
  detected,
  setDetected,
  task,
  refresh,
}: SampleObservationPanelProps) {
  async function save(form: HTMLFormElement) {
    const values = Object.fromEntries(new FormData(form))
    const data: Record<string, unknown> = {
      stage,
      elapsed_minutes: Number(values.elapsed_minutes || 0),
      detected: detected === '' ? null : detected === 'yes',
    }
    for (const name of numericFieldNames) data[name] = !values[name] ? null : Number(values[name])
    if (detected === 'no') {
      data.intensity = 0
      data.liking = null
    }
    for (const note of observationNotes) data[note.name] = values[note.name] || null
    data.perceived_notes = values.perceived_notes
      ? String(values.perceived_notes)
          .split(',')
          .map((value) => value.trim())
          .filter(Boolean)
      : null
    await api.post(
      `/calibration/presentations/${sample.id}/${sample.identity ? 'post-reveal' : 'observations'}`,
      data
    )
    form.reset()
    setDetected('')
    await refresh()
    task.setNotice('Observation saved. Original responses are retained.')
  }

  return (
    <>
      <p className="eyebrow">Sample {sample.position}</p>
      <h2 className="sample-heading">
        <span className="visually-hidden">Blind code </span>
        {sample.blind_code}
      </h2>
      {sample.identity && (
        <>
          <p className="notice">
            {sample.identity.brand} · {sample.identity.name} · {sample.identity.concentration}
          </p>
          {/*
            Rendered only inside this `identity` branch, which the backend
            populates only after reveal. Each name links to the source that
            attributes it: ADR-006 keeps a claim and its evidence together,
            and an attribution presented without a source reads as
            established fact when it is not.
          */}
          {sample.identity.perfumers && sample.identity.perfumers.length > 0 && (
            <p className="attribution">
              <span className="attribution__label">
                {sample.identity.perfumers.length === 1 ? 'Perfumer' : 'Perfumers'}
              </span>
              {sample.identity.perfumers.map((attribution, index) => (
                <span key={attribution.name}>
                  {index > 0 && ', '}
                  <a href={attribution.source_url} target="_blank" rel="noreferrer">
                    {attribution.name}
                    <span className="visually-hidden"> (opens the source)</span>
                  </a>
                </span>
              ))}
            </p>
          )}
        </>
      )}
      <label>
        Stage
        <select value={stage} onChange={(event) => setStage(event.target.value)}>
          <option value="BLOTTER">Blotter screen</option>
          {sample.skin_planned && <option value="SKIN">Skin test</option>}
        </select>
      </label>
      {!sample.skin_planned && !enrollment.skin_plan_locked && (
        <form
          onSubmit={(event) => {
            event.preventDefault()
            const reason = String(new FormData(event.currentTarget).get('reason'))
            void task.run(async () => {
              await api.post(`/calibration/presentations/${sample.id}/skin-plan`, { reason })
              await refresh()
            })
          }}
        >
          <label>
            Reason to add a skin test
            <input name="reason" required placeholder="For example: low confidence" />
          </label>
          <button disabled={task.busy}>Plan skin test</button>
        </form>
      )}
      <form
        key={`${sample.id}-${stage}`}
        onSubmit={(event) => {
          event.preventDefault()
          const form = event.currentTarget
          void task.run(() => save(form))
        }}
      >
        <fieldset
          disabled={
            task.busy ||
            (!sample.identity &&
              (stage === 'BLOTTER' ? sample.blotter_locked : sample.skin_locked))
          }
        >
          <legend>{sample.identity ? 'Post-reveal observation' : 'Blind observation'}</legend>
          <div className="fields fields-compact">
            <label>
              Elapsed minutes
              <input name="elapsed_minutes" type="number" min="0" defaultValue="0" />
            </label>
            <label>
              Detected
              <select value={detected} onChange={(event) => setDetected(event.target.value)}>
                <option value="">Unanswered</option>
                <option value="yes">Yes</option>
                <option value="no">No</option>
              </select>
            </label>
          </div>
          {detected === 'no' && (
            <p className="notice">
              Intensity will be saved as 0; liking will remain unanswered.
            </p>
          )}
          {blotterGroups.map((group) => (
            <ScaleGroupFields
              key={group.key}
              group={group}
              isDisabled={detected === 'no' ? disabledOnNonDetection : undefined}
            />
          ))}
          {stage === 'SKIN' && (
            <>
              {skinGroups.map((group) => (
                <ScaleGroupFields key={group.key} group={group} />
              ))}
              <label>
                Longevity (minutes)
                <input name="longevity_minutes" type="number" min="0" />
              </label>
            </>
          )}
          <label>
            Perceived notes
            <input name="perceived_notes" placeholder="Your own words, separated by commas" />
          </label>
          {observationNotes.map((note) => (
            <label key={note.name}>
              {note.label}
              <textarea name={note.name} rows={2} />
            </label>
          ))}
          <button>Save observation</button>
        </fieldset>
      </form>
      {!sample.identity && (
        <ConfirmAction
          actionLabel={`Lock ${stage.toLowerCase()} responses`}
          confirmLabel={`Confirm ${stage.toLowerCase()} lock`}
          description="Locking ends blind entry for this sample and stage. Review the saved observations before continuing."
          disabled={task.busy || (stage === 'BLOTTER' ? sample.blotter_locked : sample.skin_locked)}
          onConfirm={() =>
            void task.run(async () => {
              await api.post(`/calibration/presentations/${sample.id}/lock/${stage}`)
              await refresh()
            })
          }
        />
      )}
      <h3>Saved observations</h3>
      {sample.observations.length ? (
        /*
         * A blotter log: one row per timepoint, ordered by elapsed time, so
         * the evaporation curve is legible at a glance. Every professional
         * evaluation sheet this interface is modelled on is laid out this
         * way, and an unordered list of prose lines made a sequence of
         * observations read as unrelated entries.
         */
        <div className="log-scroll">
          <table className="log">
            <caption className="visually-hidden">
              Saved observations for this sample, earliest first
            </caption>
            <thead>
              <tr>
                <th scope="col">Time</th>
                <th scope="col">Stage</th>
                <th scope="col">Phase</th>
                <th scope="col">Intensity</th>
                <th scope="col">Liking</th>
                <th scope="col">Comment</th>
              </tr>
            </thead>
            <tbody>
              {timeOrdered(sample.observations).map((observation) => (
                <tr key={observation.id}>
                  <th scope="row" data-numeric>
                    {observation.elapsed_minutes} min
                  </th>
                  <td>{observation.stage === 'SKIN' ? 'Skin' : 'Blotter'}</td>
                  <td>{observation.phase.replace(/_/g, ' ')}</td>
                  <td data-numeric>{observation.intensity ?? 'n/a'}</td>
                  <td data-numeric>{observation.liking ?? 'n/a'}</td>
                  <td>{observation.comments || 'n/a'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState title="No observations yet">
          Save a timepoint to begin this sample history.
        </EmptyState>
      )}
    </>
  )
}
```

- [ ] **Step 3: Update `CalibrationPage.tsx` to use it**

In `frontend/src/pages/CalibrationPage.tsx`:

Remove the now-duplicated `ScaleGroupFields`, `disabledOnNonDetection`,
`timeOrdered` functions (former lines 52-96) and the `save()` function
(former lines 178-206); import `SampleObservationPanel` instead:

```typescript
import { SampleObservationPanel } from './SampleObservationPanel'
```

Replace the `sample ? (...) : (...)` block (former lines 332-537) with:

```typescript
            {sample ? (
              <SampleObservationPanel
                enrollment={enrollment}
                sample={sample}
                stage={stage}
                setStage={setStage}
                detected={detected}
                setDetected={setDetected}
                task={task}
                refresh={refresh}
              />
            ) : (
              <EmptyState title="Select a sample">Choose a blind code from a session.</EmptyState>
            )}
```

Also remove now-unused imports from `CalibrationPage.tsx`: `ScaleField`
(no longer referenced directly), `blotterGroups`/`numericFieldNames`/
`observationNotes`/`skinGroups`/`ScaleGroup` from `calibrationScales`, and
`ConfirmAction`'s reveal/skin-plan usages stay (those two `ConfirmAction`s in
the `<aside>` are enrollment-level, not sample-level, and remain in
`CalibrationPage.tsx` unchanged).

- [ ] **Step 4: Confirm no behavior change**

Run: `npm run test:run -- src/test/App.test.tsx src/test/revealAndLog.test.tsx`
Expected: PASS, same test count and names as Step 1's baseline

Run: `npm run typecheck`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SampleObservationPanel.tsx frontend/src/pages/CalibrationPage.tsx
git commit -S -m "refactor(frontend): extract SampleObservationPanel from CalibrationPage"
```

---

## Task 7: `GuidedCalibrationFlow` wizard

**Files:**
- Create: `frontend/src/pages/GuidedCalibrationFlow.tsx`
- Create: `frontend/src/test/GuidedCalibrationFlow.test.tsx`

depends-on: Task6 [output]

- [ ] **Step 1: Write the failing test for the pure step function**

Create `frontend/src/test/GuidedCalibrationFlow.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { nextWizardStep, GuidedCalibrationFlow } from '../pages/GuidedCalibrationFlow'
import type { Enrollment } from '../api/types'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('axios', () => ({
  default: { create: () => ({ get, post }), isAxiosError: () => false },
}))

function baseEnrollment(overrides: Partial<Enrollment> = {}): Enrollment {
  return {
    id: 'e1',
    program_id: 'p1',
    reviewer_id: 'r1',
    revealed: false,
    reveal_eligible: false,
    reveal_blocker: 'SKIN_PLAN',
    skin_plan_locked: false,
    presentations: [
      {
        id: 's1',
        session_id: 'sess1',
        blind_code: 'AAA1',
        position: 1,
        skin_planned: false,
        blotter_locked: false,
        skin_locked: false,
        observations: [],
      },
    ],
    ...overrides,
  }
}

describe('nextWizardStep', () => {
  it('starts at the skin-plan decision before it is locked', () => {
    expect(nextWizardStep(baseEnrollment())).toEqual({ kind: 'skin_plan' })
  })

  it('moves to the first unlocked blotter sample once the plan is locked', () => {
    const enrollment = baseEnrollment({ skin_plan_locked: true })
    expect(nextWizardStep(enrollment)).toEqual({ kind: 'blotter', presentationId: 's1' })
  })

  it('moves to a planned, unlocked skin sample once blotter is locked', () => {
    const enrollment = baseEnrollment({
      skin_plan_locked: true,
      presentations: [
        {
          id: 's1',
          session_id: 'sess1',
          blind_code: 'AAA1',
          position: 1,
          skin_planned: true,
          blotter_locked: true,
          skin_locked: false,
          observations: [],
        },
      ],
    })
    expect(nextWizardStep(enrollment)).toEqual({ kind: 'skin', presentationId: 's1' })
  })

  it('reaches ready_to_reveal once everything required is locked', () => {
    const enrollment = baseEnrollment({
      skin_plan_locked: true,
      presentations: [
        {
          id: 's1',
          session_id: 'sess1',
          blind_code: 'AAA1',
          position: 1,
          skin_planned: false,
          blotter_locked: true,
          skin_locked: false,
          observations: [],
        },
      ],
    })
    expect(nextWizardStep(enrollment)).toEqual({ kind: 'ready_to_reveal' })
  })
})

describe('GuidedCalibrationFlow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    get.mockResolvedValue({ data: baseEnrollment() })
    post.mockResolvedValue({ data: {} })
  })

  it('shows the step-of-total orientation and an escape hatch', async () => {
    render(
      <GuidedCalibrationFlow enrollmentId="e1" onExitToManualBrowse={vi.fn()} />
    )
    await waitFor(() => expect(get).toHaveBeenCalledWith('/calibration/enrollments/e1'))
    expect(await screen.findByText(/Step 1 of/)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Browse assignments manually instead' })
    ).toBeInTheDocument()
  })

  it('calls onExitToManualBrowse when the escape hatch is clicked', async () => {
    const onExit = vi.fn()
    render(<GuidedCalibrationFlow enrollmentId="e1" onExitToManualBrowse={onExit} />)
    await screen.findByText(/Step 1 of/)
    screen.getByRole('button', { name: 'Browse assignments manually instead' }).click()
    expect(onExit).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:run -- src/test/GuidedCalibrationFlow.test.tsx`
Expected: FAIL with a module-not-found error for `../pages/GuidedCalibrationFlow`

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/pages/GuidedCalibrationFlow.tsx`:

```typescript
import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { Enrollment } from '../api/types'
import { ConfirmAction } from '../components/ConfirmAction'
import { FeedbackBanner } from '../components/FeedbackBanner'
import { useTask } from '../hooks/useTask'
import { SampleObservationPanel } from './SampleObservationPanel'

export type WizardStep =
  | { kind: 'skin_plan' }
  | { kind: 'blotter'; presentationId: string }
  | { kind: 'skin'; presentationId: string }
  | { kind: 'ready_to_reveal' }

/**
 * The next valid step, in the same precedence CalibrationService.reveal_blocker
 * already enforces (skin plan decision, then remaining BLOTTER locks, then
 * remaining SKIN locks, then reveal). No new ordering is invented here; this
 * mirrors the backend gate so the wizard and the reveal button never disagree
 * about what's left.
 */
export function nextWizardStep(enrollment: Enrollment): WizardStep {
  if (!enrollment.skin_plan_locked) return { kind: 'skin_plan' }
  const unlockedBlotter = enrollment.presentations.find((item) => !item.blotter_locked)
  if (unlockedBlotter) return { kind: 'blotter', presentationId: unlockedBlotter.id }
  const unlockedSkin = enrollment.presentations.find(
    (item) => item.skin_planned && !item.skin_locked
  )
  if (unlockedSkin) return { kind: 'skin', presentationId: unlockedSkin.id }
  return { kind: 'ready_to_reveal' }
}

function progressFor(enrollment: Enrollment): { step: number; total: number } {
  const skinPlanned = enrollment.presentations.filter((item) => item.skin_planned)
  const done =
    (enrollment.skin_plan_locked ? 1 : 0) +
    enrollment.presentations.filter((item) => item.blotter_locked).length +
    skinPlanned.filter((item) => item.skin_locked).length
  return { step: done + 1, total: 2 + enrollment.presentations.length + skinPlanned.length }
}

export function GuidedCalibrationFlow({
  enrollmentId,
  onExitToManualBrowse,
}: {
  enrollmentId: string
  onExitToManualBrowse: () => void
}) {
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null)
  const [stage, setStage] = useState('BLOTTER')
  const [detected, setDetected] = useState('')
  const task = useTask()
  const refreshGeneration = useRef(0)

  const refresh = async () => {
    const generation = ++refreshGeneration.current
    const response = await api.get<Enrollment>(`/calibration/enrollments/${enrollmentId}`)
    if (generation === refreshGeneration.current) setEnrollment(response.data)
  }

  useEffect(() => {
    void task.run(refresh)
    // enrollmentId is the only trigger; refresh/task are recreated per render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enrollmentId])

  if (!enrollment) return <FeedbackBanner error={task.error} notice={task.notice} />

  const step = nextWizardStep(enrollment)
  const { step: stepNumber, total } = progressFor(enrollment)
  const sample =
    step.kind === 'blotter' || step.kind === 'skin'
      ? enrollment.presentations.find((item) => item.id === step.presentationId)
      : undefined

  return (
    <div className="workspace">
      <section>
        <div className="page-heading">
          <div>
            <h2>Guided calibration</h2>
          </div>
          <span className="tally">
            Step {stepNumber} of {total}
          </span>
        </div>
        <FeedbackBanner error={task.error} notice={task.notice} />
        {step.kind === 'skin_plan' && (
          <>
            <p className="notice">
              Decide whether each sample also needs a skin test, then finalize the plan.
            </p>
            <ul className="data-list">
              {enrollment.presentations.map((item) => (
                <li key={item.id}>
                  <strong>{item.blind_code}</strong>
                  <span>{item.skin_planned ? 'Skin test planned' : 'Blotter only'}</span>
                  {!item.skin_planned && (
                    <form
                      onSubmit={(event) => {
                        event.preventDefault()
                        const reason = String(
                          new FormData(event.currentTarget).get('reason')
                        )
                        void task.run(async () => {
                          await api.post(`/calibration/presentations/${item.id}/skin-plan`, {
                            reason,
                          })
                          await refresh()
                        })
                      }}
                    >
                      <label>
                        Reason to add a skin test
                        <input name="reason" required placeholder="For example: low confidence" />
                      </label>
                      <button disabled={task.busy}>Plan skin test</button>
                    </form>
                  )}
                </li>
              ))}
            </ul>
            <ConfirmAction
              actionLabel="Finalize skin-test plan"
              confirmLabel="Confirm final plan"
              description="Finalizing prevents further changes to which samples receive a skin test."
              disabled={task.busy}
              onConfirm={() =>
                void task.run(async () => {
                  await api.post(`/calibration/enrollments/${enrollment.id}/lock-skin-plan`)
                  await refresh()
                })
              }
            />
          </>
        )}
        {sample && (step.kind === 'blotter' || step.kind === 'skin') && (
          <SampleObservationPanel
            enrollment={enrollment}
            sample={sample}
            stage={step.kind === 'blotter' ? 'BLOTTER' : 'SKIN'}
            setStage={setStage}
            detected={detected}
            setDetected={setDetected}
            task={task}
            refresh={refresh}
          />
        )}
        {step.kind === 'ready_to_reveal' && (
          <>
            <p className="notice">All required blind work is locked.</p>
            <ConfirmAction
              actionLabel="Reveal completed baseline"
              confirmLabel="Confirm reveal"
              description="Reveal makes fragrance identities visible for this enrollment."
              disabled={task.busy}
              onConfirm={() =>
                void task.run(async () => {
                  await api.post(`/calibration/enrollments/${enrollment.id}/reveal`)
                  await refresh()
                })
              }
            />
          </>
        )}
        <button className="secondary" onClick={onExitToManualBrowse}>
          Browse assignments manually instead
        </button>
      </section>
    </div>
  )
}
```

`stage`/`setStage` here is a local placeholder kept only because
`SampleObservationPanel` requires the prop for its stage `<select>`; the
wizard drives which stage is active through `step.kind`, not the select, so
`stage`'s own value is unused for routing (a future cleanup could split
`SampleObservationPanel`'s props so this is not needed, out of scope here).

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test:run -- src/test/GuidedCalibrationFlow.test.tsx`
Expected: PASS (6 tests)

Run: `npm run typecheck`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/GuidedCalibrationFlow.tsx frontend/src/test/GuidedCalibrationFlow.test.tsx
git commit -S -m "feat(frontend): add GuidedCalibrationFlow wizard"
```

---

## Task 8: `CalibrationChoiceScreen`

**Files:**
- Create: `frontend/src/pages/CalibrationChoiceScreen.tsx`
- Create: `frontend/src/test/CalibrationChoiceScreen.test.tsx`

depends-on: Task4 [output]. Parallelizable with Tasks 6/7 (different files).

- [ ] **Step 1: Write the failing test**

Create `frontend/src/test/CalibrationChoiceScreen.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { CalibrationChoiceScreen } from '../pages/CalibrationChoiceScreen'
import type { Access, EnrollmentSummary, Program } from '../api/types'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('axios', () => ({
  default: { create: () => ({ get }), isAxiosError: () => false },
}))

const revealed: EnrollmentSummary = {
  id: 'e1',
  program_id: 'p1',
  reviewer_id: 'r1',
  revealed: true,
  has_started: true,
  total_presentations: 3,
  blotter_complete: 3,
  skin_planned: 0,
  skin_complete: 0,
  program_name: 'Baseline',
  program_version: '1',
  group_name_summary: 'Baseline',
}
const activeBaseline: Program = { id: 'p2', name: 'Baseline round two', version: '1', status: 'active' }
const activeRetest: Program = { id: 'p3', name: 'Skin retest round', version: '1', status: 'active' }

function membersFor(programId: string, groupName: string) {
  return [{ id: `m-${programId}`, group_name: groupName }]
}

beforeEach(() => {
  vi.clearAllMocks()
  get.mockImplementation((path: string) => {
    if (path === '/calibration/programs/p2/members')
      return Promise.resolve({ data: membersFor('p2', 'Baseline') })
    if (path === '/calibration/programs/p3/members')
      return Promise.resolve({ data: membersFor('p3', 'Skin Retest') })
    return Promise.reject(new Error(`Unexpected request: ${path}`))
  })
})

describe('CalibrationChoiceScreen', () => {
  it('shows self-assign buttons for a manager with open programs', async () => {
    const access: Access = { username: 'manager', manager: true }
    render(
      <CalibrationChoiceScreen
        assignments={[revealed]}
        programs={[activeBaseline, activeRetest]}
        access={access}
        onBrowse={vi.fn()}
      />
    )
    expect(await screen.findByRole('button', { name: /Start a new full baseline/ })).toBeInTheDocument()
    expect(
      await screen.findByRole('button', { name: /Redo "Skin Retest"/ })
    ).toBeInTheDocument()
  })

  it('shows nothing-new messaging for a non-manager', async () => {
    const access: Access = { username: 'family-member', manager: false }
    render(
      <CalibrationChoiceScreen
        assignments={[revealed]}
        programs={[activeBaseline, activeRetest]}
        access={access}
        onBrowse={vi.fn()}
      />
    )
    expect(
      await screen.findByText('Nothing new is assigned right now.')
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Start a new full baseline/ })).not.toBeInTheDocument()
  })

  it('excludes a program the identity is already enrolled in', async () => {
    const access: Access = { username: 'manager', manager: true }
    render(
      <CalibrationChoiceScreen
        assignments={[revealed, { ...revealed, id: 'e2', program_id: 'p2' }]}
        programs={[activeBaseline, activeRetest]}
        access={access}
        onBrowse={vi.fn()}
      />
    )
    await waitFor(() => expect(get).toHaveBeenCalledWith('/calibration/programs/p3/members'))
    expect(screen.queryByRole('button', { name: /Start a new full baseline/ })).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:run -- src/test/CalibrationChoiceScreen.test.tsx`
Expected: FAIL with a module-not-found error for `../pages/CalibrationChoiceScreen`

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/pages/CalibrationChoiceScreen.tsx`:

```typescript
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Access, EnrollmentSummary, Navigate, Program, ProgramMember } from '../api/types'
import { assignmentQuery } from '../routing/routes'

/**
 * The single group_name shared by a program's memberships, or "Mixed" when
 * split. Mirrors CalibrationService.group_name_summary on the backend
 * (calibration_service.py), but runs client-side against ProgramMember rows
 * fetched from the manager-only members endpoint: see the plan's "Spec
 * clarifications" section for why this isn't a second backend enrichment.
 */
function dominantGroupName(members: ProgramMember[]): string {
  if (members.length === 0) return 'Mixed'
  const names = new Set(members.map((member) => member.group_name))
  return names.size === 1 ? [...names][0] : 'Mixed'
}

type Candidate = { program: Program; groupName: string }

export function CalibrationChoiceScreen({
  assignments,
  programs,
  access,
  navigate,
  onBrowse,
}: {
  assignments: EnrollmentSummary[]
  programs: Program[]
  access: Access
  navigate: Navigate
  onBrowse: () => void
}) {
  const [candidates, setCandidates] = useState<Candidate[]>([])

  useEffect(() => {
    if (!access.manager) return
    const enrolledProgramIds = new Set(assignments.map((entry) => entry.program_id))
    const openPrograms = programs.filter(
      (program) => program.status === 'active' && !enrolledProgramIds.has(program.id)
    )
    let current = true
    void Promise.all(
      openPrograms.map(async (program) => {
        const response = await api.get<ProgramMember[]>(
          `/calibration/programs/${program.id}/members`
        )
        return { program, groupName: dominantGroupName(response.data) }
      })
    ).then((results) => {
      if (current) setCandidates(results)
    })
    return () => {
      current = false
    }
    // assignments/programs are the effect's only real inputs; access.manager
    // gates whether it runs at all.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [access.manager, assignments, programs])

  function openEnrollFor(programId: string) {
    navigate('programs', false, { program: programId })
  }

  if (!access.manager) {
    return (
      <section>
        <div className="page-heading">
          <h2>Your calibration</h2>
        </div>
        <p>Nothing new is assigned right now.</p>
      </section>
    )
  }

  const baseline = candidates.find((candidate) => candidate.groupName === 'Baseline')
  const components = candidates.filter((candidate) => candidate.groupName !== 'Baseline')

  return (
    <section>
      <div className="page-heading">
        <h2>Your calibration</h2>
      </div>
      <p>Everything currently assigned is revealed. Start something new, or browse it again.</p>
      {baseline && (
        <button onClick={() => openEnrollFor(baseline.program.id)}>
          Start a new full baseline
        </button>
      )}
      {components.map((candidate) => (
        <button key={candidate.program.id} onClick={() => openEnrollFor(candidate.program.id)}>
          Redo &quot;{candidate.groupName}&quot;
        </button>
      ))}
      {!baseline && components.length === 0 && <p>Nothing new is assigned right now.</p>}
      <button className="secondary" onClick={onBrowse}>
        Browse assignments manually instead
      </button>
    </section>
  )
}
```

`assignmentQuery` is imported but unused in this draft; remove that import
(it was carried over by mistake from `CalibrationPage`'s own query helper
usage, not needed here since `openEnrollFor` builds its own `program` query
inline via `navigate`'s third argument).

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test:run -- src/test/CalibrationChoiceScreen.test.tsx`
Expected: PASS (3 tests)

Run: `npm run typecheck`
Expected: PASS (this step also confirms `navigate('programs', false, { program: programId })`
matches `Navigate`'s signature, `(route: Route, replace?: boolean, query?: RouteQuery) => void`,
from `routes.ts:91`; no change needed there for this task, since `RouteQuery`
already accepts an arbitrary string-keyed record)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/CalibrationChoiceScreen.tsx frontend/src/test/CalibrationChoiceScreen.test.tsx
git commit -S -m "feat(frontend): add CalibrationChoiceScreen for manager self-assign"
```

---

## Task 9: Wire routing into `CalibrationPage`

**Files:**
- Modify: `frontend/src/pages/CalibrationPage.tsx`
- Modify: `frontend/src/App.tsx`

depends-on: Task5 [output], Task6 [output], Task7 [output], Task8 [output]

- [ ] **Step 1: Add `access` prop and routing state to `CalibrationPage`**

In `frontend/src/pages/CalibrationPage.tsx`, add to the imports:

```typescript
import type { Access, Assignment, Enrollment, EnrollmentSummary, Person, Program } from '../api/types'
import { calibrationEntryFor } from '../routing/calibrationEntry'
import { CalibrationChoiceScreen } from './CalibrationChoiceScreen'
import { GuidedCalibrationFlow } from './GuidedCalibrationFlow'
```

Add `access: Access` to `CalibrationPageProps` (after `navigate`):

```typescript
type CalibrationPageProps = {
  assignments: EnrollmentSummary[]
  programs: Program[]
  reviewers: Person[]
  access: Access
  navigate: (route: Route) => void
  initialAssignmentId?: AssignmentId
  unresolvedAssignmentId?: string
}
```

Destructure `access` in the component signature, and add routing state right
after the existing `const task = useTask()` line:

```typescript
  const [manualBrowse, setManualBrowse] = useState(false)
  const entry = calibrationEntryFor(assignments)
```

- [ ] **Step 2: Branch the render**

Wrap the existing return statement's content: when routing applies (no deep
link, not manually browsing, and the decision isn't `empty`), render the
wizard or choice screen instead of the dropdown/workspace section. Replace
the `return (` line and its closing `<>`/`</>` with:

```typescript
  if (!initialAssignmentId && !manualBrowse && entry.kind === 'resume') {
    return (
      <GuidedCalibrationFlow
        enrollmentId={entry.enrollmentId}
        onExitToManualBrowse={() => setManualBrowse(true)}
      />
    )
  }
  if (!initialAssignmentId && !manualBrowse && entry.kind === 'guided') {
    return (
      <GuidedCalibrationFlow
        enrollmentId={entry.enrollmentId}
        onExitToManualBrowse={() => setManualBrowse(true)}
      />
    )
  }
  if (!initialAssignmentId && !manualBrowse && entry.kind === 'choice') {
    return (
      <CalibrationChoiceScreen
        assignments={assignments}
        programs={programs}
        access={access}
        navigate={navigate}
        onBrowse={() => setManualBrowse(true)}
      />
    )
  }

  return (
    <>
```

Everything from the original `<section>` (former line 210) through the
closing `</>` (former line 542) is otherwise unchanged: it becomes the
`manualBrowse` fallback and the `entry.kind === 'empty'` case (zero
assignments still renders the dropdown section's existing `EmptyState`, since
that branch never matches any of the three `if`s above).

- [ ] **Step 3: Pass `access` from `App.tsx`**

In `frontend/src/App.tsx`, add `access={appData.access}` to the
`CalibrationPage` render (lines 81-89):

```typescript
      {route === 'calibration' && (
        <CalibrationPage
          assignments={assignments}
          programs={programs}
          reviewers={reviewers}
          access={appData.access}
          navigate={navigate}
          initialAssignmentId={assignmentLink.initialAssignmentId}
          unresolvedAssignmentId={assignmentLink.unresolvedAssignmentId}
        />
      )}
```

- [ ] **Step 4: Type-check and run the existing suite**

Run: `npm run typecheck`
Expected: PASS

Run: `npm run test:run -- src/test/App.test.tsx`
Expected: **FAIL**, this is the confirmed blast radius from Codebase
Discovery (tests at `App.test.tsx:78,85,101,114` navigate to bare
`/calibration` and expect the dropdown immediately). This failure is
expected here and fixed in Task 11; do not fix it in this task, to keep this
diff focused on the routing wiring itself.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/CalibrationPage.tsx frontend/src/App.tsx
git commit -S -m "feat(frontend): wire calibration entry routing into CalibrationPage"
```

---

## Task 10: `ProgramSetupPage` deep-link wiring

**Files:**
- Modify: `frontend/src/routing/routes.ts`
- Modify: `frontend/src/pages/ProgramSetupPage.tsx:20,58-59`
- Modify: `frontend/src/App.tsx`

depends-on: none (independent of Tasks 5-9; touches different files)

- [ ] **Step 1: Add `programLinkFor` to `routes.ts`, mirroring `assignmentLinkFor`**

In `frontend/src/routing/routes.ts`, immediately after `assignmentLinkFor`
(after line 145), add:

```typescript
/** The deep-link parameter naming a calibration program. */
const programParam = 'program'

/** Builds the query for a program self-assign deep link. */
export function programQuery(programId: string): RouteQuery {
  return { [programParam]: programId }
}

/**
 * Resolves the `program` query parameter against the programs this identity
 * can actually see, the same validate-then-brand pattern `assignmentLinkFor`
 * uses above.
 */
export function programLinkFor(query: RouteQuery, programIds: readonly string[]): string {
  const requested = query[programParam]
  return requested && programIds.includes(requested) ? requested : ''
}
```

`programLinkFor` returns a plain `string` rather than a branded type: unlike
`AssignmentId`, nothing downstream needs the brand's compile-time guarantee
(`ProgramSetupPage`'s `programId` state is already a plain `string`), so
introducing a matching brand here would add ceremony without a consumer.

- [ ] **Step 2: Add `initialProgramId` to `ProgramSetupPage`**

In `frontend/src/pages/ProgramSetupPage.tsx`, change the `Props` type
(line 20):

```typescript
type Props = {
  programs: Program[]
  reviewers: Person[]
  reload: () => Promise<void>
  initialProgramId?: string
}
```

Change the component signature and the `programId` state initializer
(lines 58-59):

```typescript
export function ProgramSetupPage({ programs, reviewers, reload, initialProgramId }: Props) {
  const [programId, setProgramId] = useState(initialProgramId ?? '')
```

- [ ] **Step 3: Wire it in `App.tsx`**

In `frontend/src/App.tsx`, import `programLinkFor` alongside the existing
`assignmentLinkFor`/`useRoute` import (line 13):

```typescript
import { assignmentLinkFor, programLinkFor, useRoute } from './routing/routes'
```

Add a memoized `programId` next to the existing `assignmentLink` memo
(after line 44):

```typescript
  const programId = useMemo(
    () => programLinkFor(query, programs.map((program) => program.id)),
    [programs, query]
  )
```

Pass it to `ProgramSetupPage` (lines 94-100):

```typescript
      {route === 'programs' && appData.capabilities.canManagePrograms && (
        <ProgramSetupPage
          programs={appData.programs}
          reviewers={appData.reviewers}
          reload={appData.reload}
          initialProgramId={programId}
        />
      )}
```

- [ ] **Step 4: Type-check**

Run: `npm run typecheck`
Expected: PASS

- [ ] **Step 5: Write a regression test**

Add to `frontend/src/test/App.test.tsx` (new `describe` block near the
existing `?assignment=` deep-link tests around line 1265, following the same
`beforeEach`/fixture conventions already in that file):

```typescript
describe('program self-assign deep link', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/programs?program=p')
    get.mockImplementation((path: string) => {
      const responses: Record<string, unknown> = {
        '/reviewers': [{ id: 'r', name: 'Evaluator' }],
        '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1', status: 'active' }],
        '/calibration/access': { username: 'manager', manager: true },
        '/calibration/enrollments': [],
        '/evaluations': [],
      }
      return path in responses
        ? Promise.resolve({ data: responses[path] })
        : Promise.reject(new Error(`Unexpected request: ${path}`))
    })
  })

  it('pre-selects the program named by the query parameter', async () => {
    render(<App />)
    expect(await screen.findByLabelText('Program')).toHaveValue('p')
  })
})
```

Run: `npm run test:run -- src/test/App.test.tsx -t "program self-assign deep link"`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routing/routes.ts frontend/src/pages/ProgramSetupPage.tsx frontend/src/App.tsx frontend/src/test/App.test.tsx
git commit -S -m "feat(frontend): add ProgramSetupPage program deep link"
```

---

## Task 11: Fix the confirmed blast radius in existing unit tests

**Files:**
- Modify: `frontend/src/test/App.test.tsx:60`
- Modify: `frontend/src/test/revealAndLog.test.tsx:103`
- Modify: `frontend/src/test/accessibility.test.tsx:28` (triage, may need no change)

depends-on: Task9 [output]

- [ ] **Step 1: Bypass routing in `App.test.tsx`'s calibration-workflow `beforeEach`**

In `frontend/src/test/App.test.tsx`, line 60, change:

```typescript
  window.history.replaceState({}, '', '/calibration')
```

to:

```typescript
  window.history.replaceState({}, '', '/calibration?assignment=assignment')
```

This is the exact `?assignment=` bypass pattern already proven at
`App.test.tsx:1265,1273,1292,1303`; these four tests (lines 78, 85, 101, 114)
are about the dropdown/observation/reveal-eligibility workflow, not entry
routing, so deep-linking straight to the one enrollment their fixture
describes preserves their original intent exactly.

- [ ] **Step 2: Same fix in `revealAndLog.test.tsx`**

In `frontend/src/test/revealAndLog.test.tsx`, line 103, change:

```typescript
    window.history.replaceState({}, '', '/calibration')
```

to:

```typescript
    window.history.replaceState({}, '', '/calibration?assignment=assignment')
```

- [ ] **Step 3: Run both files and read the failures, if any**

Run: `npm run test:run -- src/test/App.test.tsx src/test/revealAndLog.test.tsx`
Expected: PASS. If any test still fails, read its assertion and the actual
DOM output from the failure message; do not guess a fix. The two most likely
residual causes, based on the fixtures already read for this plan: (a) the
fixture's `enrollment` object under `'/calibration/enrollments/assignment'`
now also needs to satisfy `Enrollment`'s existing required fields (it already
does, per the `App.test.tsx` fixture read during planning; no change
expected there), or (b) a test elsewhere in the same file re-sets
`window.location` without the query for a sub-case that still expects the old
dropdown-first behavior, which needs the same `?assignment=` addition applied
at that specific line.

- [ ] **Step 4: Triage `accessibility.test.tsx`**

Run: `npm run test:run -- src/test/accessibility.test.tsx`
Expected: run first to see the actual failure (if any) before editing,
per this task's own Step 3 guidance. `accessibility.test.tsx:28` is a
top-level `beforeEach` (not scoped to one describe block the way
`App.test.tsx:60` is), so check whether every test in the file needs the
`?assignment=` bypass, or only the ones asserting on the workspace's
sample-level markup (an axe scan of the new routing screens themselves is
legitimate coverage to keep, not something to bypass away). If the guided
wizard or choice screen fails its own axe scan, fix the specific violation
reported (e.g., a missing accessible name), not the test.

- [ ] **Step 5: Full frontend unit suite**

Run: `npm run test:run` (from `frontend/`)
Expected: PASS, full suite

- [ ] **Step 6: Commit**

```bash
git add frontend/src/test/App.test.tsx frontend/src/test/revealAndLog.test.tsx frontend/src/test/accessibility.test.tsx
git commit -S -m "test(frontend): bypass calibration entry routing in pre-existing workspace tests"
```

---

## Task 12: e2e coverage

**Files:**
- Modify: `frontend/e2e/support/mock-api.ts:54-68`
- Modify: `frontend/e2e/blind-calibration.spec.ts`
- Create: `frontend/e2e/calibration-entry.spec.ts`

depends-on: Task9 [output], Task10 [output]

- [ ] **Step 1: Enrich the shared `bootstrapRoutes()` fixture**

In `frontend/e2e/support/mock-api.ts`, update the type import (line 6-13)
and the `/calibration/enrollments` entry (lines 64-66):

```typescript
import type {
  Access,
  Assignment,
  Enrollment,
  EnrollmentSummary,
  Observation,
  Person,
  Program,
} from '../../src/api/types'
```

```typescript
    '/calibration/enrollments': [
      {
        id: 'enr1',
        program_id: 'p1',
        reviewer_id: 'r1',
        revealed: false,
        has_started: true,
        total_presentations: 1,
        blotter_complete: 0,
        skin_planned: 0,
        skin_complete: 0,
        program_name: 'Baseline',
        program_version: '1',
        group_name_summary: 'Baseline',
      },
    ] satisfies EnrollmentSummary[],
```

`has_started: true` is chosen deliberately: it routes existing specs that
call `bootstrapRoutes()` and then deep-link via `?assignment=` (all of them,
per the grep in Codebase Discovery, since `blind-calibration.spec.ts` and
`welcome-and-workspace.spec.ts` both already use `?assignment=` or click
through a "Continue calibration" link) straight past the "notStarted" guided
first step, matching that this fixture's enrollment already has a saved
observation in `enrollmentFixture()`. Since every current e2e spec bypasses
routing via a deep link anyway (confirmed in Codebase Discovery), this value
does not change any existing spec's behavior; it only matters for the new
`calibration-entry.spec.ts` states added in Step 3 below, which override
this route explicitly per test rather than relying on the shared default.

- [ ] **Step 2: Run the existing e2e suite to confirm the shared fixture change is safe**

Run: `npm run test:e2e` (from `frontend/`; requires the dev stack running per
the project's existing e2e setup, unchanged by this plan)
Expected: PASS, same as before this task (the shared fixture change is
additive and every existing spec already deep-links past routing)

- [ ] **Step 3: Add new entry-routing states**

Create `frontend/e2e/calibration-entry.spec.ts`:

```typescript
import { test, expect, type Route } from '@playwright/test'
import { mockApi, bootstrapRoutes, managerAccess } from './support/mock-api'

test.describe('Calibration entry routing', () => {
  test('opens the guided wizard on step 1 for a never-started enrollment', async ({ page }) => {
    await mockApi(page, {
      ...bootstrapRoutes(),
      '/calibration/enrollments': [
        {
          id: 'enr1',
          program_id: 'p1',
          reviewer_id: 'r1',
          revealed: false,
          has_started: false,
          total_presentations: 1,
          blotter_complete: 0,
          skin_planned: 0,
          skin_complete: 0,
          program_name: 'Baseline',
          program_version: '1',
          group_name_summary: 'Baseline',
        },
      ],
      '/calibration/enrollments/enr1': {
        id: 'enr1',
        program_id: 'p1',
        reviewer_id: 'r1',
        revealed: false,
        reveal_eligible: false,
        reveal_blocker: 'SKIN_PLAN',
        skin_plan_locked: false,
        presentations: [
          {
            id: 'samp1',
            session_id: 'sess1',
            blind_code: 'ABC-123',
            position: 1,
            skin_planned: false,
            blotter_locked: false,
            skin_locked: false,
            observations: [],
          },
        ],
      },
    })

    await page.goto('/calibration')

    await expect(page.getByRole('heading', { name: 'Guided calibration' })).toBeVisible()
    await expect(page.getByText(/Step 1 of/)).toBeVisible()
    await expect(
      page.getByRole('button', { name: 'Finalize skin-test plan' })
    ).toBeVisible()
  })

  test('opens the guided wizard on the correct next step for an in-progress enrollment', async ({
    page,
  }) => {
    await mockApi(page, {
      ...bootstrapRoutes(),
      '/calibration/enrollments': [
        {
          id: 'enr1',
          program_id: 'p1',
          reviewer_id: 'r1',
          revealed: false,
          has_started: true,
          total_presentations: 1,
          blotter_complete: 0,
          skin_planned: 0,
          skin_complete: 0,
          program_name: 'Baseline',
          program_version: '1',
          group_name_summary: 'Baseline',
        },
      ],
      '/calibration/enrollments/enr1': {
        id: 'enr1',
        program_id: 'p1',
        reviewer_id: 'r1',
        revealed: false,
        reveal_eligible: false,
        reveal_blocker: 'BLOTTER',
        skin_plan_locked: true,
        presentations: [
          {
            id: 'samp1',
            session_id: 'sess1',
            blind_code: 'ABC-123',
            position: 1,
            skin_planned: false,
            blotter_locked: false,
            skin_locked: false,
            observations: [],
          },
        ],
      },
    })

    await page.goto('/calibration')

    await expect(page.getByRole('heading', { name: 'Guided calibration' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'ABC-123' })).toBeVisible()
    await expect(page.getByText('Blind observation')).toBeVisible()
  })

  test('shows the choice screen, self-assign only for a manager', async ({ page }) => {
    await mockApi(page, {
      ...bootstrapRoutes(managerAccess),
      '/calibration/enrollments': [
        {
          id: 'enr1',
          program_id: 'p1',
          reviewer_id: 'r1',
          revealed: true,
          has_started: true,
          total_presentations: 1,
          blotter_complete: 1,
          skin_planned: 0,
          skin_complete: 0,
          program_name: 'Baseline',
          program_version: '1',
          group_name_summary: 'Baseline',
        },
      ],
      '/calibration/programs': [
        { id: 'p1', name: 'Baseline', version: '1', status: 'active' },
        { id: 'p2', name: 'Retest round', version: '1', status: 'active' },
      ],
      '/calibration/programs/p2/members': [{ id: 'm1', group_name: 'Skin Retest' }],
    })

    await page.goto('/calibration')

    await expect(page.getByRole('heading', { name: 'Your calibration' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Redo "Skin Retest"' })).toBeVisible()
  })

  test('a deep link still bypasses routing entirely', async ({ page }) => {
    await mockApi(page, {
      ...bootstrapRoutes(),
      '/calibration/enrollments/enr1': (route: Route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 'enr1',
            program_id: 'p1',
            reviewer_id: 'r1',
            revealed: false,
            reveal_eligible: false,
            reveal_blocker: 'BLOTTER',
            skin_plan_locked: true,
            presentations: [
              {
                id: 'samp1',
                session_id: 'sess1',
                blind_code: 'ABC-123',
                position: 1,
                skin_planned: false,
                blotter_locked: false,
                skin_locked: false,
                observations: [],
              },
            ],
          }),
        }),
    })

    await page.goto('/calibration?assignment=enr1')

    await expect(page.getByLabelText('Evaluator and program')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Guided calibration' })).toHaveCount(0)
  })
})
```

- [ ] **Step 4: Run the new spec**

Run: `npm run test:e2e -- calibration-entry.spec.ts`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/support/mock-api.ts frontend/e2e/calibration-entry.spec.ts
git commit -S -m "test(e2e): cover calibration entry routing states"
```

---

## Task 13: Final verification and spec cross-link

**Files:**
- Modify: `docs/superpowers/specs/2026-09-20-calibration-workflow-design.md` (already amended
  during planning; this task only verifies and, if needed, adds a closing
  cross-link)

depends-on: Task1 [completion] through Task12 [completion]

- [ ] **Step 1: Full backend suite**

Run: `uv run pytest -v`
Expected: PASS, no regressions

- [ ] **Step 2: Full frontend suite plus typecheck**

Run: `npm run typecheck && npm run test:run` (from `frontend/`)
Expected: PASS

- [ ] **Step 3: Full e2e suite**

Run: `npm run test:e2e` (from `frontend/`)
Expected: PASS

- [ ] **Step 4: Pre-commit**

Run: `pre-commit run --all-files` (from the repo root)
Expected: PASS. If `no-em-dash` or `validate-front-matter` fail on this plan
document itself, fix inline and re-run.

- [ ] **Step 5: Commit any final fixups**

```bash
git add -u
git commit -S -m "chore(calibration): final verification pass for guided entry routing"
```

(Only if Steps 1-4 required any fixups; if everything already passed after
Task 12, skip this step; there is nothing to commit.)
