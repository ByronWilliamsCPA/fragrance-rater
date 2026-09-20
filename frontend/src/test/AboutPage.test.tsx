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
  window.history.replaceState({}, '', '/about')
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

describe('About / Methodology page', () => {
  it('renders the About page heading when navigating directly to /about and stays out of primary nav', async () => {
    render(<App />)

    expect(
      await screen.findByRole('heading', { name: 'How this project learns your taste' })
    ).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'About' })).not.toBeInTheDocument()
  })

  it('includes all the major section headings and the collapsed technical methodology summary', async () => {
    render(<App />)
    await screen.findByRole('heading', { name: 'How this project learns your taste' })

    for (const heading of [
      'Where the idea came from',
      'Why fragrance is harder',
      'How calibration works',
      'Why repeats matter',
      'Prediction, not memorization',
      'What happens after calibration',
      'What this is not',
    ])
      expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument()

    expect(screen.getByText('Technical methodology')).toBeInTheDocument()
  })

  it('keeps the technical methodology details collapsed until its summary is clicked', async () => {
    render(<App />)
    await screen.findByRole('heading', { name: 'How this project learns your taste' })

    const summary = screen.getByText('Technical methodology')
    const details = summary.closest('details')
    expect(details).not.toBeNull()
    expect(details?.open).toBeFalsy()
    expect(screen.queryByText(/33 unique fragrances/)).not.toBeVisible()

    fireEvent.click(summary)

    expect(details?.open).toBeTruthy()
    expect(screen.getByText(/33 unique fragrances/)).toBeVisible()
  })

  it('navigates from the footer link on another page without a full page reload', async () => {
    window.history.replaceState({}, '', '/calibration')
    render(<App />)

    const footerLink = await screen.findByRole('link', { name: 'About this project' })
    expect(footerLink).toHaveAttribute('href', '/about')
    fireEvent.click(footerLink)

    expect(
      await screen.findByRole('heading', { name: 'How this project learns your taste' })
    ).toBeInTheDocument()
  })

  it('cross-links to the calibration protocol page from "How calibration works"', async () => {
    render(<App />)
    await screen.findByRole('heading', { name: 'How this project learns your taste' })

    const link = screen.getByRole('link', { name: 'Read the calibration protocol' })
    expect(link).toHaveAttribute('href', '/calibration/protocol')
    fireEvent.click(link)

    expect(
      await screen.findByRole('heading', { name: 'Calibration protocol' })
    ).toBeInTheDocument()
  })

  it('never leaks experimental-control identifiers into the static page', async () => {
    render(<App />)
    await screen.findByRole('heading', { name: 'How this project learns your taste' })

    for (const leak of ['repeat_of_id', 'HIDDEN_REPEAT', 'membership_id', 'group_name']) {
      expect(document.body.textContent).not.toContain(leak)
      expect(document.body.innerHTML).not.toContain(leak)
    }
  })
})
