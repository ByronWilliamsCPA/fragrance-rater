import { useEffect, useRef, useState } from 'react'
import { api, requestErrorMessage } from '../api/client'
import type {
  HistoryItem,
  Person,
  RecommendationImpression,
  RecommendationResponse,
  RecommendationRun,
} from '../api/types'
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
  const [followUpId, setFollowUpId] = useState('')
  const [outcomes, setOutcomes] = useState<HistoryItem[]>([])
  const [explanations, setExplanations] = useState<Record<string, string>>({})
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
  }

  async function createRun() {
    const response = await api.post<RecommendationRun>('/recommendation-measurement/runs', {
      reviewer_id: reviewerId,
      limit: 10,
      exclude_rated: true,
    })
    setRecommendationRun(response.data)
    persistRunId(response.data.id)
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

  function latestResponse(item: RecommendationImpression) {
    return item.responses?.at(-1)
  }

  function currentPayload(item: RecommendationImpression) {
    const latest = latestResponse(item)
    return {
      interested: latest?.interested ?? null,
      sampling_state: latest?.sampling_state ?? null,
      unavailable_reason: latest?.unavailable_reason ?? null,
      outcome_evaluation_id: latest?.outcome_evaluation_id ?? null,
      outcome_observation_id: latest?.outcome_observation_id ?? null,
      would_wear: latest?.would_wear ?? null,
      would_buy: latest?.would_buy ?? null,
    }
  }

  async function recordResponse(
    item: RecommendationImpression,
    changes: Partial<ReturnType<typeof currentPayload>>
  ) {
    const response = await api.post<RecommendationResponse>(
      `/recommendation-measurement/impressions/${item.id}/responses`,
      { ...currentPayload(item), ...changes }
    )
    setRecommendationRun((current) =>
      current
        ? {
            ...current,
            impressions: current.impressions.map((impression) =>
              impression.id === item.id
                ? {
                    ...impression,
                    responses: [...(impression.responses ?? []), response.data],
                  }
                : impression
            ),
          }
        : current
    )
    task.setNotice('Response saved.')
  }

  async function openFollowUp(item: RecommendationImpression) {
    setFollowUpId(item.id)
    if (!outcomes.length) {
      const response = await api.get<HistoryItem[]>(`/calibration/history/${reviewerId}`)
      setOutcomes(response.data)
    }
  }

  async function explain(item: RecommendationImpression) {
    try {
      const response = await api.get<{ explanation: string }>(
        `/recommendations/${reviewerId}/${item.fragrance_id}/explain`
      )
      setExplanations((current) => ({ ...current, [item.id]: response.data.explanation }))
    } catch {
      setExplanations((current) => ({
        ...current,
        [item.id]: `${item.fragrance_name} has a ${item.match_percent}% affinity score from your recorded preference history. The optional personalized explanation service is unavailable, but your recommendations and responses still work.`,
      }))
      task.setNotice('Showing a score-based explanation while the optional service is unavailable.')
    }
  }

  async function saveFollowUp(item: RecommendationImpression, form: HTMLFormElement) {
    const values = Object.fromEntries(new FormData(form))
    const samplingState = String(values.sampling_state || '') || null
    const outcome = String(values.outcome || '')
    const [workflow, outcomeId] = outcome.split(':')
    await recordResponse(item, {
      sampling_state: samplingState as ReturnType<typeof currentPayload>['sampling_state'],
      unavailable_reason:
        samplingState === 'UNAVAILABLE' ? String(values.unavailable_reason || '') || null : null,
      outcome_evaluation_id:
        samplingState === 'SAMPLED' && workflow === 'ORDINARY' ? outcomeId : null,
      outcome_observation_id:
        samplingState === 'SAMPLED' && workflow === 'CONTROLLED' ? outcomeId : null,
      would_wear: values.would_wear === '' ? null : values.would_wear === 'yes',
      would_buy: values.would_buy === '' ? null : values.would_buy === 'yes',
    })
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
            setFollowUpId('')
            setOutcomes([])
            setExplanations({})
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
              {(() => {
                const latest = latestResponse(item)
                const eligibleOutcomes = outcomes.filter((outcome) => {
                  const observedAt = outcome.observed_at || outcome.created_at
                  return (
                    (outcome.fragrance_id || outcome.identity?.fragrance_id) ===
                      item.fragrance_id &&
                    Boolean(
                      observedAt &&
                      recommendationRun.created_at &&
                      new Date(observedAt) >= new Date(recommendationRun.created_at)
                    )
                  )
                })
                return (
                  <>
                    <div className="eyebrow">CHOICE {item.rank}</div>
                    <h3>{item.fragrance_name}</h3>
                    <p>
                      {item.fragrance_brand} · {item.match_percent}% affinity
                    </p>
                    <button
                      className="secondary"
                      disabled={task.busy}
                      onClick={() => void task.run(() => explain(item))}
                    >
                      Why this recommendation?
                    </button>
                    {explanations[item.id] && <p>{explanations[item.id]}</p>}
                    <div
                      className="interest-actions"
                      aria-label={`Interest in ${item.fragrance_name}`}
                    >
                      <button
                        aria-pressed={latest?.interested === true}
                        disabled={task.busy}
                        onClick={() =>
                          void task.run(() => recordResponse(item, { interested: true }))
                        }
                      >
                        Interested
                      </button>
                      <button
                        className="secondary"
                        aria-pressed={latest?.interested === false}
                        disabled={task.busy}
                        onClick={() =>
                          void task.run(() => recordResponse(item, { interested: false }))
                        }
                      >
                        Pass
                      </button>
                    </div>
                    <button
                      className="secondary"
                      disabled={task.busy}
                      aria-expanded={followUpId === item.id}
                      onClick={() => void task.run(() => openFollowUp(item))}
                    >
                      Update sampling and outcome
                    </button>
                    {followUpId === item.id && (
                      <form
                        onSubmit={(event) => {
                          event.preventDefault()
                          const form = event.currentTarget
                          void task.run(() => saveFollowUp(item, form))
                        }}
                      >
                        <label>
                          Sampling status
                          <select name="sampling_state" defaultValue={latest?.sampling_state ?? ''}>
                            <option value="">Not set</option>
                            <option value="PLANNED">Plan to sample</option>
                            <option value="ACQUIRED">Sample acquired</option>
                            <option value="SAMPLED">Sampled</option>
                            <option value="UNAVAILABLE">Unavailable</option>
                          </select>
                        </label>
                        <label>
                          Unavailable reason
                          <input
                            name="unavailable_reason"
                            defaultValue={latest?.unavailable_reason ?? ''}
                            placeholder="Only needed when unavailable"
                          />
                        </label>
                        <label>
                          Link a later matching encounter
                          <select
                            name="outcome"
                            defaultValue={
                              latest?.outcome_evaluation_id
                                ? `ORDINARY:${latest.outcome_evaluation_id}`
                                : latest?.outcome_observation_id
                                  ? `CONTROLLED:${latest.outcome_observation_id}`
                                  : ''
                            }
                          >
                            <option value="">No linked encounter</option>
                            {eligibleOutcomes.map((outcome) => (
                              <option
                                key={`${outcome.workflow}:${outcome.id}`}
                                value={`${outcome.workflow}:${outcome.id}`}
                              >
                                {outcome.workflow === 'ORDINARY'
                                  ? 'Journal encounter'
                                  : 'Calibration observation'}{' '}
                                ·{' '}
                                {new Date(
                                  outcome.observed_at || outcome.created_at || ''
                                ).toLocaleDateString()}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Would wear
                          <select
                            name="would_wear"
                            defaultValue={
                              latest?.would_wear == null ? '' : latest.would_wear ? 'yes' : 'no'
                            }
                          >
                            <option value="">Unanswered</option>
                            <option value="yes">Yes</option>
                            <option value="no">No</option>
                          </select>
                        </label>
                        <label>
                          Would buy
                          <select
                            name="would_buy"
                            defaultValue={
                              latest?.would_buy == null ? '' : latest.would_buy ? 'yes' : 'no'
                            }
                          >
                            <option value="">Unanswered</option>
                            <option value="yes">Yes</option>
                            <option value="no">No</option>
                          </select>
                        </label>
                        <button disabled={task.busy}>Save follow-up</button>
                        {item.responses?.length > 0 && (
                          <details>
                            <summary>{item.responses.length} saved response revisions</summary>
                            <ol>
                              {item.responses.map((response) => (
                                <li key={response.id}>
                                  Revision {response.revision} ·{' '}
                                  {new Date(response.created_at).toLocaleString()}
                                </li>
                              ))}
                            </ol>
                          </details>
                        )}
                      </form>
                    )}
                  </>
                )
              })()}
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
