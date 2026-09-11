import { useRef, useState } from 'react'
import { api } from '../api/client'
import type { Encounter, FragranceSummary, Person } from '../api/types'
import { EmptyState } from '../components/PageState'
import { FeedbackBanner } from '../components/FeedbackBanner'
import { useTask } from '../hooks/useTask'

function formatUtc(value: string) {
  const timestamp = /(Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`
  return new Date(timestamp).toLocaleString(undefined, {
    timeZone: 'UTC',
    timeZoneName: 'short',
  })
}

export function RatingsPage({ reviewers }: { reviewers: Person[] }) {
  const [catalog, setCatalog] = useState<FragranceSummary[]>([])
  const [catalogQuery, setCatalogQuery] = useState('')
  const [history, setHistory] = useState<Encounter[]>([])
  const [reviewerId, setReviewerId] = useState('')
  const [editingId, setEditingId] = useState('')
  const historyGeneration = useRef(0)
  const task = useTask()

  async function searchCatalog() {
    const response = await api.get<FragranceSummary[]>('/fragrances', {
      params: { q: catalogQuery, limit: 100 },
    })
    setCatalog(response.data)
    if (!response.data.length) task.setNotice('No fragrances matched that search.')
  }

  async function loadHistory(reviewerId: string) {
    const generation = ++historyGeneration.current
    if (!reviewerId) {
      setHistory([])
      return
    }
    const response = await api.get<Encounter[]>('/evaluations', {
      params: { reviewer_id: reviewerId },
    })
    if (generation === historyGeneration.current) setHistory(response.data)
  }

  async function saveEncounter(form: HTMLFormElement) {
    const values = Object.fromEntries(new FormData(form))
    await api.post('/evaluations', {
      ...values,
      rating: Number(values.rating),
      evaluated_at: values.evaluated_at
        ? new Date(String(values.evaluated_at)).toISOString()
        : null,
    })
    const savedReviewerId = String(values.reviewer_id)
    form.reset()
    setReviewerId(savedReviewerId)
    await loadHistory(savedReviewerId)
    task.setNotice('New encounter saved.')
  }

  async function correctEncounter(encounterId: string, form: HTMLFormElement) {
    const values = Object.fromEntries(new FormData(form))
    await api.patch(`/evaluations/${encounterId}`, {
      rating: Number(values.rating),
      notes: String(values.notes || '') || null,
    })
    setEditingId('')
    await loadHistory(reviewerId)
    task.setNotice('Correction saved; the encounter date and fragrance are unchanged.')
  }

  return (
    <section>
      <div className="page-heading">
        <div>
          <div className="eyebrow">JOURNAL</div>
          <h2>Ordinary encounters</h2>
        </div>
      </div>
      <p>Each submission adds a dated encounter. Earlier ratings remain in history.</p>
      <FeedbackBanner error={task.error} notice={task.notice} />
      <div className="search-row">
        <label>
          Search fragrances
          <input
            value={catalogQuery}
            onChange={(event) => setCatalogQuery(event.target.value)}
            placeholder="Fragrance or house"
          />
        </label>
        <button disabled={task.busy} onClick={() => void task.run(searchCatalog)}>
          Search catalog
        </button>
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault()
          const form = event.currentTarget
          void task.run(() => saveEncounter(form))
        }}
      >
        <label>
          Evaluator
          <select
            name="reviewer_id"
            required
            value={reviewerId}
            disabled={task.busy}
            onChange={(event) => {
              const id = event.target.value
              setReviewerId(id)
              void task.run(() => loadHistory(id))
            }}
          >
            <option value="">Choose evaluator</option>
            {reviewers.map((reviewer) => (
              <option key={reviewer.id} value={reviewer.id}>
                {reviewer.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Fragrance version
          <select name="fragrance_id" required>
            <option value="">Search and choose a fragrance</option>
            {catalog.map((fragrance) => (
              <option key={fragrance.id} value={fragrance.id}>
                {fragrance.brand} · {fragrance.name} · {fragrance.concentration}
              </option>
            ))}
          </select>
        </label>
        <div className="fields fields-compact">
          <label>
            Rating (1–5)
            <input name="rating" type="number" min="1" max="5" required />
          </label>
          <label>
            Encounter date (optional)
            <input name="evaluated_at" type="datetime-local" />
          </label>
        </div>
        <label>
          Observations
          <textarea name="notes" />
        </label>
        <button disabled={task.busy}>Save new encounter</button>
      </form>
      <h3>Encounter history</h3>
      {history.length ? (
        history.map((encounter) => (
          <article key={encounter.id}>
            <strong>
              {catalog.find((item) => item.id === encounter.fragrance_id)?.name ||
                'Saved fragrance'}{' '}
              · {encounter.rating}/5
            </strong>
            <p>{formatUtc(encounter.evaluated_at)}</p>
            {encounter.notes && <p>{encounter.notes}</p>}
            {editingId === encounter.id ? (
              <form
                onSubmit={(event) => {
                  event.preventDefault()
                  const form = event.currentTarget
                  void task.run(() => correctEncounter(encounter.id, form))
                }}
              >
                <label>
                  Corrected rating
                  <input
                    name="rating"
                    type="number"
                    min="1"
                    max="5"
                    defaultValue={encounter.rating}
                    required
                  />
                </label>
                <label>
                  Corrected observations
                  <textarea name="notes" defaultValue={encounter.notes ?? ''} />
                </label>
                <div className="button-row">
                  <button disabled={task.busy}>Save correction</button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => setEditingId('')}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            ) : (
              <button className="secondary" onClick={() => setEditingId(encounter.id)}>
                Correct this encounter
              </button>
            )}
          </article>
        ))
      ) : (
        <EmptyState title="No encounters loaded">
          Choose an evaluator to see history, or save a new encounter.
        </EmptyState>
      )}
    </section>
  )
}
