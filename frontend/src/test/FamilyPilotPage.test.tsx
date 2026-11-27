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
  options: { initialProgramId?: string; navigate?: Navigate } = {}
) {
  const reload = vi.fn(() => Promise.resolve())
  const navigate = options.navigate ?? vi.fn<Navigate>()
  render(
    <FamilyPilotPage
      programs={programs}
      reviewers={PEOPLE}
      username="manager-user"
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
    expect(screen.getByText(/fixed B01 to B39 and H01 to H10 bottles/)).toBeInTheDocument()
  })

  it('never renders a member fragrance, brand, or evidence', async () => {
    renderPage()
    await screen.findByText('3 baseline, 1 hidden repeats, 2 holdouts')

    const text = document.body.textContent ?? ''
    for (const hidden of ['Oak Study', 'Cedar Hour', 'Rose Ghost', 'Secret House', 'Verified']) {
      expect(text).not.toContain(hidden)
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
    expect(screen.getByRole('button', { name: 'Freeze checkpoints' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Show session progress' })).toBeInTheDocument()
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
      label_scheme: 'random',
      randomization_algorithm: 'shared-triples-latin-rotation-v1',
      persistent_membership_ids: [],
      session_template: null,
    })
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Alice is enrolled with random blind labels.'
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
