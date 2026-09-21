import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { Access, Enrollment, EnrollmentSummary, Person, Program } from '../api/types'
import { ConfirmAction } from '../components/ConfirmAction'
import { FeedbackBanner } from '../components/FeedbackBanner'
import { EmptyState } from '../components/PageState'
import { useTask } from '../hooks/useTask'
import { followRouteLink, pathFor, type AssignmentId, type Navigate } from '../routing/routes'
import { calibrationEntryFor } from '../routing/calibrationEntry'
import { CalibrationChoiceScreen } from './CalibrationChoiceScreen'
import { GuidedCalibrationFlow } from './GuidedCalibrationFlow'
import { SampleObservationPanel } from './SampleObservationPanel'

type CalibrationPageProps = {
  assignments: EnrollmentSummary[]
  programs: Program[]
  reviewers: Person[]
  access: Access
  navigate: Navigate
  /** Refetches the app-level assignments/programs/reviewers/access bundle. */
  reload: () => Promise<void>
  /**
   * A deep-linked assignment the router has already checked against this
   * identity's assignments. Branded rather than a bare string so it cannot be
   * confused with the program, reviewer, or presentation ids alongside it.
   */
  initialAssignmentId?: AssignmentId
  /**
   * The raw `?assignment=` value when it matched no assignment this identity
   * holds. Surfaced to the user instead of resolving to nothing in silence.
   */
  unresolvedAssignmentId?: string
}

/**
 * Why a deep link produced no assignment.
 *
 * Deliberately does not echo the requested id back into the page: it comes
 * from the address bar, and it tells the user nothing they can act on.
 */
const unresolvedAssignmentMessage =
  'That link points to a calibration assignment you do not have. It may have been reassigned or withdrawn. Choose an assignment below to continue.'

export function CalibrationPage({
  assignments,
  programs,
  reviewers,
  access,
  navigate,
  reload: reloadAppData,
  initialAssignmentId,
  unresolvedAssignmentId,
}: CalibrationPageProps) {
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null)
  const [assignmentId, setAssignmentId] = useState<string>(initialAssignmentId ?? '')
  const requestedAssignment = useRef<string>(initialAssignmentId ?? '')
  const refreshGeneration = useRef(0)
  const [selected, setSelected] = useState('')
  const [stage, setStage] = useState('BLOTTER')
  const [detected, setDetected] = useState('')
  const task = useTask()
  const [manualBrowse, setManualBrowse] = useState(false)
  const entry = calibrationEntryFor(assignments)
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

  // #ASSUME: timing: a deep link can arrive while an earlier enrollment fetch
  // is still in flight (back/forward between two `?assignment=` entries, or a
  // link followed over a manual dropdown pick), and this effect relies on
  // `refresh` discarding the slower response rather than ordering the
  // requests itself.
  // #VERIFY: `refresh` must keep both guards before it calls setEnrollment,
  // the generation counter and the `requestedAssignment.current === id`
  // check; dropping either lets a stale response overwrite the assignment
  // the user is actually looking at.
  useEffect(() => {
    const id = initialAssignmentId ?? ''
    // Skip only the case where there's nothing to sync: no deep link now,
    // and nothing tracked from a previous one either (an ordinary
    // `/calibration` visit, or the manual dropdown's own state, which this
    // effect must not disturb). Once a deep link HAS been tracked, its
    // disappearance still falls through below so the stale assignment gets
    // cleared instead of staying selected against a URL that no longer names
    // it.
    if (!id && !requestedAssignment.current) return
    requestedAssignment.current = id
    // Syncing the picker and sample selection to the URL, which is the source
    // of truth for a deep link; this is the effect's purpose, not derived
    // state being patched up after the fact.
    setAssignmentId(id)
    setEnrollment(null)
    setSelected('')
    if (id) {
      void task.run(() => refresh(id))
    } else {
      void refresh('')
    }
    // task is a fresh object every render (useTask isn't memoized), so it is
    // intentionally left out: this effect must fire only when
    // initialAssignmentId (or the stabilized refresh callback) changes, not
    // on every render.
    // Tracked in src/hooks/useTask.ts: memoizing what useTask returns is the
    // fix, and it retires this suppression rather than working around it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialAssignmentId, refresh])

  if (!initialAssignmentId && !unresolvedAssignmentId && !manualBrowse && entry.kind === 'resume') {
    return (
      <GuidedCalibrationFlow
        enrollmentId={entry.enrollmentId}
        onExitToManualBrowse={() => setManualBrowse(true)}
        onRevealed={reloadAppData}
      />
    )
  }
  if (!initialAssignmentId && !unresolvedAssignmentId && !manualBrowse && entry.kind === 'guided') {
    return (
      <GuidedCalibrationFlow
        enrollmentId={entry.enrollmentId}
        onExitToManualBrowse={() => setManualBrowse(true)}
        onRevealed={reloadAppData}
      />
    )
  }
  if (!initialAssignmentId && !unresolvedAssignmentId && !manualBrowse && entry.kind === 'choice') {
    return (
      <CalibrationChoiceScreen
        assignments={assignments}
        programs={programs}
        access={access}
        navigate={navigate}
        onBrowse={() => setManualBrowse(true)}
      />
    )
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
        <FeedbackBanner
          error={task.error || (unresolvedAssignmentId ? unresolvedAssignmentMessage : '')}
          notice={task.notice}
        />
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
              <SampleObservationPanel
                enrollment={enrollment}
                sample={sample}
                stage={stage}
                setStage={setStage}
                detected={detected}
                setDetected={setDetected}
                task={task}
                refresh={refresh}
              />
            ) : (
              <EmptyState title="Select a sample">Choose a blind code from a session.</EmptyState>
            )}
          </section>
        </div>
      )}
    </>
  )
}
