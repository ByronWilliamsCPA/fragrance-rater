import { test, expect, type Page, type Route } from '@playwright/test'
import { mockApi, bootstrapRoutes, familyPilotRoutes, managerAccess } from './support/mock-api'

/** A /reviewers mock that accepts one POST and then lists the new evaluator. */
function reviewerRoutes(
  reviewers: { id: string; name: string }[],
  onPost: (body: unknown) => void
) {
  return {
    '/reviewers': async (route: Route) => {
      if (route.request().method() === 'POST') {
        onPost(route.request().postDataJSON())
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
  }
}

async function addEvaluator(page: Page) {
  await page.getByLabel('Evaluator name').fill('Test Evaluator')
  await page.getByRole('button', { name: 'Add evaluator' }).click()
  await expect(page.getByRole('status')).toContainText(
    'Evaluator added. They can now be enrolled below.'
  )
}

test.describe('Manager adds an evaluator', () => {
  test('a new evaluator appears in the Family pilot list, not yet enrolled', async ({ page }) => {
    const reviewers = [{ id: 'r1', name: 'Evaluator One' }]
    let postedBody: unknown = null

    await mockApi(page, {
      ...bootstrapRoutes(managerAccess),
      ...familyPilotRoutes(),
      ...reviewerRoutes(reviewers, (body) => (postedBody = body)),
    })

    await page.goto('/programs')
    await addEvaluator(page)

    expect(postedBody).toEqual({ name: 'Test Evaluator' })
    const row = page.getByRole('listitem').filter({ hasText: 'Test Evaluator' })
    await expect(row).toContainText('Not enrolled')
    await expect(row.getByRole('button', { name: 'Enroll Test Evaluator' })).toBeEnabled()
  })

  test('on Advanced setup the new evaluator is preselected in the Enrollment dropdown', async ({
    page,
  }) => {
    const reviewers = [{ id: 'r1', name: 'Evaluator One' }]
    let postedBody: unknown = null

    await mockApi(page, {
      ...bootstrapRoutes(managerAccess),
      ...reviewerRoutes(reviewers, (body) => (postedBody = body)),
    })

    await page.goto('/programs/advanced')
    await addEvaluator(page)

    expect(postedBody).toEqual({ name: 'Test Evaluator' })
    await expect(
      page.getByRole('combobox', { name: 'Evaluator', exact: true }).first()
    ).toHaveValue('r2')
  })
})
