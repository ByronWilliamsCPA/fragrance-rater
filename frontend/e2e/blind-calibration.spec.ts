import { test, expect, type Route } from '@playwright/test'
import { mockApi, bootstrapRoutes, enrollmentFixture } from './support/mock-api'

// #ASSUME: data-integrity: the interaction sequence and text assertions below were
// verified against the real CalibrationPage.tsx source (not the plan's guessed code,
// see docs/superpowers/plans/2026-09-18-frontend-testing-and-docs.md), following the
// same corrections documented in e2e/accessibility.spec.ts:
// - The "Evaluator and program" select's option text is "<reviewer name> · <program
//   name>" (CalibrationPage.tsx renders both), not just the program name, so selecting
//   by value ('enr1') is used instead of a label match.
// - The blind_code heading and sample button only appear after selecting the
//   assignment (which triggers refresh(id) and renders a "Sessions" heading with a
//   sample button), then clicking that sample button.
// - ConfirmAction renders actionLabel/confirmLabel exactly as passed by
//   CalibrationPage: "Lock blotter responses" / "Confirm blotter lock" for the
//   blotter-stage lock, and "Reveal completed baseline" / "Confirm reveal" for the
//   enrollment reveal.
// #VERIFY: re-verify against CalibrationPage.tsx if its select option text, button
// labels, or ConfirmAction usages change.
test.describe('Blind calibration', () => {
  test('hides identity until reveal, then discloses it', async ({ page }) => {
    let revealed = false

    await mockApi(page, {
      ...bootstrapRoutes(),
      '/calibration/enrollments/enr1': (route: Route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(enrollmentFixture(revealed)),
        }),
      '/calibration/enrollments/enr1/reveal': (route: Route) => {
        revealed = true
        return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
      },
      '/calibration/presentations/samp1/lock/BLOTTER': { status: 'locked' },
    })

    // #ASSUME: data-integrity: bootstrapRoutes()'s shared '/calibration/enrollments'
    // fixture now carries has_started: true (Task 12), so calibrationEntryFor routes
    // ANY bare /calibration visit straight into GuidedCalibrationFlow (kind: 'resume')
    // rather than this manual dropdown/workspace view -- there is no combination of
    // has_started/revealed on a single assignment that reaches the dropdown without a
    // deep link, since CalibrationPage's early-return branches cover 'resume', 'guided'
    // and 'choice' unconditionally whenever assignments.length > 0. The
    // `?assignment=` deep link is the same bypass already applied to the equivalent
    // Vitest suites in commit 8f22f92 ("bypass calibration entry routing in
    // pre-existing workspace tests").
    // #VERIFY: re-check this bypass if CalibrationPage's early-return routing
    // conditions change to also branch on manualBrowse defaults or add a case that
    // reaches the dropdown for a single non-empty assignment.
    await page.goto('/calibration?assignment=enr1')
    await page.getByRole('button', { name: 'ABC-123' }).click()

    await expect(page.getByRole('heading', { name: 'ABC-123' })).toBeVisible()
    await expect(page.getByText('House')).toHaveCount(0)
    await expect(page.getByText('Signature')).toHaveCount(0)
    // Perfumer identifies a sample as surely as its name does, so it is gated
    // on reveal exactly like brand, name and concentration (ADR-005).
    await expect(page.getByText('Fixture Nose')).toHaveCount(0)
    await expect(page.getByText('Blind observation')).toBeVisible()

    await page.getByRole('button', { name: 'Lock blotter responses' }).click()
    await page.getByRole('button', { name: 'Confirm blotter lock' }).click()

    await page.getByRole('button', { name: 'Reveal completed baseline' }).click()
    await page.getByRole('button', { name: 'Confirm reveal' }).click()

    await expect(page.getByText('House · Signature · EDP')).toBeVisible()
    // The attribution links to the source that supports it (ADR-006); a name
    // rendered without its evidence reads as established fact.
    await expect(page.getByRole('link', { name: /Fixture Nose/ })).toHaveAttribute(
      'href',
      'https://example.invalid/attribution'
    )
    // #ASSUME: data-integrity: 'Post-reveal observation' also appears as a substring of
    // the sidebar guidance text ("Identities are revealed. You may add post-reveal
    // observations."), so an exact match is required to target the fieldset legend
    // specifically; without it, getByText throws a strict-mode violation for two
    // matches (found by running this spec against the real app).
    // #VERIFY: re-check both occurrences if enrollmentGuidance() or the legend text
    // in CalibrationPage.tsx changes.
    await expect(page.getByText('Post-reveal observation', { exact: true })).toBeVisible()
  })
})
