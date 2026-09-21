import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { Enrollment } from '../api/types'
import { ConfirmAction } from '../components/ConfirmAction'
import { FeedbackBanner } from '../components/FeedbackBanner'
import { useTask } from '../hooks/useTask'
import { SampleObservationPanel } from './SampleObservationPanel'

export type WizardStep =
  | { kind: 'skin_plan' }
  | { kind: 'blotter'; presentationId: string }
  | { kind: 'skin'; presentationId: string }
  | { kind: 'ready_to_reveal' }

/**
 * The next valid step, in the same precedence CalibrationService.reveal_blocker
 * already enforces (skin plan decision, then remaining BLOTTER locks, then
 * remaining SKIN locks, then reveal). No new ordering is invented here; this
 * mirrors the backend gate so the wizard and the reveal button never disagree
 * about what's left.
 */
export function nextWizardStep(enrollment: Enrollment): WizardStep {
  if (!enrollment.skin_plan_locked) return { kind: 'skin_plan' }
  const unlockedBlotter = enrollment.presentations.find((item) => !item.blotter_locked)
  if (unlockedBlotter) return { kind: 'blotter', presentationId: unlockedBlotter.id }
  const unlockedSkin = enrollment.presentations.find(
    (item) => item.skin_planned && !item.skin_locked
  )
  if (unlockedSkin) return { kind: 'skin', presentationId: unlockedSkin.id }
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
}: {
  enrollmentId: string
  onExitToManualBrowse: () => void
}) {
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null)
  // `stage` itself is never read: SampleObservationPanel is driven by
  // step.kind below, not by this local state. Only the setter is needed to
  // satisfy the panel's prop interface (documented wart, see brief).
  const [, setStage] = useState('BLOTTER')
  const [detected, setDetected] = useState('')
  const task = useTask()
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

  if (!enrollment) return <FeedbackBanner error={task.error} notice={task.notice} />

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
            setStage={setStage}
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
