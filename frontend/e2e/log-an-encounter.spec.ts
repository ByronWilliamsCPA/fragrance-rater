import { test, expect, type Route } from '@playwright/test'
import { mockApi, bootstrapRoutes, fragranceCatalog } from './support/mock-api'

// #ASSUME: data-integrity: the heading, field labels, button text, and
// /evaluations request/response shapes below were verified against the real
// RatingsPage.tsx source (not the plan's guessed text) before this spec was
// written; they all matched the plan's assumptions, so no adjustments were
// needed.
// #VERIFY: if RatingsPage.tsx's labels, button text, or /evaluations
// contract change, update this spec alongside it.
test.describe('Ordinary entry (journal encounters)', () => {
  test('records a journal encounter', async ({ page }) => {
    let savedEncounter: Record<string, unknown> | null = null

    await mockApi(page, {
      ...bootstrapRoutes(),
      '/fragrances': fragranceCatalog,
      '/evaluations': (route: Route) => {
        if (route.request().method() === 'GET') {
          return route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(savedEncounter ? [savedEncounter] : []),
          })
        }
        const body = route.request().postDataJSON()
        savedEncounter = { id: 'e1', ...body }
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(savedEncounter) })
      },
    })

    await page.goto('/ratings')
    await expect(page.getByRole('heading', { name: 'Log an encounter' })).toBeVisible()

    // #ASSUME: data-integrity: the "Worn by" select on this same form also lists
    // every reviewer as an option (including "Evaluator One" from this fixture),
    // and a <label> wrapping a <select> exposes an accessible name that includes
    // its options' rendered text in real browsers (verified against Chromium; not
    // an artifact of jsdom, where the unit tests' equivalent query does not need
    // this scoping). An unscoped getByLabel('Evaluator') therefore matches both
    // selects; .first() picks the Evaluator select, which precedes Worn by in DOM
    // order. #VERIFY: re-check if RatingsPage.tsx's field order changes.
    await page.getByLabel('Evaluator').first().selectOption('r1')
    await page.getByLabel('Search fragrances').fill('Signature')
    await page.getByRole('button', { name: 'Search catalog' }).click()
    // Search results populate the "Fragrance version" native <select> as
    // <option> elements, matching the plan's assumption. But a closed native
    // select's <option> nodes are never reported as visible by Playwright
    // (no rendered bounding box until the dropdown is open), so toBeVisible()
    // always times out here even though the option exists; assert attachment
    // instead, which is what this step is actually verifying.
    await expect(page.getByRole('option', { name: /Signature/ })).toBeAttached()

    await page.getByLabel('Fragrance version').selectOption('f1')
    await page.getByLabel('Rating (1–5)').fill('4')
    await page.getByRole('button', { name: 'Save new encounter' }).click()

    // The "Encounter history" heading renders unconditionally, even before any
    // save; assert on the saved encounter's rendered content instead so this
    // step actually verifies the save round-tripped through /evaluations.
    await expect(page.getByRole('heading', { name: 'Encounter history' })).toBeVisible()
    await expect(page.getByText('Signature · 4/5')).toBeVisible()
  })
})
