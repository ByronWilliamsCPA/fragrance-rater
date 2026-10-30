import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from '../App'
import { HouseIntakePage } from '../pages/HouseIntakePage'
import { HouseSubmissionSummary } from '../pages/HouseSubmissionSummary'
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
    review_status: null,
    reviewed_at: null,
    review_note: null,
    reviewed_by: null,
    fragrance_id: null,
    source_snapshot_id: null,
    ...overrides,
  }
}

function serve(records: HouseSubmission[]) {
  get.mockImplementation((path: string) => {
    if (path === '/house-intake/access') return Promise.resolve({ data: HOUSE })
    if (path === '/house-intake/submissions') return Promise.resolve({ data: records })
    const found = records.find((item) => path === `/house-intake/submissions/${item.id}`)
    return found ? Promise.resolve({ data: found }) : Promise.reject(new Error(path))
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  window.history.replaceState({}, '', '/')
})

describe('House intake edge cases', () => {
  it('tells an offboarded house account it is no longer active', async () => {
    get.mockImplementation((path: string) =>
      path === '/house-intake/access'
        ? Promise.resolve({
            data: { username: 'former-rep', house: null, manager: false, house_account: true },
          })
        : Promise.reject(new Error(`Unexpected request: ${path}`))
    )
    render(<App />)
    expect(await screen.findByText(/no longer active/)).toBeInTheDocument()
    expect(get).toHaveBeenCalledTimes(1)
  })

  it('shows the load error instead of an endless spinner', async () => {
    get.mockRejectedValue(new Error('offline'))
    render(<HouseIntakePage access={HOUSE} />)
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByText('Loading submissions…')).not.toBeInTheDocument()
  })

  it('moves between a record and the correction that replaced it', async () => {
    const original = record({
      status: 'submitted',
      submitted_at: '2026-10-01T12:00:00',
      review_status: 'superseded',
      superseded_by_id: 'sub-2',
    })
    const correction = record({
      id: 'sub-2',
      status: 'submitted',
      submitted_at: '2026-10-02T12:00:00',
      review_status: 'pending',
      supersedes_id: 'sub-1',
      payload: { ...emptyPayload(), fragrance_name: 'Cèdre Nocturne (corrected)' },
    })
    serve([original, correction])
    render(<HouseIntakePage access={HOUSE} />)

    expect(await screen.findByText('Replaced by a correction')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'View Cèdre Nocturne' }))
    fireEvent.click(screen.getByRole('button', { name: 'View the correction' }))
    expect(
      await screen.findByRole('heading', { name: 'Cèdre Nocturne (corrected)' })
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'View the earlier record' }))
    expect(await screen.findByRole('heading', { name: 'Cèdre Nocturne' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Back to submissions' }))
    expect(await screen.findByRole('heading', { name: 'House submissions' })).toBeInTheDocument()
  })

  it('discards a draft after confirmation', async () => {
    serve([record()])
    del.mockResolvedValue({})
    render(<HouseIntakePage access={HOUSE} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Continue editing Cèdre Nocturne' }))
    fireEvent.click(screen.getByRole('button', { name: 'Discard this draft' }))
    fireEvent.click(screen.getByRole('button', { name: 'Discard draft' }))
    await waitFor(() => expect(del).toHaveBeenCalledWith('/house-intake/submissions/sub-1'))
    expect(await screen.findByText('Draft discarded.')).toBeInTheDocument()
  })

  it('saves an edited draft with PUT and names a custom concentration', async () => {
    serve([record()])
    put.mockResolvedValue({ data: record() })
    render(<HouseIntakePage access={HOUSE} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Continue editing Cèdre Nocturne' }))
    fireEvent.change(screen.getByLabelText('Concentration'), { target: { value: 'OTHER' } })
    fireEvent.change(screen.getByLabelText('What the house calls it'), {
      target: { value: 'Eau Fraîche' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save draft' }))
    await waitFor(() => expect(put).toHaveBeenCalled())
    const [path, body] = put.mock.calls[0]
    expect(path).toBe('/house-intake/submissions/sub-1')
    expect(body).toMatchObject({ concentration: 'OTHER', concentration_other: 'Eau Fraîche' })
  })

  it('shows a server error that is not a list of problems', async () => {
    serve([record()])
    put.mockRejectedValue(new Error('Server unavailable'))
    render(<HouseIntakePage access={HOUSE} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Continue editing Cèdre Nocturne' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save draft' }))
    expect(await screen.findByText(/Request failed/)).toBeInTheDocument()
  })

  it('summarizes a single-list fragrance with its page link and own concentration', () => {
    render(
      <HouseSubmissionSummary
        house="Maison A"
        payload={{
          ...emptyPayload(),
          fragrance_name: 'Oud Solaire',
          concentration: 'OTHER',
          concentration_other: 'Attar',
          note_structure: 'linear',
          notes: [
            { text: 'Oud', position: 'unspecified' },
            { text: 'Saffron', position: 'unspecified' },
          ],
          product_url: 'https://maison.example/oud',
          contact_name: 'Ana Ruiz',
          contact_role: 'Founder',
          attested: true,
          description: 'Line one\nLine two',
        }}
      />
    )
    expect(screen.getByText('Notes (no pyramid)')).toBeInTheDocument()
    expect(screen.getByText('Attar')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'https://maison.example/oud' })).toHaveAttribute(
      'rel',
      'noopener noreferrer nofollow'
    )
    expect(screen.getByText('Yes')).toBeInTheDocument()
  })
})
