import { test, expect, type Page, type Route } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { mockApi } from './support/mock-api'
import type { HouseAccess, HouseSubmission } from '../src/api/houseIntake'
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
