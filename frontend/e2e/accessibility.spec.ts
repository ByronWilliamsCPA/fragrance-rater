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
import type { Observation } from '../src/api/types'

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
  /**
   * Per-route overrides layered on top of setUpRoute's shared mocks. Used by
   * the bare `/calibration` entry below, which needs a never-started
   * enrollment (calibrationEntryFor routes on has_started/revealed) instead
   * of the shared in-progress fixture every other entry relies on.
   */
  mocks?: Record<string, unknown>
}[] = [
  { path: '/', heading: 'Welcome' },
  { path: '/home', heading: 'Workspace' },
  {
    // #ASSUME: data-integrity: bootstrapRoutes()'s shared '/calibration/enrollments'
    // fixture carries has_started: true (Task 12), so calibrationEntryFor now routes
    // ANY bare /calibration visit straight into GuidedCalibrationFlow instead of this
    // manual dropdown/workspace view -- same root cause already fixed for
    // blind-calibration.spec.ts and, for the Vitest suites, in commit 8f22f92. The
    // `?assignment=` deep link bypasses CalibrationPage's early-return routing
    // branches and reaches the same manual workspace JSX this route check exercises,
    // pre-selected rather than picked from the dropdown.
    // #VERIFY: re-check this bypass if CalibrationPage's early-return routing
    // conditions change to also branch on manualBrowse defaults or add a case that
    // reaches the dropdown for a single non-empty assignment.
    path: '/calibration?assignment=enr1',
    heading: 'ABC-123',
    populate: async (page) => {
      await page.getByRole('button', { name: 'ABC-123' }).click()
    },
  },
  {
    // The deep-linked entry above legitimately covers the manual-workspace
    // path, but it never exercises the guided wizard (GuidedCalibrationFlow)
    // or the pre-wizard choice screen (CalibrationChoiceScreen), which is
    // where most participants now land on a bare /calibration visit. This
    // mirrors calibration-entry.spec.ts's "never-started enrollment" fixture
    // (has_started: false) so calibrationEntryFor resolves to `{kind:
    // 'guided'}` and the wizard renders its default first step (the
    // skin-test plan decision) for the scan.
    path: '/calibration',
    heading: 'Guided calibration',
    mocks: {
      '/calibration/enrollments': [
        {
          id: 'enr1',
          program_id: 'p1',
          reviewer_id: 'r1',
          revealed: false,
          has_started: false,
          total_presentations: 1,
          blotter_complete: 0,
          skin_planned: 0,
          skin_complete: 0,
          program_name: 'Baseline',
          program_version: '1',
        },
      ],
      '/calibration/enrollments/enr1': {
        id: 'enr1',
        program_id: 'p1',
        reviewer_id: 'r1',
        revealed: false,
        reveal_eligible: false,
        reveal_blocker: 'SKIN_PLAN',
        skin_plan_locked: false,
        presentations: [
          {
            id: 'samp1',
            session_id: 'sess1',
            blind_code: 'ABC-123',
            position: 1,
            skin_planned: false,
            blotter_locked: false,
            skin_locked: false,
            observations: [],
          },
        ],
      },
    },
  },
  { path: '/calibration/protocol', heading: 'Calibration protocol' },
  { path: '/ratings', heading: 'Log an encounter' },
  {
    path: '/recommendations',
    heading: 'Signature',
    populate: async (page) => {
      await page.getByLabel('Evaluator').selectOption('r1')
      await page.getByRole('button', { name: 'Get recommendations' }).click()
    },
  },
  { path: '/about', heading: 'How this project learns your taste' },
  { path: '/evidence', heading: 'Why better fragrance discovery matters' },
  { path: '/programs', heading: 'Program setup' },
]

async function setUpRoute(
  page: Page,
  path: string,
  populate?: (page: Page) => Promise<void>,
  mocks?: Record<string, unknown>
) {
  await mockApi(page, {
    ...bootstrapRoutes(managerAccess),
    [`/calibration/enrollments/enr1`]: enrollmentFixture(false),
    '/fragrances': fragranceCatalog,
    '/evaluations': [],
    '/recommendation-measurement/runs': recommendationRunFixture(),
    ...mocks,
  })

  await page.goto(path)
  await expect(page.getByRole('heading', { name: 'Fragrance Rater' })).toBeVisible()
  if (populate) await populate(page)
}

/*
 * ADR-014 sets WCAG 2.2 AA as the conformance target (amended from 2.1 AA in
 * the 2026-09-19 design pass). The `wcag22aa` tag is what brings 2.5.8 Target
 * Size and the other 2.2 additions into the scan; the earlier tags are
 * retained because 2.2 is a superset, not a replacement.
 *
 * Both colour schemes are scanned. The palette is theme-dependent, so a scan
 * of one theme says nothing about the other, and dark mode is the one an
 * evaluator is most likely to use in the low light this app gets used in.
 */
const axeTags = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']

for (const colorScheme of ['light', 'dark'] as const) {
  test.describe(`Accessibility (WCAG 2.2 AA, ${colorScheme} theme)`, () => {
    test.use({ colorScheme })

    for (const { path, heading, populate, mocks } of routeChecks) {
      test(`${path} has no automatically detectable violations`, async ({ page }) => {
        await setUpRoute(page, path, populate, mocks)
        await expect(page.getByRole('heading', { name: heading })).toBeVisible()

        const results = await new AxeBuilder({ page }).withTags(axeTags).analyze()

        expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([])
      })
    }
  })
}

test.describe('Observation log', () => {
  /*
   * The shared enrollment fixture carries no observations, so every other scan
   * renders this route with the log's empty state. The log is a data table
   * with row headers and a caption, which is exactly the kind of structure an
   * axe scan is good at checking, so it gets its own populated case.
   */
  const blank = {
    detected: true,
    confidence: null,
    sweetness: null,
    freshness: null,
    density: null,
    familiarity: null,
    dryness: null,
    clean_soapy: null,
    earthy_rooty: null,
    bodily_animalic: null,
    discomfort: null,
    opening_liking: null,
    drydown_liking: null,
    would_wear: null,
    would_buy: null,
    artistic_appreciation: null,
    projection: null,
    longevity_minutes: null,
    perceived_notes: null,
    likes: null,
    dislikes: null,
    reminds_me_of: null,
  }

  // Deliberately out of order, so the spec proves the component sorts rather
  // than that the fixture happened to arrive sorted.
  const timepoints: Observation[] = [
    {
      ...blank,
      id: 'o2',
      phase: 'blind',
      stage: 'BLOTTER',
      elapsed_minutes: 30,
      intensity: 3,
      liking: 6,
      comments: 'Softer now',
    },
    {
      ...blank,
      id: 'o1',
      phase: 'blind',
      stage: 'BLOTTER',
      elapsed_minutes: 0,
      intensity: 5,
      liking: 4,
      comments: null,
    },
    {
      ...blank,
      id: 'o3',
      phase: 'blind',
      stage: 'SKIN',
      elapsed_minutes: 15,
      intensity: 4,
      liking: 7,
      comments: null,
    },
  ]

  test('renders timepoints earliest first and scans clean', async ({ page }) => {
    await mockApi(page, {
      ...bootstrapRoutes(managerAccess),
      '/calibration/enrollments/enr1': enrollmentFixture(false, timepoints),
    })
    // See the routeChecks '/calibration' entry above: a bare /calibration visit now
    // auto-routes into GuidedCalibrationFlow, so this deep-links past routing to
    // reach the same manual workspace/log view instead.
    await page.goto('/calibration?assignment=enr1')
    await expect(page.getByRole('heading', { name: 'Fragrance Rater' })).toBeVisible()
    await page.getByRole('button', { name: 'ABC-123' }).click()

    // Fixture order is 30, 0, 15-on-skin; the log must show blotter timepoints
    // in ascending time, then the skin test.
    const rowHeaders = await page.locator('.log tbody th').allTextContents()
    expect(rowHeaders).toEqual(['0 min', '30 min', '15 min'])

    const results = await new AxeBuilder({ page }).withTags(axeTags).analyze()
    expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([])
  })
})

test.describe('Target size (WCAG 2.2 AA, 2.5.8)', () => {
  for (const { path, heading, populate, mocks } of routeChecks) {
    test(`${path} has no interactive target under 24px`, async ({ page }) => {
      // 360px is the narrowest viewport the P3 gate commits to, and the one
      // where controls are most likely to be squeezed below the minimum.
      await page.setViewportSize({ width: 360, height: 740 })
      await setUpRoute(page, path, populate, mocks)
      await expect(page.getByRole('heading', { name: heading })).toBeVisible()

      const undersized = await page.evaluate(() => {
        const selector =
          'a[href], button, select, input:not([type="radio"]):not([type="hidden"]), textarea, summary'
        return [...document.querySelectorAll(selector)]
          .filter((element) => {
            const box = element.getBoundingClientRect()
            // Off-screen controls (the skip link at rest, the visually hidden
            // radio inputs) are not rendered targets.
            if (box.width === 0 && box.height === 0) return false
            return box.width < 24 || box.height < 24
          })
          .map((element) => {
            const box = element.getBoundingClientRect()
            return `${element.tagName.toLowerCase()} "${(element.textContent ?? '')
              .trim()
              .slice(0, 40)}" ${Math.round(box.width)}x${Math.round(box.height)}`
          })
      })

      expect(undersized, undersized.join('\n')).toEqual([])
    })
  }

  test('scale options meet the minimum target size', async ({ page }) => {
    // See the routeChecks '/calibration' entry above for why this deep-links.
    await setUpRoute(page, '/calibration?assignment=enr1', async (target) => {
      await target.getByRole('button', { name: 'ABC-123' }).click()
    })

    // The radio inputs themselves are visually hidden; the rendered target is
    // the span the label paints in their place.
    const option = page.locator('.scale-field__option span').first()
    const box = await option.boundingBox()

    expect(box?.width ?? 0).toBeGreaterThanOrEqual(24)
    expect(box?.height ?? 0).toBeGreaterThanOrEqual(24)
  })
})

test.describe('Focus visibility (WCAG 2.2 AA, 1.4.11 and 2.4.11)', () => {
  test('keyboard focus paints a two-tone indicator', async ({ page }) => {
    await setUpRoute(page, '/ratings')

    await page.keyboard.press('Tab')
    const indicator = await page.evaluate(() => {
      const active = document.activeElement
      if (!active) return null
      const style = window.getComputedStyle(active)
      return {
        outlineWidth: style.outlineWidth,
        outlineStyle: style.outlineStyle,
        boxShadow: style.boxShadow,
      }
    })

    expect(indicator).not.toBeNull()
    expect(indicator?.outlineStyle).not.toBe('none')
    expect(parseFloat(indicator?.outlineWidth ?? '0')).toBeGreaterThanOrEqual(2)
    // The halo is what carries 3:1 on filled brand buttons, where the ring
    // alone cannot. Its absence would silently drop the contrast contract.
    expect(indicator?.boxShadow).not.toBe('none')
  })
})

test.describe('Keyboard operability', () => {
  test('blind calibration is fully operable via keyboard', async ({ page }) => {
    await mockApi(page, {
      ...bootstrapRoutes(),
      '/calibration/enrollments/enr1': enrollmentFixture(false),
    })

    // See the routeChecks '/calibration' entry above: a bare /calibration visit now
    // auto-routes into GuidedCalibrationFlow, which has no "Evaluator and program"
    // select at all, so this deep-links past routing to reach the same manual
    // workspace select this test exercises the keyboard path through.
    await page.goto('/calibration?assignment=enr1')
    // Wait for the loading shell to resolve before tabbing; tabbing while
    // <body> is still the only focusable element (LoadingState has no focusable
    // content) silently no-ops and desyncs the press count from the real page.
    await expect(page.getByLabel('Evaluator and program')).toBeVisible()

    // #ASSUME: timing dependencies: this Tab sequence was verified by running the test
    // headed against the real rendered page rather than guessed; it depends on the DOM
    // order of focusable elements before the assignment select:
    // 1) skip link, 2) theme toggle, 3) "Welcome" nav link, 4) "Workspace" nav link,
    // 5) "Calibration" nav link (current page, still focusable), 6) "Recommendations"
    // nav link, 7) "Log an encounter" nav link (renamed from "My Ratings"), 8) the
    // "Read the calibration protocol" link, then the "Evaluator and program" <select>.
    // Selecting the only option and pressing Enter/Space on the resulting sample
    // button reaches the blind observation form.
    // #VERIFY: re-run headed if AppShell's nav items, the header controls, the
    // CalibrationPage intro link, or their order change.
    for (let i = 0; i < 9; i++) await page.keyboard.press('Tab')
    await expect(page.getByLabel('Evaluator and program')).toBeFocused()
    await page.keyboard.press('ArrowDown')
    await expect(page.getByRole('heading', { name: 'Sessions' })).toBeVisible()

    await page.keyboard.press('Tab')
    await expect(page.getByRole('button', { name: 'ABC-123' })).toBeFocused()
    await page.keyboard.press('Enter')

    await expect(page.getByRole('heading', { name: 'ABC-123' })).toBeVisible()
    await expect(page.getByText('Blind observation')).toBeVisible()
  })

  test('a calibration scale is one tab stop with arrow-key selection', async ({ page }) => {
    // See the routeChecks '/calibration' entry above for why this deep-links.
    await setUpRoute(page, '/calibration?assignment=enr1', async (target) => {
      await target.getByRole('button', { name: 'ABC-123' }).click()
    })

    // A radio group is reached once and traversed with arrow keys, so the ten
    // perceptual dimensions no longer cost ten tab stops each to skip past.
    const intensity = page.getByRole('radio', { name: 'Not answered' }).first()
    await intensity.focus()
    await expect(intensity).toBeChecked()

    await page.keyboard.press('ArrowRight')
    await expect(page.getByRole('radio', { name: '0', exact: true }).first()).toBeChecked()
  })
})
