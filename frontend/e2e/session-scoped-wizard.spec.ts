import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page, type Route } from '@playwright/test'
import { bootstrapRoutes, managerAccess, mockApi, sessionIntroRoutes } from './support/mock-api'
import type { Enrollment, Observation, ProgramReadiness, Sample } from '../src/api/types'

/*
 * The F1 facilitated format end to end against a mocked API: one session at a
 * time, a ranking per session posted to that session, a boundary screen that
 * never auto-advances, final samples held closed until a checkpoint, and the
 * household wait. Each new screen is scanned against WCAG 2.2 AA (ADR-014).
 */
const axeTags = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']

async function expectNoViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(axeTags).analyze()
  expect(results.violations).toEqual([])
}

const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

const answered = (id: string): Observation =>
  ({
    id,
    phase: 'PRE_REVEAL',
    stage: 'BLOTTER',
    detected: true,
    response_status: 'completed',
    elapsed_minutes: 0,
  }) as Observation

function sample(
  id: string,
  sessionId: string,
  position: number,
  state: 'open' | 'done' | 'closed'
) {
  return {
    id,
    session_id: sessionId,
    blind_code: `CODE-${id.toUpperCase()}`,
    position,
    skin_planned: false,
    blotter_locked: state === 'done',
    skin_locked: false,
    post_reveal_entry: false,
    available: state !== 'closed',
    observations: state === 'done' ? [answered(`${id}-o`)] : [],
  } satisfies Sample
}

/** Two baseline sessions (the second with a hidden repeat) and a closed final session. */
function household(sessionB: 'open' | 'done', overrides: Partial<Enrollment> = {}): Enrollment {
  return {
    id: 'enr1',
    program_id: 'p1',
    reviewer_id: 'r1',
    revealed: false,
    reveal_eligible: false,
    reveal_blocker: 'SKIN_PLAN',
    skin_plan_locked: false,
    reveal_policy: 'HOUSEHOLD',
    presentations: [
      sample('a1', 'sessA', 1, 'done'),
      sample('a2', 'sessA', 2, 'done'),
      sample('a3', 'sessA', 3, 'done'),
      sample('b1', 'sessB', 1, sessionB),
      sample('repeat', 'sessB', 2, sessionB),
      sample('h1', 'sessH', 1, 'closed'),
      sample('h2', 'sessH', 2, 'closed'),
    ],
    ...overrides,
  }
}

async function expectNoFinalSamplesOrHoldoutWording(page: Page) {
  await expect(page.getByText(/CODE-H\d/)).toHaveCount(0)
  expect(await page.locator('body').innerText()).not.toMatch(/holdout/i)
}

test.describe('Session-scoped guided calibration', () => {
  test('ranks a finished session on its own id, stops at a boundary, then opens the next session', async ({
    page,
  }) => {
    const sent: { path: string; body: unknown }[] = []
    await mockApi(page, {
      ...bootstrapRoutes(),
      ...sessionIntroRoutes({ approved: true, consent: 'granted', sessionId: 'sessB' }),
      '/calibration/enrollments/enr1': household('open'),
      '/calibration/sessions/sessA/rankings': (route: Route) => {
        if (route.request().method() !== 'POST') return json(route, [])
        sent.push({ path: 'rank-sessA', body: route.request().postDataJSON() })
        return json(route, {}, 201)
      },
      '/calibration/sessions/sessB/start': (route: Route) => {
        sent.push({ path: 'start-sessB', body: route.request().postDataJSON() })
        return json(route, { id: 'sessB' }, 201)
      },
    })

    await page.goto('/calibration')

    const ranking = page.getByRole('group', { name: 'Your ranking' })
    await expect(ranking).toBeVisible()
    const places = ranking.getByRole('combobox')
    await expect(places).toHaveCount(3)
    await places.nth(0).selectOption('2')
    await places.nth(1).selectOption('1')
    await places.nth(2).selectOption('3')
    await expectNoViolations(page)
    await ranking.getByRole('button', { name: 'Save ranking' }).click()

    await expect(page.getByText('Session complete. Wait for the facilitator.')).toBeVisible()
    expect(sent).toEqual([
      {
        path: 'rank-sessA',
        body: {
          stage: 'BLOTTER',
          response_status: 'completed',
          entries: [
            { presentation_id: 'a1', rank_position: 2 },
            { presentation_id: 'a2', rank_position: 1 },
            { presentation_id: 'a3', rank_position: 3 },
          ],
        },
      },
    ])
    await expect(page.getByText('Blind observation')).toHaveCount(0)
    await expectNoViolations(page)

    await page.getByRole('button', { name: 'Facilitator: continue' }).click()
    await expect(page.getByRole('heading', { name: 'Before you begin' })).toBeVisible()
    await page.getByRole('button', { name: 'Continue to the samples' }).click()

    await expect(page.getByRole('heading', { name: 'CODE-B1' })).toBeVisible()
    await expect(page.getByText(/Session 2 of 3/)).toBeVisible()
    expect(sent.map((item) => item.path)).toEqual(['rank-sessA', 'start-sessB'])
    await expectNoFinalSamplesOrHoldoutWording(page)
  })

  test('waits for the checkpoint instead of offering a closed final sample', async ({ page }) => {
    await mockApi(page, {
      ...bootstrapRoutes(),
      '/calibration/enrollments/enr1': household('done', {
        skin_plan_locked: true,
        reveal_blocker: 'CHECKPOINT',
      }),
      '/calibration/sessions/sessB/rankings': [{ response_status: 'completed' }],
    })

    await page.goto('/calibration')
    await page.getByRole('button', { name: 'Facilitator: continue' }).click()

    await expect(
      page.getByText('Blind baseline work is complete. Wait for the facilitator.')
    ).toBeVisible()
    await expect(page.getByText('Blind observation')).toHaveCount(0)
    await expectNoFinalSamplesOrHoldoutWording(page)
    await expectNoViolations(page)
  })

  test('shows a manager who is still outstanding while the household waits', async ({ page }) => {
    const readiness: ProgramReadiness = {
      program_id: 'p1',
      reveal_policy: 'HOUSEHOLD',
      household_reveal_ready: false,
      household_revealed: false,
      enrollments: [
        {
          enrollment_id: 'enr1',
          reviewer_id: 'r1',
          reviewer_name: 'Evaluator One',
          checkpoint_count: 1,
          checkpoint_blocker: null,
          reveal_blocker: 'HOUSEHOLD_WAIT',
          revealed: false,
        },
        {
          enrollment_id: 'enr2',
          reviewer_id: 'r2',
          reviewer_name: 'Evaluator Two',
          checkpoint_count: 1,
          checkpoint_blocker: null,
          reveal_blocker: 'HOLDOUT',
          revealed: false,
        },
      ],
    }
    const finished = household('done', {
      skin_plan_locked: true,
      reveal_blocker: 'HOUSEHOLD_WAIT',
    })
    finished.presentations = finished.presentations.map((item) =>
      item.session_id === 'sessH' ? sample(item.id, 'sessH', item.position, 'done') : item
    )
    await mockApi(page, {
      ...bootstrapRoutes(managerAccess),
      '/calibration/enrollments/enr1': finished,
      '/calibration/sessions/sessH/rankings': [{ response_status: 'completed' }],
      '/calibration/programs/p1/readiness': readiness,
    })

    await page.goto('/calibration')
    await page.getByRole('button', { name: 'Facilitator: continue' }).click()

    await expect(
      page.getByText('This evaluator is finished. Wait for the facilitator.')
    ).toBeVisible()
    await expect(page.getByText('Evaluator Two')).toBeVisible()
    await expect(page.getByText('Final samples remain')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Reveal completed baseline' })).toHaveCount(0)
    await expectNoViolations(page)
  })
})

test.describe('Checkpoints and reveal in Program setup', () => {
  test('freezes checkpoints for ready evaluators and scans clean', async ({ page }) => {
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
            checkpoint_blocker: null,
            reveal_blocker: 'CHECKPOINT',
            revealed: false,
          },
        ],
      } satisfies ProgramReadiness,
      '/calibration/programs/p1/checkpoints': (route: Route) => {
        sent.push(route.request().postDataJSON())
        return json(
          route,
          {
            program_id: 'p1',
            algorithm_version: 'v',
            created: [
              {
                enrollment_id: 'enr1',
                checkpoint_id: 'c1',
                predictions_frozen: 3,
                predictions_skipped: 0,
              },
            ],
            skipped: [],
          },
          201
        )
      },
    })

    await page.goto('/programs')
    await page.getByLabel('Program').selectOption('p1')

    const readiness = page.getByRole('table', { name: 'Checkpoint and reveal readiness' })
    await expect(readiness.getByText('Ready for a checkpoint')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Reveal the household' })).toBeDisabled()
    await expectNoViolations(page)

    await page.getByRole('button', { name: 'Freeze checkpoints' }).click()
    await page.getByRole('button', { name: 'Confirm checkpoints' }).click()
    await expect(page.getByText('Froze 1 checkpoint(s).')).toBeVisible()
    expect(sent).toEqual([{ algorithm_version: null, freeze_predictions: true }])
  })
})
