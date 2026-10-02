import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import App from '../App'
import { HouseIntakePage } from '../pages/HouseIntakePage'
import { emptyPayload, type HouseSubmission } from '../api/houseIntake'

const { get, post, put, del } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
}))
vi.mock('axios', () => ({
  default: {
    create: () => ({ get, post, put, delete: del, patch: vi.fn() }),
    isAxiosError: () => false,
  },
}))

const HOUSE = { username: 'maison-rep', house: 'Maison A', manager: false }

function record(overrides: Partial<HouseSubmission> = {}): HouseSubmission {
  return {
    id: 'sub-1',
    house: 'Maison A',
    status: 'draft',
    created_by: 'maison-rep',
    created_at: '2026-10-01T10:00:00',
    updated_at: '2026-10-01T10:00:00',
    submitted_at: null,
    submitted_by: null,
    permission_state: null,
    supersedes_id: null,
    superseded_by_id: null,
    payload: { ...emptyPayload(), fragrance_name: 'Cèdre Nocturne' },
    ...overrides,
  }
}

function serve(submissions: HouseSubmission[] = []) {
  get.mockImplementation((path: string) => {
    if (path === '/house-intake/access') return Promise.resolve({ data: HOUSE })
    if (path === '/house-intake/submissions') return Promise.resolve({ data: submissions })
    const match = submissions.find((item) => path === `/house-intake/submissions/${item.id}`)
    return match
      ? Promise.resolve({ data: match })
      : Promise.reject(new Error(`Unexpected request: ${path}`))
  })
}

function type(label: string | RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

async function openNewForm() {
  render(<HouseIntakePage access={HOUSE} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Describe a new fragrance' }))
}

function fillComplete() {
  type('Fragrance name', 'Cèdre Nocturne')
  fireEvent.change(screen.getByLabelText('Concentration'), { target: { value: 'EDP' } })
  type(/^Launch year/, '2019')
  fireEvent.click(screen.getByLabelText('On sale now'))
  type('Add top note', 'Bergamot')
  fireEvent.click(within(screen.getByRole('group', { name: 'Top notes' })).getByText('Add'))
  fireEvent.click(screen.getByLabelText('Use it only to check our records'))
  type('Your name', 'Ana Ruiz')
  type('Your role at the house', 'Founder')
  fireEvent.click(screen.getByLabelText(/I am authorised to provide this information/))
}

beforeEach(() => {
  vi.clearAllMocks()
  window.history.replaceState({}, '', '/')
  serve()
})

describe('House intake form', () => {
  it('shows a house account only its own page, without requesting household data', async () => {
    window.history.replaceState({}, '', '/calibration')
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'House submissions' })).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Main navigation' })
    expect(
      within(nav)
        .getAllByRole('link')
        .map((link) => link.textContent)
    ).toEqual(['House submissions'])
    expect(screen.getByText('Fragrance house')).toBeInTheDocument()
    expect(screen.getAllByText('Maison A').length).toBeGreaterThan(0)
    await waitFor(() => expect(window.location.pathname).toBe('/house'))
    const requested = get.mock.calls.map(([path]) => path)
    expect(requested).not.toContain('/reviewers')
    expect(requested).not.toContain('/calibration/enrollments')
  })

  it('saves a draft with notes split from a pasted list, in the order given', async () => {
    post.mockResolvedValue({ data: record() })
    await openNewForm()

    type('Fragrance name', 'Cèdre Nocturne')
    type('Add top note', 'Bergamot, Pink pepper; Cardamom')
    fireEvent.keyDown(screen.getByLabelText('Add top note'), { key: 'Enter' })
    type('Add base note', 'Musk')
    fireEvent.keyDown(screen.getByLabelText('Add base note'), { key: 'Enter' })
    fireEvent.click(screen.getByRole('button', { name: 'Save draft' }))

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    const [path, payload] = post.mock.calls[0]
    expect(path).toBe('/house-intake/submissions')
    expect(payload.fragrance_name).toBe('Cèdre Nocturne')
    expect(payload.notes).toEqual([
      { text: 'Bergamot', position: 'top' },
      { text: 'Pink pepper', position: 'top' },
      { text: 'Cardamom', position: 'top' },
      { text: 'Musk', position: 'base' },
    ])
    expect(await screen.findByText(/Draft saved/)).toBeInTheDocument()
    expect(screen.getByText('All changes saved')).toBeInTheDocument()
  })

  it('lets entries be reordered and removed with named controls', async () => {
    await openNewForm()
    type('Add accord', 'woody, smoky, leathery')
    fireEvent.keyDown(screen.getByLabelText('Add accord'), { key: 'Enter' })

    fireEvent.click(screen.getByRole('button', { name: 'Move woody down' }))
    expect(screen.getByLabelText('Accord 1')).toHaveValue('smoky')
    expect(screen.getByLabelText('Accord 2')).toHaveValue('woody')
    expect(screen.getByRole('button', { name: 'Move smoky up' })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: 'Remove leathery' }))
    expect(screen.queryByLabelText('Accord 3')).not.toBeInTheDocument()
    expect(screen.getByText('Removed leathery.')).toBeInTheDocument()
  })

  it('lists what is missing before submitting and links each problem to its field', async () => {
    await openNewForm()
    type('Fragrance name', 'Cèdre Nocturne')
    fireEvent.click(screen.getByRole('button', { name: 'Review and submit' }))

    const summary = await screen.findByRole('alert')
    expect(summary).toHaveFocus()
    expect(within(summary).getByRole('heading')).toHaveTextContent('8 answers need attention')
    fireEvent.click(within(summary).getByRole('link', { name: 'Choose the concentration' }))
    expect(screen.getByLabelText('Concentration')).toHaveFocus()
    expect(screen.getByLabelText('Concentration')).toHaveAttribute('aria-invalid', 'true')
    fireEvent.click(within(summary).getByRole('link', { name: /Confirm you may provide/ }))
    expect(screen.getByLabelText(/I am authorised/)).toHaveFocus()
    expect(post).not.toHaveBeenCalled()
  })

  it('refuses an invalid barcode or a non-https page even for a draft', async () => {
    await openNewForm()
    type('Fragrance name', 'Cèdre Nocturne')
    type('Add barcode', '3508440005954')
    fireEvent.keyDown(screen.getByLabelText('Add barcode'), { key: 'Enter' })
    type(/^Official product page/, 'http://maison.example/cedre')
    fireEvent.click(screen.getByRole('button', { name: 'Save draft' }))

    const summary = await screen.findByRole('alert')
    expect(within(summary).getByText(/3508440005954/)).toBeInTheDocument()
    expect(within(summary).getByText(/https:\/\//)).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('reviews answers, then submits and returns to the list with a thank-you', async () => {
    const saved = record()
    post.mockImplementation((path: string) =>
      Promise.resolve({
        data: path.endsWith('/submit')
          ? record({ status: 'submitted', submitted_at: '2026-10-02T09:00:00' })
          : saved,
      })
    )
    await openNewForm()
    fillComplete()
    fireEvent.click(screen.getByRole('button', { name: 'Review and submit' }))

    expect(await screen.findByRole('heading', { name: 'Check your answers' })).toHaveFocus()
    expect(screen.getByText('Eau de Parfum')).toBeInTheDocument()
    expect(screen.getByText('Bergamot')).toBeInTheDocument()
    expect(screen.getByText('Ana Ruiz, Founder')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Submit to Fragrance Rater' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/house-intake/submissions/sub-1/submit'))
    const [, payload] = post.mock.calls[0]
    expect(payload).toMatchObject({
      concentration: 'EDP',
      launch_year: 2019,
      availability: 'in_production',
      permission_scope: 'retain_for_qc_only',
      contact_name: 'Ana Ruiz',
      attested: true,
    })
    expect(await screen.findByText(/Your submission has been received/)).toBeInTheDocument()
  })

  it('shows the problems the server reports when it refuses a submission', async () => {
    post.mockImplementation((path: string) =>
      path.endsWith('/submit')
        ? Promise.reject({
            response: {
              status: 422,
              data: {
                detail: {
                  error: 'SUBMISSION_INCOMPLETE',
                  problems: [{ field: 'contact_role', message: 'Enter your role at the house' }],
                },
              },
            },
          })
        : Promise.resolve({ data: record() })
    )
    await openNewForm()
    fillComplete()
    fireEvent.click(screen.getByRole('button', { name: 'Review and submit' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Submit to Fragrance Rater' }))

    const summary = await screen.findByRole('alert')
    expect(within(summary).getByText('Enter your role at the house')).toBeInTheDocument()
    expect(screen.getByLabelText('Your role at the house')).toBeInTheDocument()
  })

  it('keeps pyramid notes when switching to a single list and back', async () => {
    await openNewForm()
    type('Add heart note', 'Iris')
    fireEvent.keyDown(screen.getByLabelText('Add heart note'), { key: 'Enter' })
    fireEvent.click(screen.getByLabelText('As a single list, without a pyramid'))
    expect(screen.queryByLabelText('Heart note 1')).not.toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('As top, heart, and base notes'))
    expect(screen.getByLabelText('Heart note 1')).toHaveValue('Iris')
  })

  it('asks before leaving with unsaved changes', async () => {
    await openNewForm()
    type('Fragrance name', 'Unsaved')
    fireEvent.click(screen.getByRole('button', { name: 'Back to submissions' }))
    expect(screen.getByRole('button', { name: 'Leave without saving' })).toBeInTheDocument()
  })

  it('shows a submitted record read-only and starts a correction from it', async () => {
    const submitted = record({
      status: 'submitted',
      submitted_at: '2026-10-02T09:00:00',
      submitted_by: 'maison-rep',
      permission_state: 'retain_and_train',
      payload: { ...emptyPayload(), fragrance_name: 'Cèdre Nocturne', attested: true },
    })
    serve([submitted])
    post.mockResolvedValue({
      data: record({ id: 'sub-2', supersedes_id: 'sub-1', payload: submitted.payload }),
    })
    render(<HouseIntakePage access={HOUSE} />)

    fireEvent.click(await screen.findByRole('button', { name: 'View Cèdre Nocturne' }))
    expect(screen.getByText('Keep it and use it in recommendations')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save draft' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Start a correction' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/house-intake/submissions/sub-1/revise'))
    expect(await screen.findByText(/You are correcting a submitted record/)).toBeInTheDocument()
    expect(screen.getByLabelText('Fragrance name')).toHaveValue('Cèdre Nocturne')
  })

  it('gives a manager a read-only view across houses', async () => {
    serve([record({ house: 'Atelier B' })])
    render(<HouseIntakePage access={{ username: 'manager', house: null, manager: true }} />)

    expect(await screen.findByText(/Atelier B/)).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Describe a new fragrance' })
    ).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'View Cèdre Nocturne' })).toBeInTheDocument()
  })
})
