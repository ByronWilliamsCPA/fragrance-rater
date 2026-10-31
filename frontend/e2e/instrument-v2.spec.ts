import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page, type Route } from '@playwright/test'
import { bootstrapRoutes, mockApi, sessionIntroRoutes } from './support/mock-api'
import type { Enrollment, Observation } from '../src/api/types'

/*
 * R7b participant instrument v2, end to end against a mocked API: the consent
 * screen, the new blotter and skin fields, the end-of-session ranking and the
 * problem flag. Each screen is also scanned against WCAG 2.2 AA (ADR-014).
 */
const axeTags = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']

async function expectNoViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(axeTags).analyze()
  expect(results.violations).toEqual([])
}

const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

type Sent = { path: string; body: Record<string, unknown> }

function recorder() {
  const sent: Sent[] = []
  const record =
    (path: string, reply: unknown = {}) =>
    (route: Route) => {
      sent.push({
        path,
        body: (route.request().postDataJSON() as Record<string, unknown> | null) ?? {},
      })
      return json(route, reply, 201)
    }
  return { sent, record }
}

function sample(id: string, position: number, observations: Observation[] = []) {
  return {
    id,
    session_id: 'sess1',
    position,
    blind_code: `CODE-${position}`,
    skin_planned: false,
    blotter_locked: false,
    skin_locked: false,
    post_reveal_entry: false,
    observations,
  }
}

function enrollment(overrides: Partial<Enrollment>): Enrollment {
  return {
    id: 'enr1',
    program_id: 'p1',
    reviewer_id: 'r1',
    revealed: false,
    reveal_eligible: false,
    reveal_blocker: 'BLOTTER',
    skin_plan_locked: true,
    presentations: [sample('samp1', 1)],
    ...overrides,
  } as Enrollment
}

const detectedRow = (id: string): Observation =>
  ({
    id,
    phase: 'PRE_REVEAL',
    stage: 'BLOTTER',
    detected: true,
    response_status: 'completed',
    elapsed_minutes: 0,
  }) as Observation

test.describe('Consent and session conditions', () => {
  test('shows a draft wording without an agree button, and still lets the evaluator continue', async ({
    page,
  }) => {
    const { sent, record } = recorder()
    await mockApi(page, {
      ...bootstrapRoutes(),
      ...sessionIntroRoutes({ approved: false }),
      '/calibration/sessions/sess1/start': record('start'),
      '/calibration/enrollments/enr1': enrollment({
        skin_plan_locked: false,
        reveal_blocker: 'SKIN_PLAN',
      }),
    })

    await page.goto('/calibration')

    await expect(page.getByRole('heading', { name: 'Before you begin' })).toBeVisible()
    await expect(page.getByText(/still being finalized/i)).toBeVisible()
    await expect(page.getByRole('button', { name: /i agree/i })).toHaveCount(0)
    await expectNoViolations(page)

    await page.getByRole('button', { name: 'Continue to the samples' }).click()
    await expect(page.getByRole('heading', { name: 'Guided calibration' })).toBeVisible()
    expect(sent).toHaveLength(1)
    expect(sent[0].path).toBe('start')
    expect(typeof sent[0].body.evaluator_timezone).toBe('string')
  })

  test('records consent, then optional conditions that can each be refused', async ({ page }) => {
    const { sent, record } = recorder()
    let consent = 'none'
    await mockApi(page, {
      ...bootstrapRoutes(),
      ...sessionIntroRoutes({ approved: true }),
      '/calibration/reviewers/r1/consent': (route: Route) => {
        if (route.request().method() === 'POST') {
          consent = 'granted'
          sent.push({ path: 'consent', body: route.request().postDataJSON() as never })
          return json(route, { id: 'c1' }, 201)
        }
        return json(route, { state: { session_context: consent }, events: [] })
      },
      '/calibration/sessions/sess1/context': (route: Route) =>
        route.request().method() === 'POST'
          ? record('context')(route)
          : json(route, { recorded: false }),
      '/calibration/enrollments/enr1': enrollment({
        skin_plan_locked: false,
        reveal_blocker: 'SKIN_PLAN',
      }),
    })

    await page.goto('/calibration')
    await page.getByRole('button', { name: /i agree/i }).click()
    await expect(page.getByText(/every question is optional/i)).toBeVisible()
    await expectNoViolations(page)

    await page.getByLabel(/feeling unwell/i).selectOption('prefer_not_to_answer')
    await page.getByLabel(/hours since you last ate/i).fill('3')
    await page.getByRole('button', { name: 'Save conditions' }).click()

    await expect.poll(() => sent.map((item) => item.path)).toEqual(['consent', 'context'])
    expect(sent[0].body).toMatchObject({ scope: 'session_context', event_type: 'granted' })
    expect(sent[1].body).toEqual({ illness: 'prefer_not_to_answer', hours_since_food: 3 })
  })
})

test.describe('Observation form', () => {
  test('writes the R7b capture fields for a blotter response', async ({ page }) => {
    const { sent, record } = recorder()
    await mockApi(page, {
      ...bootstrapRoutes(),
      '/calibration/enrollments/enr1': enrollment({}),
      '/calibration/presentations/samp1/observations': record('observe', { id: 'o1' }),
    })

    await page.goto('/calibration')
    await expect(page.getByRole('heading', { name: 'CODE-1' })).toBeVisible()
    await page.getByLabel('Detected').selectOption('yes')
    await page.getByLabel(/do you recognize this/i).selectOption('vaguely_familiar')
    await page.getByLabel(/owned or worn/i).selectOption('no')
    await expectNoViolations(page)
    await page.getByRole('button', { name: 'Save observation' }).click()

    await expect.poll(() => sent.length).toBe(1)
    expect(sent[0].body).toMatchObject({
      stage: 'BLOTTER',
      detected: true,
      response_status: 'completed',
      recognition: 'vaguely_familiar',
      owned_or_worn: 'no',
    })
    expect(Date.parse(String(sent[0].body.observed_at))).not.toBeNaN()
  })

  test('offers the fixed skin timepoints, scrub-off and multi-select fit on skin', async ({
    page,
  }) => {
    const { sent, record } = recorder()
    const planned = {
      ...sample('samp1', 1, [detectedRow('o0')]),
      skin_planned: true,
      blotter_locked: true,
    }
    await mockApi(page, {
      ...bootstrapRoutes(),
      '/calibration/enrollments/enr1': enrollment({
        reveal_blocker: 'SKIN',
        presentations: [planned],
      }),
      '/calibration/presentations/samp1/observations': record('observe', { id: 'o2' }),
    })

    await page.goto('/calibration')
    await page.getByLabel('Timepoint').selectOption('240')
    await page.getByLabel(/did you wash it off/i).selectOption('yes')
    await page.getByLabel(/minutes until you washed/i).fill('90')
    await page.locator('label', { hasText: 'Spring' }).click()
    await page.locator('label', { hasText: 'Fall' }).click()
    await page.locator('label', { hasText: 'At home' }).click()
    await expectNoViolations(page)
    await page.getByRole('button', { name: 'Save observation' }).click()

    await expect.poll(() => sent.length).toBe(1)
    expect(sent[0].body).toMatchObject({
      stage: 'SKIN',
      elapsed_minutes: 240,
      scrubbed_off: true,
      time_to_scrub_minutes: 90,
      season_fit: ['spring', 'fall'],
      setting_fit: ['home'],
    })
  })
})

test.describe('Ranking and problem flag', () => {
  const ready = () =>
    enrollment({
      reveal_blocker: null,
      reveal_eligible: true,
      presentations: [
        { ...sample('a', 1, [detectedRow('oa')]), blotter_locked: true },
        { ...sample('b', 2, [detectedRow('ob')]), blotter_locked: true },
        { ...sample('c', 3, [detectedRow('oc')]), blotter_locked: true },
      ],
    })

  test('ranks the detected samples, ties included, before the reveal is offered', async ({
    page,
  }) => {
    const { sent, record } = recorder()
    await mockApi(page, {
      ...bootstrapRoutes(),
      '/calibration/enrollments/enr1': ready(),
      '/calibration/sessions/sess1/rankings': (route: Route) =>
        route.request().method() === 'POST' ? record('rank')(route) : json(route, []),
    })

    await page.goto('/calibration')
    await expect(page.getByText(/rank the samples you could smell/i)).toBeVisible()
    await expect(page.getByRole('button', { name: 'Reveal completed baseline' })).toHaveCount(0)

    const places = page.getByRole('combobox')
    await places.nth(0).selectOption('1')
    await places.nth(1).selectOption('1')
    await places.nth(2).selectOption('2')
    await expect(page.getByRole('alert')).toContainText(/places must run/i)
    await places.nth(2).selectOption('3')
    await expectNoViolations(page)
    await page.getByRole('button', { name: 'Save ranking' }).click()

    await expect.poll(() => sent.length).toBe(1)
    expect(sent[0].body).toEqual({
      stage: 'BLOTTER',
      response_status: 'completed',
      entries: [
        { presentation_id: 'a', rank_position: 1 },
        { presentation_id: 'b', rank_position: 1 },
        { presentation_id: 'c', rank_position: 3 },
      ],
    })
    await expect(page.getByRole('button', { name: 'Reveal completed baseline' })).toBeVisible()
  })

  test('raises a problem flag against a sample', async ({ page }) => {
    const { sent, record } = recorder()
    await mockApi(page, {
      ...bootstrapRoutes(),
      '/calibration/enrollments/enr1': enrollment({}),
      '/calibration/quality-flags': record('flag', { id: 'f1' }),
    })

    await page.goto('/calibration')
    await page.getByRole('button', { name: 'Flag a problem' }).click()
    await page.getByLabel('What is it about?').selectOption('samp1')
    await page.getByLabel('What happened?').selectOption('sample_spill')
    await expectNoViolations(page)
    await page.getByRole('button', { name: 'Send' }).click()

    await expect.poll(() => sent.length).toBe(1)
    expect(sent[0].body).toMatchObject({
      action: 'raised',
      source: 'evaluator',
      target_type: 'presentation',
      target_id: 'samp1',
      code: 'sample_spill',
    })
    await expect(page.getByText(/problem is noted/i)).toBeVisible()
  })
})
