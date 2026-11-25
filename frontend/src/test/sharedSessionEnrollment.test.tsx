import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ProgramSetupPage } from '../pages/ProgramSetupPage'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))

vi.mock('../api/client', () => ({
  api: { get, post },
  requestErrorMessage: () => 'Request failed.',
}))

const SHARED = 'shared-triples-latin-rotation-v1'

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
})

function renderPage() {
  render(
    <ProgramSetupPage
      programs={[{ id: 'p', name: 'Pilot', version: '1', status: 'active' }]}
      reviewers={[{ id: 'rev', name: 'Evaluator One' }]}
      reload={() => Promise.resolve()}
      initialProgramId="p"
    />
  )
  const form = screen.getByRole('heading', { name: '2. Enrollment' }).nextElementSibling
  if (!(form instanceof HTMLFormElement)) throw new Error('Enrollment form missing')
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
})
