import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { CalibrationPage } from '../pages/CalibrationPage'
import { SampleObservationPanel } from '../pages/SampleObservationPanel'
import type { Access, Enrollment, EnrollmentSummary, Sample } from '../api/types'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('../api/client', () => ({
  api: { get, post },
  requestErrorMessage: () => 'Request failed.',
}))

const SPRAYED = '2026-11-25T10:00'
const SMELLED = '2026-11-25T10:02'
const FINISHED = '2026-11-25T10:15'

const access: Access = { username: 'recorder', manager: false }

function sampleOf(id: string, session: string, code: string, position: number): Sample {
  return {
    id,
    session_id: session,
    blind_code: code,
    position,
    skin_planned: false,
    blotter_locked: false,
    skin_locked: false,
    post_reveal_entry: false,
    observations: [],
  }
}

/** A household enrollment with two sessions, worked in order. */
function enrollmentOf(id: string): Enrollment {
  const code = id.toUpperCase()
  return {
    id,
    program_id: 'p1',
    reviewer_id: `rev-${id}`,
    revealed: false,
    reveal_eligible: false,
    reveal_blocker: 'HOUSEHOLD_WAIT',
    skin_plan_locked: false,
    reveal_policy: 'HOUSEHOLD',
    presentations: [
      sampleOf(`${id}-s1`, `${id}-sess1`, `${code}A1`, 1),
      sampleOf(`${id}-s2`, `${id}-sess1`, `${code}A2`, 2),
      sampleOf(`${id}-s3`, `${id}-sess2`, `${code}B1`, 1),
    ],
  } as Enrollment
}

function summaryOf(id: string): EnrollmentSummary {
  return {
    id,
    program_id: 'p1',
    reviewer_id: `rev-${id}`,
    revealed: false,
    has_started: true,
    total_presentations: 3,
    blotter_complete: 0,
    skin_planned: 0,
    skin_complete: 0,
    program_name: 'Pilot',
    program_version: '1',
  }
}

const assignments = [summaryOf('e1'), summaryOf('e2')]
const reviewers = [
  { id: 'rev-e1', name: 'First Evaluator' },
  { id: 'rev-e2', name: 'Second Evaluator' },
]

/** The server's side of the world, which a "reload" reads again. */
let server: Record<string, Enrollment>

function renderPage(who: Access = access) {
  return render(
    <CalibrationPage
      assignments={assignments}
      programs={[{ id: 'p1', name: 'Pilot', version: '1', status: 'active' }]}
      reviewers={reviewers}
      access={who}
      navigate={() => undefined}
      reload={async () => undefined}
    />
  )
}

/** A page reload: everything in React is gone, sessionStorage stays. */
function reload(who: Access = access) {
  cleanup()
  return renderPage(who)
}

function typeInto(label: string | RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

function radio(name: string, value: string): HTMLInputElement {
  const found = document.querySelector<HTMLInputElement>(`input[name="${name}"][value="${value}"]`)
  if (!found) throw new Error(`No ${name} option ${value}`)
  return found
}

function stored(): string {
  return Object.keys(window.sessionStorage)
    .map((key) => `${key}=${window.sessionStorage.getItem(key)}`)
    .join('\n')
}

/** Passes the opening screen of the first session of the evaluator on screen. */
async function startSession(firstCode: RegExp) {
  await screen.findByRole('heading', { name: 'Before you begin' })
  typeInto('Session start time written on the sheet', SPRAYED)
  fireEvent.click(screen.getByRole('button', { name: 'Continue to the samples' }))
  await screen.findByRole('heading', { name: firstCode })
}

function typeColumn() {
  typeInto('Blind code printed on the sheet', 'E1A1')
  typeInto('Time sprayed', SPRAYED)
  typeInto('Time first smelled', SMELLED)
  typeInto('Time this column finished', FINISHED)
  typeInto('Detected', 'yes')
  typeInto('Do you recognize this?', 'new')
  typeInto('Have you owned or worn it?', 'no')
  fireEvent.click(radio('intensity', '3'))
}

afterEach(() => vi.restoreAllMocks())

beforeEach(() => {
  window.sessionStorage.clear()
  vi.clearAllMocks()
  server = { e1: enrollmentOf('e1'), e2: enrollmentOf('e2') }
  get.mockImplementation((path: string) => {
    const match = path.match(/\/calibration\/enrollments\/(e\d)$/)
    if (match) return Promise.resolve({ data: server[match[1]] })
    if (path === '/calibration/consent/text')
      return Promise.resolve({ data: { version: '1', approved: false, text: 'Consent text' } })
    if (path.endsWith('/consent')) return Promise.resolve({ data: { state: {} } })
    if (path.endsWith('/context')) return Promise.resolve({ data: { recorded: false } })
    return Promise.resolve({ data: [] })
  })
  post.mockResolvedValue({ data: { id: 'o1' } })
})

describe('a reload mid-sitting', () => {
  it('opens the first started evaluator when nothing was switched', async () => {
    renderPage()
    await screen.findByRole('heading', { name: 'Before you begin' })
    expect(screen.getByLabelText('Evaluator')).toHaveValue('e1')
  })

  it('reopens the evaluator the recorder switched to, not the first one', async () => {
    renderPage()
    await screen.findByRole('heading', { name: 'Before you begin' })
    fireEvent.change(screen.getByLabelText('Evaluator'), { target: { value: 'e2' } })
    await waitFor(() => expect(get).toHaveBeenCalledWith('/calibration/enrollments/e2'))

    reload()

    await screen.findByRole('heading', { name: 'Before you begin' })
    expect(screen.getByLabelText('Evaluator')).toHaveValue('e2')
  })

  it('does not reopen an evaluator saved by a different account', async () => {
    renderPage()
    await screen.findByRole('heading', { name: 'Before you begin' })
    fireEvent.change(screen.getByLabelText('Evaluator'), { target: { value: 'e2' } })
    await waitFor(() => expect(screen.getByLabelText('Evaluator')).toHaveValue('e2'))

    reload({ username: 'someone-else', manager: false })

    await screen.findByRole('heading', { name: 'Before you begin' })
    expect(screen.getByLabelText('Evaluator')).toHaveValue('e1')
    expect(stored()).toBe('')
  })

  it('keeps the session screens already passed, which the server cannot know yet', async () => {
    renderPage()
    await startSession(/E1A1/)

    reload()

    expect(await screen.findByRole('heading', { name: /E1A1/ })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Before you begin' })).toBeNull()
  })

  it('rebuilds the same evaluator, session and sample from the server once a column is saved', async () => {
    server.e1.presentations[0].blotter_locked = true
    server.e1.presentations[0].observations = [
      { id: 'o1', phase: 'BLOTTER', stage: 'BLOTTER', elapsed_minutes: 5 },
    ] as Sample['observations']
    renderPage()
    expect(await screen.findByRole('heading', { name: /E1A2/ })).toBeInTheDocument()
    expect(screen.getByText(/Session 1 of 2/)).toBeInTheDocument()

    reload()

    expect(await screen.findByRole('heading', { name: /E1A2/ })).toBeInTheDocument()
    expect(screen.getByText(/Session 1 of 2/)).toBeInTheDocument()
    // Nothing about the position had to be stored.
    expect(stored()).not.toMatch(/E1A2|e1-s2/)
  })

  it('restores the unsaved fields of the column being typed', async () => {
    renderPage()
    await startSession(/E1A1/)
    typeColumn()

    reload()

    await screen.findByRole('heading', { name: /E1A1/ })
    await waitFor(() => expect(screen.getByLabelText('Detected')).toHaveValue('yes'))
    expect(screen.getByLabelText('Blind code printed on the sheet')).toHaveValue('E1A1')
    expect(screen.getByLabelText('Time sprayed')).toHaveValue(SPRAYED)
    expect(screen.getByLabelText('Time first smelled')).toHaveValue(SMELLED)
    expect(screen.getByLabelText('Time this column finished')).toHaveValue(FINISHED)
    expect(screen.getByLabelText('Do you recognize this?')).toHaveValue('new')
    expect(screen.getByLabelText('Have you owned or worn it?')).toHaveValue('no')
    expect(radio('intensity', '3').checked).toBe(true)
    expect(screen.getByText('Elapsed since the spray: 15 whole minutes.')).toBeInTheDocument()
  })

  it('drops the draft once the column is saved', async () => {
    renderPage()
    await startSession(/E1A1/)
    typeColumn()
    expect(stored()).toMatch(/draft/)

    fireEvent.click(screen.getByRole('button', { name: 'Save observation' }))
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/calibration/presentations/e1-s1/observations',
        expect.anything()
      )
    )
    await screen.findByText('Observation saved. Original responses are retained.')

    expect(stored()).not.toMatch(/draft/)
    reload()
    await screen.findByRole('heading', { name: /E1A1/ })
    expect(screen.getByLabelText('Blind code printed on the sheet')).toHaveValue('')
  })

  it('does not put a restored draft back into the next column after saving', async () => {
    renderPage()
    await startSession(/E1A1/)
    typeColumn()
    reload()
    await screen.findByRole('heading', { name: /E1A1/ })
    await waitFor(() => expect(screen.getByLabelText('Detected')).toHaveValue('yes'))

    fireEvent.click(screen.getByRole('button', { name: 'Save observation' }))
    await screen.findByText('Observation saved. Original responses are retained.')

    expect(screen.getByLabelText('Blind code printed on the sheet')).toHaveValue('')
    // The spray time is carried to the next column of the same sample by design.
    expect(screen.getByLabelText('Time sprayed')).toHaveValue(SPRAYED)
    expect(screen.getByLabelText('Time this column finished')).toHaveValue('')
    expect(radio('intensity', '3').checked).toBe(false)
    expect(stored()).not.toMatch(/draft/)
  })

  it('does not bring back a draft that is for another sample', async () => {
    renderPage()
    await startSession(/E1A1/)
    typeColumn()
    // The server moves on to the next sample of the same session meanwhile.
    server.e1.presentations[0].blotter_locked = true
    server.e1.presentations[0].observations = [
      { id: 'o1', phase: 'BLOTTER', stage: 'BLOTTER', elapsed_minutes: 5 },
    ] as Sample['observations']

    reload()

    await screen.findByRole('heading', { name: /E1A2/ })
    expect(screen.getByLabelText('Blind code printed on the sheet')).toHaveValue('')
    expect(stored()).not.toMatch(/draft/)
  })

  it('forgets everything older than twelve hours', async () => {
    renderPage()
    await startSession(/E1A1/)
    typeColumn()
    for (const key of Object.keys(window.sessionStorage)) {
      const value = JSON.parse(window.sessionStorage.getItem(key) ?? '{}')
      value.savedAt = Date.now() - 13 * 60 * 60 * 1000
      window.sessionStorage.setItem(key, JSON.stringify(value))
    }

    reload()

    await screen.findByRole('heading', { name: 'Before you begin' })
    expect(stored()).toBe('')
  })

  it('still renders and works when sessionStorage throws', async () => {
    vi.spyOn(window, 'sessionStorage', 'get').mockImplementation(() => {
      throw new DOMException('denied', 'SecurityError')
    })
    renderPage()
    await startSession(/E1A1/)
    expect(() => typeColumn()).not.toThrow()
    expect(screen.getByLabelText('Blind code printed on the sheet')).toHaveValue('E1A1')

    reload()

    // Nothing was kept, so the recorder starts the session screen again, as before.
    expect(await screen.findByRole('heading', { name: 'Before you begin' })).toBeInTheDocument()
  })

  it('stores no identity, note, spoiler or token', async () => {
    server.e1.presentations[0].identity = {
      fragrance_id: 'f1',
      name: 'Secret Name',
      brand: 'Secret Brand',
      concentration: 'EDT',
    }
    renderPage()
    await startSession(/E1A1/)
    typeColumn()
    typeInto('Perceived notes', 'vanilla, secret accord')
    typeInto('What you liked', 'the secret drydown')
    typeInto('Anything else', 'it is Secret Brand')

    const everything = stored()
    expect(everything).not.toMatch(/Secret|vanilla|drydown/)
    expect(everything).not.toMatch(/token|authorization|bearer/i)
    expect(everything).not.toMatch(/blind_code_map|identity|fragrance|brand/i)
    expect(window.localStorage.length).toBe(0)
    // What is stored is exactly the position and the numeric and time fields.
    const keys = Object.keys(window.sessionStorage)
    expect(keys.every((key) => key.startsWith('fr.recorder.v1:'))).toBe(true)
    const draft = JSON.parse(
      window.sessionStorage.getItem(keys.find((key) => key.includes(':draft:')) ?? '') ?? '{}'
    )
    expect(Object.keys(draft.fields).sort()).toEqual(
      [
        'confirmed_blind_code',
        'first_smelled_at',
        'intensity',
        'observed_at',
        'owned_or_worn',
        'recognition',
        'sprayed_at',
      ].sort()
    )
  })
})

describe('the observation panel on its own', () => {
  const enrollment = { id: 'e1', program_id: 'p1', skin_plan_locked: true } as unknown as Enrollment
  const sample = sampleOf('s1', 'sess1', 'AAA1', 1)
  const setDetected = vi.fn()
  const task = {
    busy: false,
    error: '',
    notice: '',
    run: async (work: () => Promise<void>) => work(),
    setNotice: vi.fn(),
    setError: vi.fn(),
  }

  function panel(draftOwner?: string) {
    return (
      <SampleObservationPanel
        enrollment={enrollment}
        sample={sample}
        stage="BLOTTER"
        stageFixed
        detected="yes"
        setDetected={setDetected}
        task={task as never}
        refresh={async () => undefined}
        transcription
        draftOwner={draftOwner}
      />
    )
  }

  it('stores nothing when it is not given an owner', () => {
    render(panel())
    typeInto('Blind code printed on the sheet', 'AAA1')
    expect(window.sessionStorage.length).toBe(0)
  })

  it('stores nothing outside the paper column (manual browsing, post-reveal notes)', () => {
    render(
      <SampleObservationPanel
        enrollment={enrollment}
        sample={sample}
        stage="BLOTTER"
        detected=""
        setDetected={setDetected}
        task={task as never}
        refresh={async () => undefined}
        draftOwner="recorder"
      />
    )
    typeInto('Elapsed minutes', '5')
    expect(window.sessionStorage.length).toBe(0)
  })

  it('restores a typed column after the panel is mounted again', () => {
    const first = render(panel('recorder'))
    typeInto('Blind code printed on the sheet', 'AAA1')
    typeInto('Time sprayed', SPRAYED)
    first.unmount()

    render(panel('recorder'))

    expect(screen.getByLabelText('Blind code printed on the sheet')).toHaveValue('AAA1')
    expect(screen.getByLabelText('Time sprayed')).toHaveValue(SPRAYED)
  })

  it('discards the draft when the ids no longer match', () => {
    const first = render(panel('recorder'))
    typeInto('Blind code printed on the sheet', 'AAA1')
    first.unmount()

    const other = { ...enrollment, program_id: 'p2' } as Enrollment
    render(
      <SampleObservationPanel
        enrollment={other}
        sample={sample}
        stage="BLOTTER"
        stageFixed
        detected="yes"
        setDetected={setDetected}
        task={task as never}
        refresh={async () => undefined}
        transcription
        draftOwner="recorder"
      />
    )

    expect(screen.getByLabelText('Blind code printed on the sheet')).toHaveValue('')
  })
})
