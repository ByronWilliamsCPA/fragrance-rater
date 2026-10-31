import { expect, test, type Page } from '@playwright/test'
import { freshRecorder, seedAssignment, signIn, type Seeded } from './support/stack'

/*
 * Participant journeys through a real browser, the forward-auth stub, the real
 * backend and a real PostgreSQL (R13, architecture review G-01 and F-10). The
 * mocked tier proves the frontend renders what it is told; these prove the
 * whole path, including what the server actually enforces. Each journey uses
 * its own recorder so the entry routing never has to choose between assignments.
 */
async function startGuided(page: Page, label: string): Promise<Seeded> {
  const recorder = freshRecorder(label)
  const seeded = await seedAssignment(recorder)
  await signIn(page.context(), recorder)
  await page.goto('/calibration')
  return seeded
}

async function pastConsent(page: Page) {
  await expect(page.getByRole('heading', { name: 'Before you begin' })).toBeVisible()
  await page.getByRole('button', { name: 'Continue to the samples' }).click()
  await expect(page.getByRole('heading', { name: 'Guided calibration' })).toBeVisible()
}

async function finalizeSkinPlan(page: Page) {
  await page.getByRole('button', { name: 'Finalize skin-test plan' }).click()
  await page.getByRole('button', { name: 'Confirm final plan' }).click()
  await expect(page.getByRole('heading', { name: /Blind code/ })).toBeVisible()
}

async function saveDetectedObservation(page: Page) {
  await page.getByLabel('Detected').selectOption('yes')
  await page.getByRole('button', { name: 'Save observation' }).click()
}

test.describe('Blind calibration, end to end', () => {
  test('a recorder takes a sample from consent to reveal, and identity appears only at the end', async ({
    page,
  }) => {
    const seeded = await startGuided(page, 'blind')

    // The first screen of a session: consent wording, never a prerequisite.
    await pastConsent(page)
    await expect(page.getByText(seeded.fragranceName)).toHaveCount(0)

    await finalizeSkinPlan(page)
    // Blind: the sample is a code, not a name.
    await expect(page.getByText(seeded.fragranceName)).toHaveCount(0)
    await expect(page.getByText(seeded.fragranceBrand)).toHaveCount(0)

    await saveDetectedObservation(page)
    await expect(page.getByText(/observation saved/i)).toBeVisible()

    await page.getByRole('button', { name: /lock blotter responses/i }).click()
    await page.getByRole('button', { name: /confirm blotter lock/i }).click()

    // One sample means nothing to rank; the step says so and moves on.
    await expect(page.getByText(/nothing to rank/i)).toBeVisible()
    await page.getByRole('button', { name: 'Continue' }).click()

    await expect(page.getByText(seeded.fragranceName)).toHaveCount(0)
    await page.getByRole('button', { name: 'Reveal completed baseline' }).click()
    await page.getByRole('button', { name: 'Confirm reveal' }).click()

    await expect(page.getByText(/reveal complete/i)).toBeVisible()
    await expect(page.getByText(new RegExp(seeded.fragranceName))).toBeVisible()
  })

  test('an interrupted save keeps the form, says so plainly, and succeeds on retry', async ({
    page,
  }) => {
    await startGuided(page, 'retry')
    await pastConsent(page)
    await finalizeSkinPlan(page)

    // The first attempt to save fails at the network, as a flaky connection would.
    let attempts = 0
    await page.route('**/api/v1/calibration/presentations/*/observations', (route) => {
      attempts += 1
      return attempts === 1 ? route.abort('connectionreset') : route.continue()
    })
    await page.getByLabel('Detected').selectOption('yes')
    await page.getByRole('button', { name: 'Save observation' }).click()

    await expect(page.getByText(/could not be reached/i)).toBeVisible()
    await expect(page.getByLabel('Detected')).toHaveValue('yes')

    await page.getByRole('button', { name: 'Save observation' }).click()
    await expect(page.getByText(/observation saved/i)).toBeVisible()
    expect(attempts).toBe(2)

    // The saved row really is in the database: it survives a reload.
    await page.reload()
    await expect(page.getByRole('heading', { name: /Blind code/ })).toBeVisible()
    await expect(page.getByRole('table')).toContainText('Blotter')
  })

  test('a stage that was locked stays locked after a reload', async ({ page }) => {
    await startGuided(page, 'lock')
    await pastConsent(page)
    await finalizeSkinPlan(page)
    await saveDetectedObservation(page)
    await expect(page.getByText(/observation saved/i)).toBeVisible()
    await page.getByRole('button', { name: /lock blotter responses/i }).click()
    await page.getByRole('button', { name: /confirm blotter lock/i }).click()
    await expect(page.getByText(/nothing to rank/i)).toBeVisible()

    await page.reload()

    // The wizard resumes where the server says the evaluator is, not at the start.
    await expect(page.getByText(/nothing to rank|Reveal completed baseline/)).toBeVisible()
    await expect(page.getByRole('button', { name: 'Finalize skin-test plan' })).toHaveCount(0)
  })
})

test.describe('Other participant journeys', () => {
  test('the home page shows an evaluator their assignment without any identifiers', async ({
    page,
  }) => {
    const recorder = freshRecorder('home')
    const seeded = await seedAssignment(recorder)
    await signIn(page.context(), recorder)

    await page.goto('/home')

    await expect(page.getByRole('heading', { name: 'Workspace' })).toBeVisible()
    await expect(page.getByText(seeded.programName)).toBeVisible()
    await expect(page.getByText(seeded.fragranceName)).toHaveCount(0)
  })

  test('an evaluator logs an ordinary encounter and finds it in their history', async ({
    page,
  }) => {
    const recorder = freshRecorder('encounter')
    const seeded = await seedAssignment(recorder)
    await signIn(page.context(), recorder)

    await page.goto('/ratings')
    await expect(page.getByRole('heading', { name: 'Log an encounter' })).toBeVisible()
    await page.getByLabel('Evaluator').first().selectOption({ label: seeded.reviewerName })
    await page.getByLabel('Search fragrances').fill(seeded.fragranceName)
    await page.getByRole('button', { name: 'Search catalog' }).click()
    await expect(
      page.getByRole('option', { name: new RegExp(seeded.fragranceName) })
    ).toBeAttached()
    await page.getByLabel('Fragrance version').selectOption({ index: 1 })
    await page.getByLabel('Rating (1–5)').fill('4')
    await page.getByRole('button', { name: 'Save new encounter' }).click()
    await expect(page.getByText('New encounter saved.')).toBeVisible()

    // The form clears after a save; choosing the evaluator again shows their history.
    await page.getByLabel('Evaluator').first().selectOption({ label: seeded.reviewerName })
    await expect(page.getByText(`${seeded.fragranceName} · 4/5`)).toBeVisible()

    // It is in the database, not just on the page.
    await page.reload()
    await page.getByLabel('Evaluator').first().selectOption({ label: seeded.reviewerName })
    await expect(page.getByText(`${seeded.fragranceName} · 4/5`)).toBeVisible()
  })
})
