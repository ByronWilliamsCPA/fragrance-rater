import { useState } from 'react'
import { api } from '../api/client'
import type { EnrollmentReadiness } from '../api/types'
import { ConfirmAction } from '../components/ConfirmAction'
import type { useTask } from '../hooks/useTask'

/** What POST /calibration/enrollments/{id}/non-blind answers. */
type NonBlindResult = { flagged: string[]; already_flagged: string[] }

const defaultExplanation =
  'Declared mapping holder; sprays, times, transcribes and controls the reveal.'

/**
 * Manager action: mark the evaluator who holds the sample-to-code mapping as
 * non-blind.
 *
 * In the facilitated format one person knows which sample is which, so their
 * answers are not blind evidence. Marking them does not delete or hide
 * anything: every session of their enrollment gets a non-blind flag, which
 * keeps the rows out of blind-baseline training while they stay in the
 * evaluation. The written reason is kept on each flag, and repeating the
 * action is harmless.
 */
export function NonBlindPanel({
  enrollments,
  task,
}: {
  enrollments: EnrollmentReadiness[]
  task: ReturnType<typeof useTask>
}) {
  const [enrollmentId, setEnrollmentId] = useState('')
  const [explanation, setExplanation] = useState(defaultExplanation)
  const chosen = enrollments.find((row) => row.enrollment_id === enrollmentId)

  async function markNonBlind() {
    const response = await api.post<NonBlindResult>(
      `/calibration/enrollments/${enrollmentId}/non-blind`,
      { explanation: explanation.trim() }
    )
    const { flagged, already_flagged: already } = response.data
    task.setNotice(
      `${chosen?.reviewer_name ?? 'The evaluator'} is marked non-blind: ` +
        `${flagged.length} session(s) newly flagged, ${already.length} already flagged. ` +
        'Their rows stay in the evaluation and are excluded from blind-baseline training.'
    )
  }

  return (
    <section aria-labelledby="non-blind-heading">
      <h4 id="non-blind-heading">Evaluator who holds the answer key</h4>
      <p>
        Use this for the one evaluator who knows which sample is which, for example the person who
        sprays, times and keeps the mapping. Marking them non-blind does three things:
      </p>
      <ul>
        <li>Every session of their enrollment is flagged non-blind.</li>
        <li>Those rows are excluded from blind-baseline training.</li>
        <li>Those rows are kept in the evaluation. Nothing is deleted or hidden.</li>
      </ul>
      <p>
        The reason below is kept on each flag. Marking the same evaluator again changes nothing.
      </p>
      <div className="fields fields-compact">
        <label>
          Evaluator who holds the mapping
          <select value={enrollmentId} onChange={(event) => setEnrollmentId(event.target.value)}>
            <option value="">Choose an evaluator</option>
            {enrollments.map((row) => (
              <option key={row.enrollment_id} value={row.enrollment_id}>
                {row.reviewer_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Written reason
          <textarea
            rows={2}
            value={explanation}
            onChange={(event) => setExplanation(event.target.value)}
          />
        </label>
      </div>
      <ConfirmAction
        actionLabel="Mark evaluator non-blind"
        confirmLabel="Confirm non-blind"
        description={`Flags every session of ${chosen?.reviewer_name ?? 'this evaluator'} as non-blind, excludes those rows from blind-baseline training, and keeps them in the evaluation.`}
        disabled={task.busy || !chosen || explanation.trim() === ''}
        onConfirm={() => void task.run(markNonBlind)}
      />
    </section>
  )
}
