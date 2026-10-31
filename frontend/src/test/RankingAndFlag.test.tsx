import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { RankingStep } from '../pages/RankingStep'
import { FlagProblem, flagReasons } from '../pages/FlagProblem'
import type { Enrollment, Observation, Sample } from '../api/types'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('axios', () => ({
  default: { create: () => ({ get, post }), isAxiosError: () => false },
}))

function detected(id: string, position: number, detectedValue = true): Sample {
  return {
    id,
    session_id: 'sess1',
    blind_code: `C${position}`,
    position,
    skin_planned: false,
    blotter_locked: true,
    skin_locked: false,
    post_reveal_entry: false,
    observations: [
      {
        id: `${id}-o`,
        stage: 'BLOTTER',
        phase: 'PRE_REVEAL',
        detected: detectedValue,
        response_status: detectedValue ? 'completed' : 'not_detected',
      } as Observation,
    ],
  }
}

const task = {
  busy: false,
  run: async (work: () => Promise<void>) => {
    try {
      await work()
    } catch {
      /* surfaced through task.error in the app */
    }
  },
  setNotice: vi.fn(),
} as never

function enrollmentOf(samples: Sample[]) {
  return { id: 'e1', presentations: samples } as unknown as Enrollment
}

describe('RankingStep', () => {
  beforeEach(() => {
    get.mockReset()
    post.mockReset()
    get.mockResolvedValue({ data: [] })
    post.mockResolvedValue({ data: {} })
  })

  it('ranks only the detected samples and saves the evaluator order, ties included', async () => {
    const onDone = vi.fn()
    render(
      <RankingStep
        enrollment={enrollmentOf([
          detected('a', 1),
          detected('b', 2),
          detected('c', 3),
          detected('d', 4, false),
        ])}
        task={task}
        onDone={onDone}
      />
    )

    const selects = await screen.findAllByRole('combobox')
    expect(selects).toHaveLength(3)
    fireEvent.change(selects[0], { target: { value: '1' } })
    fireEvent.change(selects[1], { target: { value: '1' } })
    fireEvent.change(selects[2], { target: { value: '3' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save ranking' }))

    await waitFor(() => expect(onDone).toHaveBeenCalled())
    expect(post).toHaveBeenCalledWith('/calibration/sessions/sess1/rankings', {
      stage: 'BLOTTER',
      response_status: 'completed',
      entries: [
        { presentation_id: 'a', rank_position: 1 },
        { presentation_id: 'b', rank_position: 1 },
        { presentation_id: 'c', rank_position: 3 },
      ],
    })
  })

  it('will not save an invalid ranking and says why', async () => {
    render(
      <RankingStep
        enrollment={enrollmentOf([detected('a', 1), detected('b', 2)])}
        task={task}
        onDone={vi.fn()}
      />
    )
    const selects = await screen.findAllByRole('combobox')
    fireEvent.change(selects[0], { target: { value: '2' } })
    fireEvent.change(selects[1], { target: { value: '2' } })

    expect(screen.getByRole('alert')).toHaveTextContent(/places must run/i)
    expect(screen.getByRole('button', { name: 'Save ranking' })).toBeDisabled()
    expect(post).not.toHaveBeenCalled()
  })

  it('records a refusal to rank as skipped, with no entries', async () => {
    const onDone = vi.fn()
    render(
      <RankingStep
        enrollment={enrollmentOf([detected('a', 1), detected('b', 2)])}
        task={task}
        onDone={onDone}
      />
    )

    fireEvent.click(await screen.findByRole('button', { name: 'I would rather not rank' }))

    await waitFor(() => expect(onDone).toHaveBeenCalled())
    expect(post).toHaveBeenCalledWith('/calibration/sessions/sess1/rankings', {
      stage: 'BLOTTER',
      response_status: 'skipped',
    })
  })

  it('records "could not tell them apart" as unable to assess', async () => {
    render(
      <RankingStep
        enrollment={enrollmentOf([detected('a', 1), detected('b', 2)])}
        task={task}
        onDone={vi.fn()}
      />
    )

    fireEvent.click(await screen.findByRole('button', { name: 'I could not tell them apart' }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/calibration/sessions/sess1/rankings', {
        stage: 'BLOTTER',
        response_status: 'unable_to_assess',
      })
    )
  })

  it('moves straight on when there is nothing to rank, recording nothing', async () => {
    const onDone = vi.fn()
    render(
      <RankingStep
        enrollment={enrollmentOf([detected('a', 1), detected('b', 2, false)])}
        task={task}
        onDone={onDone}
      />
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Continue' }))

    expect(onDone).toHaveBeenCalled()
    expect(post).not.toHaveBeenCalled()
  })

  it('does not ask again when the session already has a ranking', async () => {
    get.mockResolvedValue({ data: [{ response_status: 'completed' }] })
    const onDone = vi.fn()
    render(
      <RankingStep
        enrollment={enrollmentOf([detected('a', 1), detected('b', 2)])}
        task={task}
        onDone={onDone}
      />
    )

    await waitFor(() => expect(onDone).toHaveBeenCalled())
  })

  it('asks again after the earlier ranking was invalidated', async () => {
    get.mockResolvedValue({
      data: [{ response_status: 'completed' }, { response_status: 'invalidated' }],
    })
    const onDone = vi.fn()
    render(
      <RankingStep
        enrollment={enrollmentOf([detected('a', 1), detected('b', 2)])}
        task={task}
        onDone={onDone}
      />
    )

    expect(await screen.findAllByRole('combobox')).toHaveLength(2)
    expect(onDone).not.toHaveBeenCalled()
  })

  it('lets the evaluator continue when some samples have no response yet', async () => {
    const blank = { ...detected('b', 2), observations: [] }
    const onDone = vi.fn()
    render(
      <RankingStep
        enrollment={enrollmentOf([detected('a', 1), blank])}
        task={task}
        onDone={onDone}
      />
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Continue without ranking' }))

    expect(onDone).toHaveBeenCalled()
    expect(post).not.toHaveBeenCalled()
  })
})

describe('FlagProblem', () => {
  beforeEach(() => {
    post.mockReset()
    post.mockResolvedValue({ data: {} })
  })

  it('raises a session-level flag as the evaluator, for review', async () => {
    render(<FlagProblem enrollment={enrollmentOf([detected('a', 1)])} task={task} />)
    fireEvent.click(screen.getByRole('button', { name: 'Flag a problem' }))
    fireEvent.change(screen.getByLabelText('What happened?'), {
      target: { value: 'competing_odor' },
    })
    fireEvent.change(screen.getByLabelText(/tell us more/i), { target: { value: 'Cooking' } })

    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/calibration/quality-flags', {
        action: 'raised',
        source: 'evaluator',
        disposition: 'review',
        severity: 'minor',
        target_type: 'session',
        target_id: 'sess1',
        code: 'competing_odor',
        explanation: 'Cooking',
      })
    )
  })

  it('can flag one sample instead of the whole session', async () => {
    render(
      <FlagProblem enrollment={enrollmentOf([detected('a', 1), detected('b', 2)])} task={task} />
    )
    fireEvent.click(screen.getByRole('button', { name: 'Flag a problem' }))
    fireEvent.change(screen.getByLabelText('What is it about?'), { target: { value: 'b' } })

    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(post).toHaveBeenCalled())
    expect(post.mock.calls[0][1]).toMatchObject({
      target_type: 'presentation',
      target_id: 'b',
      explanation: null,
    })
  })

  it('offers only codes the API accepts for a flag', () => {
    expect(flagReasons.map((reason) => reason.value)).toEqual([
      'evaluator_reported_problem',
      'sample_spill',
      'competing_odor',
      'interrupted',
      'mislabel_suspected',
      'instrument_fault',
    ])
  })

  it('can be cancelled without sending anything', () => {
    render(<FlagProblem enrollment={enrollmentOf([detected('a', 1)])} task={task} />)
    fireEvent.click(screen.getByRole('button', { name: 'Flag a problem' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.getByRole('button', { name: 'Flag a problem' })).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })
})
