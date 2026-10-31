import { expect, test } from '@playwright/test'
import {
  bootstrapRoutes,
  enrollmentFixture,
  fragranceCatalog,
  managerAccess,
  mockApi,
  recommendationRunFixture,
} from './support/mock-api'

/*
 * WCAG 1.4.10 Reflow (architecture review F-13): at a 360 px viewport nothing
 * forces the page itself to scroll sideways. A table inside its own scroll
 * region is allowed (the observation log needs two dimensions); the document
 * is not. Evaluators use this on a phone, at a bench.
 */
const WIDTH = 360

const routes: { path: string; heading: string | RegExp }[] = [
  { path: '/', heading: 'Welcome' },
  { path: '/home', heading: 'Workspace' },
  { path: '/calibration?assignment=enr1', heading: 'Sessions' },
  { path: '/calibration/protocol', heading: 'Calibration protocol' },
  { path: '/ratings', heading: 'Log an encounter' },
  { path: '/recommendations', heading: 'Recommendations' },
  { path: '/about', heading: 'How this project learns your taste' },
  { path: '/evidence', heading: 'Why better fragrance discovery matters' },
  { path: '/programs', heading: 'Program setup' },
]

test.use({ viewport: { width: WIDTH, height: 800 } })

for (const { path, heading } of routes) {
  test(`${path} does not scroll sideways at ${WIDTH}px`, async ({ page }) => {
    await mockApi(page, {
      ...bootstrapRoutes(managerAccess),
      '/calibration/enrollments/enr1': enrollmentFixture(false),
      '/fragrances': fragranceCatalog,
      '/evaluations': [],
      '/recommendation-measurement/runs': recommendationRunFixture(),
    })

    await page.goto(path)
    await expect(page.getByRole('heading', { name: heading }).first()).toBeVisible()

    const overflow = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }))
    expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth)
  })
}

test('the guided session screen reflows at 360px too', async ({ page }) => {
  await mockApi(page, {
    ...bootstrapRoutes(),
    '/calibration/enrollments/enr1': enrollmentFixture(false),
  })

  await page.goto('/calibration?assignment=enr1')
  await page.getByRole('button', { name: 'ABC-123' }).click()
  await expect(page.getByRole('heading', { name: /ABC-123/ })).toBeVisible()

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth
  )
  expect(overflow).toBeLessThanOrEqual(0)
})

test('the measurement does detect a page that scrolls sideways', async ({ page }) => {
  await mockApi(page, {
    ...bootstrapRoutes(),
    '/calibration/enrollments/enr1': enrollmentFixture(false),
  })
  await page.goto('/about')
  await page.evaluate(() => {
    const wide = document.createElement('div')
    wide.style.width = '900px'
    wide.style.height = '1px'
    document.body.appendChild(wide)
  })

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth
  )

  expect(overflow).toBeGreaterThan(0)
})
