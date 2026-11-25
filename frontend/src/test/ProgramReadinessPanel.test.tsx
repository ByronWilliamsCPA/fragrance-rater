import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { ProgramReadinessPanel } from '../pages/ProgramReadinessPanel'
import type { Enrollment, EnrollmentReadiness, Program, ProgramReadiness } from '../api/types'

const { get, post, put } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn() }))
vi.mock('axios', () => ({
  default: { create: () => ({ get, post, put }), isAxiosError: () => false },
}))

const program: Program = {
  id: 'p1',
  name: 'Family baseline',
  version: 'v1',
  status: 'active',
  reveal_policy: 'HOUSEHOLD',
}

function row(overrides: Partial<EnrollmentReadiness>): EnrollmentReadiness {
  return {
    enrollment_id: 'e1',
    reviewer_id: 'r1',
    reviewer_name: 'Evaluator One',
    checkpoint_count: 0,
    checkpoint_blocker: null,
    reveal_blocker: 'CHECKPOINT',
    revealed: false,
    ...overrides,
  }
}

function readiness(overrides: Partial<ProgramReadiness> = {}): ProgramReadiness {
  return {
    program_id: 'p1',
    reveal_policy: 'HOUSEHOLD',
    household_reveal_ready: false,
    household_revealed: false,
    enrollments: [
      row({}),
      row({
        enrollment_id: 'e2',
        reviewer_id: 'r2',
        reviewer_name: 'Evaluator Two',
        checkpoint_blocker: 'BLOTTER',
        reveal_blocker: 'BLOTTER',
      }),
    ],
    ...overrides,
  }
}

function renderPanel(target: Program = program) {
  const reload = vi.fn().mockResolvedValue(undefined)
  render(<ProgramReadinessPanel program={target} reload={reload} />)
  return reload
}

describe('ProgramReadinessPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    get.mockResolvedValue({ data: readiness() })
    post.mockResolvedValue({ data: {} })
    put.mockResolvedValue({ data: {} })
  })

  it('lists each evaluator with checkpoint and reveal readiness', async () => {
    renderPanel()
    const table = await screen.findByRole('table', { name: 'Checkpoint and reveal readiness' })
    expect(get).toHaveBeenCalledWith('/calibration/programs/p1/readiness')
    expect(within(table).getByText('Ready for a checkpoint')).toBeInTheDocument()
    expect(within(table).getByText('Checkpoint not frozen')).toBeInTheDocument()
    expect(within(table).getAllByText('Blotter responses remain')).toHaveLength(2)
    expect(document.body.textContent).not.toMatch(/holdout/i)
  })

  it('freezes checkpoints and reports who was not ready', async () => {
    post.mockResolvedValue({
      data: {
        program_id: 'p1',
        algorithm_version: 'v',
        created: [
          {
            enrollment_id: 'e1',
            checkpoint_id: 'c1',
            predictions_frozen: 9,
            predictions_skipped: 0,
          },
        ],
        skipped: [{ enrollment_id: 'e2', reason: 'BLOTTER' }],
      },
    })
    renderPanel()

    fireEvent.click(await screen.findByRole('button', { name: 'Freeze checkpoints' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm checkpoints' }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/calibration/programs/p1/checkpoints', {
        algorithm_version: null,
        freeze_predictions: true,
      })
    )
    expect(
      await screen.findByText(
        'Froze 1 checkpoint(s). Not ready: Evaluator Two (Blotter responses remain).'
      )
    ).toBeInTheDocument()
  })

  it('disables checkpoint freezing when nobody is ready for one', async () => {
    get.mockResolvedValue({
      data: readiness({
        enrollments: [row({ checkpoint_count: 1, reveal_blocker: 'HOLDOUT' })],
      }),
    })
    renderPanel()

    await screen.findByText('Frozen')
    expect(screen.getByRole('button', { name: 'Freeze checkpoints' })).toBeDisabled()
  })

  it('offers the household reveal only once the household is ready', async () => {
    renderPanel()
    expect(await screen.findByRole('button', { name: 'Reveal the household' })).toBeDisabled()
  })

  it('reveals the household when it is ready', async () => {
    get.mockResolvedValue({
      data: readiness({
        household_reveal_ready: true,
        enrollments: [row({ checkpoint_count: 1, reveal_blocker: null })],
      }),
    })
    renderPanel()

    fireEvent.click(await screen.findByRole('button', { name: 'Reveal the household' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm household reveal' }))

    await waitFor(() => expect(post).toHaveBeenCalledWith('/calibration/programs/p1/reveal'))
    expect(await screen.findByText(/The household is revealed/)).toBeInTheDocument()
  })

  it('has no household reveal for a program that reveals each evaluator separately', async () => {
    get.mockResolvedValue({ data: readiness({ reveal_policy: 'ENROLLMENT' }) })
    renderPanel({ ...program, reveal_policy: 'ENROLLMENT' })

    await screen.findByRole('button', { name: 'Freeze checkpoints' })
    expect(screen.queryByRole('button', { name: 'Reveal the household' })).not.toBeInTheDocument()
    expect(screen.getByText(/each evaluator separately/)).toBeInTheDocument()
  })

  it('saves the reveal policy while the program is a draft', async () => {
    const reload = renderPanel({ ...program, status: 'draft', reveal_policy: 'ENROLLMENT' })

    fireEvent.change(await screen.findByLabelText('Reveal policy'), {
      target: { value: 'HOUSEHOLD' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save reveal policy' }))

    await waitFor(() =>
      expect(put).toHaveBeenCalledWith('/calibration/programs/p1/reveal-policy', {
        reveal_policy: 'HOUSEHOLD',
      })
    )
    await waitFor(() => expect(reload).toHaveBeenCalled())
  })

  it('builds the evaluator-by-session progress matrix on request', async () => {
    const sample = (id: string, sessionId: string, extra: object = {}) => ({
      id,
      session_id: sessionId,
      blind_code: id,
      position: 1,
      skin_planned: false,
      blotter_locked: false,
      skin_locked: false,
      post_reveal_entry: false,
      available: true,
      observations: [],
      ...extra,
    })
    const detail = {
      id: 'e1',
      presentations: [
        sample('a', 's1', { blotter_locked: true }),
        sample('b', 's2', { blotter_locked: true }),
        sample('c', 's2'),
        sample('d', 's3', { available: false }),
      ],
    } as unknown as Enrollment
    get.mockImplementation((url: string) =>
      Promise.resolve({
        data: url.includes('/readiness') ? readiness({ enrollments: [row({})] }) : detail,
      })
    )
    renderPanel()

    fireEvent.click(await screen.findByRole('button', { name: 'Show session progress' }))

    const matrix = await screen.findByRole('table', { name: 'Progress by evaluator and session' })
    expect(get).toHaveBeenCalledWith('/calibration/enrollments/e1')
    const cells = within(matrix)
      .getAllByRole('cell')
      .map((cell) => cell.textContent)
    expect(cells).toEqual(['Done', '1 of 2', 'Not open'])
  })
})
