import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'

/**
 * Render paths the mocked-API e2e tier covers but Vitest did not.
 *
 * Playwright proves these work in a browser; it does not contribute to the
 * coverage report Codecov reads, so the reveal branch, the observation log and
 * the landing page's actions were all counted as untested. These are component
 * tests for the same behaviour, not duplicates of the e2e assertions: they
 * check what the markup says, where the e2e checks the rendered page.
 */

const { get, post, patch } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}))

vi.mock('axios', () => ({
  default: { create: () => ({ get, post, patch }), isAxiosError: () => false },
}))

const observation = {
  id: 'obs-1',
  phase: 'blind',
  stage: 'BLOTTER',
  elapsed_minutes: 30,
  detected: true,
  intensity: 3,
  liking: 6,
  comments: 'Softer now',
}

/** Two blotter timepoints and one skin test, deliberately out of order. */
const observations = [
  { ...observation, id: 'obs-late', elapsed_minutes: 240, intensity: 1, comments: 'Nearly gone' },
  { ...observation, id: 'obs-first', elapsed_minutes: 0, intensity: 5, comments: null },
  { ...observation, id: 'obs-skin', stage: 'SKIN', elapsed_minutes: 15, comments: null },
]

function revealedEnrollment(
  perfumers: { name: string; source_url: string }[] | undefined = [
    { name: 'First Nose', source_url: 'https://example.invalid/one' },
    { name: 'Second Nose', source_url: 'https://example.invalid/two' },
  ]
) {
  return {
    id: 'assignment',
    program_id: 'p',
    reviewer_id: 'r',
    revealed: true,
    reveal_eligible: false,
    reveal_blocker: null,
    skin_plan_locked: true,
    presentations: [
      {
        id: 'sample',
        session_id: 'session',
        blind_code: 'A82F',
        position: 1,
        skin_planned: true,
        blotter_locked: true,
        skin_locked: false,
        identity: {
          fragrance_id: 'f-1',
          name: 'Signature',
          brand: 'House',
          concentration: 'EDP',
          perfumers,
        },
        observations,
      },
    ],
  }
}

function mockApi(enrollment: unknown) {
  get.mockImplementation((path: string) => {
    const responses: Record<string, unknown> = {
      '/reviewers': [{ id: 'r', name: 'Evaluator' }],
      '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1' }],
      '/calibration/access': { username: 'family-member', manager: false },
      '/calibration/enrollments': [{ id: 'assignment', program_id: 'p', reviewer_id: 'r' }],
      '/calibration/enrollments/assignment': enrollment,
      '/evaluations': [],
    }
    return path in responses
      ? Promise.resolve({ data: responses[path] })
      : Promise.reject(new Error(`Unexpected request: ${path}`))
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  post.mockResolvedValue({ data: { id: 'saved' } })
  patch.mockResolvedValue({ data: { id: 'updated' } })
})

describe('Revealed sample', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/calibration')
    mockApi(revealedEnrollment())
  })

  async function openSample() {
    render(<App />)
    await screen.findByRole('option', { name: 'Evaluator · Baseline' })
    fireEvent.change(screen.getByLabelText('Evaluator and program'), {
      target: { value: 'assignment' },
    })
    fireEvent.click(await screen.findByRole('button', { name: /A82F/ }))
  }

  it('credits every perfumer and links each to its own source', async () => {
    await openSample()

    const first = await screen.findByRole('link', { name: /First Nose/ })
    expect(first).toHaveAttribute('href', 'https://example.invalid/one')
    expect(screen.getByRole('link', { name: /Second Nose/ })).toHaveAttribute(
      'href',
      'https://example.invalid/two'
    )
    // Plural, because a co-created fragrance credits more than one person.
    expect(screen.getByText('Perfumers')).toBeInTheDocument()
  })

  it('uses the singular label for a single perfumer', async () => {
    mockApi(
      revealedEnrollment([{ name: 'Solo Nose', source_url: 'https://example.invalid/solo' }])
    )
    await openSample()

    expect(screen.getByText('Perfumer')).toBeInTheDocument()
    expect(screen.queryByText('Perfumers')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Solo Nose/ })).toHaveAttribute(
      'href',
      'https://example.invalid/solo'
    )
  })

  it('renders no attribution when perfumers is empty', async () => {
    mockApi(revealedEnrollment([]))
    await openSample()

    await screen.findByRole('table')
    expect(screen.queryByText('Perfumer')).not.toBeInTheDocument()
    expect(screen.queryByText('Perfumers')).not.toBeInTheDocument()
    expect(screen.queryByText(/opens the source/)).not.toBeInTheDocument()
  })

  it('orders the observation log by stage, then by elapsed time', async () => {
    await openSample()

    const log = await screen.findByRole('table')
    const rows = within(log)
      .getAllByRole('rowheader')
      .map((cell) => cell.textContent)

    // Fixture order is 240, 0, then a skin test at 15. Blotter timepoints run
    // earliest first, and the skin test follows regardless of its clock value:
    // 15 trails 240 because stage outranks elapsed time.
    expect(rows).toEqual(['0 min', '240 min', '15 min'])
  })

  it('names the log for assistive technology and marks each row', async () => {
    await openSample()

    const log = await screen.findByRole('table')
    expect(
      within(log).getByText('Saved observations for this sample, earliest first')
    ).toBeInTheDocument()
    expect(
      within(log)
        .getAllByRole('columnheader')
        .map((cell) => cell.textContent)
    ).toEqual(['Time', 'Stage', 'Phase', 'Intensity', 'Liking', 'Comment'])
  })

  it('shows the skin-test scales once the skin stage is selected', async () => {
    await openSample()

    expect(screen.queryByText('How it performed on skin')).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Stage'), { target: { value: 'SKIN' } })

    expect(await screen.findByText('How it performed on skin')).toBeInTheDocument()
    expect(screen.getByText('How you responded on skin')).toBeInTheDocument()
    expect(screen.getByLabelText('Longevity (minutes)')).toBeInTheDocument()
  })
})

describe('Welcome and workspace flow', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/')
  })

  it('continues from the welcome screen into the workspace', async () => {
    mockApi(revealedEnrollment())
    render(<App />)

    expect(
      await screen.findByText("Welcome, family-member, you're set up as Recorder.")
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))

    expect(await screen.findByRole('button', { name: 'Log an encounter' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/home')
  })

  it('deep-links from a workspace calibration row directly into that assignment', async () => {
    mockApi(revealedEnrollment())
    window.history.replaceState({}, '', '/home')
    render(<App />)

    fireEvent.click(await screen.findByRole('button', { name: 'Continue calibration' }))

    expect(await screen.findByRole('heading', { name: 'Your calibration' })).toBeInTheDocument()
    expect(window.location.search).toBe('?assignment=assignment')
    expect(screen.getByLabelText('Evaluator and program')).toHaveValue('assignment')
    expect(await screen.findByRole('button', { name: /A82F/ })).toBeInTheDocument()
  })

  it('hides the calibration section for an identity with no assignments', async () => {
    get.mockImplementation((path: string) => {
      const responses: Record<string, unknown> = {
        '/reviewers': [{ id: 'r', name: 'Evaluator' }],
        '/calibration/programs': [],
        '/calibration/access': { username: 'manager-user', manager: true },
        '/calibration/enrollments': [],
      }
      return path in responses
        ? Promise.resolve({ data: responses[path] })
        : Promise.reject(new Error(`Unexpected request: ${path}`))
    })
    window.history.replaceState({}, '', '/home')
    render(<App />)

    await screen.findByRole('button', { name: 'Log an encounter' })
    expect(screen.queryByRole('heading', { name: 'Calibration work' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Manage programs' })).toBeInTheDocument()
  })
})
