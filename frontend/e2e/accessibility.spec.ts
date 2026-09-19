import { test, expect, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import {
  mockApi,
  bootstrapRoutes,
  managerAccess,
  fragranceCatalog,
  enrollmentFixture,
  recommendationRunFixture,
} from './support/mock-api'

// #ASSUME: data-integrity: each routeChecks entry's `heading` was verified against the
// real page component source (not the plan's guessed text) before this test was written.
// Corrections vs. the plan's guessed text (verified headed against the real rendered page,
// see docs/superpowers/plans/2026-09-18-frontend-testing-and-docs.md for the original brief):
// - '/calibration' and '/recommendations' render their plan-guessed heading only after a
//   user interaction (selecting an assignment/sample, or starting a recommendation run),
//   so `populate` drives that interaction before the heading assertion.
// - '/about' has no heading containing the word "about" anywhere in AboutPage.tsx; the
//   plan's `/about/i` regex never matches. Uses the page's real first heading instead.
// #VERIFY: if these page components' headings or default-load behavior change, update
// both the `heading` and `populate` fields together.
const routeChecks: {
  path: string
  heading: string | RegExp
  populate?: (page: Page) => Promise<void>
}[] = [
  { path: '/', heading: 'Your scent journal' },
  {
    path: '/calibration',
    heading: 'ABC-123',
    populate: async (page) => {
      await page.getByLabel('Evaluator and program').selectOption('enr1')
      await page.getByRole('button', { name: 'ABC-123' }).click()
    },
  },
  { path: '/ratings', heading: 'Ordinary encounters' },
  {
    path: '/recommendations',
    heading: 'Signature',
    populate: async (page) => {
      await page.getByLabel('Evaluator').selectOption('r1')
      await page.getByRole('button', { name: 'Get recommendations' }).click()
    },
  },
  { path: '/about', heading: 'How this project learns your taste' },
  { path: '/programs', heading: 'Program setup' },
]

test.describe('Accessibility (WCAG 2.1 AA)', () => {
  for (const { path, heading, populate } of routeChecks) {
    test(`${path} has no automatically detectable violations`, async ({ page }) => {
      await mockApi(page, {
        ...bootstrapRoutes(managerAccess),
        [`/calibration/enrollments/enr1`]: enrollmentFixture(false),
        '/fragrances': fragranceCatalog,
        '/evaluations': [],
        '/recommendation-measurement/runs': recommendationRunFixture(),
      })

      await page.goto(path)
      await expect(page.getByRole('heading', { name: 'Fragrance Rater' })).toBeVisible()

      if (populate) await populate(page)

      await expect(page.getByRole('heading', { name: heading })).toBeVisible()

      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
        .analyze()

      expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([])
    })
  }
})

test.describe('Keyboard operability', () => {
  test('blind calibration is fully operable via keyboard', async ({ page }) => {
    await mockApi(page, {
      ...bootstrapRoutes(),
      '/calibration/enrollments/enr1': enrollmentFixture(false),
    })

    await page.goto('/calibration')
    // Wait for the loading shell to resolve before tabbing; tabbing while
    // <body> is still the only focusable element (LoadingState has no focusable
    // content) silently no-ops and desyncs the press count from the real page.
    await expect(page.getByLabel('Evaluator and program')).toBeVisible()

    // #ASSUME: timing dependencies: this Tab sequence was verified by running the test
    // headed against the real rendered page rather than guessed; it depends on the DOM
    // order of focusable elements before the assignment select:
    // 1) skip link, 2) "Home" nav link, 3) "Calibration" nav link (current page, still
    // focusable), 4) "Recommendations" nav link, 5) "My Ratings" nav link, then the
    // "Evaluator and program" <select>. Selecting the only option and pressing Enter/
    // Space on the resulting sample button reaches the blind observation form.
    // #VERIFY: re-run headed if AppShell's nav items or their order change.
    for (let i = 0; i < 6; i++) await page.keyboard.press('Tab')
    await expect(page.getByLabel('Evaluator and program')).toBeFocused()
    await page.keyboard.press('ArrowDown')
    await expect(page.getByRole('heading', { name: 'Sessions' })).toBeVisible()

    await page.keyboard.press('Tab')
    await expect(page.getByRole('button', { name: 'ABC-123' })).toBeFocused()
    await page.keyboard.press('Enter')

    await expect(page.getByRole('heading', { name: 'ABC-123' })).toBeVisible()
    await expect(page.getByText('Blind observation')).toBeVisible()
  })
})
