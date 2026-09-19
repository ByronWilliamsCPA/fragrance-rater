import { test, expect, type Route } from '@playwright/test'
import { mockApi, bootstrapRoutes, recommendationRunFixture } from './support/mock-api'

// #ASSUME: data-integrity: the interaction sequence and text assertions below were
// verified against the real RecommendationsPage.tsx source (not the plan's guessed
// code, see docs/superpowers/plans/2026-09-18-frontend-testing-and-docs.md), following
// the same corrections documented in e2e/accessibility.spec.ts:
// - recommendationRunFixture() (mock-api.ts) already returns `impressions` (not
//   `.items`), with impression id `imp1` and `fragrance_name: 'Signature'`; this was
//   fixed for Task 6/7 and needed no further change here.
// - "Signature" only renders (as an `<h3>`) after selecting reviewer 'r1' from the
//   "Evaluator" select (matched by value, the only "Evaluator" label on this page,
//   so no `.first()` scoping is needed unlike RatingsPage) and clicking "Get
//   recommendations", which calls createRun() -> POST /recommendation-measurement/runs.
// - The "Interested" button really carries the pressed state via `aria-pressed`
//   (`aria-pressed={latest?.interested === true}` in RecommendationsPage.tsx), so the
//   brief's assumption about that attribute was correct; it starts as "false" (no
//   responses yet) and flips to "true" only once the POST response is applied to
//   local state.
// - The follow-up flow is "Update sampling and outcome" -> "Sampling status" select
//   (name="sampling_state", options include `value="PLANNED"` / label "Plan to
//   sample", matching the brief exactly) -> "Save follow-up" submit button. Opening
//   the follow-up also calls GET /calibration/history/r1 (openFollowUp() in
//   RecommendationsPage.tsx fetches it whenever the cached reviewer differs from the
//   selected one, which is always true on first open), so that mock route is real
//   coverage, not dead weight.
// - Both "Interested" and "Save follow-up" POST to the same endpoint,
//   /recommendation-measurement/impressions/imp1/responses. Rather than hardcode a
//   single canned response body (which would leave the interest response stale by
//   the time the follow-up POSTs), the mock below echoes back a real
//   RecommendationResponse shaped from the actual request body, so `interested` and
//   `sampling_state` both track what the UI really sent across both calls.
// #VERIFY: re-verify against RecommendationsPage.tsx if its select option
// values/labels, button text, or the responses endpoint contract change.
test.describe('Recommendation feedback and sampling', () => {
  test('records interest and a sampling follow-up', async ({ page }) => {
    const responses: Record<string, unknown>[] = []

    await mockApi(page, {
      ...bootstrapRoutes(),
      '/recommendation-measurement/runs': recommendationRunFixture(),
      '/recommendation-measurement/impressions/imp1/responses': (route: Route) => {
        const body = route.request().postDataJSON() as Record<string, unknown>
        responses.push(body)
        const revision = responses.length
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: `resp${revision}`,
            impression_id: 'imp1',
            revision,
            created_at: `2026-09-18T00:00:0${revision}Z`,
            interested: body.interested ?? null,
            sampling_state: body.sampling_state ?? null,
            unavailable_reason: body.unavailable_reason ?? null,
            outcome_evaluation_id: body.outcome_evaluation_id ?? null,
            outcome_observation_id: body.outcome_observation_id ?? null,
            would_wear: body.would_wear ?? null,
            would_buy: body.would_buy ?? null,
          }),
        })
      },
      '/calibration/history/r1': [],
    })

    await page.goto('/recommendations')
    await page.getByLabel('Evaluator').selectOption('r1')
    await page.getByRole('button', { name: 'Get recommendations' }).click()

    await expect(page.getByRole('heading', { name: 'Signature' })).toBeVisible()

    const interestedButton = page.getByRole('button', { name: 'Interested', exact: true })
    await expect(interestedButton).toHaveAttribute('aria-pressed', 'false')
    await interestedButton.click()
    await expect(interestedButton).toHaveAttribute('aria-pressed', 'true')

    await page.getByRole('button', { name: 'Update sampling and outcome' }).click()
    await page.getByLabel('Sampling status').selectOption({ label: 'Plan to sample' })
    await page.getByRole('button', { name: 'Save follow-up' }).click()

    await expect
      .poll(() => responses.some((r) => r.sampling_state === 'PLANNED'))
      .toBe(true)
  })
})
