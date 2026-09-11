import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from '../App'
const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('axios', () => ({ default: { create: () => ({ get, post }), isAxiosError: () => false } }))
const enrollment = {
  id: 'assignment',
  program_id: 'p',
  reviewer_id: 'r',
  revealed: false,
  skin_plan_locked: false,
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
  get.mockImplementation((path: string) =>
    Promise.resolve({
      data:
        path === '/reviewers'
          ? [{ id: 'r', name: 'Evaluator' }]
          : path === '/calibration/programs'
            ? [{ id: 'p', name: 'Baseline', version: '1' }]
            : path === '/calibration/access'
              ? { manager: false }
              : path === '/calibration/enrollments'
                ? [{ id: 'assignment', program_id: 'p', reviewer_id: 'r' }]
                : enrollment,
    })
  )
  post.mockResolvedValue({ data: { id: 'saved' } })
})
describe('Calibration participant workflow', () => {
  it('shows the application and hides manager setup for an evaluator', async () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Fragrance Rater' })).toBeInTheDocument()
    await screen.findByRole('option', { name: 'Evaluator · Baseline' })
    expect(screen.queryByRole('button', { name: 'Program setup' })).not.toBeInTheDocument()
  })
  it('submits non-detection with zero intensity and null liking', async () => {
    render(<App />)
    await screen.findByRole('option', { name: 'Evaluator · Baseline' })
    fireEvent.change(screen.getByLabelText('Evaluator and program'), {
      target: { value: 'assignment' },
    })
    fireEvent.click(await screen.findByRole('button', { name: /A82F/ }))
    fireEvent.change(screen.getByLabelText('Detected'), { target: { value: 'no' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save observation' }))
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/calibration/presentations/sample/observations',
        expect.objectContaining({ detected: false, intensity: 0, liking: null })
      )
    )
  })
  it('offers new ordinary encounters without replacing history', async () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'My Ratings' }))
    expect(screen.getByRole('button', { name: 'Save new encounter' })).toBeInTheDocument()
    await screen.findByRole('option', { name: 'Evaluator' })
  })
})
