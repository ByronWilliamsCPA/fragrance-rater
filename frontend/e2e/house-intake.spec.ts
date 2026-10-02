import { test, expect, type Page, type Route } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { bootstrapRoutes, managerAccess, mockApi } from './support/mock-api'
import type { HouseAccess, HouseSubmission, ReviewContext } from '../src/api/houseIntake'
import { emptyPayload } from '../src/api/houseIntake'

const axeTags = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']
const houseAccess = {
  username: 'maison-rep',
  house: 'Maison A',
  manager: false,
} satisfies HouseAccess

const draft: HouseSubmission = {
  id: 'sub-1',
  house: 'Maison A',
  status: 'draft',
  created_by: 'maison-rep',
  created_at: '2026-10-01T10:00:00',
  updated_at: '2026-10-01T10:00:00',
  submitted_at: null,
  submitted_by: null,
  permission_state: null,
  supersedes_id: null,
  superseded_by_id: null,
  payload: { ...emptyPayload(), fragrance_name: 'Cèdre Nocturne' },
  review_status: null,
  reviewed_at: null,
  review_note: null,
  reviewed_by: null,
  fragrance_id: null,
  source_snapshot_id: null,
}

async function openForm(page: Page) {
  const requested: string[] = []
  page.on('request', (request) => requested.push(new URL(request.url()).pathname))
  await mockApi(page, {
    '/house-intake/access': houseAccess,
    '/house-intake/submissions': async (route: Route) => {
      await route.fulfill({
        status: route.request().method() === 'POST' ? 201 : 200,
        contentType: 'application/json',
        body: JSON.stringify(route.request().method() === 'POST' ? draft : []),
      })
    },
  })
  await page.goto('/house')
  await page.getByRole('button', { name: 'Describe a new fragrance' }).click()
  await expect(page.getByRole('heading', { name: 'Tell us about a fragrance' })).toBeVisible()
  return requested
}

for (const colorScheme of ['light', 'dark'] as const) {
  test.describe(`House intake form (WCAG 2.2 AA, ${colorScheme} theme)`, () => {
    test.use({ colorScheme })

    test('the empty form has no automatically detectable violations', async ({ page }) => {
      await openForm(page)
      const results = await new AxeBuilder({ page }).withTags(axeTags).analyze()
      expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([])
    })

    test('the form with errors and entries has no violations', async ({ page }) => {
      await openForm(page)
      await page.getByLabel('Add top note').fill('Bergamot, Pink pepper')
      await page.getByLabel('Add top note').press('Enter')
      await page.getByRole('button', { name: 'Review and submit' }).click()
      await expect(page.getByRole('alert')).toBeFocused()
      const results = await new AxeBuilder({ page }).withTags(axeTags).analyze()
      expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([])
    })
  })
}

test('a house account never requests household endpoints', async ({ page }) => {
  const requested = await openForm(page)
  expect(requested.filter((path) => /\/(reviewers|calibration|evaluations)\b/.test(path))).toEqual(
    []
  )
})

const pending: HouseSubmission = {
  ...draft,
  status: 'submitted',
  submitted_at: '2026-10-02T09:00:00',
  submitted_by: 'maison-rep',
  permission_state: 'retain_and_train',
  review_status: 'pending',
  payload: {
    ...draft.payload,
    concentration: 'EDP',
    launch_year: 2019,
    marketed_for: 'Unisex',
    perfumers: ['Ana Ruiz'],
  },
}

const reviewContext: ReviewContext = {
  submission: pending,
  proposed: {
    name: 'Cèdre Nocturne',
    brand: 'Maison A',
    concentration: 'EDP',
    launch_year: 2019,
    gender_target: 'Unisex',
  },
  candidates: [
    {
      id: 'f-1',
      name: 'Cèdre Nocturne',
      brand: 'Maison A',
      concentration: 'Eau de Parfum',
      version_key: 'legacy',
      launch_year: 2018,
      gender_target: 'Unisex',
      primary_family: 'Woody',
      subfamily: 'Dry Woods',
      comparison: {
        name: 'same',
        brand: 'same',
        concentration: 'same',
        launch_year: 'differs',
        gender_target: 'same',
      },
    },
  ],
}

async function openReview(page: Page) {
  await mockApi(page, {
    ...bootstrapRoutes(managerAccess),
    '/house-intake/access': { username: 'manager', house: null, manager: true },
    '/house-intake/submissions': [pending],
    '/house-intake/submissions/sub-1/review': reviewContext,
  })
  await page.goto('/house')
  await page.getByRole('button', { name: 'Review Cèdre Nocturne' }).click()
  await page.getByLabel(/Maison A · Cèdre Nocturne · Eau de Parfum/).check()
  await expect(page.getByRole('table')).toBeVisible()
}

for (const colorScheme of ['light', 'dark'] as const) {
  test.describe(`House review (WCAG 2.2 AA, ${colorScheme} theme)`, () => {
    test.use({ colorScheme })

    test('the review screen has no automatically detectable violations', async ({ page }) => {
      await openReview(page)
      const results = await new AxeBuilder({ page }).withTags(axeTags).analyze()
      expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([])
    })
  })
}
