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

function mockBootstrap(overrides: Record<string, unknown> = {}) {
  get.mockImplementation((path: string) => {
    const responses: Record<string, unknown> = {
      '/reviewers': [{ id: 'r', name: 'Evaluator' }],
      '/calibration/programs': [],
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
  window.history.replaceState({}, '', '/')
  mockBootstrap()
})

describe('WelcomePage', () => {
  it('shows the hero statement, the identity line, and a single continue action', async () => {
    render(<App />)

    expect(
      await screen.findByText(
        'Learn your fragrance taste by measuring what you actually respond to.'
      )
    ).toBeInTheDocument()
    expect(
      screen.getByText("Welcome, family-member, you're set up as Participant.")
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument()
  })

  it('labels a manager identity with the Manager role', async () => {
    mockBootstrap({ '/calibration/access': { username: 'manager-user', manager: true } })
    render(<App />)

    expect(
      await screen.findByText("Welcome, manager-user, you're set up as Manager.")
    ).toBeInTheDocument()
  })

  it('continues into the workspace', async () => {
    render(<App />)

    fireEvent.click(await screen.findByRole('button', { name: 'Continue' }))

    expect(window.location.pathname).toBe('/home')
  })

  it('links to the full methodology page', async () => {
    render(<App />)

    fireEvent.click(await screen.findByRole('button', { name: 'Read the full methodology' }))

    expect(
      await screen.findByRole('heading', { name: 'How this project learns your taste' })
    ).toBeInTheDocument()
  })
})
