import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import App from '../App'

const { get, post, patch } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}))
vi.mock('axios', () => ({
  default: { create: () => ({ get, post, patch }), isAxiosError: () => false },
}))

beforeEach(() => {
  vi.clearAllMocks()
  window.history.replaceState({}, '', '/calibration/protocol')
  get.mockImplementation((path: string) => {
    const responses: Record<string, unknown> = {
      '/reviewers': [{ id: 'r', name: 'Evaluator' }],
      '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1' }],
      '/calibration/access': { username: 'family-member', manager: false },
      '/calibration/enrollments': [{ id: 'assignment', program_id: 'p', reviewer_id: 'r' }],
    }
    return path in responses
      ? Promise.resolve({ data: responses[path] })
      : Promise.reject(new Error(`Unexpected request: ${path}`))
  })
  post.mockResolvedValue({ data: { id: 'saved' } })
  patch.mockResolvedValue({ data: { id: 'updated' } })
})

describe('Calibration protocol page', () => {
  it('renders the protocol page heading when navigating directly to /calibration/protocol and stays out of primary nav', async () => {
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Calibration protocol' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Calibration protocol' })).not.toBeInTheDocument()
  })

  it('includes the major section headings and the collapsed access-details summary', async () => {
    render(<App />)
    await screen.findByRole('heading', { name: 'Calibration protocol' })

    for (const heading of [
      'Find your sample by its code',
      'Two blind stages, locked independently',
      'What each observation records',
      'When your identities appear',
      'Concealed repeats',
      'Frozen predictions, when a checkpoint is taken',
    ])
      expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument()

    expect(screen.getByText('Access and verification details')).toBeInTheDocument()
  })

  it('cross-links to the About page for the rationale behind the protocol', async () => {
    render(<App />)
    await screen.findByRole('heading', { name: 'Calibration protocol' })

    const link = screen.getByRole('link', { name: 'How this project learns your taste' })
    expect(link).toHaveAttribute('href', '/about')
    fireEvent.click(link)

    expect(
      await screen.findByRole('heading', { name: 'How this project learns your taste' })
    ).toBeInTheDocument()
  })

  it('keeps the access-details summary collapsed until clicked', async () => {
    render(<App />)
    await screen.findByRole('heading', { name: 'Calibration protocol' })

    const summary = screen.getByText('Access and verification details')
    const details = summary.closest('details')
    expect(details).not.toBeNull()
    expect(details?.open).toBeFalsy()

    fireEvent.click(summary)

    expect(details?.open).toBeTruthy()
  })

  it('navigates from the Calibration page link without a full page reload', async () => {
    window.history.replaceState({}, '', '/calibration?assignment=assignment')
    render(<App />)

    const link = await screen.findByRole('link', { name: 'Read the calibration protocol' })
    expect(link).toHaveAttribute('href', '/calibration/protocol')
    fireEvent.click(link)

    expect(await screen.findByRole('heading', { name: 'Calibration protocol' })).toBeInTheDocument()
  })

  it('cross-links to the About page from "Concealed repeats"', async () => {
    render(<App />)
    await screen.findByRole('heading', { name: 'Calibration protocol' })

    const link = screen.getByRole('link', { name: 'Why repeats matter' })
    expect(link).toHaveAttribute('href', '/about')
    fireEvent.click(link)

    expect(
      await screen.findByRole('heading', { name: 'How this project learns your taste' })
    ).toBeInTheDocument()
  })

  it('never leaks experimental-control identifiers into the static page', async () => {
    render(<App />)
    await screen.findByRole('heading', { name: 'Calibration protocol' })

    for (const leak of ['repeat_of_id', 'HIDDEN_REPEAT', 'membership_id', 'group_name']) {
      expect(document.body.textContent).not.toContain(leak)
      expect(document.body.innerHTML).not.toContain(leak)
    }
  })
})
