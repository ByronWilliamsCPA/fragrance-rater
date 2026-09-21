import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from '../App'

const { get, post, patch } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}))

vi.mock('axios', () => ({
  default: { create: () => ({ get, post, patch }), isAxiosError: () => false },
}))

function expectAccessibleControls() {
  for (const control of document.querySelectorAll('input, select, textarea'))
    expect((control as HTMLInputElement).labels?.length, control.outerHTML).toBeGreaterThan(0)

  for (const action of document.querySelectorAll('button, a[href]'))
    expect(action.textContent?.trim(), action.outerHTML).not.toBe('')

  const ids = [...document.querySelectorAll('[id]')].map((element) => element.id)
  expect(new Set(ids).size).toBe(ids.length)
}

const enrollment = {
  id: 'assignment',
  program_id: 'p',
  reviewer_id: 'r',
  revealed: false,
  reveal_eligible: false,
  reveal_blocker: 'BLOTTER',
  skin_plan_locked: true,
  presentations: [
    {
      id: 'sample',
      session_id: 'session',
      blind_code: 'A82F',
      position: 1,
      skin_planned: false,
      blotter_locked: false,
      skin_locked: false,
      observations: [],
    },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  // Bypass the guided-wizard auto-routing (calibrationEntryFor) via the same
  // `?assignment=` deep-link pattern used by App.test.tsx and
  // revealAndLog.test.tsx, so this scan exercises the real manual-workspace
  // markup instead of GuidedCalibrationFlow's pre-load empty state. Without
  // this, the fixture's enrollment (no `revealed`/`has_started`) resolves to
  // `{kind:'guided'}`, and the wizard's `/calibration/enrollments/assignment`
  // fetch has no matching mock, so `enrollment` stays null and the component
  // early-returns an empty `<main>` -- making expectAccessibleControls()
  // iterate nothing and pass vacuously.
  window.history.replaceState({}, '', '/calibration?assignment=assignment')
  get.mockImplementation((path: string) => {
    const responses: Record<string, unknown> = {
      '/reviewers': [{ id: 'r', name: 'Evaluator' }],
      '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1', status: 'active' }],
      '/calibration/access': { username: 'family-member', manager: false },
      '/calibration/enrollments': [{ id: 'assignment', program_id: 'p', reviewer_id: 'r' }],
      '/calibration/enrollments/assignment': enrollment,
    }
    return Promise.resolve({ data: responses[path] })
  })
})

describe('P3 accessibility baseline', () => {
  it('provides named landmarks, a working skip target, and labelled controls', async () => {
    render(<App />)

    await screen.findByRole('heading', { name: 'Fragrance Rater' })
    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument()
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content')
    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute(
      'href',
      '#main-content'
    )
    expectAccessibleControls()
  })

  it('provides labelled controls and unique ids on the About page', async () => {
    window.history.replaceState({}, '', '/about')
    render(<App />)

    await screen.findByRole('heading', { name: 'How this project learns your taste' })
    expectAccessibleControls()
  })
})
