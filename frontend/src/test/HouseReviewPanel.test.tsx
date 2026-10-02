import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { HouseReviewPanel } from '../pages/HouseReviewPanel'
import {
  emptyPayload,
  type CatalogCandidate,
  type HouseSubmission,
  type ReviewContext,
} from '../api/houseIntake'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('axios', () => ({
  default: {
    create: () => ({ get, post, put: vi.fn(), delete: vi.fn(), patch: vi.fn() }),
    isAxiosError: () => false,
  },
}))

const submission: HouseSubmission = {
  id: 'sub-1',
  house: 'Maison A',
  status: 'submitted',
  created_by: 'maison-rep',
  created_at: '2026-10-01T10:00:00',
  updated_at: '2026-10-02T09:00:00',
  submitted_at: '2026-10-02T09:00:00',
  submitted_by: 'maison-rep',
  permission_state: 'retain_for_qc_only',
  supersedes_id: null,
  superseded_by_id: null,
  payload: {
    ...emptyPayload(),
    fragrance_name: 'Cèdre Nocturne',
    concentration: 'EDP',
    launch_year: 2019,
    marketed_for: 'not_specified',
    perfumers: ['Ana Ruiz'],
  },
  review_status: 'pending',
  reviewed_at: null,
  review_note: null,
  reviewed_by: null,
  fragrance_id: null,
  source_snapshot_id: null,
}

const match: CatalogCandidate = {
  id: 'f-1',
  name: 'Cèdre Nocturne',
  brand: 'Maison A',
  concentration: 'Eau de Parfum',
  version_key: 'legacy',
  launch_year: 2018,
  gender_target: 'Unisex',
  primary_family: 'Woody',
  subfamily: 'Dry Woods',
  comparison: {
    name: 'same',
    brand: 'same',
    concentration: 'same',
    launch_year: 'differs',
    gender_target: 'house_silent',
  },
}
const otherVersion: CatalogCandidate = {
  ...match,
  id: 'f-2',
  concentration: 'EDT',
  comparison: { ...match.comparison, concentration: 'differs' },
}

const context: ReviewContext = {
  submission,
  proposed: {
    name: 'Cèdre Nocturne',
    brand: 'Maison A',
    concentration: 'EDP',
    launch_year: 2019,
    gender_target: null,
  },
  candidates: [match, otherVersion],
}

const onReviewed = vi.fn()

async function renderPanel() {
  render(<HouseReviewPanel submission={submission} onReviewed={onReviewed} />)
  await screen.findByRole('heading', { name: 'Review' })
}

function confirm(action: string, confirmation: string) {
  fireEvent.click(screen.getByRole('button', { name: action }))
  fireEvent.click(screen.getByRole('button', { name: confirmation }))
}

beforeEach(() => {
  vi.clearAllMocks()
  get.mockResolvedValue({ data: context })
  post.mockResolvedValue({ data: { ...submission, review_status: 'adopted' } })
})

describe('Manager review of a house submission', () => {
  it('states the permission the house granted', async () => {
    await renderPanel()
    expect(screen.getByText('Use it only to check our records')).toBeInTheDocument()
  })

  it('accepts agreeing facts by default and applies a differing year only when chosen', async () => {
    await renderPanel()
    fireEvent.click(screen.getByLabelText(/Cèdre Nocturne · Eau de Parfum/))

    const table = screen.getByRole('table')
    const rows = within(table).getAllByRole('row')
    expect(within(rows[1]).getByLabelText('Accept')).toBeChecked()
    const year = within(table).getByLabelText('Accept and update the catalog')
    expect(year).not.toBeChecked()
    expect(within(table).getByText('The house did not say')).toBeInTheDocument()

    fireEvent.click(year)
    confirm('Adopt as evidence', 'Confirm adoption')
    await waitFor(() => expect(post).toHaveBeenCalled())
    const [path, body] = post.mock.calls[0]
    expect(path).toBe('/house-intake/submissions/sub-1/adopt')
    expect(body).toEqual({
      target: { kind: 'existing', fragrance_id: 'f-1' },
      confirmed_fields: ['name', 'brand', 'concentration', 'launch_year'],
      apply_updates: ['launch_year'],
      record_perfumers: true,
      review_note: null,
    })
    await waitFor(() => expect(onReviewed).toHaveBeenCalled())
  })

  it('warns that a differing concentration means another version and offers no accept', async () => {
    await renderPanel()
    fireEvent.click(screen.getByLabelText(/Maison A · Cèdre Nocturne · EDT/))
    expect(screen.getByRole('note')).toHaveTextContent(/concentration differs/)
    expect(screen.getByText('Differs: likely another version')).toBeInTheDocument()
  })

  it('adds a new version, asking only for what the house cannot supply', async () => {
    await renderPanel()
    fireEvent.click(screen.getByLabelText('Add it as a new catalog version'))
    const adopt = screen.getByRole('button', { name: 'Adopt as evidence' })
    expect(adopt).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: 'No Edwards family fits' }))
    expect(screen.getByLabelText('Edwards family')).toHaveValue('Unclassified')
    fireEvent.change(screen.getByLabelText(/Gender target/), { target: { value: 'Feminine' } })
    expect(adopt).toBeEnabled()
    expect(screen.getAllByText('Recorded from the house')).toHaveLength(4)

    confirm('Adopt as evidence', 'Confirm adoption')
    await waitFor(() => expect(post).toHaveBeenCalled())
    expect(post.mock.calls[0][1].target).toEqual({
      kind: 'new',
      version_key: 'original',
      primary_family: 'Unclassified',
      subfamily: 'Unclassified',
      gender_target: 'Feminine',
    })
  })

  it('declines only with a reason, and sends it', async () => {
    await renderPanel()
    fireEvent.click(screen.getByText('Decline instead'))
    expect(screen.getByRole('button', { name: 'Decline submission' })).toBeDisabled()
    fireEvent.change(screen.getByLabelText(/Reason/), {
      target: { value: 'We need the barcode.' },
    })
    confirm('Decline submission', 'Confirm decline')
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/house-intake/submissions/sub-1/decline', {
        reason: 'We need the barcode.',
      })
    )
  })

  it('searches the catalog for other versions', async () => {
    await renderPanel()
    fireEvent.change(screen.getByLabelText('Search the catalog'), { target: { value: 'Cedre' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() =>
      expect(get).toHaveBeenLastCalledWith('/house-intake/submissions/sub-1/review', {
        params: { q: 'Cedre' },
      })
    )
  })
})
