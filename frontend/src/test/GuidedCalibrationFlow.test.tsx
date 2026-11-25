import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { GuidedCalibrationFlow } from '../pages/GuidedCalibrationFlow'
import { nextWizardStep, noProgress, type WizardProgress } from '../routing/wizardSteps'
import type { Enrollment, Observation, ProgramReadiness, Sample } from '../api/types'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('axios', () => ({
  default: { create: () => ({ get, post }), isAxiosError: () => false },
}))

/** A blotter response; `detected` false records a non-detection. */
function answered(id: string, detected = true): Observation {
  return {
    id: `${id}-o`,
    stage: 'BLOTTER',
    phase: 'PRE_REVEAL',
    elapsed_minutes: 0,
    detected,
    response_status: detected ? 'completed' : 'not_detected',
  } as Observation
}

function sample(
  id: string,
  sessionId: string,
  position: number,
  overrides: Partial<Sample> = {}
): Sample {
  return {
    id,
    session_id: sessionId,
    blind_code: `CODE-${id.toUpperCase()}`,
    position,
    skin_planned: false,
    blotter_locked: false,
    skin_locked: false,
    post_reveal_entry: false,
    available: true,
    observations: [],
    ...overrides,
  }
}

/** A finished (answered and locked) sample. */
function done(id: string, sessionId: string, position: number): Sample {
  return sample(id, sessionId, position, {
    blotter_locked: true,
    observations: [answered(id)],
  })
}

/** A final (prospective) sample the server holds closed until a checkpoint. */
function closed(id: string, sessionId: string, position: number): Sample {
  return sample(id, sessionId, position, { available: false })
}

function baseEnrollment(overrides: Partial<Enrollment> = {}): Enrollment {
  return {
    id: 'e1',
    program_id: 'p1',
    reviewer_id: 'r1',
    revealed: false,
    reveal_eligible: false,
    reveal_blocker: 'SKIN_PLAN',
    skin_plan_locked: false,
    reveal_policy: 'ENROLLMENT',
    presentations: [sample('s1', 'sess1', 1)],
    ...overrides,
  }
}

/*
 * The F1 shape: three baseline sessions of three (the third holds a hidden
 * repeat of a session-A fragrance under its own code) and a final session of
 * two samples the server closes until a checkpoint exists.
 */
const sessionA = (state: 'open' | 'done') =>
  state === 'done'
    ? [done('a1', 'sessA', 1), done('a2', 'sessA', 2), done('a3', 'sessA', 3)]
    : [sample('a1', 'sessA', 1), sample('a2', 'sessA', 2), sample('a3', 'sessA', 3)]
const sessionB = (state: 'open' | 'done') =>
  state === 'done'
    ? [done('b1', 'sessB', 1), done('b2', 'sessB', 2), done('b3', 'sessB', 3)]
    : [sample('b1', 'sessB', 1), sample('b2', 'sessB', 2), sample('b3', 'sessB', 3)]
const sessionC = (state: 'open' | 'done') =>
  state === 'done'
    ? [done('c1', 'sessC', 1), done('repeat', 'sessC', 2), done('c3', 'sessC', 3)]
    : [sample('c1', 'sessC', 1), sample('repeat', 'sessC', 2), sample('c3', 'sessC', 3)]
const finalClosed = [closed('h1', 'sessH', 1), closed('h2', 'sessH', 2)]
const finalOpen = [sample('h1', 'sessH', 1), sample('h2', 'sessH', 2)]

function household(presentations: Sample[], overrides: Partial<Enrollment> = {}): Enrollment {
  return baseEnrollment({ reveal_policy: 'HOUSEHOLD', presentations, ...overrides })
}

function passed(sessions: string[], keys: (keyof WizardProgress)[]): WizardProgress {
  return {
    introduced: new Set(keys.includes('introduced') ? sessions : []),
    ranked: new Set(keys.includes('ranked') ? sessions : []),
    acknowledged: new Set(keys.includes('acknowledged') ? sessions : []),
  }
}

describe('nextWizardStep', () => {
  it('opens the first session, not the skin plan, while the server still reports SKIN_PLAN first', () => {
    const enrollment = household([...sessionA('open'), ...sessionB('open'), ...finalClosed])
    expect(nextWizardStep(enrollment)).toEqual({ kind: 'session_intro', sessionId: 'sessA' })
    expect(nextWizardStep(enrollment, passed(['sessA'], ['introduced']))).toEqual({
      kind: 'blotter',
      sessionId: 'sessA',
      presentationId: 'a1',
    })
  })

  it('continues a session already under way without reopening its intro', () => {
    const enrollment = household([
      done('a1', 'sessA', 1),
      sample('a2', 'sessA', 2),
      sample('a3', 'sessA', 3),
      ...sessionB('open'),
    ])
    expect(nextWizardStep(enrollment)).toEqual({
      kind: 'blotter',
      sessionId: 'sessA',
      presentationId: 'a2',
    })
  })

  it('ends a session with its ranking, then a boundary, and never auto-advances', () => {
    const enrollment = household([...sessionA('done'), ...sessionB('open'), ...finalClosed])
    expect(nextWizardStep(enrollment)).toEqual({ kind: 'session_ranking', sessionId: 'sessA' })
    expect(nextWizardStep(enrollment, passed(['sessA'], ['ranked']))).toEqual({
      kind: 'session_boundary',
      sessionId: 'sessA',
    })
    expect(nextWizardStep(enrollment, passed(['sessA'], ['ranked', 'acknowledged']))).toEqual({
      kind: 'session_intro',
      sessionId: 'sessB',
    })
  })

  it('does not bounce back to the boundary once the next session has responses', () => {
    const enrollment = household([
      ...sessionA('done'),
      done('b1', 'sessB', 1),
      sample('b2', 'sessB', 2),
      sample('b3', 'sessB', 3),
    ])
    expect(nextWizardStep(enrollment)).toEqual({
      kind: 'blotter',
      sessionId: 'sessB',
      presentationId: 'b2',
    })
  })

  it('reaches the skin-plan step only after every open session is done, never a closed sample', () => {
    const enrollment = household([
      ...sessionA('done'),
      ...sessionB('done'),
      ...sessionC('done'),
      ...finalClosed,
    ])
    const past = passed(['sessC'], ['ranked', 'acknowledged'])
    expect(nextWizardStep(enrollment)).toEqual({ kind: 'session_ranking', sessionId: 'sessC' })
    expect(nextWizardStep(enrollment, past)).toEqual({ kind: 'skin_plan' })
  })

  it('waits for the checkpoint instead of offering the closed final samples', () => {
    const enrollment = household(
      [...sessionA('done'), ...sessionB('done'), ...sessionC('done'), ...finalClosed],
      { skin_plan_locked: true, reveal_blocker: 'CHECKPOINT' }
    )
    expect(nextWizardStep(enrollment, passed(['sessC'], ['ranked', 'acknowledged']))).toEqual({
      kind: 'awaiting_checkpoint',
    })
  })

  it('opens the final session after the checkpoint, behind the previous boundary', () => {
    const enrollment = household(
      [...sessionA('done'), ...sessionB('done'), ...sessionC('done'), ...finalOpen],
      { skin_plan_locked: true, reveal_blocker: 'HOLDOUT' }
    )
    expect(nextWizardStep(enrollment, passed(['sessC'], ['ranked']))).toEqual({
      kind: 'session_boundary',
      sessionId: 'sessC',
    })
    const past = passed(['sessC'], ['ranked', 'acknowledged'])
    expect(nextWizardStep(enrollment, past)).toEqual({ kind: 'session_intro', sessionId: 'sessH' })
    past.introduced = new Set(['sessH'])
    expect(nextWizardStep(enrollment, past)).toEqual({
      kind: 'blotter',
      sessionId: 'sessH',
      presentationId: 'h1',
    })
  })

  it('waits for the household once this evaluator is finished, and is ready only on null', () => {
    const finished = [
      ...sessionA('done'),
      ...sessionB('done'),
      ...sessionC('done'),
      done('h1', 'sessH', 1),
      done('h2', 'sessH', 2),
    ]
    const past = passed(['sessH'], ['ranked', 'acknowledged'])
    expect(
      nextWizardStep(
        household(finished, { skin_plan_locked: true, reveal_blocker: 'HOUSEHOLD_WAIT' }),
        past
      )
    ).toEqual({ kind: 'household_wait' })
    expect(
      nextWizardStep(household(finished, { skin_plan_locked: true, reveal_blocker: null }), past)
    ).toEqual({ kind: 'household_ready' })
  })

  it('moves to a planned, unlocked skin sample once the plan is locked', () => {
    const enrollment = baseEnrollment({
      skin_plan_locked: true,
      reveal_blocker: 'SKIN',
      presentations: [{ ...done('s1', 'sess1', 1), skin_planned: true }],
    })
    expect(nextWizardStep(enrollment, passed(['sess1'], ['ranked', 'acknowledged']))).toEqual({
      kind: 'skin',
      presentationId: 's1',
    })
  })

  it('finishes all open blotters before any skin step, even when another sample is skin-ready', () => {
    const enrollment = baseEnrollment({
      skin_plan_locked: true,
      reveal_blocker: 'BLOTTER',
      presentations: [{ ...done('s1', 'sess1', 1), skin_planned: true }, sample('s2', 'sess1', 2)],
    })
    expect(nextWizardStep(enrollment)).toEqual({
      kind: 'blotter',
      sessionId: 'sess1',
      presentationId: 's2',
    })
  })

  it('offers an ENROLLMENT reveal on null without ever offering the closed final sample', () => {
    const enrollment = baseEnrollment({
      skin_plan_locked: true,
      reveal_blocker: null,
      reveal_eligible: true,
      presentations: [done('s1', 'sess1', 1), closed('h1', 'sessH', 1)],
    })
    expect(nextWizardStep(enrollment, passed(['sess1'], ['ranked', 'acknowledged']))).toEqual({
      kind: 'ready_to_reveal',
    })
  })

  it('treats an unknown blocker as not ready rather than as a reveal', () => {
    const enrollment = baseEnrollment({
      skin_plan_locked: true,
      reveal_blocker: 'SOMETHING_NEW',
      presentations: [done('s1', 'sess1', 1)],
    })
    expect(nextWizardStep(enrollment, passed(['sess1'], ['ranked', 'acknowledged']))).toEqual({
      kind: 'not_ready',
      blocker: 'SOMETHING_NEW',
    })
  })

  it('shows the revealed view when nothing is left, and keeps working an open final sample', () => {
    const revealedSample = { ...done('s1', 'sess1', 1), post_reveal_entry: true }
    expect(
      nextWizardStep(
        baseEnrollment({
          revealed: true,
          skin_plan_locked: true,
          reveal_blocker: null,
          presentations: [revealedSample],
        })
      )
    ).toEqual({ kind: 'revealed' })
    const withFinal = baseEnrollment({
      revealed: true,
      skin_plan_locked: true,
      reveal_blocker: null,
      presentations: [revealedSample, sample('h1', 'sessH', 1)],
    })
    // No ranking for a session whose identities are visible; the boundary
    // still separates it from the final session.
    expect(nextWizardStep(withFinal)).toEqual({ kind: 'session_boundary', sessionId: 'sess1' })
    expect(
      nextWizardStep(withFinal, passed(['sess1', 'sessH'], ['acknowledged', 'introduced']))
    ).toEqual({ kind: 'blotter', sessionId: 'sessH', presentationId: 'h1' })
  })

  it('reads a sample with no `available` field as open (servers older than the gate)', () => {
    const legacy = baseEnrollment({ presentations: [sample('s1', 'sess1', 1)] })
    delete legacy.presentations[0].available
    expect(nextWizardStep(legacy, passed(['sess1'], ['introduced']))).toEqual({
      kind: 'blotter',
      sessionId: 'sess1',
      presentationId: 's1',
    })
    expect(noProgress.introduced.size).toBe(0)
  })
})

const rankingsUrl = /\/sessions\/([^/]+)\/rankings$/

/** Answers each GET by URL: rankings per session, the intro's reads, readiness. */
function routeGets(
  enrollment: Enrollment,
  options: {
    rankings?: Record<string, { response_status: string }[]>
    readiness?: ProgramReadiness
  } = {}
) {
  get.mockImplementation((url: string) => {
    const ranking = url.match(rankingsUrl)
    if (ranking) return Promise.resolve({ data: options.rankings?.[ranking[1]] ?? [] })
    if (url.includes('/readiness')) return Promise.resolve({ data: options.readiness })
    if (url.includes('/consent/text'))
      return Promise.resolve({ data: { version: 'v', approved: false, text: 'Draft wording' } })
    if (url.includes('/consent')) return Promise.resolve({ data: { state: {} } })
    if (url.includes('/context')) return Promise.resolve({ data: { recorded: false } })
    return Promise.resolve({ data: enrollment })
  })
}

async function pastIntro() {
  fireEvent.click(await screen.findByRole('button', { name: 'Continue to the samples' }))
}

function renderFlow(props: Partial<Parameters<typeof GuidedCalibrationFlow>[0]> = {}) {
  return render(
    <GuidedCalibrationFlow
      enrollmentId="e1"
      onExitToManualBrowse={vi.fn()}
      onRevealed={vi.fn()}
      {...props}
    />
  )
}

const ranked = { response_status: 'completed' }

describe('GuidedCalibrationFlow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeGets(baseEnrollment())
    post.mockResolvedValue({ data: {} })
  })

  it('shows the step-of-total orientation and an escape hatch', async () => {
    renderFlow()
    await waitFor(() => expect(get).toHaveBeenCalledWith('/calibration/enrollments/e1'))
    await pastIntro()
    expect(await screen.findByText(/Step 1 of/)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Browse assignments manually instead' })
    ).toBeInTheDocument()
  })

  it('calls onExitToManualBrowse when the escape hatch is clicked', async () => {
    const onExit = vi.fn()
    renderFlow({ onExitToManualBrowse: onExit })
    await pastIntro()
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
    renderFlow()

    expect(
      await screen.findByRole('button', { name: 'Browse assignments manually instead' })
    ).toBeInTheDocument()
    expect(screen.getByText(/Loading/)).toBeInTheDocument()

    deferred.resolve({ data: baseEnrollment() })
    await pastIntro()
    await screen.findByText(/Step 1 of/)
  })

  it('offers no inline skin-test form on a blotter screen', async () => {
    renderFlow()
    await pastIntro()
    expect(await screen.findByText('Blind observation')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Plan skin test' })).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Finalize skin-test plan' })
    ).not.toBeInTheDocument()
  })

  it('stops at a boundary after a session and opens the next session on its own id', async () => {
    routeGets(household([...sessionA('done'), ...sessionB('open'), ...finalClosed]), {
      rankings: { sessA: [ranked] },
    })
    renderFlow()

    expect(
      await screen.findByText('Session complete. Wait for the facilitator.')
    ).toBeInTheDocument()
    expect(screen.queryByText('Blind observation')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Facilitator: continue' }))
    await pastIntro()

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/calibration/sessions/sessB/start', expect.any(Object))
    )
    expect(post).not.toHaveBeenCalledWith('/calibration/sessions/sessA/start', expect.anything())
    expect(await screen.findByText('Blind observation')).toBeInTheDocument()
    // Sessions A and B plus the closed final session.
    expect(screen.getByText(/Session 2 of 3/)).toBeInTheDocument()
  })

  it("ranks only the finished session's samples and posts to that session", async () => {
    routeGets(household([...sessionA('done'), ...sessionB('done'), ...sessionC('open')]), {
      rankings: { sessA: [ranked] },
    })
    renderFlow()

    const ranking = await screen.findByRole('group', { name: 'Your ranking' })
    const places = within(ranking).getAllByRole('combobox')
    expect(places).toHaveLength(3)
    expect(within(ranking).getByText(/CODE-B1/)).toBeInTheDocument()
    expect(within(ranking).queryByText(/CODE-A1/)).not.toBeInTheDocument()
    places.forEach((place, index) => {
      fireEvent.change(place, { target: { value: String(index + 1) } })
    })
    fireEvent.click(within(ranking).getByRole('button', { name: 'Save ranking' }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/calibration/sessions/sessB/rankings', {
        stage: 'BLOTTER',
        response_status: 'completed',
        entries: [
          { presentation_id: 'b1', rank_position: 1 },
          { presentation_id: 'b2', rank_position: 2 },
          { presentation_id: 'b3', rank_position: 3 },
        ],
      })
    )
    expect(
      await screen.findByText('Session complete. Wait for the facilitator.')
    ).toBeInTheDocument()
  })

  it('does not let a closed final session block the ranking of a finished one', async () => {
    routeGets(household([...sessionA('done'), ...finalClosed]))
    renderFlow()

    const ranking = await screen.findByRole('group', { name: 'Your ranking' })
    expect(within(ranking).getAllByRole('combobox')).toHaveLength(3)
    expect(screen.queryByText(/needs a response/)).not.toBeInTheDocument()
  })

  it('never offers a closed final sample before the checkpoint', async () => {
    routeGets(
      household(
        [...sessionA('done'), ...sessionB('done'), ...sessionC('done'), ...finalClosed],
        { skin_plan_locked: true, reveal_blocker: 'CHECKPOINT' }
      ),
      { rankings: { sessC: [ranked] } }
    )
    renderFlow()

    fireEvent.click(await screen.findByRole('button', { name: 'Facilitator: continue' }))

    expect(await screen.findByText(/Blind baseline work is complete/)).toBeInTheDocument()
    expect(screen.getByText(/freezes this evaluator's checkpoint/)).toBeInTheDocument()
    expect(screen.queryByText('Blind observation')).not.toBeInTheDocument()
    expect(screen.queryByText(/CODE-H1/)).not.toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/holdout/i)
    expect(post).not.toHaveBeenCalled()
  })

  it('finalizes the skin plan as its own step after the baseline', async () => {
    routeGets(household([...sessionA('done'), ...finalClosed]), { rankings: { sessA: [ranked] } })
    renderFlow()

    fireEvent.click(await screen.findByRole('button', { name: 'Facilitator: continue' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Finalize skin-test plan' }))
    expect(
      screen.getByText(/no skin tests planned means this evaluator has none/)
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Confirm final plan' }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/calibration/enrollments/e1/lock-skin-plan')
    )
    // Only open samples can be planned; a closed one is not even listed.
    expect(screen.queryByText(/CODE-H1/)).not.toBeInTheDocument()
  })

  it('tells a manager who is outstanding while the household waits', async () => {
    routeGets(
      household([done('s1', 'sess1', 1)], {
        skin_plan_locked: true,
        reveal_blocker: 'HOUSEHOLD_WAIT',
      }),
      {
        rankings: { sess1: [ranked] },
        readiness: {
          program_id: 'p1',
          reveal_policy: 'HOUSEHOLD',
          household_reveal_ready: false,
          household_revealed: false,
          enrollments: [
            {
              enrollment_id: 'e1',
              reviewer_id: 'r1',
              reviewer_name: 'Evaluator One',
              checkpoint_count: 1,
              checkpoint_blocker: null,
              reveal_blocker: 'HOUSEHOLD_WAIT',
              revealed: false,
            },
            {
              enrollment_id: 'e2',
              reviewer_id: 'r2',
              reviewer_name: 'Evaluator Two',
              checkpoint_count: 0,
              checkpoint_blocker: 'BLOTTER',
              reveal_blocker: 'BLOTTER',
              revealed: false,
            },
          ],
        },
      }
    )
    renderFlow({ isManager: true })

    fireEvent.click(await screen.findByRole('button', { name: 'Facilitator: continue' }))

    expect(await screen.findByText(/This evaluator is finished/)).toBeInTheDocument()
    expect(await screen.findByText('Evaluator Two')).toBeInTheDocument()
    expect(screen.getByText('Blotter responses remain')).toBeInTheDocument()
    expect(screen.queryByText('Evaluator One')).not.toBeInTheDocument()
    expect(get).toHaveBeenCalledWith('/calibration/programs/p1/readiness')
  })

  it('does not call the manager readiness endpoint for a recorder', async () => {
    routeGets(
      household([done('s1', 'sess1', 1)], {
        skin_plan_locked: true,
        reveal_blocker: 'HOUSEHOLD_WAIT',
      }),
      { rankings: { sess1: [ranked] } }
    )
    renderFlow()

    fireEvent.click(await screen.findByRole('button', { name: 'Facilitator: continue' }))

    expect(
      await screen.findByText(/who is still outstanding in Program setup/)
    ).toBeInTheDocument()
    expect(get).not.toHaveBeenCalledWith('/calibration/programs/p1/readiness')
  })

  it('offers no per-evaluator reveal when the household is ready', async () => {
    routeGets(
      household([done('s1', 'sess1', 1)], { skin_plan_locked: true, reveal_blocker: null }),
      { rankings: { sess1: [ranked] } }
    )
    renderFlow()

    fireEvent.click(await screen.findByRole('button', { name: 'Facilitator: continue' }))

    expect(await screen.findByText(/reveals the whole household together/)).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Reveal completed baseline' })
    ).not.toBeInTheDocument()
  })

  it('lets a facilitator switch to another evaluator', async () => {
    const onSwitch = vi.fn()
    renderFlow({
      switchOptions: [
        { id: 'e1', label: 'Evaluator One · Baseline' },
        { id: 'e2', label: 'Evaluator Two · Baseline' },
      ],
      onSwitchEnrollment: onSwitch,
    })
    fireEvent.change(await screen.findByLabelText('Evaluator'), { target: { value: 'e2' } })
    expect(onSwitch).toHaveBeenCalledWith('e2')
  })

  it('shows a completion state and calls onRevealed after a successful reveal', async () => {
    const beforeReveal = baseEnrollment({
      skin_plan_locked: true,
      reveal_blocker: null,
      reveal_eligible: true,
      presentations: [done('s1', 'sess1', 1)],
    })
    const revealed = baseEnrollment({
      skin_plan_locked: true,
      revealed: true,
      reveal_blocker: null,
      reveal_eligible: true,
      presentations: [
        {
          ...done('s1', 'sess1', 1),
          post_reveal_entry: true,
          identity: {
            fragrance_id: 'f1',
            name: 'Signature',
            brand: 'House',
            concentration: 'EDP',
          },
        },
      ],
    })
    let enrollmentReads = 0
    get.mockImplementation((url: string) => {
      if (url.includes('/rankings')) return Promise.resolve({ data: [ranked] })
      enrollmentReads += 1
      return Promise.resolve({ data: enrollmentReads === 1 ? beforeReveal : revealed })
    })
    const onRevealed = vi.fn().mockResolvedValue(undefined)
    renderFlow({ onRevealed })

    fireEvent.click(await screen.findByRole('button', { name: 'Facilitator: continue' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Reveal completed baseline' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Confirm reveal' }))

    await waitFor(() => expect(onRevealed).toHaveBeenCalled())
    expect(await screen.findByText(/Reveal complete/)).toBeInTheDocument()
    expect(screen.getByText(/House.*Signature.*EDP/)).toBeInTheDocument()
  })
})
