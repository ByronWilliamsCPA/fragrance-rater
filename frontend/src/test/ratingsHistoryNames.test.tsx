import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { delay, http, HttpResponse } from 'msw'
import { RatingsPage } from '../pages/RatingsPage'
import { apiUrl, getJson, server } from './msw/server'

/*
 * Found by the real-stack tier: after a reload the encounter history said
 * "Saved fragrance" for every row, because the label came from the catalog
 * search results, which are empty until the evaluator searches. The history now
 * looks up the names it needs.
 */
const reviewers = [{ id: 'r1', name: 'Evaluator One' }]

function encounter(id: string, fragranceId: string, rating: number) {
  return {
    id,
    reviewer_id: 'r1',
    fragrance_id: fragranceId,
    rating,
    notes: '',
    evaluated_at: '2026-10-30T12:00:00Z',
    worn_by_reviewer_id: null,
  }
}

async function chooseEvaluator() {
  fireEvent.change((await screen.findAllByLabelText('Evaluator'))[0], { target: { value: 'r1' } })
}

describe('encounter history names', () => {
  it('names each fragrance even though nothing has been searched', async () => {
    server.use(
      getJson('/evaluations', [encounter('e1', 'f1', 4), encounter('e2', 'f2', 2)]),
      getJson('/fragrances/f1', { id: 'f1', name: 'Signature' }),
      getJson('/fragrances/f2', { id: 'f2', name: 'Second Skin' })
    )
    render(<RatingsPage reviewers={reviewers} />)

    await chooseEvaluator()

    expect(await screen.findByText('Signature · 4/5')).toBeInTheDocument()
    expect(await screen.findByText('Second Skin · 2/5')).toBeInTheDocument()
  })

  it('asks for each fragrance once, however many encounters share it', async () => {
    let lookups = 0
    server.use(
      getJson('/evaluations', [encounter('e1', 'f1', 4), encounter('e2', 'f1', 5)]),
      http.get(apiUrl('/fragrances/f1'), () => {
        lookups += 1
        return HttpResponse.json({ id: 'f1', name: 'Signature' })
      })
    )
    render(<RatingsPage reviewers={reviewers} />)

    await chooseEvaluator()

    expect(await screen.findByText('Signature · 5/5')).toBeInTheDocument()
    expect(lookups).toBe(1)
  })

  it('still shows the history when a fragrance can no longer be fetched', async () => {
    server.use(
      getJson('/evaluations', [encounter('e1', 'gone', 3), encounter('e2', 'f1', 4)]),
      getJson('/fragrances/gone', { detail: 'Fragrance not found' }, 404),
      getJson('/fragrances/f1', { id: 'f1', name: 'Signature' })
    )
    render(<RatingsPage reviewers={reviewers} />)

    await chooseEvaluator()

    expect(await screen.findByText('Signature · 4/5')).toBeInTheDocument()
    expect(screen.getByText('Saved fragrance · 3/5')).toBeInTheDocument()
  })

  it('does not keep the page busy while a name is still being looked up', async () => {
    server.use(
      getJson('/evaluations', [encounter('e1', 'slow', 3)]),
      http.get(apiUrl('/fragrances/slow'), async () => {
        await delay('infinite')
        return HttpResponse.json({ id: 'slow', name: 'Never arrives' })
      })
    )
    render(<RatingsPage reviewers={reviewers} />)

    await chooseEvaluator()

    expect(await screen.findByText('Saved fragrance · 3/5')).toBeInTheDocument()
    expect((await screen.findAllByLabelText('Evaluator'))[0]).toBeEnabled()
  })

  it('keeps a name taken from the catalog after a later search replaces the catalog', async () => {
    let lookups = 0
    let searches = 0
    server.use(
      http.get(apiUrl('/fragrances'), () => {
        searches += 1
        return HttpResponse.json(searches === 1 ? [{ id: 'f1', name: 'Signature' }] : [])
      }),
      getJson('/evaluations', [encounter('e1', 'f1', 4)]),
      http.get(apiUrl('/fragrances/f1'), () => {
        lookups += 1
        return HttpResponse.json({ id: 'f1', name: 'Signature' })
      })
    )
    render(<RatingsPage reviewers={reviewers} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Search catalog' }))
    await waitFor(() => expect(searches).toBe(1))
    await chooseEvaluator()
    expect(await screen.findByText('Signature · 4/5')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Search catalog' }))
    await waitFor(() => expect(searches).toBe(2))

    expect(screen.getByText('Signature · 4/5')).toBeInTheDocument()
    expect(lookups).toBe(0)
  })
})
