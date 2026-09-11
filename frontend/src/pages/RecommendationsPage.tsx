import { useEffect, useRef, useState } from 'react'
import { api, requestErrorMessage } from '../api/client'
import type { Person, RecommendationRun } from '../api/types'
import { EmptyState } from '../components/PageState'
import { FeedbackBanner } from '../components/FeedbackBanner'
import { useTask } from '../hooks/useTask'

const recommendationRunParameter = 'recommendation_run'

function persistedRunId() {
  return new URLSearchParams(window.location.search).get(recommendationRunParameter)
}

function persistRunId(runId: string | null) {
  const url = new URL(window.location.href)
  if (runId) url.searchParams.set(recommendationRunParameter, runId)
  else url.searchParams.delete(recommendationRunParameter)
  window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`)
}

export function RecommendationsPage({ reviewers }: { reviewers: Person[] }) {
  const [reviewerId, setReviewerId] = useState('')
  const [recommendationRun, setRecommendationRun] = useState<RecommendationRun | null>(null)
  const [interest, setInterest] = useState<Record<string, boolean>>({})
  const hydrationGeneration = useRef(0)
  const task = useTask()
  const setError = task.setError

  useEffect(() => {
    const runId = persistedRunId()
    if (!runId) return
    const generation = ++hydrationGeneration.current
    void api
      .get<RecommendationRun>(`/recommendation-measurement/runs/${runId}`)
      .then((response) => {
        if (generation !== hydrationGeneration.current || persistedRunId() !== runId) return
        setRecommendationRun(response.data)
        setReviewerId(response.data.reviewer_id)
      })
      .catch((reason: unknown) => {
        if (generation !== hydrationGeneration.current || persistedRunId() !== runId) return
        persistRunId(null)
        setError(requestErrorMessage(reason))
      })
  }, [setError])

  async function hydrate(runId: string) {
    const response = await api.get<RecommendationRun>(`/recommendation-measurement/runs/${runId}`)
    setRecommendationRun(response.data)
    setReviewerId(response.data.reviewer_id)
    setInterest({})
  }

  async function createRun() {
    const response = await api.post<RecommendationRun>('/recommendation-measurement/runs', {
      reviewer_id: reviewerId,
      limit: 10,
      exclude_rated: true,
    })
    setRecommendationRun(response.data)
    persistRunId(response.data.id)
    setInterest({})
    task.setNotice('Recommendations saved. Your response helps measure what is useful.')
  }

  async function startRun() {
    const runId = persistedRunId()
    if (runId) {
      await hydrate(runId)
      task.setNotice('Saved recommendations reopened without creating another impression.')
    } else await createRun()
  }

  async function startNewRun() {
    await createRun()
  }

  async function recordInterest(impressionId: string, interested: boolean) {
    await api.post(`/recommendation-measurement/impressions/${impressionId}/responses`, {
      interested,
    })
    setInterest((current) => ({ ...current, [impressionId]: interested }))
    task.setNotice('Response saved.')
  }

  return (
    <section>
      <div className="page-heading">
        <div>
          <div className="eyebrow">DISCOVER</div>
          <h2>Recommendations</h2>
        </div>
        {recommendationRun && <span className="status-chip">Saved set</span>}
      </div>
      <p>
        Start a new set when you want fresh choices. Opening this saved set again does not count as
        another impression.
      </p>
      <FeedbackBanner error={task.error} notice={task.notice} />
      <label>
        Evaluator
        <select
          value={reviewerId}
          onChange={(event) => {
            hydrationGeneration.current += 1
            setReviewerId(event.target.value)
            setRecommendationRun(null)
            persistRunId(null)
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
      <div className="button-row">
        <button disabled={task.busy || !reviewerId} onClick={() => void task.run(startRun)}>
          Get recommendations
        </button>
        {recommendationRun && (
          <button
            className="secondary"
            disabled={task.busy}
            onClick={() => void task.run(startNewRun)}
          >
            Start new set
          </button>
        )}
      </div>
      {recommendationRun ? (
        <div className="recommendation-grid">
          {recommendationRun.impressions.map((item) => (
            <article className="recommendation-card" key={item.id}>
              <div className="eyebrow">CHOICE {item.rank}</div>
              <h3>{item.fragrance_name}</h3>
              <p>
                {item.fragrance_brand} · {item.match_percent}% affinity
              </p>
              <div className="interest-actions" aria-label={`Interest in ${item.fragrance_name}`}>
                <button
                  aria-pressed={interest[item.id] === true}
                  disabled={task.busy}
                  onClick={() => void task.run(() => recordInterest(item.id, true))}
                >
                  Interested
                </button>
                <button
                  className="secondary"
                  aria-pressed={interest[item.id] === false}
                  disabled={task.busy}
                  onClick={() => void task.run(() => recordInterest(item.id, false))}
                >
                  Pass
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState title="No recommendation set open">
          Choose an evaluator to create or reopen a measured set.
        </EmptyState>
      )}
    </section>
  )
}
