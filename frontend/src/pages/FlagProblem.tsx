import { useState } from 'react'
import { api } from '../api/client'
import type { Enrollment } from '../api/types'
import type { useTask } from '../hooks/useTask'

/** What an evaluator can report, in their words; values are API flag codes. */
export const flagReasons = [
  { value: 'evaluator_reported_problem', label: 'Something went wrong' },
  { value: 'sample_spill', label: 'A sample was spilled' },
  { value: 'competing_odor', label: 'Another smell got in the way' },
  { value: 'interrupted', label: 'I was interrupted' },
  { value: 'mislabel_suspected', label: 'The sample may be mislabelled' },
  { value: 'instrument_fault', label: 'This form is not working properly' },
]

/**
 * "Flag a problem with this session or sample".
 *
 * A flag describes the evidence; it never changes or hides it. It is always
 * available, and raising one is how an evaluator says a result should be read
 * with care.
 */
export function FlagProblem({
  enrollment,
  task,
}: {
  enrollment: Enrollment
  task: ReturnType<typeof useTask>
}) {
  const [open, setOpen] = useState(false)
  const sessionId = enrollment.presentations[0]?.session_id

  if (!open) {
    return (
      <button className="secondary" onClick={() => setOpen(true)}>
        Flag a problem
      </button>
    )
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        const values = Object.fromEntries(new FormData(event.currentTarget))
        const target = String(values.target)
        void task.run(async () => {
          await api.post('/calibration/quality-flags', {
            action: 'raised',
            source: 'evaluator',
            disposition: 'review',
            severity: 'minor',
            target_type: target === 'session' ? 'session' : 'presentation',
            target_id: target === 'session' ? sessionId : target,
            code: values.code,
            explanation: values.explanation || null,
          })
          setOpen(false)
          task.setNotice('Thank you. The problem is noted and your answers are kept.')
        })
      }}
    >
      <fieldset disabled={task.busy}>
        <legend>Flag a problem</legend>
        <label>
          What is it about?
          <select name="target" defaultValue="session">
            <option value="session">The whole session</option>
            {enrollment.presentations.map((sample) => (
              <option key={sample.id} value={sample.id}>
                Sample {sample.position} (code {sample.blind_code})
              </option>
            ))}
          </select>
        </label>
        <label>
          What happened?
          <select name="code" defaultValue="evaluator_reported_problem">
            {flagReasons.map((reason) => (
              <option key={reason.value} value={reason.value}>
                {reason.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Tell us more (optional)
          <textarea name="explanation" rows={2} />
        </label>
        <button>Send</button>
        <button type="button" className="secondary" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </fieldset>
    </form>
  )
}
