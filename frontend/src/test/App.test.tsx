import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from '../App'
const { get, post, patch } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}))
vi.mock('axios', () => ({
  default: { create: () => ({ get, post, patch }), isAxiosError: () => false },
}))

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((complete) => {
    resolve = complete
  })
  return { promise, resolve }
}
const enrollment = {
  id: 'assignment',
  program_id: 'p',
  reviewer_id: 'r',
  revealed: false,
  reveal_eligible: false,
  reveal_blocker: 'BLOTTER',
  skin_plan_locked: true,
  presentations: [
    {
      id: 'sample',
      session_id: 'session',
      blind_code: 'A82F',
      position: 1,
      skin_planned: false,
      blotter_locked: false,
      skin_locked: false,
      observations: [],
    },
  ],
}
const recommendationRun = {
  id: 'run-1',
  reviewer_id: 'r',
  created_at: '2026-09-11T12:00:00Z',
  impressions: [
    {
      id: 'impression-1',
      fragrance_id: 'f-1',
      fragrance_name: 'Candidate',
      fragrance_brand: 'House',
      rank: 1,
      match_percent: 78,
      shown_at: '2026-09-11T12:00:05',
      responses: [],
    },
  ],
}
beforeEach(() => {
  vi.clearAllMocks()
  window.history.replaceState({}, '', '/calibration')
  get.mockImplementation((path: string) => {
    const responses: Record<string, unknown> = {
      '/reviewers': [{ id: 'r', name: 'Evaluator' }],
      '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1' }],
      '/calibration/access': { username: 'family-member', manager: false },
      '/calibration/enrollments': [{ id: 'assignment', program_id: 'p', reviewer_id: 'r' }],
      '/calibration/enrollments/assignment': enrollment,
      '/evaluations': [],
    }
    return path in responses
      ? Promise.resolve({ data: responses[path] })
      : Promise.reject(new Error(`Unexpected request: ${path}`))
  })
  post.mockResolvedValue({ data: { id: 'saved' } })
  patch.mockResolvedValue({ data: { id: 'updated' } })
})
describe('Calibration participant workflow', () => {
  it('shows assignment progress and a safe next action on the home page', async () => {
    window.history.replaceState({}, '', '/')
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Your scent journal' })).toBeInTheDocument()
    expect(await screen.findByText('Continue required blind blotter screens.')).toBeInTheDocument()
    expect(screen.getByText(/0 of 1 blind screens locked/)).toBeInTheDocument()
    expect(screen.queryByText('assignment')).not.toBeInTheDocument()
  })

  it('offers reveal from home when only concealed holdout work remains', async () => {
    get.mockImplementation((path: string) => {
      const responses: Record<string, unknown> = {
        '/reviewers': [{ id: 'r', name: 'Evaluator' }],
        '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1' }],
        '/calibration/access': { username: 'family-member', manager: false },
        '/calibration/enrollments': [{ id: 'assignment', program_id: 'p', reviewer_id: 'r' }],
        '/calibration/enrollments/assignment': {
          ...enrollment,
          reveal_eligible: true,
          reveal_blocker: null,
          skin_plan_locked: true,
        },
      }
      return Promise.resolve({ data: responses[path] })
    })
    window.history.replaceState({}, '', '/')
    render(<App />)

    expect(
      await screen.findByText('Required blind work is complete. Reveal when ready.')
    ).toBeInTheDocument()
  })

  it('retries assignment progress without reloading the application', async () => {
    let progressUnavailable = true
    get.mockImplementation((path: string) => {
      const responses: Record<string, unknown> = {
        '/reviewers': [{ id: 'r', name: 'Evaluator' }],
        '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1' }],
        '/calibration/access': { username: 'family-member', manager: false },
        '/calibration/enrollments': [{ id: 'assignment', program_id: 'p', reviewer_id: 'r' }],
        '/calibration/enrollments/assignment': enrollment,
      }
      if (path === '/calibration/enrollments/assignment' && progressUnavailable) {
        return Promise.reject(new Error('offline'))
      }
      return Promise.resolve({ data: responses[path] })
    })
    window.history.replaceState({}, '', '/')
    render(<App />)

    expect(
      await screen.findByText('Request failed. Check your connection and try again.')
    ).toBeInTheDocument()
    progressUnavailable = false
    fireEvent.click(screen.getByRole('button', { name: 'Retry assignment progress' }))

    expect(await screen.findByText('Continue required blind blotter screens.')).toBeInTheDocument()
    expect(screen.queryByText('Request failed. Check your connection and try again.')).toBeNull()
  })

  it('shows the application and hides manager setup for an evaluator', async () => {
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Fragrance Rater' })).toBeInTheDocument()
    await screen.findByRole('option', { name: 'Evaluator · Baseline' })
    expect(screen.getByText('family-member')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Program setup' })).not.toBeInTheDocument()
  })
  it('submits non-detection with zero intensity and null liking', async () => {
    render(<App />)
    await screen.findByRole('option', { name: 'Evaluator · Baseline' })
    fireEvent.change(screen.getByLabelText('Evaluator and program'), {
      target: { value: 'assignment' },
    })
    fireEvent.click(await screen.findByRole('button', { name: /A82F/ }))
    fireEvent.change(screen.getByLabelText('Detected'), { target: { value: 'no' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save observation' }))
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/calibration/presentations/sample/observations',
        expect.objectContaining({ detected: false, intensity: 0, liking: null })
      )
    )
  })
  it('explains reveal eligibility before allowing identity disclosure', async () => {
    render(<App />)
    await screen.findByRole('option', { name: 'Evaluator · Baseline' })
    fireEvent.change(screen.getByLabelText('Evaluator and program'), {
      target: { value: 'assignment' },
    })

    expect(
      await screen.findByText('Required blind blotter screens still need to be locked.')
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reveal completed baseline' })).toBeDisabled()
  })

  it('uses server eligibility when an unlocked concealed holdout remains', async () => {
    get.mockImplementation((path: string) => {
      const responses: Record<string, unknown> = {
        '/reviewers': [{ id: 'r', name: 'Evaluator' }],
        '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1' }],
        '/calibration/access': { username: 'family-member', manager: false },
        '/calibration/enrollments': [{ id: 'assignment', program_id: 'p', reviewer_id: 'r' }],
        '/calibration/enrollments/assignment': {
          ...enrollment,
          reveal_eligible: true,
          reveal_blocker: null,
          skin_plan_locked: true,
        },
      }
      return Promise.resolve({ data: responses[path] })
    })
    render(<App />)
    fireEvent.change(await screen.findByLabelText('Evaluator and program'), {
      target: { value: 'assignment' },
    })

    expect(
      await screen.findByText(
        'All required blind work is locked. The enrollment is eligible to reveal.'
      )
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reveal completed baseline' })).toBeEnabled()
  })
  it('offers the form for recording a new ordinary encounter', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('link', { name: 'My Ratings' }))
    expect(screen.getByRole('button', { name: 'Save new encounter' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/ratings')
    expect(screen.getByRole('main')).toHaveFocus()
    await screen.findByRole('option', { name: 'Evaluator' })
  })

  it('corrects an ordinary encounter without exposing its identifier', async () => {
    get.mockImplementation((path: string) => {
      const responses: Record<string, unknown> = {
        '/reviewers': [{ id: 'r', name: 'Evaluator' }],
        '/calibration/programs': [],
        '/calibration/access': { username: 'family-member', manager: false },
        '/calibration/enrollments': [],
        '/evaluations': [
          {
            id: 'encounter-secret-id',
            fragrance_id: 'f',
            rating: 3,
            notes: 'Original',
            evaluated_at: '2026-09-11T12:00:00',
          },
        ],
      }
      return Promise.resolve({ data: responses[path] })
    })
    window.history.replaceState({}, '', '/ratings')
    render(<App />)
    fireEvent.change(await screen.findByLabelText('Evaluator'), { target: { value: 'r' } })
    fireEvent.click(await screen.findByRole('button', { name: 'Correct this encounter' }))
    fireEvent.change(screen.getByLabelText('Corrected rating'), { target: { value: '5' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save correction' }))

    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith('/evaluations/encounter-secret-id', {
        rating: 5,
        notes: 'Original',
      })
    )
    expect(screen.queryByText('encounter-secret-id')).not.toBeInTheDocument()
  })
  it('records recommendation interest with one interaction', async () => {
    post.mockImplementation((path: string) => {
      if (path === '/recommendation-measurement/runs') {
        return Promise.resolve({ data: recommendationRun })
      }
      return Promise.resolve({ data: { revision: 1 } })
    })
    render(<App />)
    fireEvent.click(await screen.findByRole('link', { name: 'Recommendations' }))
    fireEvent.change(await screen.findByLabelText('Evaluator'), { target: { value: 'r' } })
    fireEvent.click(screen.getByRole('button', { name: 'Get recommendations' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Interested' }))
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/recommendation-measurement/impressions/impression-1/responses',
        expect.objectContaining({ interested: true })
      )
    )
    expect(window.location.search).toBe('?recommendation_run=run-1')
  })
  it('records a recommendation follow-up without asking for identifiers', async () => {
    get.mockImplementation((path: string) => {
      const responses: Record<string, unknown> = {
        '/reviewers': [{ id: 'r', name: 'Evaluator' }],
        '/calibration/programs': [],
        '/calibration/access': { username: 'family-member', manager: false },
        '/calibration/enrollments': [],
        '/calibration/history/r': [
          {
            id: 'historical-encounter',
            workflow: 'ORDINARY',
            fragrance_id: 'f-1',
            observed_at: '2026-09-10T12:00:00Z',
          },
          {
            id: 'premature-encounter',
            workflow: 'ORDINARY',
            fragrance_id: 'f-1',
            observed_at: '2026-09-11T12:00:03Z',
          },
          {
            id: 'encounter-1',
            workflow: 'ORDINARY',
            fragrance_id: 'f-1',
            observed_at: '2026-09-12T12:00:00Z',
          },
        ],
      }
      return Promise.resolve({ data: responses[path] })
    })
    post.mockImplementation((path: string, data: Record<string, unknown>) => {
      if (path === '/recommendation-measurement/runs')
        return Promise.resolve({ data: recommendationRun })
      return Promise.resolve({
        data: {
          id: 'response-1',
          impression_id: 'impression-1',
          revision: 1,
          created_at: '2026-09-12T12:01:00Z',
          ...data,
        },
      })
    })

    window.history.replaceState({}, '', '/recommendations')
    render(<App />)
    fireEvent.change(await screen.findByLabelText('Evaluator'), { target: { value: 'r' } })
    fireEvent.click(screen.getByRole('button', { name: 'Get recommendations' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Update sampling and outcome' }))
    expect(await screen.findByLabelText('Link a later matching encounter')).toBeDisabled()
    fireEvent.change(await screen.findByLabelText('Sampling status'), {
      target: { value: 'SAMPLED' },
    })
    expect(screen.getByLabelText('Link a later matching encounter')).toBeEnabled()
    fireEvent.change(screen.getByLabelText('Link a later matching encounter'), {
      target: { value: 'ORDINARY:encounter-1' },
    })
    expect(
      screen
        .getByLabelText('Link a later matching encounter')
        .querySelector('option[value="ORDINARY:historical-encounter"]')
    ).toBeNull()
    expect(
      screen
        .getByLabelText('Link a later matching encounter')
        .querySelector('option[value="ORDINARY:premature-encounter"]')
    ).toBeNull()
    fireEvent.change(screen.getByLabelText('Would wear'), { target: { value: 'yes' } })
    fireEvent.change(screen.getByLabelText('Would buy'), { target: { value: 'no' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save follow-up' }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/recommendation-measurement/impressions/impression-1/responses',
        expect.objectContaining({
          sampling_state: 'SAMPLED',
          outcome_evaluation_id: 'encounter-1',
          would_wear: true,
          would_buy: false,
        })
      )
    )
    expect(screen.queryByText('encounter-1')).not.toBeInTheDocument()
  })

  it('falls back to a score-based recommendation explanation', async () => {
    post.mockImplementation((path: string) =>
      path === '/recommendation-measurement/runs'
        ? Promise.resolve({ data: recommendationRun })
        : Promise.resolve({ data: { revision: 1 } })
    )
    window.history.replaceState({}, '', '/recommendations')
    render(<App />)
    fireEvent.change(await screen.findByLabelText('Evaluator'), { target: { value: 'r' } })
    fireEvent.click(screen.getByRole('button', { name: 'Get recommendations' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Why this recommendation?' }))

    expect(await screen.findByText(/78% affinity score/)).toBeInTheDocument()
    expect(screen.getByText(/optional service is unavailable/)).toBeInTheDocument()
    expect(get).toHaveBeenCalledWith(
      '/recommendation-measurement/impressions/impression-1/explanation'
    )
  })

  it('caches a successfully loaded empty outcome history', async () => {
    get.mockImplementation((path: string) => {
      const responses: Record<string, unknown> = {
        '/reviewers': [{ id: 'r', name: 'Evaluator' }],
        '/calibration/programs': [],
        '/calibration/access': { username: 'family-member', manager: false },
        '/calibration/enrollments': [],
        '/calibration/history/r': [],
      }
      return Promise.resolve({ data: responses[path] })
    })
    post.mockImplementation((path: string) =>
      path === '/recommendation-measurement/runs'
        ? Promise.resolve({ data: recommendationRun })
        : Promise.resolve({ data: { revision: 1 } })
    )
    window.history.replaceState({}, '', '/recommendations')
    render(<App />)
    fireEvent.change(await screen.findByLabelText('Evaluator'), { target: { value: 'r' } })
    fireEvent.click(screen.getByRole('button', { name: 'Get recommendations' }))
    const followUp = await screen.findByRole('button', { name: 'Update sampling and outcome' })
    fireEvent.click(followUp)
    await screen.findByLabelText('Sampling status')
    fireEvent.click(followUp)

    await waitFor(() =>
      expect(get.mock.calls.filter(([path]) => path === '/calibration/history/r')).toHaveLength(1)
    )
  })

  it('ignores outcome history returned after the evaluator changes', async () => {
    const firstHistory = deferred<{ data: unknown[] }>()
    get.mockImplementation((path: string) => {
      const responses: Record<string, unknown> = {
        '/reviewers': [
          { id: 'r', name: 'Evaluator' },
          { id: 'r2', name: 'Second evaluator' },
        ],
        '/calibration/programs': [],
        '/calibration/access': { username: 'family-member', manager: false },
        '/calibration/enrollments': [],
        '/calibration/history/r2': [],
      }
      if (path === '/calibration/history/r') return firstHistory.promise
      return Promise.resolve({ data: responses[path] })
    })
    post.mockImplementation((_path: string, data: { reviewer_id: string }) =>
      Promise.resolve({ data: { ...recommendationRun, reviewer_id: data.reviewer_id } })
    )
    window.history.replaceState({}, '', '/recommendations')
    render(<App />)
    const reviewer = await screen.findByLabelText('Evaluator')
    fireEvent.change(reviewer, { target: { value: 'r' } })
    fireEvent.click(screen.getByRole('button', { name: 'Get recommendations' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Update sampling and outcome' }))
    fireEvent.change(reviewer, { target: { value: 'r2' } })
    firstHistory.resolve({
      data: [
        {
          id: 'stale-encounter',
          workflow: 'ORDINARY',
          fragrance_id: 'f-1',
          observed_at: '2026-09-12T12:00:00Z',
        },
      ],
    })
    await waitFor(() => expect(screen.queryByText('Candidate')).not.toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Get recommendations' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Update sampling and outcome' }))

    await waitFor(() => expect(get).toHaveBeenCalledWith('/calibration/history/r2'))
    expect(screen.queryByDisplayValue('ORDINARY:stale-encounter')).toBeNull()
  })
  it('restores a saved recommendation run without creating another exposure', async () => {
    window.history.replaceState({}, '', '/recommendations?recommendation_run=run-1')
    get.mockImplementation((path: string) => {
      const responses: Record<string, unknown> = {
        '/reviewers': [{ id: 'r', name: 'Evaluator' }],
        '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1' }],
        '/calibration/access': { username: 'family-member', manager: false },
        '/calibration/enrollments': [{ id: 'assignment', program_id: 'p', reviewer_id: 'r' }],
        '/recommendation-measurement/runs/run-1': recommendationRun,
      }
      return path in responses
        ? Promise.resolve({ data: responses[path] })
        : Promise.reject(new Error(`Unexpected request: ${path}`))
    })

    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Candidate' })).toBeInTheDocument()
    expect(get).toHaveBeenCalledWith('/recommendation-measurement/runs/run-1')
    expect(post).not.toHaveBeenCalledWith('/recommendation-measurement/runs', expect.anything())
  })

  it('loads a route directly and supports browser navigation', async () => {
    window.history.replaceState({}, '', '/ratings')
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Ordinary encounters' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'My Ratings' })).toHaveAttribute('aria-current', 'page')

    window.history.pushState({}, '', '/calibration')
    window.dispatchEvent(new PopStateEvent('popstate'))
    expect(await screen.findByRole('heading', { name: 'Your calibration' })).toBeInTheDocument()
  })

  it('shows manager navigation only from verified access', async () => {
    get.mockImplementation((path: string) => {
      const responses: Record<string, unknown> = {
        '/reviewers': [{ id: 'r', name: 'Evaluator' }],
        '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1', status: 'draft' }],
        '/calibration/access': { username: 'manager-user', manager: true },
        '/calibration/enrollments': [],
      }
      return path in responses
        ? Promise.resolve({ data: responses[path] })
        : Promise.reject(new Error(`Unexpected request: ${path}`))
    })

    render(<App />)

    expect(await screen.findByRole('link', { name: 'Program setup' })).toBeInTheDocument()
    expect(screen.getByText('Manager')).toBeInTheDocument()
  })

  it('requires explicit confirmation before activating a program', async () => {
    get.mockImplementation((path: string) => {
      const responses: Record<string, unknown> = {
        '/reviewers': [{ id: 'r', name: 'Evaluator' }],
        '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1', status: 'draft' }],
        '/calibration/access': { username: 'manager-user', manager: true },
        '/calibration/enrollments': [],
        '/calibration/programs/p/members': [
          {
            id: 'member-secret',
            fragrance_id: 'fragrance-secret',
            fragrance_name: 'Oak Study',
            fragrance_brand: 'Family House',
            concentration: 'EDP',
            version_key: 'oak-2026',
            role: 'UNIVERSAL_BASELINE',
            repeat_of_id: null,
            group_name: 'Baseline',
            identity_evidence: 'Bottle and batch checked',
          },
        ],
      }
      return path in responses
        ? Promise.resolve({ data: responses[path] })
        : Promise.reject(new Error(`Unexpected request: ${path}`))
    })

    render(<App />)
    fireEvent.click(await screen.findByRole('link', { name: 'Program setup' }))
    fireEvent.change(screen.getByLabelText('Program'), { target: { value: 'p' } })
    expect(await screen.findByText('Bottle and batch checked')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Activate and lock definition' }))

    expect(post).not.toHaveBeenCalledWith('/calibration/programs/p/activate')
    const confirm = screen.getByRole('button', { name: 'Confirm activation' })
    expect(confirm).toHaveFocus()
    fireEvent.click(confirm)
    await waitFor(() => expect(post).toHaveBeenCalledWith('/calibration/programs/p/activate'))
  })

  it('includes a scanned GTIN when adding a catalog version to a draft', async () => {
    get.mockImplementation((path: string) => {
      const responses: Record<string, unknown> = {
        '/reviewers': [{ id: 'r', name: 'Evaluator' }],
        '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1', status: 'draft' }],
        '/calibration/access': { username: 'manager-user', manager: true },
        '/calibration/enrollments': [],
        '/calibration/programs/p/members': [],
        '/fragrances': [
          {
            id: 'fragrance-secret',
            name: 'Oak Study',
            brand: 'Family House',
            concentration: 'EDP',
            version_key: 'oak-2026',
          },
        ],
      }
      return path in responses
        ? Promise.resolve({ data: responses[path] })
        : Promise.reject(new Error(`Unexpected request: ${path}`))
    })

    render(<App />)
    fireEvent.click(await screen.findByRole('link', { name: 'Program setup' }))
    fireEvent.change(screen.getByLabelText('Program'), { target: { value: 'p' } })
    // Selecting a program kicks off its own task.run() to load members;
    // the search form's button stays disabled (shared task.busy state)
    // until that settles, so wait for it before interacting further.
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Search catalog' })).not.toBeDisabled()
    )

    fireEvent.change(screen.getByLabelText('Find catalog version'), {
      target: { value: 'Oak Study' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Search catalog' }))
    await waitFor(() =>
      expect(screen.getByRole('option', { name: /Family House/ })).toBeInTheDocument()
    )

    fireEvent.change(screen.getByLabelText('Exact catalog version'), {
      target: { value: 'fragrance-secret' },
    })
    fireEvent.change(screen.getByLabelText('Version verification evidence'), {
      target: { value: 'Bottle and batch checked' },
    })
    fireEvent.change(screen.getByLabelText('GTIN barcode (optional)'), {
      target: { value: '3508440005953' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add version' }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/calibration/programs/p/members', {
        fragrance_id: 'fragrance-secret',
        role: 'UNIVERSAL_BASELINE',
        repeat_of_id: null,
        group_name: 'Baseline',
        identity_evidence: 'Bottle and batch checked',
        gtin: '3508440005953',
      })
    )
  })

  it('runs a manual Fragella check and shows an already-checked result as reference only', async () => {
    const uncheckedMember = {
      id: 'member-unchecked',
      fragrance_id: 'fragrance-unchecked',
      fragrance_name: 'Aimez-Moi',
      fragrance_brand: 'Caron',
      concentration: 'EDT',
      version_key: 'aimez-moi-1996',
      role: 'UNIVERSAL_BASELINE',
      repeat_of_id: null,
      group_name: 'Baseline',
      identity_evidence: 'Bottle and batch checked',
      fragella: null,
    }
    const checkedMember = {
      ...uncheckedMember,
      id: 'member-checked',
      fragrance_id: 'fragrance-checked',
      fragrance_name: 'Fougere Royale',
      identity_evidence: 'Bottle and batch checked',
      fragella: {
        checked_at: '2026-09-13T10:00:00Z',
        query: 'Houbigant Fougere Royale',
        status: 'success',
        error_message: null,
        results: [
          {
            id: 'fougere-royale-2010',
            name: 'Fougere Royale',
            brand: 'Houbigant',
            year: 2010,
            oil_type: 'Eau de Parfum',
            gender: null,
            general_notes: [],
            top_notes: [],
            middle_notes: [],
            base_notes: [],
            confidence: 'medium',
          },
        ],
      },
    }
    get.mockImplementation((path: string) => {
      const responses: Record<string, unknown> = {
        '/reviewers': [{ id: 'r', name: 'Evaluator' }],
        '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1', status: 'draft' }],
        '/calibration/access': { username: 'manager-user', manager: true },
        '/calibration/enrollments': [],
        '/calibration/programs/p/members': [uncheckedMember, checkedMember],
      }
      return path in responses
        ? Promise.resolve({ data: responses[path] })
        : Promise.reject(new Error(`Unexpected request: ${path}`))
    })
    post.mockResolvedValue({
      data: { checked_at: '2026-09-13T10:05:00Z', status: 'success', results: [] },
    })

    render(<App />)
    fireEvent.click(await screen.findByRole('link', { name: 'Program setup' }))
    fireEvent.change(screen.getByLabelText('Program'), { target: { value: 'p' } })

    // Already-checked membership: shows the recorded result, never edits
    // fragrance fields, and offers only a confirmed re-check.
    expect(await screen.findByText(/Fragella checked/)).toBeInTheDocument()
    expect(screen.getByText(/Houbigant/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Re-check Fragella' })).toBeInTheDocument()

    // Re-check, then cancel: no request is spent, and the action reverts
    // to its unconfirmed state.
    fireEvent.click(screen.getByRole('button', { name: 'Re-check Fragella' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(post).not.toHaveBeenCalledWith(
      '/calibration/programs/p/members/member-checked/fragella-lookup'
    )
    expect(screen.getByRole('button', { name: 'Re-check Fragella' })).toBeInTheDocument()

    // Re-check, then confirm: the request is spent against this
    // membership's own path.
    fireEvent.click(screen.getByRole('button', { name: 'Re-check Fragella' }))
    fireEvent.click(screen.getByRole('button', { name: 'Spend another monthly request' }))
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/calibration/programs/p/members/member-checked/fragella-lookup'
      )
    )

    // Never-checked membership: the first check spends the same scarce
    // monthly quota as a re-check, so it is gated behind the same
    // explicit confirmation step, not run on the first click.
    fireEvent.click(screen.getByRole('button', { name: 'Run Fragella check' }))
    expect(post).not.toHaveBeenCalledWith(
      '/calibration/programs/p/members/member-unchecked/fragella-lookup'
    )
    const confirmCheck = screen.getByRole('button', { name: 'Spend a monthly request' })
    expect(confirmCheck).toHaveFocus()
    fireEvent.click(confirmCheck)
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/calibration/programs/p/members/member-unchecked/fragella-lookup'
      )
    )
    await waitFor(() => expect(get).toHaveBeenCalledWith('/calibration/programs/p/members'))
  })

  it('operates the pilot with human-readable manager data', async () => {
    get.mockImplementation((path: string) => {
      const responses: Record<string, unknown> = {
        '/reviewers': [{ id: 'reviewer-secret', name: 'Evaluator' }],
        '/calibration/programs': [
          { id: 'program-secret', name: 'Family pilot', version: '1', status: 'active' },
        ],
        '/calibration/access': { username: 'manager-user', manager: true },
        '/calibration/enrollments': [],
        '/calibration/manager/enrollments': [
          {
            id: 'enrollment-secret',
            program_name: 'Family pilot',
            program_version: '1',
            reviewer_name: 'Evaluator',
            recorder_usernames: ['recorder'],
            total_presentations: 2,
            blotter_complete: 1,
            skin_planned: 0,
            skin_complete: 0,
            reveal_eligible: false,
            reveal_blocker: 'BLOTTER',
            revealed: false,
          },
        ],
        '/recommendation-measurement/operational-events': [],
        '/recommendation-measurement/operational-status': {
          status: 'available',
          unresolved_reviewer_ids: [],
          guidance: 'No unresolved pilot connectivity incidents.',
        },
        '/calibration/enrollments/enrollment-secret/mapping': [
          {
            session_id: 'session-secret',
            position: 1,
            blind_code: 'A82F',
            fragrance_name: 'Oak Study',
            fragrance_brand: 'Family House',
            concentration: 'EDP',
            version_key: 'oak-2026',
            role: 'UNIVERSAL_BASELINE',
          },
        ],
      }
      return path in responses
        ? Promise.resolve({ data: responses[path] })
        : Promise.reject(new Error(`Unexpected request: ${path}`))
    })

    render(<App />)
    fireEvent.click(await screen.findByRole('link', { name: 'Program setup' }))
    fireEvent.click(screen.getByRole('button', { name: 'Refresh operations' }))
    expect(await screen.findByText('1 of 2 blotter samples complete')).toBeInTheDocument()
    expect(screen.getByText('Blotter responses remain')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Label set'), {
      target: { value: 'enrollment-secret' },
    })
    expect(await screen.findByText(/Oak Study/)).toBeInTheDocument()
    expect(screen.getByText(/version oak-2026/)).toBeInTheDocument()
    expect(screen.getByText('A82F')).toBeInTheDocument()
    expect(screen.queryByText('enrollment-secret')).not.toBeInTheDocument()
    expect(screen.queryByText('fragrance-secret')).not.toBeInTheDocument()
  })

  it('ignores an obsolete calibration assignment response', async () => {
    const first = deferred<{ data: typeof enrollment }>()
    const secondEnrollment = {
      ...enrollment,
      id: 'assignment-2',
      presentations: [{ ...enrollment.presentations[0], id: 'sample-2', blind_code: 'B19Q' }],
    }
    const second = deferred<{ data: typeof secondEnrollment }>()
    get.mockImplementation((path: string) => {
      const responses: Record<string, unknown> = {
        '/reviewers': [{ id: 'r', name: 'Evaluator' }],
        '/calibration/programs': [{ id: 'p', name: 'Baseline', version: '1' }],
        '/calibration/access': { username: 'family-member', manager: false },
        '/calibration/enrollments': [
          { id: 'assignment', program_id: 'p', reviewer_id: 'r' },
          { id: 'assignment-2', program_id: 'p', reviewer_id: 'r' },
        ],
      }
      if (path === '/calibration/enrollments/assignment') return first.promise
      if (path === '/calibration/enrollments/assignment-2') return second.promise
      return Promise.resolve({ data: responses[path] })
    })

    render(<App />)
    const assignment = await screen.findByLabelText('Evaluator and program')
    fireEvent.change(assignment, { target: { value: 'assignment' } })
    fireEvent.change(assignment, { target: { value: 'assignment-2' } })
    second.resolve({ data: secondEnrollment })
    expect(await screen.findByRole('button', { name: /B19Q/ })).toBeInTheDocument()
    first.resolve({ data: enrollment })
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /A82F/ })).not.toBeInTheDocument()
    )
  })

  it('redirects a non-manager away from a direct manager URL', async () => {
    window.history.replaceState({}, '', '/programs')
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Your calibration' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/calibration')
    expect(screen.queryByRole('heading', { name: 'Program setup' })).not.toBeInTheDocument()
  })

  it('offers a retry when initial application data cannot be loaded', async () => {
    let unavailable = true
    get.mockImplementation((path: string) => {
      if (unavailable) return Promise.reject(new Error('offline'))
      const responses: Record<string, unknown> = {
        '/reviewers': [{ id: 'r', name: 'Evaluator' }],
        '/calibration/programs': [],
        '/calibration/access': { username: 'family-member', manager: false },
        '/calibration/enrollments': [],
      }
      return Promise.resolve({ data: responses[path] })
    })

    render(<App />)
    expect(
      await screen.findByRole('heading', { name: 'We could not load this page' })
    ).toBeInTheDocument()

    unavailable = false
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('heading', { name: 'Fragrance Rater' })).toBeInTheDocument()
  })

  it('preserves a manager URL when access data fails to load', async () => {
    window.history.replaceState({}, '', '/programs')
    get.mockRejectedValue(new Error('offline'))

    render(<App />)
    expect(
      await screen.findByRole('heading', { name: 'We could not load this page' })
    ).toBeInTheDocument()
    expect(window.location.pathname).toBe('/programs')
  })

  it('keeps a saved recommendation set when creating a replacement fails', async () => {
    window.history.replaceState({}, '', '/recommendations?recommendation_run=run-1')
    get.mockImplementation((path: string) => {
      const responses: Record<string, unknown> = {
        '/reviewers': [{ id: 'r', name: 'Evaluator' }],
        '/calibration/programs': [],
        '/calibration/access': { username: 'family-member', manager: false },
        '/calibration/enrollments': [],
        '/recommendation-measurement/runs/run-1': recommendationRun,
      }
      return Promise.resolve({ data: responses[path] })
    })
    post.mockRejectedValue(new Error('offline'))

    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Candidate' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Start new set' }))
    expect(
      await screen.findByText('Request failed. Check your connection and try again.')
    ).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Candidate' })).toBeInTheDocument()
    expect(window.location.search).toBe('?recommendation_run=run-1')
  })
})
