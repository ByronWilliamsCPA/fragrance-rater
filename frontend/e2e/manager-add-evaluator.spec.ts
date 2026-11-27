import { test, expect, type Route } from '@playwright/test'
import { mockApi, bootstrapRoutes, managerAccess } from './support/mock-api'

test.describe('Manager adds an evaluator', () => {
  test('a new evaluator appears in the Enrollment dropdown and is preselected', async ({
    page,
  }) => {
    const reviewers = [{ id: 'r1', name: 'Evaluator One' }]
    let postedBody: unknown = null

    await mockApi(page, {
      ...bootstrapRoutes(managerAccess),
      '/reviewers': async (route: Route) => {
        if (route.request().method() === 'POST') {
          postedBody = route.request().postDataJSON()
          const created = { id: 'r2', name: 'Test Evaluator' }
          reviewers.push(created)
          await route.fulfill({
            status: 201,
            contentType: 'application/json',
            body: JSON.stringify({
              ...created,
              created_at: '2026-11-26T00:00:00',
              evaluation_count: 0,
            }),
          })
          return
        }
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(reviewers),
        })
      },
    })

    await page.goto('/programs')
    await page.getByLabel('Evaluator name').fill('Test Evaluator')
    await page.getByRole('button', { name: 'Add evaluator' }).click()

    await expect(page.getByRole('status')).toContainText(
      'Evaluator added. They can now be enrolled below.'
    )
    expect(postedBody).toEqual({ name: 'Test Evaluator' })
    await expect(
      page.getByRole('combobox', { name: 'Evaluator', exact: true }).first()
    ).toHaveValue('r2')
  })
})
