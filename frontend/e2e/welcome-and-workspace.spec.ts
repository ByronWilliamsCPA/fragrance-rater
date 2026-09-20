import { test, expect, type Route } from '@playwright/test'
import { bootstrapRoutes, enrollmentFixture, managerAccess, mockApi } from './support/mock-api'

// #ASSUME: data-integrity: bootstrapRoutes()'s fixed '/calibration/enrollments'
// fixture always seeds one assignment (id 'enr1'), regardless of which access
// fixture is passed, so every test here also mocks
// '/calibration/enrollments/enr1' to avoid an unmocked-501 request, matching
// the convention in blind-calibration.spec.ts and manager-authorization.spec.ts.
function withEnrollment(overrides: Parameters<typeof bootstrapRoutes>[0] = undefined) {
  return {
    ...bootstrapRoutes(overrides),
    '/calibration/enrollments/enr1': (route: Route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(enrollmentFixture(false)),
      }),
  }
}

test.describe('Welcome and workspace', () => {
  test('continues from welcome into a role-aware workspace', async ({ page }) => {
    await mockApi(page, withEnrollment())

    await page.goto('/')
    await expect(
      page.getByText('Learn your fragrance taste by measuring what you actually respond to.')
    ).toBeVisible()
    await page.getByRole('button', { name: 'Continue' }).click()

    await expect(page).toHaveURL('/home')
    await expect(page.getByRole('button', { name: 'Log an encounter' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Manage programs' })).toHaveCount(0)
  })

  test('offers program management from the workspace to a manager', async ({ page }) => {
    await mockApi(page, withEnrollment(managerAccess))

    await page.goto('/home')

    await expect(page.getByRole('button', { name: 'Manage programs' })).toBeVisible()
  })

  test('deep-links a calibration row directly into its assignment', async ({ page }) => {
    await mockApi(page, withEnrollment())

    await page.goto('/home')
    await page.getByRole('button', { name: 'Continue calibration' }).click()

    await expect(page).toHaveURL('/calibration?assignment=enr1')
    await expect(page.getByLabel('Evaluator and program')).toHaveValue('enr1')
    await expect(page.getByRole('button', { name: 'ABC-123' })).toBeVisible()
  })
})
