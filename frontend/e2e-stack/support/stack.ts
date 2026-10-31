import { request, type APIRequestContext, type BrowserContext } from '@playwright/test'

/** Must be listed in the backend's CALIBRATION_ADMIN_USERNAMES. */
export const MANAGER = process.env.STACK_MANAGER_USERNAME ?? 'manager'
export const RECORDER = process.env.STACK_RECORDER_USERNAME ?? 'stack-recorder'
export const baseURL = `http://127.0.0.1:${process.env.STACK_PORT ?? 8080}`

/** Start a browser session as `username`, the way an Authentik login would. */
export async function signIn(context: BrowserContext, username: string) {
  await context.addCookies([{ name: 'stack_session', value: username, url: baseURL }])
}

/** An API client that goes through the stub with `username`'s session. */
export async function apiAs(username: string): Promise<APIRequestContext> {
  return request.newContext({
    baseURL,
    extraHTTPHeaders: { Cookie: `stack_session=${username}` },
  })
}

async function ok(
  response: { ok(): boolean; status(): number; text(): Promise<string> },
  step: string
) {
  if (!response.ok())
    throw new Error(`${step} failed (${response.status()}): ${await response.text()}`)
}

export type Seeded = {
  enrollmentId: string
  recorder: string
  programId: string
  programName: string
  reviewerName: string
  fragranceName: string
  fragranceBrand: string
}

/** A recorder username no other test shares, so entry routing is unambiguous. */
export function freshRecorder(label: string): string {
  return `stack-${label}-${Date.now() % 1e9}-${Math.floor(Math.random() * 1e4)}`
}

/**
 * Create one evaluator with one active single-sample program and an enrollment
 * the recorder can work, as the manager would. Names carry a per-run token
 * because reviewers, programs and fragrances are uniquely constrained.
 */
export async function seedAssignment(recorder: string = RECORDER): Promise<Seeded> {
  const manager = await apiAs(MANAGER)
  const token = `${Date.now()}-${Math.floor(Math.random() * 1e6)}`
  const reviewerName = `Stack reviewer ${token}`
  const fragranceName = `Stack fragrance ${token}`
  const fragranceBrand = `Stack house ${token}`

  const reviewer = await manager.post('/api/v1/reviewers', { data: { name: reviewerName } })
  await ok(reviewer, 'create reviewer')
  const fragrance = await manager.post('/api/v1/fragrances', {
    data: {
      name: fragranceName,
      brand: fragranceBrand,
      concentration: 'EDT',
      gender_target: 'Unisex',
      primary_family: 'woody',
      subfamily: 'aromatic',
    },
  })
  await ok(fragrance, 'create fragrance')
  const programName = `Stack protocol ${token}`
  const program = await manager.post('/api/v1/calibration/programs', {
    data: { name: programName, version: '1' },
  })
  await ok(program, 'create program')
  const programId = (await program.json()).id as string
  await ok(
    await manager.post(`/api/v1/calibration/programs/${programId}/members`, {
      data: {
        fragrance_id: (await fragrance.json()).id,
        role: 'UNIVERSAL_BASELINE',
        identity_evidence: 'Real-stack test seed, not product evidence.',
      },
    }),
    'add member'
  )
  await ok(await manager.post(`/api/v1/calibration/programs/${programId}/activate`), 'activate')
  const enrollment = await manager.post(`/api/v1/calibration/programs/${programId}/enroll`, {
    data: {
      reviewer_id: (await reviewer.json()).id,
      recorder_usernames: [recorder],
    },
  })
  await ok(enrollment, 'enroll')
  const enrollmentId = (await enrollment.json()).id as string
  await manager.dispose()
  return {
    enrollmentId,
    recorder,
    programId,
    programName,
    reviewerName,
    fragranceName,
    fragranceBrand,
  }
}
