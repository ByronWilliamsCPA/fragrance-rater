import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page, type Route } from '@playwright/test'
import type { ProgramReadiness } from '../src/api/types'
import { bootstrapRoutes, familyPilotRoutes, managerAccess, mockApi } from './support/mock-api'

/*
 * The manager's Family pilot screen (/programs) and the Advanced setup page it
 * links to (/programs/advanced), against a mocked API. The pilot screen has one
 * job: enroll evaluators with the fixed pilot settings and run the steps after
 * the sittings. It never creates a program and never names a member fragrance.
 */
const axeTags = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']

async function expectNoViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(axeTags).analyze()
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([])
}

const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

const twoEvaluators = [
  { id: 'r1', name: 'Evaluator One' },
  { id: 'r2', name: 'Evaluator Two' },
]

/** Readiness that grows as evaluators are enrolled, so a refresh shows them. */
function enrollingRoutes(sent: { enroll: unknown[]; nonBlind: unknown[]; order: string[] }) {
  const enrolled: ProgramReadiness['enrollments'] = []
  return {
    ...bootstrapRoutes(managerAccess),
    ...familyPilotRoutes(),
    '/reviewers': twoEvaluators,
    '/calibration/programs/p1/readiness': (route: Route) =>
      json(route, {
        program_id: 'p1',
        reveal_policy: 'HOUSEHOLD',
        household_reveal_ready: false,
        household_revealed: false,
        enrollments: enrolled,
      } satisfies ProgramReadiness),
    '/calibration/programs/p1/enroll': (route: Route) => {
      const body = route.request().postDataJSON() as { reviewer_id: string }
      sent.enroll.push(body)
      sent.order.push('enroll')
      const reviewer = twoEvaluators.find((item) => item.id === body.reviewer_id)
      enrolled.push({
        enrollment_id: `enr-${body.reviewer_id}`,
        reviewer_id: body.reviewer_id,
        reviewer_name: reviewer?.name ?? '',
        checkpoint_count: 0,
        checkpoint_blocker: 'BLOTTER',
        reveal_blocker: 'BLOTTER',
        revealed: false,
      })
      return json(route, { id: `enr-${body.reviewer_id}` }, 201)
    },
    '/calibration/enrollments/enr-r1/non-blind': (route: Route) => {
      sent.nonBlind.push(route.request().postDataJSON())
      sent.order.push('non-blind')
      return json(route, { flagged: ['s1'], already_flagged: [] }, 201)
    },
  }
}

test.describe('Family pilot screen', () => {
  test('shows the program and its role counts without naming any member fragrance', async ({
    page,
  }) => {
    await mockApi(page, { ...bootstrapRoutes(managerAccess), ...familyPilotRoutes() })

    await page.goto('/programs')

    await expect(page.getByRole('heading', { name: 'Family pilot' })).toBeVisible()
    await expect(page.getByText('Family pilot · version 3.2')).toBeVisible()
    await expect(page.getByText('33 baseline, 6 hidden repeats, 10 holdouts')).toBeVisible()
    await expect(page.getByText(/Their identities are not shown on this page/)).toBeVisible()
    // The blind answer key: the fixture's member names must never reach the page.
    await expect(page.getByText(/Hidden name|Hidden brand/)).toHaveCount(0)
    await expect(page.getByRole('button', { name: /create|activate/i })).toHaveCount(0)
    await expectNoViolations(page)
  })

  test('with no active family pilot program it says so and offers no create button', async ({
    page,
  }) => {
    await mockApi(page, bootstrapRoutes(managerAccess))

    await page.goto('/programs')

    await expect(
      page.getByText('No family pilot program is active. Ask the operator to load one.')
    ).toBeVisible()
    await expect(page.getByRole('button', { name: /create|enroll/i })).toHaveCount(0)
    await expectNoViolations(page)
  })

  test('enrolls an evaluator with the fixed pilot settings', async ({ page }) => {
    const sent = { enroll: [] as unknown[], nonBlind: [] as unknown[], order: [] as string[] }
    await mockApi(page, enrollingRoutes(sent))

    await page.goto('/programs')
    const row = page.getByRole('listitem').filter({ hasText: 'Evaluator Two' })
    await expect(row).toContainText('Not enrolled')
    await row.getByRole('button', { name: 'Enroll Evaluator Two' }).click()

    await expect(page.getByRole('status')).toContainText(
      'Evaluator Two is enrolled with random blind labels.'
    )
    await expect(row).toContainText('Enrolled')
    expect(sent.enroll).toEqual([
      {
        reviewer_id: 'r2',
        recorder_usernames: ['manager'],
        session_size: 3,
        label_scheme: 'random',
        randomization_algorithm: 'shared-triples-latin-rotation-v1',
        persistent_membership_ids: [],
        session_template: null,
      },
    ])
    expect(sent.nonBlind).toEqual([])
  })

  test('a facilitator is flagged non-blind after enrolling, using the keyboard only', async ({
    page,
  }) => {
    const sent = { enroll: [] as unknown[], nonBlind: [] as unknown[], order: [] as string[] }
    await mockApi(page, enrollingRoutes(sent))

    await page.goto('/programs')
    const row = page.getByRole('listitem').filter({ hasText: 'Evaluator One' })
    const facilitator = row.getByRole('checkbox', { name: /Facilitator \(non-blind\)/ })
    const enroll = row.getByRole('button', { name: 'Enroll Evaluator One' })

    await facilitator.focus()
    await expect(facilitator).toBeFocused()
    await page.keyboard.press('Space')
    await expect(facilitator).toBeChecked()
    await page.keyboard.press('Tab')
    await expect(enroll).toBeFocused()
    await page.keyboard.press('Enter')

    await expect(page.getByRole('status')).toContainText(
      'Evaluator One is enrolled and marked non-blind.'
    )
    expect(sent.order).toEqual(['enroll', 'non-blind'])
    expect(sent.nonBlind).toEqual([
      { explanation: 'Facilitator who labels and sprays the samples' },
    ])
    await expectNoViolations(page)
  })

  test('says clearly when the non-blind flag fails after a successful enroll', async ({ page }) => {
    const sent = { enroll: [] as unknown[], nonBlind: [] as unknown[], order: [] as string[] }
    await mockApi(page, {
      ...enrollingRoutes(sent),
      '/calibration/enrollments/enr-r1/non-blind': (route: Route) =>
        json(route, { detail: 'flagging is down' }, 500),
    })

    await page.goto('/programs')
    const row = page.getByRole('listitem').filter({ hasText: 'Evaluator One' })
    await row.getByRole('checkbox', { name: /Facilitator \(non-blind\)/ }).check()
    await row.getByRole('button', { name: 'Enroll Evaluator One' }).click()

    await expect(page.getByRole('alert')).toContainText(
      'Evaluator One is enrolled but could NOT be marked non-blind'
    )
    await expect(
      row.getByRole('button', { name: 'Retry non-blind flag for Evaluator One' })
    ).toBeVisible()
    await expect(page.getByText(/is enrolled and marked non-blind/)).toHaveCount(0)
  })

  test('keeps the irreversible-action confirmation on freezing checkpoints', async ({ page }) => {
    await mockApi(page, {
      ...bootstrapRoutes(managerAccess),
      ...familyPilotRoutes({
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
      }),
    })

    await page.goto('/programs')
    await page.getByRole('button', { name: 'Freeze checkpoints' }).click()

    await expect(page.getByText(/A checkpoint cannot be undone/)).toBeVisible()
    await expect(page.getByRole('button', { name: 'Confirm checkpoints' })).toBeFocused()
    await expect(page.getByText('Reveal policy: whole household together')).toBeVisible()
    await expect(page.getByRole('combobox', { name: 'Reveal policy' })).toHaveCount(0)
  })
})

test.describe('Advanced setup', () => {
  const draftProgram = [
    { id: 'p1', name: 'Baseline', version: '1', status: 'draft', reveal_policy: 'ENROLLMENT' },
  ]

  test('shows the reveal policy before the Activate button and warns before activating', async ({
    page,
  }) => {
    let activated = 0
    await mockApi(page, {
      ...bootstrapRoutes(managerAccess),
      ...familyPilotRoutes(),
      '/calibration/programs': draftProgram,
      '/calibration/programs/p1/activate': (route: Route) => {
        activated += 1
        return json(route, { id: 'p1', status: 'active' })
      },
    })

    await page.goto('/programs/advanced')
    await page.getByLabel('Program').selectOption('p1')

    const policy = page.getByLabel('Reveal policy for this program')
    const activate = page.getByRole('button', { name: 'Activate and lock definition' })
    await expect(policy).toBeVisible()
    const policyBox = await policy.boundingBox()
    const activateBox = await activate.boundingBox()
    expect(policyBox).not.toBeNull()
    expect(activateBox).not.toBeNull()
    expect(policyBox!.y).toBeLessThan(activateBox!.y)

    await activate.click()
    await expect(page.getByText(/is permanent and cannot be undone/)).toBeVisible()
    await expect(page.getByText(/each evaluator separately/).first()).toBeVisible()
    await expectNoViolations(page)
    expect(activated).toBe(0)

    await page.getByRole('button', { name: 'Confirm activation' }).click()
    await expect.poll(() => activated).toBe(1)
  })

  test('links back to the Family pilot screen', async ({ page }) => {
    await mockApi(page, bootstrapRoutes(managerAccess))

    await page.goto('/programs/advanced')
    await page
      .getByRole('link', { name: /Family pilot/ })
      .first()
      .click()

    await expect(page).toHaveURL('/programs')
    await expect(page.getByRole('heading', { name: 'Family pilot' })).toBeVisible()
  })
})
