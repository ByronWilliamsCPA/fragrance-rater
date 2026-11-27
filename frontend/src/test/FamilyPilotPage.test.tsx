import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Program, ProgramReadiness } from '../api/types'
import { FamilyPilotPage } from '../pages/FamilyPilotPage'
import type { Navigate } from '../routing/routes'

const { get, post, put } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn() }))

vi.mock('../api/client', () => ({
  api: { get, post, put },
  requestErrorMessage: () => 'Request failed.',
}))

const PILOT: Program = {
  id: 'pilot',
  name: 'Family F1',
  version: 'v3.2',
  status: 'active',
  reveal_policy: 'HOUSEHOLD',
  blotter_mode: 'INDIVIDUAL',
}

const member = (id: string, role: string, name: string) => ({
  id,
  fragrance_id: `f-${id}`,
  fragrance_name: name,
  fragrance_brand: 'Secret House',
  concentration: 'EDT',
  version_key: 'edt-current-2026',
  role,
  repeat_of_id: null,
  group_name: 'Baseline',
  identity_evidence: 'Verified',
  fragella: null,
})

const MEMBERS = [
  member('m1', 'UNIVERSAL_BASELINE', 'Oak Study'),
  member('m2', 'UNIVERSAL_BASELINE', 'Cedar Hour'),
  member('m3', 'UNIVERSAL_BASELINE', 'Amber Night'),
  member('m4', 'HIDDEN_REPEAT', 'Oak Study'),
  member('m5', 'HOLDOUT', 'Rose Ghost'),
  member('m6', 'HOLDOUT', 'Iris Echo'),
]

const PEOPLE = [
  { id: 'r1', name: 'Alice' },
  { id: 'r2', name: 'Byron' },
]

/** The readiness the server would answer, with these reviewers enrolled. */
function readinessWith(enrolledIds: string[]): ProgramReadiness {
  return {
    program_id: 'pilot',
    reveal_policy: 'HOUSEHOLD',
    household_reveal_ready: false,
    household_revealed: false,
    enrollments: enrolledIds.map((id) => ({
      enrollment_id: `enr-${id}`,
      reviewer_id: id,
      reviewer_name: PEOPLE.find((person) => person.id === id)?.name ?? id,
      checkpoint_count: 0,
      checkpoint_blocker: 'BLOTTER',
      reveal_blocker: 'BLOTTER',
      revealed: false,
    })),
  }
}

let enrolled: string[] = []

function renderPage(
  programs: Program[] = [PILOT],
  options: { initialProgramId?: string; navigate?: Navigate; username?: string } = {}
) {
  const reload = vi.fn(() => Promise.resolve())
  const navigate = options.navigate ?? vi.fn<Navigate>()
  render(
    <FamilyPilotPage
      programs={programs}
      reviewers={PEOPLE}
      username={options.username ?? 'manager-user'}
      reload={reload}
      navigate={navigate}
      {...(options.initialProgramId ? { initialProgramId: options.initialProgramId } : {})}
    />
  )
  return { reload, navigate }
}

beforeEach(() => {
  vi.clearAllMocks()
  enrolled = []
  get.mockImplementation((path: string) => {
    if (path.endsWith('/members')) return Promise.resolve({ data: MEMBERS })
    if (path.endsWith('/readiness')) return Promise.resolve({ data: readinessWith(enrolled) })
    return Promise.resolve({ data: [] })
  })
  post.mockImplementation((path: string, body?: { reviewer_id?: string }) => {
    if (path.endsWith('/enroll') && body?.reviewer_id) {
      enrolled = [...enrolled, body.reviewer_id]
      return Promise.resolve({ data: { id: `enr-${body.reviewer_id}` } })
    }
    return Promise.resolve({ data: {} })
  })
})

describe('family pilot page: program', () => {
  it('picks the one active household, one-blotter program and ignores the others', async () => {
    renderPage([
      { ...PILOT, id: 'draft', name: 'Draft', status: 'draft' },
      { ...PILOT, id: 'each', name: 'Per evaluator', reveal_policy: 'ENROLLMENT' },
      { ...PILOT, id: 'group', name: 'Group', blotter_mode: 'SHARED_GROUP' },
      PILOT,
    ])

    expect(await screen.findByText('Family F1 · version v3.2')).toBeInTheDocument()
    expect(screen.queryByLabelText('Family pilot program')).toBeNull()
    await waitFor(() => expect(get).toHaveBeenCalledWith('/calibration/programs/pilot/members'))
    expect(get).not.toHaveBeenCalledWith('/calibration/programs/each/members')
    expect(screen.getByText('active')).toBeInTheDocument()
    expect(
      screen.getByText('whole household together, after the final samples', { selector: 'dd' })
    ).toBeInTheDocument()
    expect(screen.getByText('One per evaluator')).toBeInTheDocument()
    expect(await screen.findByText('3 baseline, 1 hidden repeats, 2 holdouts')).toBeInTheDocument()
    expect(screen.getByText(/Their identities are not shown on this page/)).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/B01|H01/)
  })

  it('never renders a member fragrance, brand, or evidence', async () => {
    renderPage()
    await screen.findByText('3 baseline, 1 hidden repeats, 2 holdouts')

    // innerHTML also covers attributes, titles, ids and hidden text, not just visible text.
    const markup = document.body.innerHTML
    for (const hidden of [
      'Oak Study',
      'Cedar Hour',
      'Amber Night',
      'Rose Ghost',
      'Iris Echo',
      'Secret House',
      'Verified',
      'f-m1',
      'f-m5',
      'edt-current-2026',
      'Baseline"',
    ]) {
      expect(markup).not.toContain(hidden)
    }
  })

  it('says so, with no way to create one, when no family pilot program is active', () => {
    renderPage([
      { ...PILOT, id: 'draft', status: 'draft' },
      { ...PILOT, id: 'each', reveal_policy: 'ENROLLMENT' },
    ])

    expect(
      screen.getByText('No family pilot program is active. Ask the operator to load one.')
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /create/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /enroll/i })).toBeNull()
    expect(get).not.toHaveBeenCalled()
  })

  it('offers a plain choice limited to family pilot programs when there are several', async () => {
    renderPage([
      PILOT,
      { ...PILOT, id: 'second', name: 'Rehearsal' },
      { ...PILOT, id: 'x', status: 'draft' },
    ])

    const select = await screen.findByLabelText('Family pilot program')
    const options = within(select)
      .getAllByRole('option')
      .map((option) => option.textContent)
    expect(options).toEqual(['Choose program', 'Family F1 · v3.2', 'Rehearsal · v3.2'])
    expect(get).not.toHaveBeenCalledWith('/calibration/programs/pilot/members')

    fireEvent.change(select, { target: { value: 'second' } })
    await waitFor(() => expect(get).toHaveBeenCalledWith('/calibration/programs/second/members'))
  })

  it('has none of the builder, activation, catalog, or metrics controls', async () => {
    enrolled = ['r1']
    renderPage()
    await screen.findByText('3 baseline, 1 hidden repeats, 2 holdouts')
    // The readiness panel remounts when the enrollment count arrives; settle it first so the
    // absence checks below see the final page.
    expect(await screen.findByRole('button', { name: 'Freeze checkpoints' })).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: 'Show session progress' })).toBeInTheDocument()

    for (const name of [
      /create draft/i,
      /activate/i,
      /add version/i,
      /search catalog/i,
      /fragella/i,
      /calculate metrics/i,
      /record event/i,
      /preview session plan/i,
    ]) {
      expect(screen.queryByRole('button', { name })).toBeNull()
    }
    for (const label of [
      /blotter mode/i,
      /session order/i,
      /label scheme/i,
      /samples per session/i,
    ]) {
      expect(screen.queryByLabelText(label)).toBeNull()
    }
    expect(screen.queryByLabelText('Reveal policy')).toBeNull()
  })

  it('links to the advanced page and a deep link to another program', async () => {
    const { navigate } = renderPage([PILOT, { ...PILOT, id: 'old', status: 'draft' }], {
      initialProgramId: 'old',
    })
    const link = await screen.findByRole('link', {
      name: 'Advanced setup (not needed for the family pilot)',
    })
    expect(link).toHaveAttribute('href', '/programs/advanced')
    fireEvent.click(link)
    expect(navigate).toHaveBeenCalledWith('programsAdvanced')

    fireEvent.click(screen.getByRole('button', { name: 'Open it in Advanced setup' }))
    expect(navigate).toHaveBeenCalledWith('programsAdvanced', false, { program: 'old' })
  })
})

describe('family pilot page: evaluators', () => {
  it('shows who is enrolled and offers Enroll only for the rest', async () => {
    enrolled = ['r1']
    renderPage()

    const alice = (await screen.findByText('Alice', { selector: 'strong' })).closest('li')
    const byron = screen.getByText('Byron', { selector: 'strong' }).closest('li')
    if (!alice || !byron) throw new Error('rows missing')
    await waitFor(() => expect(within(alice).getByText('Enrolled')).toBeInTheDocument())
    expect(within(alice).queryByRole('button')).toBeNull()
    expect(within(alice).queryByRole('checkbox')).toBeNull()
    expect(within(byron).getByText('Not enrolled')).toBeInTheDocument()
    expect(within(byron).getByRole('button', { name: 'Enroll Byron' })).toBeEnabled()
  })

  it('enrolls with exactly the fixed pilot payload and nothing else', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Enroll Alice' }))

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    expect(post).toHaveBeenCalledWith('/calibration/programs/pilot/enroll', {
      reviewer_id: 'r1',
      recorder_usernames: ['manager-user'],
      session_size: 3,
      label_scheme: 'shared',
      randomization_algorithm: 'shared-triples-latin-rotation-v1',
      persistent_membership_ids: [],
      session_template: null,
    })
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Alice is enrolled with shared blind labels.'
    )
    // Enrolled now, so the row shows it and offers no second enrollment.
    expect(await screen.findByRole('button', { name: 'Enroll Byron' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Enroll Alice' })).toBeNull()
    expect(post).not.toHaveBeenCalledWith(expect.stringContaining('/non-blind'), expect.anything())
  })

  it('marks a facilitator non-blind after enrolling, before reporting done', async () => {
    renderPage()
    const checkbox = await screen.findByLabelText('Facilitator (non-blind) for Byron')
    expect(checkbox).not.toBeChecked()
    fireEvent.click(checkbox)
    fireEvent.click(screen.getByRole('button', { name: 'Enroll Byron' }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Byron is enrolled and marked non-blind.'
    )
    const paths = post.mock.calls.map(([path]) => path)
    expect(paths).toEqual([
      '/calibration/programs/pilot/enroll',
      '/calibration/enrollments/enr-r2/non-blind',
    ])
    expect(post).toHaveBeenLastCalledWith('/calibration/enrollments/enr-r2/non-blind', {
      explanation: 'Facilitator who labels and sprays the samples',
    })
  })

  it('reports a failed non-blind flag clearly and lets the manager retry it', async () => {
    post.mockImplementation((path: string, body?: { reviewer_id?: string }) => {
      if (path.endsWith('/enroll') && body?.reviewer_id) {
        enrolled = [...enrolled, body.reviewer_id]
        return Promise.resolve({ data: { id: `enr-${body.reviewer_id}` } })
      }
      return Promise.reject(new Error('boom'))
    })
    renderPage()
    fireEvent.click(await screen.findByLabelText('Facilitator (non-blind) for Byron'))
    fireEvent.click(screen.getByRole('button', { name: 'Enroll Byron' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Byron is enrolled but could NOT be marked non-blind')
    expect(screen.queryByText(/is enrolled and marked non-blind/)).toBeNull()

    post.mockResolvedValue({ data: {} })
    fireEvent.click(await screen.findByRole('button', { name: 'Retry non-blind flag for Byron' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Byron is marked non-blind.')
    expect(post).toHaveBeenLastCalledWith('/calibration/enrollments/enr-r2/non-blind', {
      explanation: 'Facilitator who labels and sprays the samples',
    })
    expect(screen.queryByRole('button', { name: /Retry non-blind flag/ })).toBeNull()
  })

  it('keeps the add-an-evaluator form', async () => {
    const { reload } = renderPage()
    post.mockResolvedValueOnce({ data: { id: 'r3', name: 'Casey' } })
    fireEvent.change(await screen.findByLabelText('Evaluator name'), {
      target: { value: ' Casey ' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add evaluator' }))

    await waitFor(() => expect(post).toHaveBeenCalledWith('/reviewers', { name: 'Casey' }))
    await waitFor(() => expect(reload).toHaveBeenCalled())
  })
})

describe('family pilot page: enroll guards and failure recovery', () => {
  /** The row of a named evaluator. */
  function rowOf(name: string) {
    const row = screen.getByText(name, { selector: 'strong' }).closest('li')
    if (!row) throw new Error(`row for ${name} missing`)
    return row
  }

  it('disables Enroll when there is no signed-in username', async () => {
    renderPage([PILOT], { username: '' })
    const button = await screen.findByRole('button', { name: 'Enroll Alice' })

    expect(button).toBeDisabled()
    fireEvent.click(button)
    expect(post).not.toHaveBeenCalled()
  })

  it('offers no Enroll until one of several programs is chosen', async () => {
    renderPage([PILOT, { ...PILOT, id: 'pilot-2', name: 'Family F1 again' }])
    await screen.findByLabelText('Family pilot program')

    expect(screen.queryByRole('button', { name: /^Enroll/ })).toBeNull()
    expect(get).not.toHaveBeenCalled()

    fireEvent.change(screen.getByLabelText('Family pilot program'), { target: { value: 'pilot' } })
    expect(await screen.findByRole('button', { name: 'Enroll Alice' })).toBeEnabled()
  })

  it('keeps Enroll disabled until readiness has loaded', async () => {
    let release: (value: { data: ProgramReadiness }) => void = () => undefined
    get.mockImplementation((path: string) => {
      if (path.endsWith('/members')) return Promise.resolve({ data: MEMBERS })
      return new Promise((resolve) => {
        release = resolve
      })
    })
    renderPage()

    const button = await screen.findByRole('button', { name: 'Enroll Alice' })
    expect(button).toBeDisabled()

    release({ data: readinessWith([]) })
    await waitFor(() => expect(button).toBeEnabled())
  })

  it('posts one enrollment for a double click', async () => {
    let finish: (value: { data: { id: string } }) => void = () => undefined
    post.mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve
        })
    )
    renderPage()
    const button = await screen.findByRole('button', { name: 'Enroll Alice' })
    await waitFor(() => expect(button).toBeEnabled())

    fireEvent.click(button)
    fireEvent.click(button)

    expect(post).toHaveBeenCalledTimes(1)
    enrolled = ['r1']
    finish({ data: { id: 'enr-r1' } })
    expect(await screen.findByRole('status')).toHaveTextContent('Alice is enrolled')
    expect(post).toHaveBeenCalledTimes(1)
  })

  it('still marks a facilitator non-blind when the readiness reload fails after enrolling', async () => {
    let readinessDown = false
    get.mockImplementation((path: string) => {
      if (path.endsWith('/members')) return Promise.resolve({ data: MEMBERS })
      if (readinessDown) return Promise.reject(new Error('reload failed'))
      return Promise.resolve({ data: readinessWith(enrolled) })
    })
    renderPage()
    fireEvent.click(await screen.findByLabelText('Facilitator (non-blind) for Byron'))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Enroll Byron' })).toBeEnabled())
    readinessDown = true
    fireEvent.click(screen.getByRole('button', { name: 'Enroll Byron' }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Byron is enrolled and marked non-blind.'
    )
    expect(post).toHaveBeenLastCalledWith('/calibration/enrollments/enr-r2/non-blind', {
      explanation: 'Facilitator who labels and sprays the samples',
    })
    // The row reflects the enrollment even though the reload never came back.
    expect(within(rowOf('Byron')).getByText('Enrolled')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Enroll Byron' })).toBeNull()
  })

  it('exposes Retry with the returned enrollment id when both the reload and the flag fail', async () => {
    let readinessDown = false
    get.mockImplementation((path: string) => {
      if (path.endsWith('/members')) return Promise.resolve({ data: MEMBERS })
      if (readinessDown) return Promise.reject(new Error('reload failed'))
      return Promise.resolve({ data: readinessWith(enrolled) })
    })
    post.mockImplementation((path: string, body?: { reviewer_id?: string }) => {
      if (path.endsWith('/enroll') && body?.reviewer_id) {
        enrolled = [...enrolled, body.reviewer_id]
        return Promise.resolve({ data: { id: `enr-${body.reviewer_id}` } })
      }
      return Promise.reject(new Error('flag failed'))
    })
    renderPage()
    fireEvent.click(await screen.findByLabelText('Facilitator (non-blind) for Byron'))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Enroll Byron' })).toBeEnabled())
    readinessDown = true
    fireEvent.click(screen.getByRole('button', { name: 'Enroll Byron' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Byron is enrolled but could NOT be marked non-blind'
    )
    const retry = await screen.findByRole('button', { name: 'Retry non-blind flag for Byron' })
    expect(screen.queryByRole('button', { name: 'Enroll Byron' })).toBeNull()

    post.mockResolvedValue({ data: {} })
    fireEvent.click(retry)
    expect(await screen.findByRole('status')).toHaveTextContent('Byron is marked non-blind.')
    expect(post).toHaveBeenLastCalledWith('/calibration/enrollments/enr-r2/non-blind', {
      explanation: 'Facilitator who labels and sprays the samples',
    })
    expect(screen.queryByRole('button', { name: /Retry non-blind flag/ })).toBeNull()
  })

  it('reloads readiness after a failed enroll and shows the server state (409)', async () => {
    renderPage()
    // Readiness loaded with Alice not enrolled; the server then gains her enrollment.
    const first = await screen.findByRole('button', { name: 'Enroll Alice' })
    await waitFor(() => expect(first).toBeEnabled())
    enrolled = ['r1']
    post.mockRejectedValue(new Error('Reviewer already enrolled'))
    const readinessCalls = () =>
      get.mock.calls.filter(([path]) => String(path).endsWith('/readiness')).length
    const before = readinessCalls()

    fireEvent.click(first)

    expect(await screen.findByRole('alert')).toHaveTextContent('Request failed.')
    await waitFor(() => expect(readinessCalls()).toBeGreaterThan(before))
    await waitFor(() => expect(within(rowOf('Alice')).getByText('Enrolled')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Enroll Alice' })).toBeNull()
  })

  it('offers Retry when a failed enroll of a ticked facilitator turns out to exist', async () => {
    renderPage()
    fireEvent.click(await screen.findByLabelText('Facilitator (non-blind) for Byron'))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Enroll Byron' })).toBeEnabled())
    // The enrollment went through, but its answer was lost to a timeout.
    enrolled = ['r2']
    post.mockRejectedValueOnce(new Error('timeout'))
    fireEvent.click(screen.getByRole('button', { name: 'Enroll Byron' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Byron is enrolled, but this page cannot confirm they were marked non-blind'
    )
    post.mockResolvedValue({ data: {} })
    fireEvent.click(await screen.findByRole('button', { name: 'Retry non-blind flag for Byron' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Byron is marked non-blind.')
    // The id comes from readiness because the POST response was lost.
    expect(post).toHaveBeenLastCalledWith('/calibration/enrollments/enr-r2/non-blind', {
      explanation: 'Facilitator who labels and sprays the samples',
    })
  })

  it('does not carry facilitator ticks or pending flags to another program', async () => {
    renderPage([PILOT, { ...PILOT, id: 'pilot-2', name: 'Family F1 again' }], {
      initialProgramId: 'pilot',
    })
    const tick = await screen.findByLabelText('Facilitator (non-blind) for Byron')
    fireEvent.click(tick)
    expect(tick).toBeChecked()

    fireEvent.change(screen.getByLabelText('Family pilot program'), {
      target: { value: 'pilot-2' },
    })

    await waitFor(() => expect(get).toHaveBeenCalledWith('/calibration/programs/pilot-2/members'))
    expect(await screen.findByLabelText('Facilitator (non-blind) for Byron')).not.toBeChecked()
  })
})

describe('family pilot page: after the sittings', () => {
  it('shows the reveal policy as text and keeps the irreversible confirmations', async () => {
    enrolled = ['r1']
    const ready = readinessWith(enrolled)
    ready.enrollments = ready.enrollments.map((row) => ({ ...row, checkpoint_blocker: null }))
    get.mockImplementation((path: string) =>
      Promise.resolve({
        data: path.endsWith('/members') ? MEMBERS : path.endsWith('/readiness') ? ready : [],
      })
    )
    renderPage()
    await screen.findByRole('table', { name: 'Checkpoint and reveal readiness' })

    expect(screen.queryByRole('button', { name: 'Save reveal policy' })).toBeNull()
    expect(screen.getByText(/Reveal policy:/)).toHaveTextContent(
      'whole household together, after the final samples'
    )
    // The free-form non-blind panel is not part of this page.
    expect(screen.queryByRole('heading', { name: /holds the answer key/ })).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Freeze checkpoints' }))
    expect(screen.getByRole('group')).toHaveTextContent('A checkpoint cannot be undone')
  })
})
