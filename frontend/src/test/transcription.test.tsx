import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { SampleObservationPanel } from '../pages/SampleObservationPanel'
import { SessionIntroStep } from '../pages/SessionIntroStep'
import { SessionBoundaryStep } from '../pages/SessionBoundaryStep'
import { NonBlindPanel } from '../pages/NonBlindPanel'
import {
  SPRAY_TO_SMELL_CEILING_MINUTES,
  blindCodeMatches,
  elapsedWholeMinutes,
  fromServerInstant,
  isExposureAlreadyRecorded,
  isSessionAlreadyEnded,
  isTranscribed,
  overCeiling,
  paperTimeProblem,
  sprayToSmellMinutes,
  toInstant,
} from '../content/transcription'
import type { Enrollment, EnrollmentReadiness, Sample } from '../api/types'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('axios', () => ({
  default: {
    create: () => ({ get, post }),
    isAxiosError: (value: unknown) =>
      typeof value === 'object' && value !== null && 'isAxiosError' in value,
  },
}))

/** A failed request the way axios reports one. */
function conflict(detail: string) {
  return { isAxiosError: true, response: { status: 409, data: { detail } } }
}

const SPRAYED = '2026-11-25T10:00'
const SMELLED = '2026-11-25T10:02'
const FINISHED = '2026-11-25T10:15'

function makeTask() {
  return {
    busy: false,
    error: '',
    notice: '',
    run: async (work: () => Promise<void>) => {
      try {
        await work()
      } catch {
        /* surfaced through task.error in the app */
      }
    },
    setNotice: vi.fn(),
    setError: vi.fn(),
  }
}

function typeInto(label: string | RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

describe('transcription helpers', () => {
  it('treats only the household format as transcribed from paper', () => {
    expect(isTranscribed('HOUSEHOLD')).toBe(true)
    expect(isTranscribed('ENROLLMENT')).toBe(false)
    expect(isTranscribed(undefined)).toBe(false)
  })

  it('compares the blind code trimmed and case-insensitively, never blank', () => {
    expect(blindCodeMatches(' aaa1 ', 'AAA1')).toBe(true)
    expect(blindCodeMatches('AAA2', 'AAA1')).toBe(false)
    expect(blindCodeMatches('   ', '')).toBe(false)
  })

  it('reads a server instant without a zone as UTC', () => {
    expect(fromServerInstant('2026-11-25T10:00:00').toISOString()).toBe('2026-11-25T10:00:00.000Z')
    expect(fromServerInstant('2026-11-25T10:00:00+00:00').toISOString()).toBe(
      '2026-11-25T10:00:00.000Z'
    )
  })

  it('floors whole elapsed minutes and refuses a reversed or missing pair', () => {
    expect(elapsedWholeMinutes('2026-11-25T10:00', '2026-11-25T10:09')).toBe(9)
    expect(elapsedWholeMinutes('2026-11-25T10:00', '2026-11-25T10:00')).toBe(0)
    expect(elapsedWholeMinutes('2026-11-25T10:10', '2026-11-25T10:00')).toBeNull()
    expect(elapsedWholeMinutes('', '2026-11-25T10:00')).toBeNull()
    expect(toInstant('')).toBeNull()
    expect(toInstant('not a time')).toBeNull()
  })

  it('flags a first smell only when it is later than the ceiling', () => {
    expect(SPRAY_TO_SMELL_CEILING_MINUTES).toBe(5)
    expect(sprayToSmellMinutes(SPRAYED, SMELLED)).toBe(2)
    expect(overCeiling(SPRAYED, '2026-11-25T10:05')).toBe(false)
    expect(overCeiling(SPRAYED, '2026-11-25T10:06')).toBe(true)
    expect(overCeiling(SPRAYED, '')).toBe(false)
  })

  it('names the first problem with the three paper times', () => {
    const base = { sprayed: SPRAYED, smelled: SMELLED, finished: FINISHED }
    expect(paperTimeProblem({ ...base, firstSmellStillToRecord: true })).toBeNull()
    expect(paperTimeProblem({ ...base, sprayed: '', firstSmellStillToRecord: true })).toMatch(
      /sprayed/
    )
    expect(paperTimeProblem({ ...base, smelled: '', firstSmellStillToRecord: true })).toMatch(
      /first smelled/
    )
    expect(paperTimeProblem({ ...base, finished: '', firstSmellStillToRecord: true })).toMatch(
      /finished/
    )
    expect(
      paperTimeProblem({ ...base, smelled: '2026-11-25T09:59', firstSmellStillToRecord: true })
    ).toMatch(/first smell cannot be before the spray/)
    expect(
      paperTimeProblem({ ...base, finished: '2026-11-25T10:01', firstSmellStillToRecord: true })
    ).toMatch(/cannot finish before the first smell/)
    expect(
      paperTimeProblem({ ...base, finished: '2026-11-25T09:00', firstSmellStillToRecord: false })
    ).toMatch(/cannot finish before the spray/)
    // After the first smell is recorded it is not asked for again.
    expect(paperTimeProblem({ ...base, smelled: '', firstSmellStillToRecord: false })).toBeNull()
  })

  it('recognises only the two already-done conflicts', () => {
    expect(isExposureAlreadyRecorded(conflict('Blotter exposure already recorded'))).toBe(true)
    expect(isExposureAlreadyRecorded(conflict('Session already ended'))).toBe(false)
    expect(isSessionAlreadyEnded(conflict('Session already ended'))).toBe(true)
    expect(isSessionAlreadyEnded(new Error('boom'))).toBe(false)
  })
})

const sample: Sample = {
  id: 's1',
  session_id: 'sess1',
  blind_code: 'AAA1',
  position: 1,
  skin_planned: false,
  blotter_locked: false,
  skin_locked: false,
  post_reveal_entry: false,
  observations: [],
}
const enrollment = { id: 'e1', skin_plan_locked: true } as unknown as Enrollment

function renderPanel(task: ReturnType<typeof makeTask>, overrides: Partial<Sample> = {}) {
  return render(
    <SampleObservationPanel
      enrollment={enrollment}
      sample={{ ...sample, ...overrides }}
      stage="BLOTTER"
      stageFixed
      detected="yes"
      setDetected={vi.fn()}
      task={task as never}
      refresh={async () => undefined}
      transcription
    />
  )
}

function fillPaper(code: string, times: { sprayed?: string; smelled?: string; finished?: string }) {
  typeInto('Blind code printed on the sheet', code)
  typeInto('Time sprayed', times.sprayed ?? SPRAYED)
  if (times.smelled !== undefined) typeInto('Time first smelled', times.smelled)
  typeInto('Time this column finished', times.finished ?? FINISHED)
}

describe('paper column of the observation panel', () => {
  beforeEach(() => {
    post.mockReset()
    post.mockResolvedValue({ data: { id: 'o1' } })
  })

  it('refuses to save when the typed blind code is not this sample, and sends nothing', async () => {
    const task = makeTask()
    renderPanel(task)
    fillPaper('BBB2', { smelled: SMELLED })

    fireEvent.click(screen.getByRole('button', { name: 'Save observation' }))

    await waitFor(() =>
      expect(task.setError).toHaveBeenCalledWith(
        expect.stringMatching(/does not match this sample/)
      )
    )
    expect(post).not.toHaveBeenCalled()
  })

  it('refuses to save when a paper time is missing', async () => {
    const task = makeTask()
    renderPanel(task)
    typeInto('Blind code printed on the sheet', 'AAA1')

    fireEvent.click(screen.getByRole('button', { name: 'Save observation' }))

    await waitFor(() =>
      expect(task.setError).toHaveBeenCalledWith(expect.stringMatching(/sprayed/))
    )
    expect(post).not.toHaveBeenCalled()
  })

  it('stamps the first smell, then saves the column with the paper times and no typed minutes', async () => {
    const task = makeTask()
    renderPanel(task)
    fillPaper(' aaa1 ', { smelled: SMELLED })
    expect(screen.getByText('Elapsed since the spray: 15 whole minutes.')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Save observation' }))

    await waitFor(() => expect(post).toHaveBeenCalledTimes(2))
    expect(post.mock.calls[0]).toEqual([
      '/calibration/presentations/s1/exposure',
      {
        stage: 'BLOTTER',
        at: new Date(SMELLED).toISOString(),
        sprayed_at: new Date(SPRAYED).toISOString(),
        confirmed_blind_code: 'aaa1',
      },
    ])
    const [path, data] = post.mock.calls[1] as [string, Record<string, unknown>]
    expect(path).toBe('/calibration/presentations/s1/observations')
    expect(data).toMatchObject({
      stage: 'BLOTTER',
      response_status: 'completed',
      observed_at: new Date(FINISHED).toISOString(),
      sprayed_at: new Date(SPRAYED).toISOString(),
      confirmed_blind_code: 'aaa1',
    })
    expect(data).not.toHaveProperty('elapsed_minutes')
  })

  it('does not ask for or stamp the first smell again once it is recorded', async () => {
    const task = makeTask()
    renderPanel(task, { presented_at: '2026-11-25T10:02:00' })
    expect(screen.queryByLabelText('Time first smelled')).not.toBeInTheDocument()
    expect(screen.getByText(/First smelled at/)).toBeInTheDocument()
    fillPaper('AAA1', {})

    fireEvent.click(screen.getByRole('button', { name: 'Save observation' }))

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    expect(post.mock.calls[0][0]).toBe('/calibration/presentations/s1/observations')
  })

  it('carries on to the observation when the first smell was already stamped', async () => {
    post.mockImplementation((url: string) =>
      url.endsWith('/exposure')
        ? Promise.reject(conflict('Blotter exposure already recorded'))
        : Promise.resolve({ data: { id: 'o1' } })
    )
    const task = makeTask()
    renderPanel(task)
    fillPaper('AAA1', { smelled: SMELLED })

    fireEvent.click(screen.getByRole('button', { name: 'Save observation' }))

    await waitFor(() => expect(post).toHaveBeenCalledTimes(2))
    expect(post.mock.calls[1][0]).toBe('/calibration/presentations/s1/observations')
  })

  it('warns, without blocking, when the first smell is over the ceiling', async () => {
    const task = makeTask()
    renderPanel(task)
    typeInto('Time sprayed', SPRAYED)
    typeInto('Time first smelled', '2026-11-25T10:08')

    expect(await screen.findByText(/over the 5-minute ceiling/)).toBeInTheDocument()
    expect(screen.getByText(/saved as written and flagged as a deviation/)).toBeInTheDocument()
  })
})

const twoSessions = {
  id: 'e1',
  reviewer_id: 'r1',
  presentations: [
    { id: 's1', session_id: 'sess1' },
    { id: 's2', session_id: 'sess2' },
  ],
} as unknown as Enrollment

function routeIntroGets(approved: boolean, consent = 'none') {
  get.mockImplementation((url: string) => {
    if (url.includes('/consent/text'))
      return Promise.resolve({ data: { version: 'v1', approved, text: 'Consent wording here' } })
    if (url.includes('/consent'))
      return Promise.resolve({ data: { state: { session_context: consent } } })
    return Promise.resolve({ data: { recorded: false } })
  })
}

function renderIntro(sessionId: string, task = makeTask()) {
  const onDone = vi.fn()
  render(
    <SessionIntroStep
      enrollment={twoSessions}
      sessionId={sessionId}
      task={task as never}
      onDone={onDone}
      transcription
    />
  )
  return { onDone, task }
}

describe('session intro in the facilitated format', () => {
  beforeEach(() => {
    get.mockReset()
    post.mockReset()
    post.mockResolvedValue({ data: {} })
  })

  it('asks for consent once, with a note of where it was written', async () => {
    routeIntroGets(true)
    const { task } = renderIntro('sess1')

    fireEvent.click(await screen.findByRole('button', { name: /i agree/i }))
    await waitFor(() =>
      expect(task.setError).toHaveBeenCalledWith(
        expect.stringMatching(/Say where the evaluator wrote/)
      )
    )
    expect(post).not.toHaveBeenCalled()

    typeInto('Where the evaluator wrote their consent', 'signed on the paper sheet')
    fireEvent.click(screen.getByRole('button', { name: /i agree/i }))
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/calibration/reviewers/r1/consent', {
        scope: 'session_context',
        event_type: 'granted',
        enrollment_id: 'e1',
        note: 'signed on the paper sheet',
      })
    )
  })

  it('does not ask again in a later session', async () => {
    routeIntroGets(true)
    renderIntro('sess2')

    expect(await screen.findByText(/asked once, before the first session/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /i agree/i })).not.toBeInTheDocument()
    expect(screen.queryByText('Consent wording here')).not.toBeInTheDocument()
  })

  it('starts the session at the time written on the sheet, and refuses a blank one', async () => {
    routeIntroGets(false)
    const { onDone, task } = renderIntro('sess1')
    const go = await screen.findByRole('button', { name: 'Continue to the samples' })

    fireEvent.click(go)
    await waitFor(() =>
      expect(task.setError).toHaveBeenCalledWith(
        expect.stringMatching(/start time written on the sheet/)
      )
    )
    expect(post).not.toHaveBeenCalled()

    typeInto('Session start time written on the sheet', SPRAYED)
    fireEvent.click(go)
    await waitFor(() => expect(onDone).toHaveBeenCalled())
    expect(post).toHaveBeenCalledWith(
      '/calibration/sessions/sess1/start',
      expect.objectContaining({ started_at: new Date(SPRAYED).toISOString() })
    )
  })
})

describe('session boundary', () => {
  beforeEach(() => {
    post.mockReset()
    post.mockResolvedValue({ data: {} })
  })

  it('continues at once outside the facilitated format', () => {
    const onContinue = vi.fn()
    render(
      <SessionBoundaryStep sessionId="sess1" task={makeTask() as never} onContinue={onContinue} />
    )

    fireEvent.click(screen.getByRole('button', { name: 'Facilitator: continue' }))

    expect(onContinue).toHaveBeenCalled()
    expect(post).not.toHaveBeenCalled()
  })

  it('records the end time from the sheet, then continues', async () => {
    const onContinue = vi.fn()
    const task = makeTask()
    render(
      <SessionBoundaryStep
        sessionId="sess1"
        task={task as never}
        onContinue={onContinue}
        transcription
      />
    )

    fireEvent.click(screen.getByRole('button', { name: 'Facilitator: continue' }))
    await waitFor(() => expect(task.setError).toHaveBeenCalled())
    expect(post).not.toHaveBeenCalled()
    expect(onContinue).not.toHaveBeenCalled()

    typeInto('Session end time written on the sheet', FINISHED)
    fireEvent.click(screen.getByRole('button', { name: 'Facilitator: continue' }))
    await waitFor(() => expect(onContinue).toHaveBeenCalled())
    expect(post).toHaveBeenCalledWith('/calibration/sessions/sess1/end', {
      ended_at: new Date(FINISHED).toISOString(),
    })
  })

  it('treats a session that already ended as done', async () => {
    post.mockRejectedValue(conflict('Session already ended'))
    const onContinue = vi.fn()
    render(
      <SessionBoundaryStep
        sessionId="sess1"
        task={makeTask() as never}
        onContinue={onContinue}
        transcription
      />
    )
    typeInto('Session end time written on the sheet', FINISHED)

    fireEvent.click(screen.getByRole('button', { name: 'Facilitator: continue' }))

    await waitFor(() => expect(onContinue).toHaveBeenCalled())
  })

  it('does not continue when ending the session fails for another reason', async () => {
    post.mockRejectedValue(new Error('network down'))
    const onContinue = vi.fn()
    render(
      <SessionBoundaryStep
        sessionId="sess1"
        task={makeTask() as never}
        onContinue={onContinue}
        transcription
      />
    )
    typeInto('Session end time written on the sheet', FINISHED)

    fireEvent.click(screen.getByRole('button', { name: 'Facilitator: continue' }))

    await waitFor(() => expect(post).toHaveBeenCalled())
    expect(onContinue).not.toHaveBeenCalled()
  })
})

const readiness: EnrollmentReadiness[] = [
  {
    enrollment_id: 'e1',
    reviewer_id: 'r1',
    reviewer_name: 'Evaluator One',
    checkpoint_count: 0,
    checkpoint_blocker: 'SKIN_PLAN',
    reveal_blocker: 'SKIN_PLAN',
    revealed: false,
  },
]

describe('non-blind panel', () => {
  beforeEach(() => {
    post.mockReset()
  })

  it('explains what marking an evaluator non-blind does', () => {
    render(<NonBlindPanel enrollments={readiness} task={makeTask() as never} />)

    expect(screen.getByText(/flagged non-blind/)).toBeInTheDocument()
    expect(screen.getByText(/excluded from blind-baseline training/)).toBeInTheDocument()
    expect(screen.getByText(/kept in the evaluation/)).toBeInTheDocument()
  })

  it('posts the written reason for the chosen evaluator after a confirmation', async () => {
    post.mockResolvedValue({ data: { flagged: ['sess1', 'sess2'], already_flagged: [] } })
    const task = makeTask()
    render(<NonBlindPanel enrollments={readiness} task={task as never} />)

    expect(screen.getByRole('button', { name: 'Mark evaluator non-blind' })).toBeDisabled()
    typeInto('Evaluator who holds the mapping', 'e1')
    typeInto('Written reason', 'Holds the mapping and sprays.')
    fireEvent.click(screen.getByRole('button', { name: 'Mark evaluator non-blind' }))
    expect(post).not.toHaveBeenCalled()
    fireEvent.click(await screen.findByRole('button', { name: 'Confirm non-blind' }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/calibration/enrollments/e1/non-blind', {
        explanation: 'Holds the mapping and sprays.',
      })
    )
    await waitFor(() =>
      expect(task.setNotice).toHaveBeenCalledWith(
        expect.stringMatching(/2 session\(s\) newly flagged/)
      )
    )
  })

  it('cannot be confirmed without a written reason', () => {
    render(<NonBlindPanel enrollments={readiness} task={makeTask() as never} />)
    typeInto('Evaluator who holds the mapping', 'e1')
    typeInto('Written reason', '   ')

    expect(screen.getByRole('button', { name: 'Mark evaluator non-blind' })).toBeDisabled()
  })
})
