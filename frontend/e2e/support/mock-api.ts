import type { Page, Route } from '@playwright/test'
import type {
  EnrollmentApiV1CalibrationEnrollmentsEnrollmentIdGetResponse,
  RunView,
} from '../../src/client/types.gen'
import type {
  Access,
  Assignment,
  Enrollment,
  Observation,
  Person,
  Program,
} from '../../src/api/types'

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
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(handler),
    })
  })
}

export const reviewers = [{ id: 'r1', name: 'Evaluator One' }] satisfies Person[]
export const participantAccess = { username: 'family-member', manager: false } satisfies Access
export const managerAccess = { username: 'manager', manager: true } satisfies Access

/**
 * useAppData fetches these four endpoints on mount for EVERY route. Any
 * spec that omits one gets an ErrorState render instead of its target page.
 */
export function bootstrapRoutes(
  access: typeof participantAccess | typeof managerAccess = participantAccess
): MockRoutes {
  return {
    '/reviewers': reviewers,
    '/calibration/access': access,
    '/calibration/programs': [{ id: 'p1', name: 'Baseline', version: '1' }] satisfies Pick<
      Program,
      'id' | 'name' | 'version'
    >[],
    '/calibration/enrollments': [
      { id: 'enr1', program_id: 'p1', reviewer_id: 'r1' },
    ] satisfies Assignment[],
  }
}

export const fragranceCatalog = [
  { id: 'f1', brand: 'House', name: 'Signature', concentration: 'EDP', version_key: '1' },
]

// The generated client type is `dict[str, object]` with only an index signature
// (src/fragrance_rater/api/calibration.py::enrollment has no response_model), so it
// cannot enforce field shape on its own. Intersecting it with the hand-written
// `Enrollment` type (frontend/src/api/types.ts, which mirrors what CalibrationPage.tsx
// actually reads) gives this fixture a real, field-level contract while still
// confirming the generated operation type still exists.
type EnrollmentFixture = Enrollment & EnrollmentApiV1CalibrationEnrollmentsEnrollmentIdGetResponse

export function enrollmentFixture(
  revealed: boolean,
  /**
   * Saved timepoints for the single presentation. Defaults to none, which is
   * the state most specs want; pass rows to exercise the observation log.
   * Typed as `Observation[]` so the fixture-contract check (ADR-014) still
   * catches drift in the rows a spec supplies, not just the ones declared here.
   */
  observations: Observation[] = []
) {
  return {
    id: 'enr1',
    program_id: 'p1',
    reviewer_id: 'r1',
    revealed,
    reveal_eligible: true,
    reveal_blocker: null,
    skin_plan_locked: false,
    presentations: [
      {
        id: 'samp1',
        session_id: 'sess1',
        position: 1,
        blind_code: 'ABC-123',
        blotter_locked: revealed,
        skin_locked: false,
        skin_planned: false,
        identity: revealed
          ? {
              fragrance_id: 'f1',
              brand: 'House',
              name: 'Signature',
              concentration: 'EDP',
              perfumers: [
                { name: 'Fixture Nose', source_url: 'https://example.invalid/attribution' },
              ],
            }
          : undefined,
        observations,
      },
    ],
    // #ASSUME: data-integrity: `Enrollment` (frontend/src/api/types.ts) is hand-written
    // against what the frontend reads, not generated from the backend's untyped
    // `dict[str, object]` response, so it can still drift from the real payload if the
    // backend response-assembly function (participant_view in
    // src/fragrance_rater/services/calibration_service.py) changes independently.
    // #VERIFY: if the backend ever gains a typed response_model for this endpoint, add
    // that generated type to the `EnrollmentFixture` intersection above so both the
    // hand-written and backend-derived contracts are checked together.
  } satisfies EnrollmentFixture
}

export function recommendationRunFixture(interested = false) {
  return {
    id: 'run1',
    reviewer_id: 'r1',
    algorithm_version: 'affinity-v1',
    candidate_strategy: 'catalog-affinity',
    created_at: '2026-09-18T00:00:00Z',
    impressions: [
      {
        id: 'imp1',
        fragrance_id: 'f1',
        fragrance_name: 'Signature',
        fragrance_brand: 'House',
        rank: 1,
        score_type: 'uncalibrated-affinity',
        score_value: 0.87,
        match_percent: 87,
        shown_at: '2026-09-18T00:00:00Z',
        responses: interested
          ? [
              {
                id: 'resp1',
                impression_id: 'imp1',
                revision: 1,
                interested: true,
                sampling_state: null,
                created_at: '2026-09-18T00:00:01Z',
                recorded_by: null,
              },
            ]
          : [],
      },
    ],
  } satisfies RunView
}
