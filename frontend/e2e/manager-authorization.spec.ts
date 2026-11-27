import { test, expect, type Route } from '@playwright/test'
import { mockApi, bootstrapRoutes, participantAccess, managerAccess } from './support/mock-api'

// #ASSUME: data-integrity: the redirect and route-guard mechanism below were
// verified against the real App.tsx and routing/routes.ts source (not the
// plan's guessed code):
// - navigationItems in routes.ts marks '/programs' and '/programs/advanced'
//   `managerOnly: true`, but that flag is never read at render time. The
//   actual guard is a useEffect in App.tsx that runs once appData has loaded
//   without error: if `(route === 'programs' || route === 'programsAdvanced')
//   && !appData.capabilities.canManagePrograms`, it
//   calls `navigate('calibration', true)`, which pushes history state to
//   `/calibration`. The plan's brief guessed `/calibration` as the redirect
//   target and that guess was correct.
// - capabilitiesFor() (api/types.ts) sets `canManagePrograms: access.manager`
//   directly, so participantAccess (`manager: false`) and managerAccess
//   (`manager: true`) do produce the differing authorization outcome the
//   guard reads.
// - App.tsx only renders <FamilyPilotPage> (/programs) or <ProgramSetupPage>
//   (/programs/advanced) when the route matches and
//   `appData.capabilities.canManagePrograms` holds, so a non-manager who is
//   (hypothetically) not redirected still never sees either heading; the
//   heading-count-0 assertions cover both the redirect and the render guard.
// #VERIFY: re-check both App.tsx's useEffect condition and capabilitiesFor()
// if manager gating grows a role beyond the current boolean `manager` flag.
test.describe('Manager route authorization', () => {
  for (const path of ['/programs', '/programs/advanced']) {
    test(`redirects a non-manager away from ${path}`, async ({ page }) => {
      await mockApi(page, bootstrapRoutes(participantAccess))

      await page.goto(path)

      await expect(page).toHaveURL('/calibration')
      await expect(page.getByRole('heading', { name: 'Family pilot' })).toHaveCount(0)
      await expect(page.getByRole('heading', { name: 'Advanced program setup' })).toHaveCount(0)
    })
  }

  test('allows a manager to reach the Family pilot screen at /programs', async ({ page }) => {
    await mockApi(page, bootstrapRoutes(managerAccess))

    await page.goto('/programs')

    await expect(page).toHaveURL('/programs')
    await expect(page.getByRole('heading', { name: 'Family pilot' })).toBeVisible()
  })

  test('allows a manager to reach Advanced setup at /programs/advanced', async ({ page }) => {
    await mockApi(page, bootstrapRoutes(managerAccess))

    await page.goto('/programs/advanced')

    await expect(page).toHaveURL('/programs/advanced')
    await expect(page.getByRole('heading', { name: 'Advanced program setup' })).toBeVisible()
  })

  test('the Family pilot screen links to Advanced setup', async ({ page }) => {
    await mockApi(page, bootstrapRoutes(managerAccess))

    await page.goto('/programs')
    await page
      .getByRole('link', { name: 'Advanced setup (not needed for the family pilot)' })
      .click()

    await expect(page).toHaveURL('/programs/advanced')
    await expect(page.getByRole('heading', { name: 'Advanced program setup' })).toBeVisible()
  })

  // #ASSUME: data-integrity: the activation control and 403 handling below
  // were verified against the real ProgramSetupPage.tsx and api/client.ts
  // source, and differ from the plan's brief in several ways:
  // - The activation moved with the full page to /programs/advanced. The
  //   activation button only renders once a program is selected from the
  //   "Program" <select> AND `selectedProgram.status === 'draft'`, and stays
  //   disabled until at least one program member has loaded. bootstrapRoutes'
  //   default program fixture (`{ id: 'p1', name: 'Baseline', version: '1' }`)
  //   has no `status` field, so `status === 'draft'` would be false and the
  //   button would never appear; this test overrides `/calibration/programs`
  //   with a fixture that includes `status: 'draft'`, and adds a
  //   `/calibration/programs/p1/members` fixture with one member so the
  //   button becomes enabled, matching how CalibrationPage/RecommendationsPage
  //   required prior selection before their target elements appeared (Tasks
  //   5 and 7).
  // - The button's real accessible name is "Activate and lock definition"
  //   (via ConfirmAction's `actionLabel`), not a generic /activate/i regex
  //   match. ConfirmAction is a two-step control: the first click reveals a
  //   confirmation group with a second button labeled "Confirm activation"
  //   (`confirmLabel`); only that second click invokes the actual
  //   `POST /calibration/programs/p1/activate` call. The brief's single
  //   `.first().click()` on an `/activate/i` button would have hit the first
  //   "Activate and lock definition" button and never triggered the API call
  //   this test exists to exercise.
  // - `requestErrorMessage()` (api/client.ts) returns the literal string
  //   "You do not have access to this action." only when a 403 response's
  //   body has no non-empty string `detail` field; if `detail` is a non-empty
  //   string (as the brief's `{ detail: 'forbidden' }` body would produce),
  //   that string is surfaced verbatim instead ("forbidden"), never the
  //   generic 403 message. The mock body below is `{}` so the 403 branch is
  //   actually reached. This is a real, working degradation path (the error
  //   is caught in useTask.run and rendered via FeedbackBanner's
  //   `role="alert"` paragraph), not a missing app capability.
  // #VERIFY: re-check ConfirmAction's action/confirm label wiring and
  // requestErrorMessage()'s detail-string branch if either changes.
  test('degrades gracefully when the API rejects a manager action with 403', async ({ page }) => {
    await mockApi(page, {
      ...bootstrapRoutes(managerAccess),
      '/calibration/programs': [{ id: 'p1', name: 'Baseline', version: '1', status: 'draft' }],
      '/calibration/programs/p1/members': [
        {
          id: 'mem1',
          fragrance_id: 'f1',
          fragrance_name: 'Signature',
          fragrance_brand: 'House',
          concentration: 'EDP',
          version_key: '1',
          role: 'UNIVERSAL_BASELINE',
          repeat_of_id: null,
          group_name: 'Baseline',
          identity_evidence: 'Scanned barcode confirms version.',
          fragella: null,
        },
      ],
      '/calibration/programs/p1/activate': (route: Route) =>
        route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({}) }),
    })

    await page.goto('/programs/advanced')
    await page.getByLabel('Program').selectOption('p1')
    await page.getByRole('button', { name: 'Activate and lock definition' }).click()
    // The in-page confirm names what activation locks before anything is sent.
    await expect(page.getByText(/is permanent and cannot be undone/)).toBeVisible()
    await page.getByRole('button', { name: 'Confirm activation' }).click()

    await expect(page.getByText('You do not have access to this action.')).toBeVisible()
  })
})
