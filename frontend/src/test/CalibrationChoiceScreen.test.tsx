import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { CalibrationChoiceScreen } from '../pages/CalibrationChoiceScreen'
import type { Access, EnrollmentSummary, Program } from '../api/types'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('axios', () => ({
  default: { create: () => ({ get }), isAxiosError: () => false },
}))

const revealed: EnrollmentSummary = {
  id: 'e1',
  program_id: 'p1',
  reviewer_id: 'r1',
  revealed: true,
  has_started: true,
  total_presentations: 3,
  blotter_complete: 3,
  skin_planned: 0,
  skin_complete: 0,
  program_name: 'Baseline',
  program_version: '1',
  group_name_summary: 'Baseline',
}
const activeBaseline: Program = { id: 'p2', name: 'Baseline round two', version: '1', status: 'active' }
const activeRetest: Program = { id: 'p3', name: 'Skin retest round', version: '1', status: 'active' }

function membersFor(programId: string, groupName: string) {
  return [{ id: `m-${programId}`, group_name: groupName }]
}

beforeEach(() => {
  vi.clearAllMocks()
  get.mockImplementation((path: string) => {
    if (path === '/calibration/programs/p2/members')
      return Promise.resolve({ data: membersFor('p2', 'Baseline') })
    if (path === '/calibration/programs/p3/members')
      return Promise.resolve({ data: membersFor('p3', 'Skin Retest') })
    return Promise.reject(new Error(`Unexpected request: ${path}`))
  })
})

describe('CalibrationChoiceScreen', () => {
  it('shows self-assign buttons for a manager with open programs', async () => {
    const access: Access = { username: 'manager', manager: true }
    render(
      <CalibrationChoiceScreen
        assignments={[revealed]}
        programs={[activeBaseline, activeRetest]}
        access={access}
        navigate={vi.fn()}
        onBrowse={vi.fn()}
      />
    )
    expect(await screen.findByRole('button', { name: /Start a new full baseline/ })).toBeInTheDocument()
    expect(
      await screen.findByRole('button', { name: /Redo "Skin Retest"/ })
    ).toBeInTheDocument()
  })

  it('shows nothing-new messaging for a non-manager', async () => {
    const access: Access = { username: 'family-member', manager: false }
    render(
      <CalibrationChoiceScreen
        assignments={[revealed]}
        programs={[activeBaseline, activeRetest]}
        access={access}
        navigate={vi.fn()}
        onBrowse={vi.fn()}
      />
    )
    expect(
      await screen.findByText('Nothing new is assigned right now.')
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Start a new full baseline/ })).not.toBeInTheDocument()
    expect(
      await screen.findByRole('button', { name: /Browse assignments manually instead/ })
    ).toBeInTheDocument()
  })

  it('keeps a successful candidate and surfaces an error when another candidate lookup rejects', async () => {
    const access: Access = { username: 'manager', manager: true }
    get.mockImplementation((path: string) => {
      if (path === '/calibration/programs/p2/members')
        return Promise.resolve({ data: membersFor('p2', 'Baseline') })
      if (path === '/calibration/programs/p3/members')
        return Promise.reject({ isAxiosError: true, response: { status: 403 } })
      return Promise.reject(new Error(`Unexpected request: ${path}`))
    })
    render(
      <CalibrationChoiceScreen
        assignments={[revealed]}
        programs={[activeBaseline, activeRetest]}
        access={access}
        navigate={vi.fn()}
        onBrowse={vi.fn()}
      />
    )
    expect(
      await screen.findByRole('button', { name: /Start a new full baseline/ })
    ).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Redo "Skin Retest"/ })).not.toBeInTheDocument()
  })

  it('excludes a program the identity is already enrolled in', async () => {
    const access: Access = { username: 'manager', manager: true }
    render(
      <CalibrationChoiceScreen
        assignments={[revealed, { ...revealed, id: 'e2', program_id: 'p2' }]}
        programs={[activeBaseline, activeRetest]}
        access={access}
        navigate={vi.fn()}
        onBrowse={vi.fn()}
      />
    )
    await waitFor(() => expect(get).toHaveBeenCalledWith('/calibration/programs/p3/members'))
    expect(screen.queryByRole('button', { name: /Start a new full baseline/ })).not.toBeInTheDocument()
  })
})
