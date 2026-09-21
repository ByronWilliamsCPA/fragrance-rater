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

beforeEach(() => {
  vi.clearAllMocks()
  window.history.replaceState({}, '', '/evidence')
  get.mockImplementation((path: string) => {
    const responses: Record<string, unknown> = {
      '/reviewers': [{ id: 'r', name: 'Evaluator' }],
      '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1' }],
      '/calibration/access': { username: 'family-member', manager: false },
      '/calibration/enrollments': [],
    }
    return path in responses
      ? Promise.resolve({ data: responses[path] })
      : Promise.reject(new Error(`Unexpected request: ${path}`))
  })
  post.mockResolvedValue({ data: { id: 'saved' } })
  patch.mockResolvedValue({ data: { id: 'updated' } })
})

describe('Evidence page', () => {
  it('presents qualified evidence for buyers and sellers', async () => {
    render(<App />)

    expect(
      await screen.findByRole('heading', { name: 'Why better fragrance discovery matters' })
    ).toBeInTheDocument()
    expect(screen.getByText('For fragrance buyers')).toBeInTheDocument()
    expect(screen.getByText('For makers and sellers')).toBeInTheDocument()
    expect(screen.getByText('What we still have to prove')).toBeInTheDocument()
    expect(screen.getByText(/not performance claims about this application/)).toBeInTheDocument()
    expect(screen.getByText('A claim the evidence can support')).toBeInTheDocument()
    expect(
      screen.getByText(/Physical product sampling can increase trial and sales/)
    ).toBeInTheDocument()
  })

  it('links every displayed figure to a named source with a limitation', async () => {
    render(<App />)
    await screen.findByRole('heading', { name: 'Why better fragrance discovery matters' })

    const sourceSection = screen
      .getByRole('heading', { name: 'Sources, uses, and limits' })
      .closest('section')
    expect(sourceSection).not.toBeNull()
    expect(within(sourceSection!).getAllByRole('link')).toHaveLength(7)
    expect(within(sourceSection!).getAllByText('Limit:')).toHaveLength(7)
  })

  it('links each headline stat to its own named source, not a neighboring one', async () => {
    render(<App />)
    await screen.findByRole('heading', { name: 'Why better fragrance discovery matters' })

    const snapshotSection = screen
      .getByRole('heading', { name: 'What the available data says' })
      .closest('section')
    expect(snapshotSection).not.toBeNull()

    const statLinkHrefs = within(snapshotSection!)
      .getAllByRole('link', { name: 'Source and scope' })
      .map((link) => link.getAttribute('href'))

    expect(statLinkHrefs).toEqual([
      'https://nielseniq.com/global/en/insights/commentary/2024/beauty-2024-mid-year-update/',
      'https://www.circana.com/post/us-prestige-beauty-industry-sales-grow-by-8-in-the-first-half-circana-reports',
      'https://doi.org/10.1287/mnsc.2020.00902',
      'https://www.odore.com/case-studies/ysl-product-sampling',
      'https://doi.org/10.1371/journal.pone.0033810',
    ])
  })

  it('discloses that the generated reports’ headline regret and repurchase figures are unsupported', async () => {
    render(<App />)
    await screen.findByRole('heading', { name: 'Why better fragrance discovery matters' })

    expect(
      screen.getByText(/The generated reports.*86% less regret.*3\.2\D?\s?repurchase.*unsupported/)
    ).toBeInTheDocument()
  })

  it('cross-links back to the methodology page', async () => {
    render(<App />)
    await screen.findByRole('heading', { name: 'Why better fragrance discovery matters' })

    const link = screen.getByRole('link', { name: 'How this project learns your taste' })
    expect(link).toHaveAttribute('href', '/about')
    fireEvent.click(link)

    expect(
      await screen.findByRole('heading', { name: 'How this project learns your taste' })
    ).toBeInTheDocument()
  })

  it('is available from the footer without entering primary task navigation', async () => {
    window.history.replaceState({}, '', '/')
    render(<App />)

    const link = await screen.findByRole('link', { name: 'Evidence behind the approach' })
    expect(link).toHaveAttribute('href', '/evidence')
    expect(
      within(screen.getByRole('navigation', { name: 'Main navigation' })).queryByText('Evidence')
    ).not.toBeInTheDocument()

    fireEvent.click(link)
    expect(
      await screen.findByRole('heading', { name: 'Why better fragrance discovery matters' })
    ).toBeInTheDocument()
  })
})
