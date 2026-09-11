import { useRef, useState } from 'react'
import { api } from '../api/client'
import type { Assignment, Enrollment, Person, Program } from '../api/types'
import { ConfirmAction } from '../components/ConfirmAction'
import { FeedbackBanner } from '../components/FeedbackBanner'
import { EmptyState } from '../components/PageState'
import { useTask } from '../hooks/useTask'

type CalibrationPageProps = {
  assignments: Assignment[]
  programs: Program[]
  reviewers: Person[]
}

const dimensions = [
  'confidence',
  'sweetness',
  'freshness',
  'density',
  'familiarity',
  'dryness',
  'clean_soapy',
  'earthy_rooty',
  'bodily_animalic',
  'discomfort',
]

export function CalibrationPage({ assignments, programs, reviewers }: CalibrationPageProps) {
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null)
  const [assignmentId, setAssignmentId] = useState('')
  const requestedAssignment = useRef('')
  const refreshGeneration = useRef(0)
  const [selected, setSelected] = useState('')
  const [stage, setStage] = useState('BLOTTER')
  const [detected, setDetected] = useState('')
  const task = useTask()
  const sample = enrollment?.presentations.find((presentation) => presentation.id === selected)

  async function refresh(id = requestedAssignment.current) {
    const generation = ++refreshGeneration.current
    if (!id) {
      setEnrollment(null)
      return
    }
    const response = await api.get<Enrollment>(`/calibration/enrollments/${id}`)
    if (generation === refreshGeneration.current && requestedAssignment.current === id)
      setEnrollment(response.data)
  }

  function scale(name: string, max: number, disabled = false) {
    return (
      <label key={name}>
        {name.replace(/_/g, ' ')}
        <select name={name} defaultValue="" disabled={disabled}>
          <option value="">Unanswered</option>
          {Array.from({ length: max + 1 }, (_, index) => (
            <option key={index} value={index}>
              {index}
            </option>
          ))}
        </select>
      </label>
    )
  }

  async function save(form: HTMLFormElement) {
    if (!sample) return
    const values = Object.fromEntries(new FormData(form))
    const data: Record<string, unknown> = {
      stage,
      elapsed_minutes: Number(values.elapsed_minutes || 0),
      detected: detected === '' ? null : detected === 'yes',
    }
    for (const name of [
      'liking',
      'intensity',
      ...dimensions,
      'opening_liking',
      'drydown_liking',
      'would_wear',
      'would_buy',
      'artistic_appreciation',
      'projection',
      'longevity_minutes',
    ])
      data[name] = !values[name] ? null : Number(values[name])
    if (detected === 'no') {
      data.intensity = 0
      data.liking = null
    }
    for (const name of ['likes', 'dislikes', 'reminds_me_of', 'comments'])
      data[name] = values[name] || null
    data.perceived_notes = values.perceived_notes
      ? String(values.perceived_notes)
          .split(',')
          .map((value) => value.trim())
          .filter(Boolean)
      : null
    await api.post(
      `/calibration/presentations/${sample.id}/${sample.identity ? 'post-reveal' : 'observations'}`,
      data
    )
    form.reset()
    setDetected('')
    await refresh()
    task.setNotice('Observation saved. Original responses are retained.')
  }

  return (
    <>
      <section>
        <div className="page-heading">
          <div>
            <div className="eyebrow">BLIND EVALUATION</div>
            <h2>Your calibration</h2>
          </div>
          {enrollment && (
            <span className="status-chip">
              {enrollment.presentations.filter((item) => item.blotter_locked).length}/
              {enrollment.presentations.length} locked
            </span>
          )}
        </div>
        <p>
          Use the code on your sample. Identities appear after required blind evaluations are
          locked.
        </p>
        <FeedbackBanner error={task.error} notice={task.notice} />
        {assignments.length ? (
          <label>
            Evaluator and program
            <select
              value={assignmentId}
              onChange={(event) => {
                const id = event.target.value
                requestedAssignment.current = id
                setAssignmentId(id)
                setEnrollment(null)
                setSelected('')
                void task.run(() => refresh(id))
              }}
            >
              <option value="">Choose assignment</option>
              {assignments.map((assignment) => (
                <option key={assignment.id} value={assignment.id}>
                  {reviewers.find((reviewer) => reviewer.id === assignment.reviewer_id)?.name ||
                    assignment.reviewer_id}{' '}
                  ·{' '}
                  {programs.find((program) => program.id === assignment.program_id)?.name ||
                    'Program'}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <EmptyState title="No calibration assignments">
            A manager or authorized recorder must assign a program before calibration begins.
          </EmptyState>
        )}
      </section>
      {enrollment && (
        <div className="workspace">
          <aside>
            <h2>Sessions</h2>
            <p>
              {enrollment.presentations.filter((item) => item.blotter_locked).length} /{' '}
              {enrollment.presentations.length} screens locked
            </p>
            {Array.from(
              new Set(enrollment.presentations.map((presentation) => presentation.session_id))
            ).map((sessionId, index) => (
              <div key={sessionId}>
                <h3>Session {index + 1}</h3>
                {enrollment.presentations
                  .filter((presentation) => presentation.session_id === sessionId)
                  .map((presentation) => (
                    <button
                      className="sample"
                      key={presentation.id}
                      aria-pressed={selected === presentation.id}
                      onClick={() => {
                        setSelected(presentation.id)
                        setStage('BLOTTER')
                        setDetected('')
                      }}
                    >
                      {presentation.blind_code}
                      <small>{presentation.blotter_locked ? 'Locked' : 'Open'}</small>
                    </button>
                  ))}
              </div>
            ))}
            <button
              disabled={task.busy || enrollment.skin_plan_locked}
              onClick={() =>
                void task.run(async () => {
                  await api.post(`/calibration/enrollments/${enrollment.id}/lock-skin-plan`)
                  await refresh()
                })
              }
            >
              Finalize skin-test plan
            </button>
            <ConfirmAction
              actionLabel="Reveal completed baseline"
              confirmLabel="Confirm reveal"
              description="Reveal makes fragrance identities visible for this enrollment. Confirm that all required blind responses are locked."
              disabled={task.busy || enrollment.revealed}
              onConfirm={() =>
                void task.run(async () => {
                  await api.post(`/calibration/enrollments/${enrollment.id}/reveal`)
                  await refresh()
                })
              }
            />
          </aside>
          <section>
            {sample ? (
              <>
                <div className="eyebrow">SAMPLE {sample.position}</div>
                <h2>{sample.blind_code}</h2>
                {sample.identity && (
                  <p className="notice">
                    {sample.identity.brand} · {sample.identity.name} ·{' '}
                    {sample.identity.concentration}
                  </p>
                )}
                <label>
                  Stage
                  <select value={stage} onChange={(event) => setStage(event.target.value)}>
                    <option value="BLOTTER">Blotter screen</option>
                    {sample.skin_planned && <option value="SKIN">Skin test</option>}
                  </select>
                </label>
                {!sample.skin_planned && !enrollment.skin_plan_locked && (
                  <form
                    onSubmit={(event) => {
                      event.preventDefault()
                      const reason = String(new FormData(event.currentTarget).get('reason'))
                      void task.run(async () => {
                        await api.post(`/calibration/presentations/${sample.id}/skin-plan`, {
                          reason,
                        })
                        await refresh()
                      })
                    }}
                  >
                    <label>
                      Reason to add a skin test
                      <input name="reason" required placeholder="For example: low confidence" />
                    </label>
                    <button disabled={task.busy}>Plan skin test</button>
                  </form>
                )}
                <form
                  key={`${sample.id}-${stage}`}
                  onSubmit={(event) => {
                    event.preventDefault()
                    const form = event.currentTarget
                    void task.run(() => save(form))
                  }}
                >
                  <fieldset
                    disabled={
                      task.busy ||
                      (!sample.identity &&
                        (stage === 'BLOTTER' ? sample.blotter_locked : sample.skin_locked))
                    }
                  >
                    <legend>
                      {sample.identity ? 'Post-reveal observation' : 'Blind observation'}
                    </legend>
                    <div className="fields">
                      <label>
                        Elapsed minutes
                        <input name="elapsed_minutes" type="number" min="0" defaultValue="0" />
                      </label>
                      <label>
                        Detected
                        <select
                          value={detected}
                          onChange={(event) => setDetected(event.target.value)}
                        >
                          <option value="">Unanswered</option>
                          <option value="yes">Yes</option>
                          <option value="no">No</option>
                        </select>
                      </label>
                      {scale('intensity', 5, detected === 'no')}
                      {scale('liking', 10, detected === 'no')}
                      {dimensions.map((dimension) => scale(dimension, 5))}
                    </div>
                    {detected === 'no' && (
                      <p>Intensity will be saved as 0; liking will remain unanswered.</p>
                    )}
                    {stage === 'SKIN' && (
                      <div className="fields">
                        {[
                          'opening_liking',
                          'drydown_liking',
                          'would_wear',
                          'would_buy',
                          'artistic_appreciation',
                        ].map((dimension) => scale(dimension, 10))}
                        {scale('projection', 5)}
                        <label>
                          Longevity (minutes)
                          <input name="longevity_minutes" type="number" min="0" />
                        </label>
                      </div>
                    )}
                    <label>
                      Perceived notes
                      <input
                        name="perceived_notes"
                        placeholder="Your own words, separated by commas"
                      />
                    </label>
                    {['likes', 'dislikes', 'reminds_me_of', 'comments'].map((name) => (
                      <label key={name}>
                        {name.replace(/_/g, ' ')}
                        <textarea name={name} rows={2} />
                      </label>
                    ))}
                    <button>Save observation</button>
                  </fieldset>
                </form>
                {!sample.identity && (
                  <button
                    disabled={
                      task.busy ||
                      (stage === 'BLOTTER' ? sample.blotter_locked : sample.skin_locked)
                    }
                    onClick={() =>
                      void task.run(async () => {
                        await api.post(`/calibration/presentations/${sample.id}/lock/${stage}`)
                        await refresh()
                      })
                    }
                  >
                    Lock {stage.toLowerCase()} responses
                  </button>
                )}
                <h3>Saved observations</h3>
                {sample.observations.length ? (
                  sample.observations.map((observation) => (
                    <article key={observation.id}>
                      <strong>
                        {observation.stage} · {observation.elapsed_minutes} min ·{' '}
                        {observation.phase.replace(/_/g, ' ')}
                      </strong>
                      <p>
                        Liking: {observation.liking ?? 'Unanswered'}
                        {observation.comments ? ` · ${observation.comments}` : ''}
                      </p>
                    </article>
                  ))
                ) : (
                  <EmptyState title="No observations yet">
                    Save a timepoint to begin this sample history.
                  </EmptyState>
                )}
              </>
            ) : (
              <EmptyState title="Select a sample">Choose a blind code from a session.</EmptyState>
            )}
          </section>
        </div>
      )}
    </>
  )
}
