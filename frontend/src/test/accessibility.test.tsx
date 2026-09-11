import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from '../App'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))

vi.mock('axios', () => ({
  default: { create: () => ({ get, post }), isAxiosError: () => false },
}))

function expectAccessibleControls() {
  for (const control of document.querySelectorAll('input, select, textarea'))
    expect((control as HTMLInputElement).labels?.length, control.outerHTML).toBeGreaterThan(0)

  for (const action of document.querySelectorAll('button, a[href]'))
    expect(action.textContent?.trim(), action.outerHTML).not.toBe('')

  const ids = [...document.querySelectorAll('[id]')].map((element) => element.id)
  expect(new Set(ids).size).toBe(ids.length)
}

beforeEach(() => {
  vi.clearAllMocks()
  window.history.replaceState({}, '', '/calibration')
  get.mockImplementation((path: string) => {
    const responses: Record<string, unknown> = {
      '/reviewers': [{ id: 'r', name: 'Evaluator' }],
      '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1', status: 'active' }],
      '/calibration/access': { username: 'family-member', manager: false },
      '/calibration/enrollments': [{ id: 'assignment', program_id: 'p', reviewer_id: 'r' }],
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
})
