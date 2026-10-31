import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Enrollment } from '../api/types'
import { allAssessed, rankableSamples, rankError } from '../content/ranking'
import type { useTask } from '../hooks/useTask'

type RankEvent = { response_status: string }

/**
 * End-of-session ranking of the samples the evaluator detected, best first.
 *
 * Ties are allowed (1, 1, 3). Ranking is never required: the evaluator can say
 * they would rather not or could not, and each of those is recorded as such.
 * It happens before reveal, so it is a blind judgment.
 */
export function RankingStep({
  enrollment,
  task,
  onDone,
}: {
  enrollment: Enrollment
  task: ReturnType<typeof useTask>
  onDone: () => void
}) {
  const sessionId = enrollment.presentations[0]?.session_id
  const [places, setPlaces] = useState<Record<string, string>>({})
  const [checked, setChecked] = useState(!sessionId)
  const samples = rankableSamples(enrollment.presentations)

  useEffect(() => {
    if (!sessionId) return
    void task.run(async () => {
      const events = await api.get<RankEvent[]>(`/calibration/sessions/${sessionId}/rankings`)
      const last = events.data.at(-1)
      if (last && last.response_status !== 'invalidated') onDone()
      setChecked(true)
    })
    // Read once per enrollment.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enrollment.id])

  if (!checked) return null

  if (!allAssessed(enrollment.presentations)) {
    return (
      <>
        <p className="notice">Every sample needs a response before it can be ranked.</p>
        <button className="secondary" onClick={onDone}>
          Continue without ranking
        </button>
      </>
    )
  }

  if (samples.length < 2) {
    return (
      <>
        <p className="notice">Fewer than two samples were detected, so there is nothing to rank.</p>
        <button onClick={onDone}>Continue</button>
      </>
    )
  }

  const positions = samples.map((sample) => (places[sample.id] ? Number(places[sample.id]) : null))
  const problem = rankError(positions)

  async function submit(status: 'completed' | 'skipped' | 'unable_to_assess') {
    await api.post(`/calibration/sessions/${sessionId}/rankings`, {
      stage: 'BLOTTER',
      response_status: status,
      ...(status === 'completed'
        ? {
            entries: samples.map((sample, index) => ({
              presentation_id: sample.id,
              rank_position: positions[index],
            })),
          }
        : {}),
    })
    onDone()
  }

  return (
    <>
      <p className="notice">
        Rank the samples you could smell, 1 for the one you liked most. Samples can share a place:
        give both 1, and the next sample is 3.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault()
          if (!problem) void task.run(() => submit('completed'))
        }}
      >
        <fieldset disabled={task.busy}>
          <legend>Your ranking</legend>
          {samples.map((sample) => (
            <label key={sample.id}>
              Sample {sample.position} (code {sample.blind_code})
              <select
                value={places[sample.id] ?? ''}
                onChange={(event) => setPlaces({ ...places, [sample.id]: event.target.value })}
              >
                <option value="">Choose a place</option>
                {samples.map((_, index) => (
                  <option key={index} value={index + 1}>
                    {index + 1}
                  </option>
                ))}
              </select>
            </label>
          ))}
          {problem && Object.keys(places).length > 0 && (
            <p className="field-error" role="alert">
              {problem}
            </p>
          )}
          <button disabled={problem !== null}>Save ranking</button>
        </fieldset>
      </form>
      <div className="fields fields-compact">
        <button
          className="secondary"
          disabled={task.busy}
          onClick={() => void task.run(() => submit('skipped'))}
        >
          I would rather not rank
        </button>
        <button
          className="secondary"
          disabled={task.busy}
          onClick={() => void task.run(() => submit('unable_to_assess'))}
        >
          I could not tell them apart
        </button>
      </div>
    </>
  )
}
