import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ProgramSetupPage } from '../pages/ProgramSetupPage'

const { get, post, put } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
}))

vi.mock('../api/client', () => ({
  api: { get, post, put },
  requestErrorMessage: () => 'Request failed.',
}))

const SHARED = 'shared-triples-latin-rotation-v1'
const GROUP = 'shared-triples-group-blotter-v1'

const member = (id: string, role: string, name: string, repeatOf: string | null = null) => ({
  id,
  fragrance_id: `f-${id}`,
  fragrance_name: name,
  fragrance_brand: 'House',
  concentration: 'EDT',
  version_key: 'edt-current-2026',
  role,
  repeat_of_id: repeatOf,
  group_name: '',
  identity_evidence: 'Verified',
  fragella: null,
})

const preview = {
  source: 'generated',
  next_rotation: 0,
  session_size: 1,
  session_template: [['m1'], ['m2'], ['r1'], ['h1']],
  sessions: [
    {
      number: 1,
      block: 'baseline',
      members: [
        {
          membership_id: 'm1',
          role: 'UNIVERSAL_BASELINE',
          fragrance_name: 'Alpha',
          fragrance_brand: 'House',
          persistent: true,
        },
      ],
    },
    {
      number: 4,
      block: 'holdout',
      members: [
        {
          membership_id: 'h1',
          role: 'HOLDOUT',
          fragrance_name: 'Omega',
          fragrance_brand: 'House',
          persistent: false,
        },
      ],
    },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  get.mockImplementation((path: string) =>
    path === '/calibration/programs/p/members'
      ? Promise.resolve({
          data: [
            member('m1', 'UNIVERSAL_BASELINE', 'Alpha'),
            member('m2', 'UNIVERSAL_BASELINE', 'Beta'),
            member('r1', 'HIDDEN_REPEAT', 'Alpha', 'm1'),
            member('h1', 'HOLDOUT', 'Omega'),
          ],
        })
      : Promise.resolve({ data: [] })
  )
  post.mockImplementation((path: string) =>
    path.endsWith('/session-template/preview')
      ? Promise.resolve({ data: preview })
      : Promise.resolve({ data: { id: 'enrollment' } })
  )
  put.mockResolvedValue({ data: { id: 'p', blotter_mode: 'SHARED_GROUP' } })
})

function renderPage(blotterMode?: 'INDIVIDUAL' | 'SHARED_GROUP', reload = () => Promise.resolve()) {
  render(
    <ProgramSetupPage
      programs={[
        {
          id: 'p',
          name: 'Pilot',
          version: '1',
          status: 'active',
          ...(blotterMode ? { blotter_mode: blotterMode } : {}),
        },
      ]}
      reviewers={[{ id: 'rev', name: 'Evaluator One' }]}
      reload={reload}
      initialProgramId="p"
    />
  )
  const form = screen.getByRole('button', { name: 'Enroll evaluator' }).closest('form')
  if (!form) throw new Error('Enrollment form missing')
  return within(form)
}

describe('shared-session enrollment', () => {
  it('keeps the independent shuffle as the default with a label choice', async () => {
    const form = renderPage()
    await waitFor(() => expect(get).toHaveBeenCalledWith('/calibration/programs/p/members'))
    expect(form.getByLabelText('Session order')).toHaveValue('system-random-shuffle-v1')
    expect(form.getByLabelText('Blind label scheme')).toBeInTheDocument()
    expect(form.queryByRole('button', { name: 'Preview session plan' })).toBeNull()

    fireEvent.change(form.getByLabelText('Evaluator'), { target: { value: 'rev' } })
    fireEvent.change(form.getByLabelText('Authorized recorder usernames'), {
      target: { value: 'recorder' },
    })
    fireEvent.click(form.getByRole('button', { name: 'Enroll evaluator' }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/calibration/programs/p/enroll', {
        reviewer_id: 'rev',
        recorder_usernames: ['recorder'],
        session_size: 3,
        label_scheme: 'standard',
      })
    )
  })

  it('previews a shared plan with identities collapsed and enrolls with its template', async () => {
    const form = renderPage()
    fireEvent.change(form.getByLabelText('Session order'), { target: { value: SHARED } })
    await waitFor(() =>
      expect(form.getAllByRole('option', { name: 'House Alpha' })).toHaveLength(1)
    )
    // Shared sessions never offer the standard labels.
    expect(form.queryByLabelText('Blind label scheme')).toBeNull()
    // Hidden repeats are not offered separately; they inherit their original.
    const persistent = form.getByLabelText(/persistent or animalic/)
    expect(within(persistent).getAllByRole('option')).toHaveLength(3)

    fireEvent.change(form.getByLabelText('Samples per session'), { target: { value: '1' } })
    within(persistent).getByRole('option', { name: 'House Alpha' }).setAttribute('selected', '')
    fireEvent.click(form.getByRole('button', { name: 'Preview session plan' }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/calibration/programs/p/session-template/preview', {
        session_size: 1,
        persistent_membership_ids: ['m1'],
      })
    )
    const plan = await form.findByLabelText('Session plan preview')
    expect(plan).toHaveTextContent('2 sessions')
    // Identities sit inside a closed manager-only disclosure.
    const details = plan.querySelector('details')
    expect(details).not.toBeNull()
    expect(details!.open).toBe(false)
    expect(within(plan).getByText('Show fragrance identities (manager only)')).toBeInTheDocument()

    fireEvent.change(form.getByLabelText('Evaluator'), { target: { value: 'rev' } })
    fireEvent.change(form.getByLabelText('Authorized recorder usernames'), {
      target: { value: 'recorder' },
    })
    fireEvent.click(form.getByRole('button', { name: 'Enroll evaluator' }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/calibration/programs/p/enroll', {
        reviewer_id: 'rev',
        recorder_usernames: ['recorder'],
        session_size: 1,
        randomization_algorithm: SHARED,
        label_scheme: 'random',
        persistent_membership_ids: ['m1'],
        session_template: preview.session_template,
      })
    )
    // The shared settings stay for the next evaluator; only the evaluator resets.
    await waitFor(() => expect(form.getByLabelText('Evaluator')).toHaveValue(''))
    expect(form.getByLabelText('Session order')).toHaveValue(SHARED)
    expect(form.getByLabelText('Samples per session')).toHaveValue(1)
  })

  it('drops a preview whose inputs changed, including a late response', async () => {
    let resolvePreview: (value: { data: typeof preview }) => void = () => undefined
    post.mockImplementation((path: string) =>
      path.endsWith('/session-template/preview')
        ? new Promise((resolve) => {
            resolvePreview = resolve
          })
        : Promise.resolve({ data: { id: 'enrollment' } })
    )
    const form = renderPage()
    fireEvent.change(form.getByLabelText('Session order'), { target: { value: SHARED } })
    const previewButton = form.getByRole('button', { name: 'Preview session plan' })
    // Loading the members keeps the shared task busy; wait until it settles.
    await waitFor(() => expect(previewButton).toBeEnabled())
    fireEvent.click(previewButton)
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    // The size changes while the request is still in flight.
    fireEvent.change(form.getByLabelText('Samples per session'), { target: { value: '1' } })
    await act(async () => resolvePreview({ data: preview }))
    expect(form.queryByLabelText('Session plan preview')).toBeNull()

    post.mockImplementation((path: string) =>
      path.endsWith('/session-template/preview')
        ? Promise.resolve({ data: preview })
        : Promise.resolve({ data: { id: 'enrollment' } })
    )
    fireEvent.click(form.getByRole('button', { name: 'Preview session plan' }))
    await form.findByLabelText('Session plan preview')
    // Changing the persistent samples invalidates the shown plan too.
    fireEvent.change(form.getByLabelText(/persistent or animalic/))
    expect(form.queryByLabelText('Session plan preview')).toBeNull()
  })

  it('offers no group blotter by default and says what the group mode trades away', () => {
    renderPage()
    const select = screen.getByLabelText('Blotter mode for this program')
    expect(select).toHaveValue('INDIVIDUAL')
    expect(screen.getAllByText(/confounded with their seat in the circle/)).toHaveLength(1)
    expect(screen.getByText(/shares each sample's blind code and the session order/)).toBeVisible()
    expect(screen.getByText(/flagged as group-blotter scores/)).toBeVisible()
  })

  it('creates a draft without a mode unless the group session is chosen', async () => {
    render(<ProgramSetupPage programs={[]} reviewers={[]} reload={() => Promise.resolve()} />)
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'F1' } })
    fireEvent.change(screen.getByLabelText('Version'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create draft' }))
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/calibration/programs', {
        name: 'F1',
        version: '2',
        description: '',
      })
    )

    // The form clears itself once the draft exists; only then fill the next one.
    await waitFor(() => expect(screen.getByLabelText('Name')).toHaveValue(''))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'G' } })
    fireEvent.change(screen.getByLabelText('Version'), { target: { value: '3' } })
    fireEvent.change(screen.getByLabelText('Blotter mode'), { target: { value: 'SHARED_GROUP' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create draft' }))
    await waitFor(() =>
      expect(post).toHaveBeenLastCalledWith('/calibration/programs', {
        name: 'G',
        version: '3',
        description: '',
        blotter_mode: 'SHARED_GROUP',
      })
    )
  })

  it('changes the mode of the selected program and reloads', async () => {
    const reload = vi.fn(() => Promise.resolve())
    renderPage('INDIVIDUAL', reload)
    await waitFor(() => expect(get).toHaveBeenCalledWith('/calibration/programs/p/members'))
    fireEvent.change(screen.getByLabelText('Blotter mode for this program'), {
      target: { value: 'SHARED_GROUP' },
    })
    await waitFor(() =>
      expect(put).toHaveBeenCalledWith('/calibration/programs/p/blotter-mode', {
        blotter_mode: 'SHARED_GROUP',
      })
    )
    await waitFor(() => expect(reload).toHaveBeenCalled())
  })

  it('says so when a group program goes back to one blotter per evaluator', async () => {
    put.mockResolvedValue({ data: { id: 'p', blotter_mode: 'INDIVIDUAL' } })
    renderPage('SHARED_GROUP')
    await waitFor(() => expect(get).toHaveBeenCalledWith('/calibration/programs/p/members'))
    fireEvent.change(screen.getByLabelText('Blotter mode for this program'), {
      target: { value: 'INDIVIDUAL' },
    })
    await waitFor(() =>
      expect(put).toHaveBeenCalledWith('/calibration/programs/p/blotter-mode', {
        blotter_mode: 'INDIVIDUAL',
      })
    )
    expect(await screen.findByText('One blotter per evaluator selected.')).toBeInTheDocument()
  })

  it('shows the server refusal when the mode is already locked', async () => {
    put.mockRejectedValue(new Error('locked'))
    renderPage('INDIVIDUAL')
    await waitFor(() => expect(get).toHaveBeenCalledWith('/calibration/programs/p/members'))
    fireEvent.change(screen.getByLabelText('Blotter mode for this program'), {
      target: { value: 'SHARED_GROUP' },
    })
    expect(await screen.findByText('Request failed.')).toBeInTheDocument()
  })

  it('enrolls a group program with the group algorithm and no order choice', async () => {
    const form = renderPage('SHARED_GROUP')
    await waitFor(() => expect(get).toHaveBeenCalledWith('/calibration/programs/p/members'))
    const order = form.getByLabelText('Session order')
    expect(order).toHaveValue(GROUP)
    expect(order).toBeDisabled()
    expect(form.getAllByRole('option')).not.toContainEqual(
      expect.objectContaining({ value: SHARED })
    )
    // Group sessions never offer the standard labels either.
    expect(form.queryByLabelText('Blind label scheme')).toBeNull()
    expect(form.getByText(/from one blotter passed around the group/)).toBeVisible()

    fireEvent.change(form.getByLabelText('Evaluator'), { target: { value: 'rev' } })
    fireEvent.change(form.getByLabelText('Authorized recorder usernames'), {
      target: { value: 'recorder' },
    })
    fireEvent.change(form.getByLabelText('Samples per session'), { target: { value: '1' } })
    fireEvent.click(form.getByRole('button', { name: 'Preview session plan' }))
    await form.findByLabelText('Session plan preview')
    fireEvent.click(form.getByRole('button', { name: 'Enroll evaluator' }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/calibration/programs/p/enroll', {
        reviewer_id: 'rev',
        recorder_usernames: ['recorder'],
        session_size: 1,
        label_scheme: 'random',
        randomization_algorithm: GROUP,
        persistent_membership_ids: [],
        session_template: preview.session_template,
      })
    )
  })
})
