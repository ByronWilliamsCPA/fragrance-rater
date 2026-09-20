import { fireEvent, render, screen } from '@testing-library/react'
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
