import { useEffect, useRef, useState, type ReactNode } from 'react'
import { api } from '../api/client'
import type { Enrollment, ProgramReadiness } from '../api/types'
import { ConfirmAction } from '../components/ConfirmAction'
import { FeedbackBanner } from '../components/FeedbackBanner'
import { LoadingState } from '../components/PageState'
import { revealBlockerLabel } from '../content/revealBlockers'
import { isTranscribed } from '../content/transcription'
import { useTask } from '../hooks/useTask'
import {
  isOpen,
  nextWizardStep,
  progressFor,
  sessionsOf,
  type WizardProgress,
} from '../routing/wizardSteps'
import { SampleObservationPanel } from './SampleObservationPanel'
import { FlagProblem } from './FlagProblem'
import { RankingStep } from './RankingStep'
import { SessionBoundaryStep } from './SessionBoundaryStep'
import { SessionIntroStep } from './SessionIntroStep'

/** Another enrollment the same recorder can switch the wizard to. */
export type WizardSwitchOption = { id: string; label: string }

/**
 * For a manager, who in the household still has work outstanding. Read from
 * the manager-only readiness endpoint, so a recorder who is not a manager
 * sees only the general wording around it.
 */
function HouseholdOutstanding({ programId }: { programId: string }) {
  const [readiness, setReadiness] = useState<ProgramReadiness | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let current = true
    api
      .get<ProgramReadiness>(`/calibration/programs/${programId}/readiness`)
      .then((response) => {
        if (current) setReadiness(response.data)
      })
      .catch(() => {
        if (current) setFailed(true)
      })
    return () => {
      current = false
    }
  }, [programId])
  if (failed)
    return <p>The outstanding list could not be loaded. Program setup shows it as well.</p>
  if (!readiness) return null
  const outstanding = readiness.enrollments.filter(
    (row) => !row.revealed && row.reveal_blocker !== null && row.reveal_blocker !== 'HOUSEHOLD_WAIT'
  )
  if (outstanding.length === 0) return <p>Nobody in the household has work outstanding.</p>
  return (
    <>
      <p>Still outstanding:</p>
      <ul className="data-list">
        {outstanding.map((row) => (
          <li key={row.enrollment_id}>
            <strong>{row.reviewer_name}</strong>
            <span>{revealBlockerLabel(row.reveal_blocker)}</span>
          </li>
        ))}
      </ul>
    </>
  )
}

function WizardShell({
  heading,
  tally,
  task,
  switcher,
  children,
}: {
  heading: string
  tally?: ReactNode
  task: ReturnType<typeof useTask>
  switcher?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="workspace">
      <section>
        <div className="page-heading">
          <div>
            <h2>{heading}</h2>
          </div>
          {tally}
        </div>
        {switcher}
        <FeedbackBanner error={task.error} notice={task.notice} />
        {children}
      </section>
    </div>
  )
}

export function GuidedCalibrationFlow({
  enrollmentId,
  onExitToManualBrowse,
  onRevealed,
  switchOptions = [],
  onSwitchEnrollment,
  isManager = false,
}: {
  enrollmentId: string
  onExitToManualBrowse: () => void
  /**
   * Called after a successful reveal, once this wizard's own `enrollment`
   * state already reflects it. Refetches the app-level assignments list
   * (calibrationEntryFor's input), so the routing decision that picks what
   * renders next catches up with this enrollment's now-revealed state
   * instead of leaving the participant on this same wizard indefinitely.
   */
  onRevealed: () => Promise<void>
  /**
   * Every enrollment this identity can record for, this one included. With
   * more than one, the wizard offers a switch so a facilitator transcribing a
   * household's sheets can move between evaluators without leaving the flow.
   */
  switchOptions?: WizardSwitchOption[]
  onSwitchEnrollment?: (enrollmentId: string) => void
  /** Managers see who is outstanding while a household waits. */
  isManager?: boolean
}) {
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null)
  const [detected, setDetected] = useState('')
  const [progress, setProgress] = useState<WizardProgress>({
    introduced: new Set(),
    ranked: new Set(),
    acknowledged: new Set(),
  })
  const task = useTask()
  // #CRITICAL: Timing Dependencies: enrollmentId can change, or refresh() can
  // be called again (e.g. after a lock/reveal action), before an in-flight
  // GET resolves. Without a guard, a slower superseded response could land
  // after a newer one and overwrite current state with stale data.
  // #VERIFY: every setEnrollment call is gated on generation === current, so
  // only the most recently issued request's response is ever applied.
  const refreshGeneration = useRef(0)

  const refresh = async () => {
    const generation = ++refreshGeneration.current
    const response = await api.get<Enrollment>(`/calibration/enrollments/${enrollmentId}`)
    if (generation === refreshGeneration.current) setEnrollment(response.data)
  }

  useEffect(() => {
    void task.run(refresh)
    // enrollmentId is the only trigger; refresh/task are recreated per render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enrollmentId])

  function mark(key: keyof WizardProgress, sessionId: string) {
    setProgress((previous) => ({ ...previous, [key]: new Set(previous[key]).add(sessionId) }))
  }

  const switcher =
    switchOptions.length > 1 && onSwitchEnrollment ? (
      <label>
        Evaluator
        <select value={enrollmentId} onChange={(event) => onSwitchEnrollment(event.target.value)}>
          {switchOptions.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    ) : undefined

  const escapeHatch = (
    <button className="secondary" onClick={onExitToManualBrowse}>
      Browse assignments manually instead
    </button>
  )

  if (!enrollment) {
    // A slow, 403'd, or 404'd enrollment-detail fetch must not strand the
    // participant with no controls: show the loading shell while the
    // request is in flight, and keep the manual-workspace escape hatch
    // available even before the wizard has anything to render.
    return (
      <WizardShell heading="Guided calibration" task={task} switcher={switcher}>
        {task.busy && <LoadingState label="Loading your calibration…" />}
        {escapeHatch}
      </WizardShell>
    )
  }

  const step = nextWizardStep(enrollment, progress)
  // The facilitated format: a facilitator copies paper sheets in afterwards.
  const transcription = isTranscribed(enrollment.reveal_policy)
  const sessions = sessionsOf(enrollment)
  const closedRemain = enrollment.presentations.some((item) => !isOpen(item))
  const refreshButton = (
    <button className="secondary" disabled={task.busy} onClick={() => void task.run(refresh)}>
      Check again
    </button>
  )

  if (step.kind === 'revealed') {
    // A successful reveal leaves lock state unchanged, so without this step
    // the wizard would keep offering the reveal with no confirmation and no
    // path forward (see SampleObservationPanel's `sample.identity` branch for
    // the same disclosed-identity display pattern used here).
    const revealedSamples = enrollment.presentations.filter((item) => item.identity)
    return (
      <WizardShell heading="Guided calibration" task={task} switcher={switcher}>
        <p className="notice" role="status">
          Reveal complete. Identities are now visible for this enrollment.
        </p>
        {closedRemain && (
          <p className="notice">
            More samples open after the organizer freezes this evaluator&apos;s checkpoint.
          </p>
        )}
        {revealedSamples.length > 0 && (
          <ul className="data-list">
            {revealedSamples.map((item) => (
              <li key={item.id}>
                <strong>{item.blind_code}</strong>
                <span>
                  {item.identity?.brand} · {item.identity?.name} · {item.identity?.concentration}
                </span>
              </li>
            ))}
          </ul>
        )}
        {escapeHatch}
      </WizardShell>
    )
  }

  if (step.kind === 'session_intro') {
    // The opening screen of a session: consent, optional conditions, start.
    // It never blocks: Continue is always offered.
    return (
      <WizardShell heading="Before you begin" task={task} switcher={switcher}>
        <SessionIntroStep
          key={step.sessionId}
          enrollment={enrollment}
          sessionId={step.sessionId}
          task={task}
          onDone={() => mark('introduced', step.sessionId)}
          transcription={transcription}
        />
      </WizardShell>
    )
  }

  const { step: stepNumber, total } = progressFor(enrollment)
  const currentSessionId =
    step.kind === 'blotter' || step.kind === 'session_ranking' || step.kind === 'session_boundary'
      ? step.sessionId
      : undefined
  const session = sessions.find((item) => item.id === currentSessionId)
  const sample =
    step.kind === 'blotter' || step.kind === 'skin'
      ? enrollment.presentations.find((item) => item.id === step.presentationId)
      : undefined
  // In the facilitated (household) format, choosing who gets a skin test is the
  // organizer's call, so only a manager sees the per-sample planning form there.
  // #ASSUME: Security: this is a UI restriction only; the skin-plan endpoint
  // still accepts any recorder of the enrollment.
  // #VERIFY: a server-side role check on POST /presentations/{id}/skin-plan for
  // HOUSEHOLD programs if recorders other than the organizer ever get logins.
  const canPlanSkin = isManager || enrollment.reveal_policy !== 'HOUSEHOLD'
  const planCandidates = canPlanSkin
    ? enrollment.presentations.filter((item) => isOpen(item) && !item.skin_planned)
    : []
  const plannedSkin = enrollment.presentations.filter((item) => item.skin_planned)

  return (
    <WizardShell
      heading="Guided calibration"
      task={task}
      switcher={switcher}
      tally={
        <span className="tally">
          {session && (
            <>
              Session {session.number} of {sessions.length}
              {' · '}
            </>
          )}
          Step {stepNumber} of {total}
        </span>
      }
    >
      {sample && (step.kind === 'blotter' || step.kind === 'skin') && (
        <SampleObservationPanel
          enrollment={enrollment}
          sample={sample}
          stage={step.kind === 'blotter' ? 'BLOTTER' : 'SKIN'}
          stageFixed
          allowSkinPlanning={false}
          detected={detected}
          setDetected={setDetected}
          task={task}
          refresh={refresh}
          transcription={transcription}
        />
      )}
      {step.kind === 'session_ranking' && (
        <RankingStep
          key={step.sessionId}
          enrollment={enrollment}
          sessionId={step.sessionId}
          task={task}
          onDone={() => mark('ranked', step.sessionId)}
          transcription={transcription}
        />
      )}
      {step.kind === 'session_boundary' && (
        <SessionBoundaryStep
          key={step.sessionId}
          sessionId={step.sessionId}
          task={task}
          onContinue={() => mark('acknowledged', step.sessionId)}
          transcription={transcription}
        />
      )}
      {step.kind === 'skin_plan' && (
        <>
          <p className="notice">
            The blotter sessions are done. Skin tests are a separate, optional step on their own
            day. Finalize the skin-test plan now; leave it empty if this evaluator has no skin
            tests.
          </p>
          {plannedSkin.length > 0 && (
            <ul className="data-list">
              {plannedSkin.map((item) => (
                <li key={item.id}>
                  <strong>{item.blind_code}</strong>
                  <span>Skin test planned</span>
                </li>
              ))}
            </ul>
          )}
          <ConfirmAction
            actionLabel="Finalize skin-test plan"
            confirmLabel="Confirm final plan"
            description={
              plannedSkin.length === 0
                ? 'Finalizing with no skin tests planned means this evaluator has none. It cannot be changed afterwards.'
                : 'Finalizing prevents further changes to which samples receive a skin test.'
            }
            disabled={task.busy}
            onConfirm={() =>
              void task.run(async () => {
                await api.post(`/calibration/enrollments/${enrollment.id}/lock-skin-plan`)
                await refresh()
              })
            }
          />
          {planCandidates.length > 0 && (
            <details>
              <summary>Plan a skin test for a sample (facilitator only)</summary>
              <ul className="data-list">
                {planCandidates.map((item) => (
                  <li key={item.id}>
                    <strong>{item.blind_code}</strong>
                    <form
                      onSubmit={(event) => {
                        event.preventDefault()
                        const reason = String(new FormData(event.currentTarget).get('reason'))
                        void task.run(async () => {
                          await api.post(`/calibration/presentations/${item.id}/skin-plan`, {
                            reason,
                          })
                          await refresh()
                        })
                      }}
                    >
                      <label>
                        Reason to add a skin test for {item.blind_code}
                        <input name="reason" required placeholder="For example: low confidence" />
                      </label>
                      <button disabled={task.busy}>Plan skin test</button>
                    </form>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
      {step.kind === 'awaiting_checkpoint' && (
        <>
          <p className="notice" role="status">
            Blind baseline work is complete. Wait for the facilitator.
          </p>
          <p>
            The next samples open after the organizer freezes this evaluator&apos;s checkpoint in
            Program setup.
          </p>
          {refreshButton}
        </>
      )}
      {step.kind === 'household_wait' && (
        <>
          <p className="notice" role="status">
            This evaluator is finished. Wait for the facilitator.
          </p>
          <p>
            Identities are revealed for everyone in the household together, once every evaluator has
            finished.
          </p>
          {isManager ? (
            <HouseholdOutstanding programId={enrollment.program_id} />
          ) : (
            <p>The facilitator can see who is still outstanding in Program setup.</p>
          )}
          {refreshButton}
        </>
      )}
      {step.kind === 'household_ready' && (
        <>
          <p className="notice" role="status">
            Every evaluator in the household has finished.
          </p>
          <p>A manager reveals the whole household together from Program setup.</p>
          {refreshButton}
        </>
      )}
      {step.kind === 'not_ready' && (
        <>
          <p className="notice" role="status">
            Nothing is ready to record here right now. {revealBlockerLabel(step.blocker)}.
          </p>
          {refreshButton}
        </>
      )}
      {step.kind === 'ready_to_reveal' && (
        <>
          <p className="notice">All required blind work is locked.</p>
          <ConfirmAction
            actionLabel="Reveal completed baseline"
            confirmLabel="Confirm reveal"
            description="Reveal makes fragrance identities visible for this enrollment."
            disabled={task.busy}
            onConfirm={() =>
              void task.run(async () => {
                await api.post(`/calibration/enrollments/${enrollment.id}/reveal`)
                await refresh()
                await onRevealed()
              })
            }
          />
        </>
      )}
      <FlagProblem
        enrollment={enrollment}
        sessionId={currentSessionId ?? sample?.session_id}
        task={task}
      />
      {escapeHatch}
    </WizardShell>
  )
}
