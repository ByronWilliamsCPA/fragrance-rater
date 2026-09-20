import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { navigationItems } from '../routing/routes'

/**
 * WCAG 2.4.2 Page Titled.
 *
 * Before this design pass every route reported the static title from
 * index.html, because nothing in a pushState application updates it. axe-core
 * cannot catch that: a title was present, it was simply the same one six
 * times. These are real, bookmarkable URLs a family member can keep open in
 * several tabs at once, and a screen-reader user relies on the title changing
 * as confirmation that navigation happened at all.
 */

const { get, post, patch } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}))

vi.mock('axios', () => ({
  default: { create: () => ({ get, post, patch }), isAxiosError: () => false },
}))

function mockBootstrap(manager: boolean) {
  get.mockImplementation((path: string) => {
    const responses: Record<string, unknown> = {
      '/reviewers': [{ id: 'r', name: 'Evaluator' }],
      '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1', status: 'active' }],
      '/calibration/access': { username: 'family-member', manager },
      '/calibration/enrollments': [],
      '/evaluations': [],
    }
    return Promise.resolve({ data: responses[path] })
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  document.title = 'Fragrance Rater'
  mockBootstrap(true)
})

describe('every route has a distinct, descriptive document title', () => {
  it.each(navigationItems.map((item) => [item.path, item.documentTitle] as const))(
    '%s is titled "%s"',
    async (path, documentTitle) => {
      window.history.replaceState({}, '', path)
      render(<App />)

      await screen.findByRole('heading', { name: 'Fragrance Rater' })
      await waitFor(() => {
        expect(document.title).toBe(`${documentTitle} · Fragrance Rater`)
      })
    }
  )

  it('gives no two routes the same title', () => {
    const titles = navigationItems.map((item) => item.documentTitle)
    expect(new Set(titles).size).toBe(titles.length)
  })

  it('updates the title when navigating without a reload', async () => {
    window.history.replaceState({}, '', '/')
    render(<App />)

    await screen.findByRole('heading', { name: 'Fragrance Rater' })
    await waitFor(() => expect(document.title).toBe('Home · Fragrance Rater'))

    fireEvent.click(screen.getByRole('link', { name: 'My Ratings' }))

    await waitFor(() => expect(document.title).toBe('My ratings · Fragrance Rater'))
  })

  it('leaves a modified click (e.g. cmd/ctrl-click to open in a new tab) to the browser', async () => {
    window.history.replaceState({}, '', '/')
    render(<App />)

    await screen.findByRole('heading', { name: 'Fragrance Rater' })
    await waitFor(() => expect(document.title).toBe('Home · Fragrance Rater'))

    fireEvent.click(screen.getByRole('link', { name: 'My Ratings' }), { metaKey: true })

    // A real modified click never reaches our handler's navigate() call, so
    // the SPA stays on its current route instead of switching client-side.
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(document.title).toBe('Home · Fragrance Rater')
  })
})
