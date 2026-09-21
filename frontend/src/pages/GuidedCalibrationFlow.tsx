import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { Enrollment } from '../api/types'
import { ConfirmAction } from '../components/ConfirmAction'
import { FeedbackBanner } from '../components/FeedbackBanner'
import { LoadingState } from '../components/PageState'
import { useTask } from '../hooks/useTask'
import { SampleObservationPanel } from './SampleObservationPanel'

export type WizardStep =
  | { kind: 'skin_plan' }
  | { kind: 'blotter'; presentationId: string }
  | { kind: 'skin'; presentationId: string }
  | { kind: 'ready_to_reveal' }

/**
 * The next valid step. The STAGE decision is keyed off the enrollment's
 * authoritative `reveal_blocker` (mirroring CalibrationService.reveal_blocker
 * exactly, see calibration_service.py:488-504), not off locally-derived lock
 * state: the backend's gate excludes HOLDOUT-role presentations from the
 * BLOTTER check, and the frontend's `Sample` type deliberately withholds
 * `role`, so the wizard cannot re-derive that exclusion itself. Presentation
 * lock state is used only to pick *which* presentation within a stage (the
 * first unlocked one for BLOTTER/SKIN); that pick is NOT role-filtered (it
 * can't be, `role` isn't in `Sample`), so it relies on an untested ordering
 * invariant elsewhere rather than excluding a HOLDOUT presentation itself.
 */
export function nextWizardStep(enrollment: Enrollment): WizardStep {
  if (enrollment.reveal_blocker === 'SKIN_PLAN') return { kind: 'skin_plan' }
  if (enrollment.reveal_blocker === 'BLOTTER') {
    const unlockedBlotter = enrollment.presentations.find((item) => !item.blotter_locked)
    if (unlockedBlotter) return { kind: 'blotter', presentationId: unlockedBlotter.id }
  }
  if (enrollment.reveal_blocker === 'SKIN') {
    const unlockedSkin = enrollment.presentations.find(
      (item) => item.skin_planned && !item.skin_locked
    )
    if (unlockedSkin) return { kind: 'skin', presentationId: unlockedSkin.id }
  }
  // #ASSUME: External Resources: reveal_blocker is the backend's
  // authoritative gate, but a known blocker whose expected unlocked
  // presentation can't be found locally (or a future/unrecognized blocker
  // value) is a client/server disagreement, not proof reveal is ready.
  // Falling through to ready_to_reveal in that case would offer a reveal the
  // backend still considers blocked.
  // #VERIFY: only a literal `null` reveal_blocker, the backend's explicit
  // "nothing left" signal, reaches ready_to_reveal; any other value routes
  // back to the earliest stage instead of assuming completion.
  if (enrollment.reveal_blocker !== null) return { kind: 'skin_plan' }
  return { kind: 'ready_to_reveal' }
}

function progressFor(enrollment: Enrollment): { step: number; total: number } {
  const skinPlanned = enrollment.presentations.filter((item) => item.skin_planned)
  const done =
    (enrollment.skin_plan_locked ? 1 : 0) +
    enrollment.presentations.filter((item) => item.blotter_locked).length +
    skinPlanned.filter((item) => item.skin_locked).length
  return { step: done + 1, total: 2 + enrollment.presentations.length + skinPlanned.length }
}

export function GuidedCalibrationFlow({
  enrollmentId,
  onExitToManualBrowse,
  onRevealed,
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
}) {
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null)
  const [detected, setDetected] = useState('')
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

  if (!enrollment) {
    // A slow, 403'd, or 404'd enrollment-detail fetch must not strand the
    // participant with no controls: show the loading shell while the
    // request is in flight, and keep the manual-workspace escape hatch
    // available even before the wizard has anything to render.
    return (
      <div className="workspace">
        <section>
          <div className="page-heading">
            <div>
              <h2>Guided calibration</h2>
            </div>
          </div>
          <FeedbackBanner error={task.error} notice={task.notice} />
          {task.busy && <LoadingState label="Loading your calibration…" />}
          <button className="secondary" onClick={onExitToManualBrowse}>
            Browse assignments manually instead
          </button>
        </section>
      </div>
    )
  }

  if (enrollment.revealed) {
    // A successful reveal leaves lock state (and therefore nextWizardStep)
    // unchanged, so without this branch the wizard would keep re-rendering
    // the same "Reveal completed baseline" button with no confirmation and
    // no path forward (see SampleObservationPanel's `sample.identity` branch
    // for the same disclosed-identity display pattern used here).
    const revealedSamples = enrollment.presentations.filter((item) => item.identity)
    return (
      <div className="workspace">
        <section>
          <div className="page-heading">
            <div>
              <h2>Guided calibration</h2>
            </div>
          </div>
          <FeedbackBanner error={task.error} notice={task.notice} />
          <p className="notice" role="status">
            Reveal complete. Identities are now visible for this enrollment.
          </p>
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
          <button className="secondary" onClick={onExitToManualBrowse}>
            Browse assignments manually instead
          </button>
        </section>
      </div>
    )
  }

  const step = nextWizardStep(enrollment)
  const { step: stepNumber, total } = progressFor(enrollment)
  const sample =
    step.kind === 'blotter' || step.kind === 'skin'
      ? enrollment.presentations.find((item) => item.id === step.presentationId)
      : undefined

  return (
    <div className="workspace">
      <section>
        <div className="page-heading">
          <div>
            <h2>Guided calibration</h2>
          </div>
          <span className="tally">
            Step {stepNumber} of {total}
          </span>
        </div>
        <FeedbackBanner error={task.error} notice={task.notice} />
        {step.kind === 'skin_plan' && (
          <>
            <p className="notice">
              Decide whether each sample also needs a skin test, then finalize the plan.
            </p>
            <ul className="data-list">
              {enrollment.presentations.map((item) => (
                <li key={item.id}>
                  <strong>{item.blind_code}</strong>
                  <span>{item.skin_planned ? 'Skin test planned' : 'Blotter only'}</span>
                  {!item.skin_planned && (
                    <form
                      onSubmit={(event) => {
                        event.preventDefault()
                        const reason = String(
                          new FormData(event.currentTarget).get('reason')
                        )
                        void task.run(async () => {
                          await api.post(`/calibration/presentations/${item.id}/skin-plan`, {
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
                </li>
              ))}
            </ul>
            <ConfirmAction
              actionLabel="Finalize skin-test plan"
              confirmLabel="Confirm final plan"
              description="Finalizing prevents further changes to which samples receive a skin test."
              disabled={task.busy}
              onConfirm={() =>
                void task.run(async () => {
                  await api.post(`/calibration/enrollments/${enrollment.id}/lock-skin-plan`)
                  await refresh()
                })
              }
            />
          </>
        )}
        {sample && (step.kind === 'blotter' || step.kind === 'skin') && (
          <SampleObservationPanel
            enrollment={enrollment}
            sample={sample}
            stage={step.kind === 'blotter' ? 'BLOTTER' : 'SKIN'}
            stageFixed
            detected={detected}
            setDetected={setDetected}
            task={task}
            refresh={refresh}
          />
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
        <button className="secondary" onClick={onExitToManualBrowse}>
          Browse assignments manually instead
        </button>
      </section>
    </div>
  )
}
