import { expect, test } from '@playwright/test'
import { MANAGER, freshRecorder, signIn } from './support/stack'

/*
 * The manager journey through the real stack (P5): sign in as a manager, build
 * a program draft, survive an interrupted request, and see that a non-manager
 * is kept out. The manager role comes from the backend's allow-list, behind the
 * edge's verified identity, not from anything the browser claims.
 */
test.describe('Manager journey', () => {
  test('a manager creates a program draft, recovering from an interrupted request', async ({
    page,
  }) => {
    await signIn(page.context(), MANAGER)
    const name = `Stack program ${Date.now()}`

    await page.goto('/programs')
    await expect(page.getByRole('heading', { name: 'Program setup' })).toBeVisible()

    // The first attempt fails at the network; the form must keep what was typed.
    let attempts = 0
    await page.route('**/api/v1/calibration/programs', (route) => {
      if (route.request().method() !== 'POST') return route.continue()
      attempts += 1
      return attempts === 1 ? route.abort('connectionreset') : route.continue()
    })
    await page.getByLabel('Name', { exact: true }).fill(name)
    await page.getByLabel('Version').fill('1')
    await page.getByRole('button', { name: 'Create draft' }).click()

    await expect(page.getByText(/could not be reached/i)).toBeVisible()
    await expect(page.getByLabel('Name', { exact: true })).toHaveValue(name)

    await page.getByRole('button', { name: 'Create draft' }).click()
    await expect(page.getByText('Draft created.')).toBeVisible()
    expect(attempts).toBe(2)

    // The draft is real: it is offered again after a reload.
    await page.reload()
    await expect(page.getByRole('option', { name: new RegExp(name) })).toBeAttached()
  })

  test('a non-manager is kept off the manager screen', async ({ page }) => {
    await signIn(page.context(), freshRecorder('outsider'))

    await page.goto('/programs')

    await expect(page).not.toHaveURL(/\/programs$/)
    await expect(page.getByRole('heading', { name: 'Program setup' })).toHaveCount(0)
  })

  test('a manager who is not signed in is sent no further than the edge', async ({ page }) => {
    // No session cookie: the edge challenges every API call.
    const statuses: number[] = []
    page.on('response', (response) => {
      if (response.url().includes('/api/v1/')) statuses.push(response.status())
    })

    await page.goto('/programs')
    await page.waitForLoadState('networkidle')

    expect(statuses.length).toBeGreaterThan(0)
    expect(statuses.every((status) => status === 401)).toBe(true)
    await expect(page.getByRole('heading', { name: 'Program setup' })).toHaveCount(0)
  })
})
