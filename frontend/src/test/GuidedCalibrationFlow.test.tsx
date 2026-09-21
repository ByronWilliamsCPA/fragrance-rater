import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { nextWizardStep, GuidedCalibrationFlow } from '../pages/GuidedCalibrationFlow'
import type { Enrollment } from '../api/types'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('axios', () => ({
  default: { create: () => ({ get, post }), isAxiosError: () => false },
}))

function baseEnrollment(overrides: Partial<Enrollment> = {}): Enrollment {
  return {
    id: 'e1',
    program_id: 'p1',
    reviewer_id: 'r1',
    revealed: false,
    reveal_eligible: false,
    reveal_blocker: 'SKIN_PLAN',
    skin_plan_locked: false,
    presentations: [
      {
        id: 's1',
        session_id: 'sess1',
        blind_code: 'AAA1',
        position: 1,
        skin_planned: false,
        blotter_locked: false,
        skin_locked: false,
        observations: [],
      },
    ],
    ...overrides,
  }
}

describe('nextWizardStep', () => {
  it('starts at the skin-plan decision before it is locked', () => {
    expect(nextWizardStep(baseEnrollment())).toEqual({ kind: 'skin_plan' })
  })

  it('moves to the first unlocked blotter sample once the plan is locked', () => {
    const enrollment = baseEnrollment({ skin_plan_locked: true })
    expect(nextWizardStep(enrollment)).toEqual({ kind: 'blotter', presentationId: 's1' })
  })

  it('moves to a planned, unlocked skin sample once blotter is locked', () => {
    const enrollment = baseEnrollment({
      skin_plan_locked: true,
      presentations: [
        {
          id: 's1',
          session_id: 'sess1',
          blind_code: 'AAA1',
          position: 1,
          skin_planned: true,
          blotter_locked: true,
          skin_locked: false,
          observations: [],
        },
      ],
    })
    expect(nextWizardStep(enrollment)).toEqual({ kind: 'skin', presentationId: 's1' })
  })

  it('reaches ready_to_reveal once everything required is locked', () => {
    const enrollment = baseEnrollment({
      skin_plan_locked: true,
      presentations: [
        {
          id: 's1',
          session_id: 'sess1',
          blind_code: 'AAA1',
          position: 1,
          skin_planned: false,
          blotter_locked: true,
          skin_locked: false,
          observations: [],
        },
      ],
    })
    expect(nextWizardStep(enrollment)).toEqual({ kind: 'ready_to_reveal' })
  })

  it('finishes all blotter locks before any skin step, even when another sample is skin-ready', () => {
    const enrollment = baseEnrollment({
      skin_plan_locked: true,
      presentations: [
        {
          id: 's1',
          session_id: 'sess1',
          blind_code: 'AAA1',
          position: 1,
          skin_planned: true,
          blotter_locked: true,
          skin_locked: false,
          observations: [],
        },
        {
          id: 's2',
          session_id: 'sess1',
          blind_code: 'AAA2',
          position: 2,
          skin_planned: false,
          blotter_locked: false,
          skin_locked: false,
          observations: [],
        },
      ],
    })
    expect(nextWizardStep(enrollment)).toEqual({ kind: 'blotter', presentationId: 's2' })
  })
})

describe('GuidedCalibrationFlow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    get.mockResolvedValue({ data: baseEnrollment() })
    post.mockResolvedValue({ data: {} })
  })

  it('shows the step-of-total orientation and an escape hatch', async () => {
    render(
      <GuidedCalibrationFlow enrollmentId="e1" onExitToManualBrowse={vi.fn()} />
    )
    await waitFor(() => expect(get).toHaveBeenCalledWith('/calibration/enrollments/e1'))
    expect(await screen.findByText(/Step 1 of/)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Browse assignments manually instead' })
    ).toBeInTheDocument()
  })

  it('calls onExitToManualBrowse when the escape hatch is clicked', async () => {
    const onExit = vi.fn()
    render(<GuidedCalibrationFlow enrollmentId="e1" onExitToManualBrowse={onExit} />)
    await screen.findByText(/Step 1 of/)
    screen.getByRole('button', { name: 'Browse assignments manually instead' }).click()
    expect(onExit).toHaveBeenCalled()
  })
})
