import { http, HttpResponse, type RequestHandler } from 'msw'
import { setupServer } from 'msw/node'

/**
 * The API as the browser sees it, for tests that need real axios behaviour.
 *
 * The older suites replace axios wholesale with `isAxiosError: () => false`, so
 * the user-facing error branch of `requestErrorMessage` never runs in them
 * (architecture review F-11). Tests built on this server leave axios alone and
 * intercept at the network edge, so a 403, a 422 with a detail, or a dropped
 * connection reaches the component as the real error object it would be.
 *
 * The base URL is relative (`/api/v1`) in a test build, so handlers match on
 * the path with a wildcard origin.
 */
export const apiUrl = (path: string) => `*/api/v1${path}`

export const server = setupServer()

/** A JSON GET reply. */
export const getJson = (path: string, body: unknown, status = 200): RequestHandler =>
  http.get(apiUrl(path), () => HttpResponse.json(body as never, { status }))

/** A JSON POST reply. */
export const postJson = (path: string, body: unknown, status = 201): RequestHandler =>
  http.post(apiUrl(path), () => HttpResponse.json(body as never, { status }))

/** What every page loads on mount: the household (non-house) experience. */
export function bootstrapHandlers(
  access: { username: string; manager: boolean } = { username: 'family-member', manager: false },
  assignments: unknown[] = [
    { id: 'enr1', program_id: 'p1', reviewer_id: 'r1', revealed: false, has_started: true },
  ]
): RequestHandler[] {
  return [
    // The house probe fails closed to the household experience.
    http.get(apiUrl('/house-intake/access'), () =>
      HttpResponse.json({ detail: 'Not a house account' }, { status: 404 })
    ),
    getJson('/reviewers', [{ id: 'r1', name: 'Evaluator One' }]),
    getJson('/calibration/access', access),
    getJson('/calibration/programs', [
      { id: 'p1', name: 'Baseline', version: '1', status: 'active' },
    ]),
    getJson('/calibration/enrollments', assignments),
  ]
}
