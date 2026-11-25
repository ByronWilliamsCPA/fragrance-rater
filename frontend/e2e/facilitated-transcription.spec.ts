import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page, type Route } from '@playwright/test'
import { bootstrapRoutes, managerAccess, mockApi, sessionIntroRoutes } from './support/mock-api'
import type { Enrollment, ProgramReadiness, Sample } from '../src/api/types'

/*
 * A facilitator copying an evaluator's paper sheet into the app, against a
 * mocked API: the blind code on the sheet must match the open sample, the
 * sheet's own times are what is sent, a slow first smell is warned about but
 * still saved, and a manager can mark the answer-key holder non-blind. Each new
 * screen is scanned against WCAG 2.2 AA (ADR-014).
 */
const axeTags = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']

async function expectNoViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(axeTags).analyze()
  expect(results.violations).toEqual([])
}

const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

const SPRAYED = '2026-11-25T10:00'
const SMELLED_LATE = '2026-11-25T10:08'
const FINISHED = '2026-11-25T10:20'

const openSample = {
  id: 'a1',
  session_id: 'sessA',
  blind_code: 'CODE-A1',
  position: 1,
  skin_planned: false,
  blotter_locked: false,
  skin_locked: false,
  post_reveal_entry: false,
  available: true,
  observations: [],
} satisfies Sample

const enrollment: Enrollment = {
  id: 'enr1',
  program_id: 'p1',
  reviewer_id: 'r1',
  revealed: false,
  reveal_eligible: false,
  reveal_blocker: 'BLOTTER',
  skin_plan_locked: false,
  reveal_policy: 'HOUSEHOLD',
  presentations: [openSample],
}

test.describe('Facilitator transcription of a paper sheet', () => {
  test('refuses a column keyed to the wrong sample, then saves the sheet times and warns about a slow first smell', async ({
    page,
  }) => {
    const sent: { path: string; body: Record<string, unknown> }[] = []
    const record = (path: string) => (route: Route) => {
      sent.push({ path, body: route.request().postDataJSON() })
      return json(route, { id: 'x' }, 201)
    }
    await mockApi(page, {
      ...bootstrapRoutes(),
      ...sessionIntroRoutes({ approved: false, sessionId: 'sessA' }),
      '/calibration/enrollments/enr1': enrollment,
      '/calibration/presentations/a1/exposure': record('exposure'),
      '/calibration/presentations/a1/observations': record('observation'),
    })

    await page.goto('/calibration')
    await page.getByLabel('Session start time written on the sheet').fill(SPRAYED)
    await page.getByRole('button', { name: 'Continue to the samples' }).click()

    await expect(page.getByRole('heading', { name: 'CODE-A1' })).toBeVisible()
    await page.getByLabel('Time sprayed').fill(SPRAYED)
    await page.getByLabel('Time first smelled').fill(SMELLED_LATE)
    await page.getByLabel('Time this column finished').fill(FINISHED)
    await expect(page.getByText('Elapsed since the spray: 20 whole minutes.')).toBeVisible()
    await expect(page.getByText(/over the 2-minute ceiling/)).toBeVisible()
    await expectNoViolations(page)

    await page.getByLabel('Blind code printed on the sheet').fill('CODE-A2')
    await page.getByRole('button', { name: 'Save observation' }).click()
    await expect(page.getByText(/does not match this sample/)).toBeVisible()
    expect(sent).toEqual([])

    await page.getByLabel('Blind code printed on the sheet').fill('code-a1')
    await page.getByRole('button', { name: 'Save observation' }).click()
    await expect(
      page.getByText('Observation saved. Original responses are retained.')
    ).toBeVisible()

    expect(sent.map((item) => item.path)).toEqual(['exposure', 'observation'])
    expect(sent[0].body).toMatchObject({ stage: 'BLOTTER', confirmed_blind_code: 'code-a1' })
    expect(sent[0].body.at).toEqual(expect.any(String))
    expect(sent[0].body.sprayed_at).toEqual(expect.any(String))
    expect(sent[1].body).toMatchObject({ confirmed_blind_code: 'code-a1' })
    expect(sent[1].body.observed_at).toEqual(expect.any(String))
    expect(sent[1].body).not.toHaveProperty('elapsed_minutes')
  })
})

test.describe('Marking the answer-key holder non-blind', () => {
  test('explains the effect and posts the written reason once confirmed', async ({ page }) => {
    const sent: unknown[] = []
    await mockApi(page, {
      ...bootstrapRoutes(managerAccess),
      '/calibration/programs': [
        { id: 'p1', name: 'Baseline', version: '1', status: 'active', reveal_policy: 'HOUSEHOLD' },
      ],
      '/calibration/programs/p1/members': [],
      '/calibration/programs/p1/readiness': {
        program_id: 'p1',
        reveal_policy: 'HOUSEHOLD',
        household_reveal_ready: false,
        household_revealed: false,
        enrollments: [
          {
            enrollment_id: 'enr1',
            reviewer_id: 'r1',
            reviewer_name: 'Evaluator One',
            checkpoint_count: 0,
            checkpoint_blocker: 'BLOTTER',
            reveal_blocker: 'BLOTTER',
            revealed: false,
          },
        ],
      } satisfies ProgramReadiness,
      '/calibration/enrollments/enr1/non-blind': (route: Route) => {
        sent.push(route.request().postDataJSON())
        return json(route, { flagged: ['sessA', 'sessB'], already_flagged: [] }, 201)
      },
    })

    await page.goto('/programs')
    await page.getByLabel('Program').selectOption('p1')

    await expect(page.getByText(/excluded from blind-baseline training/)).toBeVisible()
    await page.getByLabel('Evaluator who holds the mapping').selectOption('enr1')
    await expectNoViolations(page)
    await page.getByRole('button', { name: 'Mark evaluator non-blind' }).click()
    await page.getByRole('button', { name: 'Confirm non-blind' }).click()

    await expect(page.getByText(/2 session\(s\) newly flagged/)).toBeVisible()
    expect(sent).toEqual([
      {
        explanation: 'Declared mapping holder; sprays, times, transcribes and controls the reveal.',
      },
    ])
  })
})
