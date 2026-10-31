import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { axe } from 'vitest-axe'
import * as axeMatchers from 'vitest-axe/matchers'
import App from '../App'
import { apiUrl, bootstrapHandlers, getJson, server } from './msw/server'

expect.extend(axeMatchers)

declare module 'vitest' {
  interface Assertion {
    toHaveNoViolations(): void
  }
}

/*
 * An axe scan over every route (architecture review F-13), through the real
 * App and real axios against MSW, replacing the label-and-landmark checks the
 * old baseline made on two routes.
 *
 * jsdom has no layout, so axe cannot compute colour contrast here; that rule is
 * off, and contrast is covered by `contrast.test.ts` (token ratios) and the
 * Playwright accessibility spec (rendered pages, both themes). Everything else
 * axe checks in the DOM runs.
 *
 * Each case first waits for the page's own heading, so a scan of a loading or
 * error state cannot pass for the page it is named after.
 */
const enrollment = {
  id: 'enr1',
  program_id: 'p1',
  reviewer_id: 'r1',
  revealed: false,
  reveal_eligible: false,
  reveal_blocker: 'BLOTTER',
  skin_plan_locked: true,
  presentations: [
    {
      id: 'samp1',
      session_id: 'sess1',
      blind_code: 'ABC-123',
      position: 1,
      skin_planned: false,
      blotter_locked: false,
      skin_locked: false,
      post_reveal_entry: false,
      observations: [],
    },
  ],
}

const routes: { path: string; heading: string | RegExp; manager?: boolean }[] = [
  { path: '/', heading: 'Welcome' },
  { path: '/home', heading: 'Workspace' },
  { path: '/calibration?assignment=enr1', heading: 'Sessions' },
  { path: '/calibration/protocol', heading: 'Calibration protocol' },
  { path: '/ratings', heading: 'Log an encounter' },
  { path: '/recommendations', heading: 'Recommendations' },
  { path: '/about', heading: 'How this project learns your taste' },
  { path: '/evidence', heading: 'Why better fragrance discovery matters' },
  { path: '/programs', heading: 'Program setup', manager: true },
]

describe('every route has no axe violations (jsdom-checkable rules)', () => {
  it.each(routes)('$path', async ({ path, heading, manager }) => {
    window.history.replaceState({}, '', path)
    server.use(
      getJson('/calibration/enrollments/enr1', enrollment),
      ...bootstrapHandlers(
        manager
          ? { username: 'manager', manager: true }
          : { username: 'family-member', manager: false }
      ),
      // Whatever else a page reads on mount is an empty list: the scan is of
      // the page's structure, and the data-driven views have their own tests.
      http.get(apiUrl('/*'), () => HttpResponse.json([]))
    )

    const { container } = render(<App />)

    await screen.findByRole('heading', { name: heading })
    expect(
      await axe(container, { rules: { 'color-contrast': { enabled: false } } })
    ).toHaveNoViolations()
  })
})

describe('the scan itself', () => {
  it('catches a real violation, so a clean result means something', async () => {
    const { container } = render(
      <main>
        {/* Deliberately missing alt text: the control must see this. */}
        {/* eslint-disable-next-line jsx-a11y/alt-text */}
        <img src="x.png" />
        <button />
      </main>
    )

    const results = await axe(container, { rules: { 'color-contrast': { enabled: false } } })

    expect(results.violations.map((violation) => violation.id)).toEqual(
      expect.arrayContaining(['image-alt', 'button-name'])
    )
  })
})
