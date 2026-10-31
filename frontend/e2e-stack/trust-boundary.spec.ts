import { expect, request, test } from '@playwright/test'
import { MANAGER, RECORDER, apiAs, baseURL, seedAssignment } from './support/stack'

/*
 * What the edge guarantees, checked against the real backend. In production
 * Traefik + Authentik establish identity and nginx strips every client-sent
 * X-Authentik-* header; the stub reproduces that, so these tests fail if the
 * backend ever starts trusting something the edge does not vouch for.
 */
test.describe('Trust boundary', () => {
  test('a request with no session is challenged, not served', async () => {
    const anonymous = await request.newContext({ baseURL })

    const response = await anonymous.get('/api/v1/calibration/access')

    expect(response.status()).toBe(401)
  })

  test('a session establishes identity and the manager role comes from the allow-list', async () => {
    const recorder = await apiAs(RECORDER)
    const manager = await apiAs(MANAGER)

    const asRecorder = await (await recorder.get('/api/v1/calibration/access')).json()
    const asManager = await (await manager.get('/api/v1/calibration/access')).json()

    expect(asRecorder).toMatchObject({ username: RECORDER, manager: false })
    expect(asManager).toMatchObject({ username: MANAGER, manager: true })
  })

  test('a client cannot choose its own identity by sending the header itself', async () => {
    const spoofing = await request.newContext({
      baseURL,
      extraHTTPHeaders: {
        Cookie: `stack_session=${RECORDER}`,
        'X-Authentik-Username': MANAGER,
        'x-authentik-groups': 'admins',
      },
    })

    const access = await (await spoofing.get('/api/v1/calibration/access')).json()
    const activate = await spoofing.post('/api/v1/calibration/programs/nope/activate')

    expect(access).toMatchObject({ username: RECORDER, manager: false })
    expect(activate.status()).toBe(403)
  })

  test('a spoofed header without any session still gets nowhere', async () => {
    const spoofing = await request.newContext({
      baseURL,
      extraHTTPHeaders: { 'X-Authentik-Username': MANAGER },
    })

    expect((await spoofing.get('/api/v1/calibration/access')).status()).toBe(401)
  })

  test('an unrevealed enrollment discloses no identity through the edge', async () => {
    const seeded = await seedAssignment()
    const recorder = await apiAs(RECORDER)

    const response = await recorder.get(`/api/v1/calibration/enrollments/${seeded.enrollmentId}`)
    const text = await response.text()

    expect(response.status()).toBe(200)
    for (const presentation of JSON.parse(text).presentations) {
      expect(Object.prototype.hasOwnProperty.call(presentation, 'identity')).toBe(false)
    }
    expect(text).not.toContain(seeded.fragranceName)
    expect(text).not.toContain(seeded.fragranceBrand)
  })

  test('someone who is not assigned cannot read another evaluator’s enrollment', async () => {
    const seeded = await seedAssignment()
    const stranger = await apiAs('someone-else')

    const response = await stranger.get(`/api/v1/calibration/enrollments/${seeded.enrollmentId}`)

    expect(response.status()).toBe(403)
  })
})
