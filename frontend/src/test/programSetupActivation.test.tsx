import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Program } from '../api/types'
import { ProgramSetupPage } from '../pages/ProgramSetupPage'

const { get, post, put } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn() }))

vi.mock('../api/client', () => ({
  api: { get, post, put },
  requestErrorMessage: () => 'Request failed.',
}))

const member = (id: string) => ({
  id,
  fragrance_id: `f-${id}`,
  fragrance_name: `Name ${id}`,
  fragrance_brand: 'House',
  concentration: 'EDT',
  version_key: 'edt-current-2026',
  role: 'UNIVERSAL_BASELINE',
  repeat_of_id: null,
  group_name: 'Baseline',
  identity_evidence: 'Verified',
  fragella: null,
})

function renderPage(program: Program, reload = vi.fn(() => Promise.resolve())) {
  render(
    <ProgramSetupPage
      programs={[program]}
      reviewers={[]}
      reload={reload}
      navigate={vi.fn()}
      initialProgramId={program.id}
    />
  )
  return reload
}

const draft: Program = {
  id: 'p',
  name: 'Pilot',
  version: '3',
  status: 'draft',
  reveal_policy: 'HOUSEHOLD',
}

beforeEach(() => {
  vi.clearAllMocks()
  get.mockImplementation((path: string) =>
    Promise.resolve({
      data: path === '/calibration/programs/p/members' ? [member('a'), member('b')] : [],
    })
  )
  post.mockResolvedValue({ data: {} })
  put.mockResolvedValue({ data: {} })
})

describe('advanced setup: reveal policy before activation', () => {
  it('offers the reveal policy in the Definition section for a draft and saves a change', async () => {
    const reload = renderPage(draft)
    const select = await screen.findByLabelText('Reveal policy for this program')
    expect(select).toHaveValue('HOUSEHOLD')

    fireEvent.change(select, { target: { value: 'ENROLLMENT' } })

    await waitFor(() =>
      expect(put).toHaveBeenCalledWith('/calibration/programs/p/reveal-policy', {
        reveal_policy: 'ENROLLMENT',
      })
    )
    await waitFor(() => expect(reload).toHaveBeenCalled())
  })

  it('shows the readiness panel policy as text only, so it is decided in one place', async () => {
    renderPage(draft)
    await screen.findByLabelText('Reveal policy for this program')
    expect(screen.queryByLabelText('Reveal policy')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Save reveal policy' })).toBeNull()
  })

  it('shows the policy as locked, with no control, once the program is active', async () => {
    renderPage({ ...draft, status: 'active' })
    expect(await screen.findByText(/It was locked when the program was activated/)).toBeVisible()
    expect(screen.queryByLabelText('Reveal policy for this program')).toBeNull()
  })
})

describe('advanced setup: activation warning', () => {
  it('names the permanence, the reveal policy and the members, and posts only on confirm', async () => {
    renderPage(draft)
    await screen.findAllByText('Verified')
    fireEvent.click(screen.getByRole('button', { name: 'Activate and lock definition' }))

    const group = screen.getByRole('group', { name: 'Confirm Activate and lock definition' })
    expect(group).toHaveTextContent('permanent and cannot be undone')
    expect(group).toHaveTextContent('"Pilot" (version 3)')
    expect(group).toHaveTextContent('whole household together, after the final samples')
    expect(group).toHaveTextContent('all 2 exact versions')
    expect(post).not.toHaveBeenCalledWith('/calibration/programs/p/activate')

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(post).not.toHaveBeenCalledWith('/calibration/programs/p/activate')

    fireEvent.click(screen.getByRole('button', { name: 'Activate and lock definition' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm activation' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/calibration/programs/p/activate'))
  })

  it('uses the policy of the program as it now stands', async () => {
    renderPage({ ...draft, reveal_policy: 'ENROLLMENT' })
    await screen.findAllByText('Verified')
    fireEvent.click(screen.getByRole('button', { name: 'Activate and lock definition' }))
    expect(screen.getByRole('group')).toHaveTextContent('reveal policy (each evaluator separately)')
  })
})
