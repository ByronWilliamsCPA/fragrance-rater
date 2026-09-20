import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { Assignment, Enrollment, Person, Program } from '../api/types'
import { ConfirmAction } from '../components/ConfirmAction'
import { FeedbackBanner } from '../components/FeedbackBanner'
import { EmptyState } from '../components/PageState'
import { ScaleField } from '../components/ScaleField'
import {
  blotterGroups,
  numericFieldNames,
  observationNotes,
  skinGroups,
  type ScaleGroup,
} from '../content/calibrationScales'
import { useTask } from '../hooks/useTask'
import { followRouteLink, pathFor, type Route } from '../routing/routes'

type CalibrationPageProps = {
  assignments: Assignment[]
  programs: Program[]
  reviewers: Person[]
  navigate: (route: Route) => void
  initialAssignmentId?: string
}

/**
 * Renders one group of scales under a shared heading.
 *
 * The heading is what carries the descriptive/affective separation: without
 * it the twelve scales read as one undifferentiated run, and an evaluator has
 * no cue that "Discomfort" is a fact about them rather than about the scent.
 */
function ScaleGroupFields({
  group,
  isDisabled,
}: {
  group: ScaleGroup
  isDisabled?: (name: string) => boolean
}) {
  return (
    <div className="scale-group">
      <h3 className="scale-group__legend">{group.legend}</h3>
      <p className="scale-group__description">{group.description}</p>
      <div className="scale-stack">
        {group.scales.map((item) => (
          <ScaleField key={item.name} scale={item} disabled={isDisabled?.(item.name)} />
        ))}
      </div>
    </div>
  )
}

/**
 * Non-detection forces intensity to 0 and clears liking, so those two must not
 * accept input. The perceptual dimensions stay enabled, which is the behaviour
 * this form already had: whether they should also be closed off when nothing
 * was smelled is a data-model question, not a presentational one.
 */
function disabledOnNonDetection(name: string) {
  return name === 'intensity' || name === 'liking'
}

/**
 * Orders a sample's observations into a readable log.
 *
 * Blotter screens precede skin tests, and within a stage the timepoints run
 * earliest first. The API does not guarantee an order, and an out-of-sequence
 * row in an evaporation curve is actively misleading rather than merely untidy.
 */
function timeOrdered(observations: Enrollment['presentations'][number]['observations']) {
  const stageRank = (stage: string) => (stage === 'SKIN' ? 1 : 0)
  return [...observations].sort(
    (first, second) =>
      stageRank(first.stage) - stageRank(second.stage) ||
      first.elapsed_minutes - second.elapsed_minutes
  )
}

export function CalibrationPage({
  assignments,
  programs,
  reviewers,
  navigate,
  initialAssignmentId,
}: CalibrationPageProps) {
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null)
  const [assignmentId, setAssignmentId] = useState(initialAssignmentId ?? '')
  const requestedAssignment = useRef(initialAssignmentId ?? '')
  const refreshGeneration = useRef(0)
  const [selected, setSelected] = useState('')
  const [stage, setStage] = useState('BLOTTER')
  const [detected, setDetected] = useState('')
  const task = useTask()
  const sample = enrollment?.presentations.find((presentation) => presentation.id === selected)
  function enrollmentGuidance() {
    if (!enrollment) return ''
    if (enrollment.revealed) return 'Identities are revealed. You may add post-reveal observations.'
    if (enrollment.reveal_blocker === 'SKIN_PLAN')
      return 'All blotter screens are locked. Review and finalize the skin-test plan.'
    if (enrollment.reveal_blocker === 'BLOTTER')
      return 'Required blind blotter screens still need to be locked.'
    if (enrollment.reveal_blocker === 'SKIN')
      return 'Planned blind skin tests still need to be locked.'
    return 'All required blind work is locked. The enrollment is eligible to reveal.'
  }

  const refresh = useCallback(async (id = requestedAssignment.current) => {
    const generation = ++refreshGeneration.current
    if (!id) {
      setEnrollment(null)
      return
    }
    const response = await api.get<Enrollment>(`/calibration/enrollments/${id}`)
    if (generation === refreshGeneration.current && requestedAssignment.current === id)
      setEnrollment(response.data)
  }, [])

  useEffect(() => {
    if (!initialAssignmentId) return
    requestedAssignment.current = initialAssignmentId
    void task.run(() => refresh(initialAssignmentId))
    // task is a fresh object every render (useTask isn't memoized), so it is
    // intentionally left out: this effect must fire only when
    // initialAssignmentId (or the stabilized refresh callback) changes, not
    // on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialAssignmentId, refresh])

  async function save(form: HTMLFormElement) {
    if (!sample) return
    const values = Object.fromEntries(new FormData(form))
    const data: Record<string, unknown> = {
      stage,
      elapsed_minutes: Number(values.elapsed_minutes || 0),
      detected: detected === '' ? null : detected === 'yes',
    }
    for (const name of numericFieldNames) data[name] = !values[name] ? null : Number(values[name])
    if (detected === 'no') {
      data.intensity = 0
      data.liking = null
    }
    for (const note of observationNotes) data[note.name] = values[note.name] || null
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
            <h2>Your calibration</h2>
          </div>
          {enrollment && (
            <span className="tally">
              {enrollment.presentations.filter((item) => item.blotter_locked).length} /{' '}
              {enrollment.presentations.length} locked
            </span>
          )}
        </div>
        <p>
          Use the code on your sample. Identities appear after required blind evaluations are
          locked.
        </p>
        <p>
          <a
            className="inline-target-link"
            href={pathFor('protocol')}
            onClick={(event) => followRouteLink(event, 'protocol', navigate)}
          >
            Read the calibration protocol
          </a>
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
            <p className="notice" role="status">
              {enrollmentGuidance()}
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
            <ConfirmAction
              actionLabel="Finalize skin-test plan"
              confirmLabel="Confirm final plan"
              description="Finalizing prevents further changes to which samples receive a skin test."
              disabled={task.busy || enrollment.skin_plan_locked}
              onConfirm={() =>
                void task.run(async () => {
                  await api.post(`/calibration/enrollments/${enrollment.id}/lock-skin-plan`)
                  await refresh()
                })
              }
            />
            <ConfirmAction
              actionLabel="Reveal completed baseline"
              confirmLabel="Confirm reveal"
              description="Reveal makes fragrance identities visible for this enrollment. Confirm that all required blind responses are locked."
              disabled={task.busy || enrollment.revealed || !enrollment.reveal_eligible}
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
                <p className="eyebrow">Sample {sample.position}</p>
                <h2 className="sample-heading">
                  <span className="visually-hidden">Blind code </span>
                  {sample.blind_code}
                </h2>
                {sample.identity && (
                  <>
                    <p className="notice">
                      {sample.identity.brand} · {sample.identity.name} ·{' '}
                      {sample.identity.concentration}
                    </p>
                    {/*
                      Rendered only inside this `identity` branch, which the
                      backend populates only after reveal. Each name links to
                      the source that attributes it: ADR-006 keeps a claim and
                      its evidence together, and an attribution presented
                      without a source reads as established fact when it is not.
                    */}
                    {sample.identity.perfumers && sample.identity.perfumers.length > 0 && (
                      <p className="attribution">
                        <span className="attribution__label">
                          {sample.identity.perfumers.length === 1 ? 'Perfumer' : 'Perfumers'}
                        </span>
                        {sample.identity.perfumers.map((attribution, index) => (
                          <span key={attribution.name}>
                            {index > 0 && ', '}
                            <a href={attribution.source_url} target="_blank" rel="noreferrer">
                              {attribution.name}
                              <span className="visually-hidden"> (opens the source)</span>
                            </a>
                          </span>
                        ))}
                      </p>
                    )}
                  </>
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
                    <div className="fields fields-compact">
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
                    </div>
                    {detected === 'no' && (
                      <p className="notice">
                        Intensity will be saved as 0; liking will remain unanswered.
                      </p>
                    )}
                    {blotterGroups.map((group) => (
                      <ScaleGroupFields
                        key={group.key}
                        group={group}
                        isDisabled={detected === 'no' ? disabledOnNonDetection : undefined}
                      />
                    ))}
                    {stage === 'SKIN' && (
                      <>
                        {skinGroups.map((group) => (
                          <ScaleGroupFields key={group.key} group={group} />
                        ))}
                        <label>
                          Longevity (minutes)
                          <input name="longevity_minutes" type="number" min="0" />
                        </label>
                      </>
                    )}
                    <label>
                      Perceived notes
                      <input
                        name="perceived_notes"
                        placeholder="Your own words, separated by commas"
                      />
                    </label>
                    {observationNotes.map((note) => (
                      <label key={note.name}>
                        {note.label}
                        <textarea name={note.name} rows={2} />
                      </label>
                    ))}
                    <button>Save observation</button>
                  </fieldset>
                </form>
                {!sample.identity && (
                  <ConfirmAction
                    actionLabel={`Lock ${stage.toLowerCase()} responses`}
                    confirmLabel={`Confirm ${stage.toLowerCase()} lock`}
                    description="Locking ends blind entry for this sample and stage. Review the saved observations before continuing."
                    disabled={
                      task.busy ||
                      (stage === 'BLOTTER' ? sample.blotter_locked : sample.skin_locked)
                    }
                    onConfirm={() =>
                      void task.run(async () => {
                        await api.post(`/calibration/presentations/${sample.id}/lock/${stage}`)
                        await refresh()
                      })
                    }
                  />
                )}
                <h3>Saved observations</h3>
                {sample.observations.length ? (
                  /*
                   * A blotter log: one row per timepoint, ordered by elapsed
                   * time, so the evaporation curve is legible at a glance.
                   * Every professional evaluation sheet this interface is
                   * modelled on is laid out this way, and the previous
                   * unordered list of prose lines made a sequence of
                   * observations read as unrelated entries.
                   */
                  <div className="log-scroll">
                    <table className="log">
                      <caption className="visually-hidden">
                        Saved observations for this sample, earliest first
                      </caption>
                      <thead>
                        <tr>
                          <th scope="col">Time</th>
                          <th scope="col">Stage</th>
                          <th scope="col">Phase</th>
                          <th scope="col">Intensity</th>
                          <th scope="col">Liking</th>
                          <th scope="col">Comment</th>
                        </tr>
                      </thead>
                      <tbody>
                        {timeOrdered(sample.observations).map((observation) => (
                          <tr key={observation.id}>
                            <th scope="row" data-numeric>
                              {observation.elapsed_minutes} min
                            </th>
                            <td>{observation.stage === 'SKIN' ? 'Skin' : 'Blotter'}</td>
                            <td>{observation.phase.replace(/_/g, ' ')}</td>
                            <td data-numeric>{observation.intensity ?? 'n/a'}</td>
                            <td data-numeric>{observation.liking ?? 'n/a'}</td>
                            <td>{observation.comments || 'n/a'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
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
