import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'

const { get, post, patch } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}))

vi.mock('axios', () => ({
  default: { create: () => ({ get, post, patch }), isAxiosError: () => false },
}))

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

function mockBootstrap(overrides: Record<string, unknown> = {}) {
  get.mockImplementation((path: string) => {
    const responses: Record<string, unknown> = {
      '/reviewers': [{ id: 'r', name: 'Evaluator' }],
      '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1' }],
      '/calibration/access': { username: 'family-member', manager: false },
      '/calibration/enrollments': [],
      ...overrides,
    }
    return path in responses
      ? Promise.resolve({ data: responses[path] })
      : Promise.reject(new Error(`Unexpected request: ${path}`))
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  window.history.replaceState({}, '', '/home')
  mockBootstrap()
})

describe('WorkspacePage', () => {
  it('always offers the participant baseline rows', async () => {
    render(<App />)

    expect(await screen.findByRole('button', { name: 'Log an encounter' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'See recommendations' })).toBeInTheDocument()
  })

  it('hides program management from a non-manager', async () => {
    render(<App />)

    await screen.findByRole('button', { name: 'Log an encounter' })
    expect(screen.queryByRole('button', { name: 'Manage programs' })).not.toBeInTheDocument()
  })

  it('offers program management to a manager', async () => {
    mockBootstrap({ '/calibration/access': { username: 'manager-user', manager: true } })
    render(<App />)

    expect(await screen.findByRole('button', { name: 'Manage programs' })).toBeInTheDocument()
  })

  it('hides the calibration section entirely when there are no assignments', async () => {
    render(<App />)

    await screen.findByRole('button', { name: 'Log an encounter' })
    expect(screen.queryByRole('heading', { name: 'Calibration work' })).not.toBeInTheDocument()
  })

  it('shows one row per open enrollment with its own deep-linking action', async () => {
    mockBootstrap({
      '/calibration/enrollments': [{ id: 'assignment', program_id: 'p', reviewer_id: 'r' }],
      '/calibration/enrollments/assignment': enrollment,
    })
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Baseline' })).toBeInTheDocument()
    expect(screen.getByText('Continue required blind blotter screens.')).toBeInTheDocument()
    expect(screen.getByText('0 of 1 blind screens locked')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Continue calibration' }))

    expect(await screen.findByRole('heading', { name: 'Your calibration' })).toBeInTheDocument()
    expect(window.location.search).toBe('?assignment=assignment')
    expect(screen.getByLabelText('Evaluator and program')).toHaveValue('assignment')
    expect(await screen.findByRole('button', { name: /A82F/ })).toBeInTheDocument()
  })

  it('retries assignment progress without reloading the application', async () => {
    let progressUnavailable = true
    get.mockImplementation((path: string) => {
      const responses: Record<string, unknown> = {
        '/reviewers': [{ id: 'r', name: 'Evaluator' }],
        '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1' }],
        '/calibration/access': { username: 'family-member', manager: false },
        '/calibration/enrollments': [{ id: 'assignment', program_id: 'p', reviewer_id: 'r' }],
        '/calibration/enrollments/assignment': enrollment,
      }
      if (path === '/calibration/enrollments/assignment' && progressUnavailable) {
        return Promise.reject(new Error('offline'))
      }
      return Promise.resolve({ data: responses[path] })
    })
    render(<App />)

    expect(
      await screen.findByText('Request failed. Check your connection and try again.')
    ).toBeInTheDocument()
    progressUnavailable = false
    fireEvent.click(screen.getByRole('button', { name: 'Retry assignment progress' }))

    expect(await screen.findByText('Continue required blind blotter screens.')).toBeInTheDocument()
    expect(
      screen.queryByText('Request failed. Check your connection and try again.')
    ).not.toBeInTheDocument()
  })

  it('sends each assignment row to its own assignment, not a shared or swapped one', async () => {
    const secondEnrollment = {
      ...enrollment,
      id: 'assignment-2',
      reviewer_id: 'r2',
      presentations: [{ ...enrollment.presentations[0], id: 'sample-2', blind_code: 'B19Q' }],
    }
    mockBootstrap({
      '/reviewers': [
        { id: 'r', name: 'Evaluator' },
        { id: 'r2', name: 'Second Evaluator' },
      ],
      '/calibration/enrollments': [
        { id: 'assignment', program_id: 'p', reviewer_id: 'r' },
        { id: 'assignment-2', program_id: 'p', reviewer_id: 'r2' },
      ],
      '/calibration/enrollments/assignment': enrollment,
      '/calibration/enrollments/assignment-2': secondEnrollment,
    })
    render(<App />)

    const articles = await screen.findAllByRole('article')
    expect(articles).toHaveLength(2)
    const firstArticle = articles.find((article) => within(article).queryByText('Evaluator'))
    const secondArticle = articles.find((article) =>
      within(article).queryByText('Second Evaluator')
    )
    if (!firstArticle || !secondArticle) throw new Error('expected both assignment rows to render')

    fireEvent.click(within(firstArticle).getByRole('button', { name: 'Continue calibration' }))

    expect(await screen.findByRole('button', { name: /A82F/ })).toBeInTheDocument()
    expect(window.location.search).toBe('?assignment=assignment')

    window.history.replaceState({}, '', '/home')
    window.dispatchEvent(new PopStateEvent('popstate'))

    const rowsAfterReturning = await screen.findAllByRole('article')
    const secondRowAfterReturning = rowsAfterReturning.find((article) =>
      within(article).queryByText('Second Evaluator')
    )
    if (!secondRowAfterReturning) throw new Error('expected the second assignment row to persist')
    fireEvent.click(
      within(secondRowAfterReturning).getByRole('button', { name: 'Continue calibration' })
    )

    expect(await screen.findByRole('button', { name: /B19Q/ })).toBeInTheDocument()
    expect(window.location.search).toBe('?assignment=assignment-2')
  })

  it('navigates to the log-an-encounter page when "Log an encounter" is clicked', async () => {
    render(<App />)

    fireEvent.click(await screen.findByRole('button', { name: 'Log an encounter' }))

    expect(await screen.findByRole('heading', { name: 'Log an encounter' })).toBeInTheDocument()
  })

  it('navigates to the recommendations page when "See recommendations" is clicked', async () => {
    render(<App />)

    fireEvent.click(await screen.findByRole('button', { name: 'See recommendations' }))

    expect(await screen.findByRole('heading', { name: 'Recommendations' })).toBeInTheDocument()
  })

  it('navigates to program setup when "Manage programs" is clicked', async () => {
    mockBootstrap({ '/calibration/access': { username: 'manager-user', manager: true } })
    render(<App />)

    fireEvent.click(await screen.findByRole('button', { name: 'Manage programs' }))

    expect(await screen.findByRole('heading', { name: 'Program setup' })).toBeInTheDocument()
  })
})
