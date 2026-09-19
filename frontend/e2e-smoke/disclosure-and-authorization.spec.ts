import { test, expect, type APIRequestContext } from '@playwright/test'

// Real-backend smoke tier (Task 10 of the frontend testing plan).
//
// Tasks 5, 7, and 9 mock the API, so they only prove the frontend renders
// what it is told. The two invariants below can only be proven against a
// real running backend (docker compose), which is why this tier is
// config-isolated from the mocked e2e suite (separate Playwright config,
// separate npm script, never wired into `npm run test:e2e`) and intended to
// run nightly or pre-deploy rather than on every PR.
//
// #ASSUME: external-resources: grounded in src/fragrance_rater/core/auth.py,
// src/fragrance_rater/api/calibration.py, and
// tests/unit/test_api/test_calibration.py (read directly, not guessed):
// - Auth is Authentik/Traefik forward-auth. The backend trusts an
//   `X-Authentik-Username` request header as-is; Traefik is the component
//   that normally strips a client-supplied copy of that header before
//   injecting its own verified one. docker-compose.yml (repo root) does not
//   front the "app" service with Traefik, so a request that reaches the
//   backend directly (as this spec's `request` fixture does) can set this
//   header to whatever value it likes, exactly like the pytest integration
//   suite's `test_app` client does.
// - Manager status is `identity.username in settings.calibration_admin_usernames`
//   (see `manager()` in api/calibration.py). pytest tests monkeypatch that
//   setting per-test; a real running server can't be monkeypatched from a
//   Playwright spec, so the manager username here is a required environment
//   precondition, not something this spec can grant on its own.
// #VERIFY: SMOKE_MANAGER_USERNAME must be present in the running stack's
// `CALIBRATION_ADMIN_USERNAMES` setting (see .env / .env.example) or every
// setup call in beforeAll will 403 and both tests will fail at setup, not at
// the assertion they exist to make.
const MANAGER_USERNAME = process.env.SMOKE_MANAGER_USERNAME || 'manager'
const RECORDER_USERNAME = process.env.SMOKE_RECORDER_USERNAME || 'smoke-recorder'

const PREFIX = '/api/v1/calibration'

function managerHeaders(): Record<string, string> {
  return { 'X-Authentik-Username': MANAGER_USERNAME }
}

function recorderHeaders(): Record<string, string> {
  return { 'X-Authentik-Username': RECORDER_USERNAME }
}

async function expectOk(response: { ok(): boolean; status(): number; text(): Promise<string> }, step: string) {
  if (!response.ok()) {
    const body = await response.text()
    throw new Error(`${step} failed with status ${response.status()}: ${body}`)
  }
}

// Seed state shared by both tests. Names/versions include a per-run token
// (Date.now()) because Reviewer.name, the (Program.name, Program.version)
// pair, and the fragrance name/brand pairing are all uniquely constrained
// (see models/reviewer.py, models/calibration.py, models/fragrance.py); a
// fixed literal would 409 on the second run against docker compose's
// persistent Postgres volume.
// #ASSUME: data-integrity: there is no afterAll teardown, so each nightly or
// pre-deploy run of this spec leaves one Reviewer, Fragrance, Program,
// ProgramMember, and Enrollment row permanently in the smoke stack's
// Postgres volume; the per-run token above only prevents collisions, it does
// not bound growth.
// #VERIFY: add teardown (delete the created rows in an afterAll) or a
// periodic prune job before this tier runs unattended for an extended period.
let enrollmentId: string
let programId: string
let fragranceName: string
let fragranceBrand: string

test.beforeAll(async ({ request }: { request: APIRequestContext }) => {
  const unique = Date.now()
  fragranceName = `Smoke fragrance ${unique}`
  fragranceBrand = `Smoke house ${unique}`

  const reviewer = await request.post('/api/v1/reviewers', {
    headers: managerHeaders(),
    data: { name: `Smoke reviewer ${unique}` },
  })
  await expectOk(reviewer, 'create reviewer')
  const reviewerId = (await reviewer.json()).id as string

  const fragrance = await request.post('/api/v1/fragrances', {
    headers: managerHeaders(),
    data: {
      name: fragranceName,
      brand: fragranceBrand,
      concentration: 'EDT',
      gender_target: 'Unisex',
      primary_family: 'woody',
      subfamily: 'aromatic',
    },
  })
  await expectOk(fragrance, 'create fragrance')
  const fragranceId = (await fragrance.json()).id as string

  const program = await request.post(`${PREFIX}/programs`, {
    headers: managerHeaders(),
    data: { name: `Smoke protocol ${unique}`, version: '1' },
  })
  await expectOk(program, 'create program')
  programId = (await program.json()).id as string

  const member = await request.post(`${PREFIX}/programs/${programId}/members`, {
    headers: managerHeaders(),
    data: {
      fragrance_id: fragranceId,
      role: 'UNIVERSAL_BASELINE',
      identity_evidence: 'Smoke tier seed data, not real product evidence.',
    },
  })
  await expectOk(member, 'add program member')

  const activation = await request.post(`${PREFIX}/programs/${programId}/activate`, {
    headers: managerHeaders(),
  })
  await expectOk(activation, 'activate program')

  const enrollment = await request.post(`${PREFIX}/programs/${programId}/enroll`, {
    headers: managerHeaders(),
    data: {
      reviewer_id: reviewerId,
      recorder_usernames: [RECORDER_USERNAME],
    },
  })
  await expectOk(enrollment, 'enroll reviewer')
  enrollmentId = (await enrollment.json()).id as string
})

test.describe('Real-backend disclosure and authorization invariants', () => {
  test('never sends identity data for an unrevealed enrollment', async ({ request }) => {
    const response = await request.get(`${PREFIX}/enrollments/${enrollmentId}`, {
      headers: recorderHeaders(),
    })
    expect(response.status()).toBe(200)

    const bodyText = await response.text()
    // Structural check: participant_view() (calibration_service.py) only
    // ever assigns row["identity"] once `enrollment.revealed_at` is set.
    // This enrollment was never revealed, so the key must be absent
    // entirely, not present-and-null.
    const body = JSON.parse(bodyText) as { presentations: Array<Record<string, unknown>> }
    expect(body.presentations.length).toBeGreaterThan(0)
    for (const presentation of body.presentations) {
      expect(Object.prototype.hasOwnProperty.call(presentation, 'identity')).toBe(false)
    }

    // Defense in depth: the seeded fragrance's real name/brand must not
    // leak anywhere else in the payload either.
    expect(bodyText).not.toContain(fragranceName)
    expect(bodyText).not.toContain(fragranceBrand)

    // Perfumer attribution is disclosed on the same condition as name and
    // brand, because knowing the perfumer often identifies the sample.
    //
    // This is a structural check, not a data one: nothing in the API can write
    // a perfumer row (only the Parfumo scraper does), so the seeded fragrance
    // has no attribution and a value-based assertion would pass vacuously.
    // What this catches is the realistic regression, the key being serialised
    // onto the presentation row instead of into the gated identity block.
    expect(bodyText.toLowerCase()).not.toContain('perfumer')
  })

  test('rejects a non-manager call to a manager-only endpoint with 403', async ({ request }) => {
    // manager() (api/calibration.py) runs as the first line of activate(),
    // before any program-state check, so a non-manager gets 403 regardless
    // of whether this program is already active.
    const response = await request.post(`${PREFIX}/programs/${programId}/activate`, {
      headers: recorderHeaders(),
    })
    expect(response.status()).toBe(403)
  })
})
