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
