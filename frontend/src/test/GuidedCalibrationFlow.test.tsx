import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
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
    const enrollment = baseEnrollment({ skin_plan_locked: true, reveal_blocker: 'BLOTTER' })
    expect(nextWizardStep(enrollment)).toEqual({ kind: 'blotter', presentationId: 's1' })
  })

  it('moves to a planned, unlocked skin sample once blotter is locked', () => {
    const enrollment = baseEnrollment({
      skin_plan_locked: true,
      reveal_blocker: 'SKIN',
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
      reveal_blocker: null,
      reveal_eligible: true,
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
      reveal_blocker: 'BLOTTER',
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

  it('defers to the server reveal_blocker over locally-derived lock state, so a still-unlocked HOLDOUT blotter does not block reveal', () => {
    // Simulates a HOLDOUT-shaped enrollment: baseline/repeat blotters locked,
    // skin plan locked, but one presentation's blotter (the holdout's, which
    // the frontend cannot identify as such because `Sample` withholds
    // `role`) is still unlocked. The backend's reveal_blocker excludes
    // HOLDOUT from the BLOTTER gate (calibration_service.py:505-521), so it
    // reports ready even though a presentation's blotter is unlocked. The
    // wizard must follow that authoritative signal, not the lock-derived
    // answer, or it will steer the participant into locking (and later
    // disclosing) the holdout early.
    const enrollment = baseEnrollment({
      skin_plan_locked: true,
      reveal_blocker: null,
      reveal_eligible: true,
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
    })
    expect(nextWizardStep(enrollment)).toEqual({ kind: 'ready_to_reveal' })
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
      <GuidedCalibrationFlow
        enrollmentId="e1"
        onExitToManualBrowse={vi.fn()}
        onRevealed={vi.fn()}
      />
    )
    await waitFor(() => expect(get).toHaveBeenCalledWith('/calibration/enrollments/e1'))
    expect(await screen.findByText(/Step 1 of/)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Browse assignments manually instead' })
    ).toBeInTheDocument()
  })

  it('calls onExitToManualBrowse when the escape hatch is clicked', async () => {
    const onExit = vi.fn()
    render(
      <GuidedCalibrationFlow
        enrollmentId="e1"
        onExitToManualBrowse={onExit}
        onRevealed={vi.fn()}
      />
    )
    await screen.findByText(/Step 1 of/)
    screen.getByRole('button', { name: 'Browse assignments manually instead' }).click()
    expect(onExit).toHaveBeenCalled()
  })

  it('shows the pre-load loading state and escape hatch while the enrollment fetch is in flight', async () => {
    const deferred = (() => {
      let resolve!: (value: { data: Enrollment }) => void
      const promise = new Promise<{ data: Enrollment }>((complete) => {
        resolve = complete
      })
      return { promise, resolve }
    })()
    get.mockReturnValueOnce(deferred.promise)
    const onExit = vi.fn()
    render(
      <GuidedCalibrationFlow
        enrollmentId="e1"
        onExitToManualBrowse={onExit}
        onRevealed={vi.fn()}
      />
    )

    expect(
      await screen.findByRole('button', { name: 'Browse assignments manually instead' })
    ).toBeInTheDocument()
    expect(screen.getByText(/Loading/)).toBeInTheDocument()

    deferred.resolve({ data: baseEnrollment() })
    await screen.findByText(/Step 1 of/)
  })

  it('shows a completion state and calls onRevealed after a successful reveal', async () => {
    const revealed = baseEnrollment({
      skin_plan_locked: true,
      revealed: true,
      reveal_blocker: null,
      reveal_eligible: true,
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
          identity: {
            fragrance_id: 'f1',
            name: 'Signature',
            brand: 'House',
            concentration: 'EDP',
          },
        },
      ],
    })
    get.mockResolvedValueOnce({
      data: baseEnrollment({
        skin_plan_locked: true,
        reveal_blocker: null,
        reveal_eligible: true,
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
      }),
    })
    get.mockResolvedValueOnce({ data: revealed })
    const onRevealed = vi.fn().mockResolvedValue(undefined)
    render(
      <GuidedCalibrationFlow
        enrollmentId="e1"
        onExitToManualBrowse={vi.fn()}
        onRevealed={onRevealed}
      />
    )

    const revealButton = await screen.findByRole('button', {
      name: 'Reveal completed baseline',
    })
    fireEvent.click(revealButton)
    const confirmButton = await screen.findByRole('button', { name: 'Confirm reveal' })
    fireEvent.click(confirmButton)

    await waitFor(() => expect(onRevealed).toHaveBeenCalled())
    expect(await screen.findByText(/Reveal complete/)).toBeInTheDocument()
    expect(screen.getByText(/House.*Signature.*EDP/)).toBeInTheDocument()
    expect(onRevealed).toHaveBeenCalled()
  })
})
