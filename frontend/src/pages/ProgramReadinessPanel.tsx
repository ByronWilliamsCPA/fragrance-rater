import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type {
  BulkCheckpointResult,
  Enrollment,
  Program,
  ProgramReadiness,
  RevealPolicy,
} from '../api/types'
import { ConfirmAction } from '../components/ConfirmAction'
import { FeedbackBanner } from '../components/FeedbackBanner'
import { checkpointBlockerLabel, revealBlockerLabel } from '../content/revealBlockers'
import { useTask } from '../hooks/useTask'
import { isOpen, sessionsOf } from '../routing/wizardSteps'
import { NonBlindPanel } from './NonBlindPanel'

type ProgressRow = { enrollmentId: string; name: string; cells: string[] }

/** One evaluator's state in one session, for the manager's matrix. */
function sessionCell(samples: Enrollment['presentations']): string {
  if (samples.some((sample) => !isOpen(sample))) return 'Not open'
  const locked = samples.filter((sample) => sample.blotter_locked).length
  if (locked === samples.length) return 'Done'
  const answered = samples.some((sample) => sample.observations.length > 0)
  return locked > 0 || answered ? `${locked} of ${samples.length}` : 'Not started'
}

/**
 * Manager actions for the phases after the blind baseline: the program's
 * reveal policy, checkpoint freezing (which opens each evaluator's final
 * samples), the household reveal, and an evaluator-by-session progress matrix.
 *
 * Uses only the manager endpoints of the gate API contract. Nothing here shows
 * a blind code or a fragrance, so it can stay on screen during a session.
 */
export function ProgramReadinessPanel({
  program,
  reload,
}: {
  program: Program
  reload: () => Promise<void>
}) {
  const task = useTask()
  const [readiness, setReadiness] = useState<ProgramReadiness | null>(null)
  const [progress, setProgress] = useState<ProgressRow[] | null>(null)
  const [policy, setPolicy] = useState<RevealPolicy>(program.reveal_policy ?? 'ENROLLMENT')

  async function loadReadiness() {
    const response = await api.get<ProgramReadiness>(
      `/calibration/programs/${program.id}/readiness`
    )
    setReadiness(response.data)
  }

  useEffect(() => {
    void task.run(loadReadiness)
    // Loaded once per program; the panel is keyed by program id.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [program.id])

  async function savePolicy() {
    await api.put(`/calibration/programs/${program.id}/reveal-policy`, { reveal_policy: policy })
    await reload()
    await loadReadiness()
    task.setNotice('Reveal policy saved.')
  }

  async function freezeCheckpoints() {
    const response = await api.post<BulkCheckpointResult>(
      `/calibration/programs/${program.id}/checkpoints`,
      { algorithm_version: null, freeze_predictions: true }
    )
    await loadReadiness()
    const names = new Map(
      (readiness?.enrollments ?? []).map((row) => [row.enrollment_id, row.reviewer_name])
    )
    const skipped = response.data.skipped
      .filter((row) => row.reason !== 'HAS_CHECKPOINT')
      .map(
        (row) =>
          `${names.get(row.enrollment_id) ?? 'An evaluator'} (${checkpointBlockerLabel(row.reason)})`
      )
    task.setNotice(
      `Froze ${response.data.created.length} checkpoint(s).` +
        (skipped.length ? ` Not ready: ${skipped.join(', ')}.` : '')
    )
  }

  async function revealHousehold() {
    await api.post(`/calibration/programs/${program.id}/reveal`)
    await loadReadiness()
    task.setNotice('The household is revealed. Identities are visible to every evaluator.')
  }

  async function loadProgress() {
    const rows = readiness?.enrollments ?? []
    const details = await Promise.all(
      rows.map((row) =>
        api.get<Enrollment>(`/calibration/enrollments/${row.enrollment_id}`).then((response) => ({
          row,
          enrollment: response.data,
        }))
      )
    )
    setProgress(
      details.map(({ row, enrollment }) => ({
        enrollmentId: row.enrollment_id,
        name: row.reviewer_name,
        cells: sessionsOf(enrollment).map((session) => sessionCell(session.samples)),
      }))
    )
  }

  const enrollments = readiness?.enrollments ?? []
  const checkpointReady = enrollments.some(
    (row) => row.checkpoint_count === 0 && row.checkpoint_blocker === null
  )
  const household = (readiness?.reveal_policy ?? program.reveal_policy) === 'HOUSEHOLD'
  const sessionCount = Math.max(0, ...(progress ?? []).map((row) => row.cells.length))

  return (
    <>
      <hr />
      <div className="page-heading">
        <div>
          <h3>Checkpoints and reveal</h3>
          <p>
            {program.name} · {program.version}. Final samples open for an evaluator only after their
            checkpoint is frozen.
          </p>
        </div>
        <button disabled={task.busy} onClick={() => void task.run(loadReadiness)}>
          Refresh readiness
        </button>
      </div>
      <FeedbackBanner error={task.error} notice={task.notice} />
      {program.status === 'draft' ? (
        <form
          className="search-row"
          onSubmit={(event) => {
            event.preventDefault()
            void task.run(savePolicy)
          }}
        >
          <label>
            Reveal policy
            <select
              value={policy}
              onChange={(event) => setPolicy(event.target.value as RevealPolicy)}
            >
              <option value="ENROLLMENT">Each evaluator separately</option>
              <option value="HOUSEHOLD">Whole household together, after the final samples</option>
            </select>
          </label>
          <button disabled={task.busy}>Save reveal policy</button>
        </form>
      ) : (
        <p>
          Reveal policy:{' '}
          {household
            ? 'whole household together, after the final samples'
            : 'each evaluator separately'}
          .
        </p>
      )}
      {readiness && enrollments.length === 0 && <p>No evaluators are enrolled yet.</p>}
      {enrollments.length > 0 && (
        <div
          className="log-scroll"
          // A region that scrolls sideways must be reachable by keyboard
          // (WCAG 2.1.1; axe: scrollable-region-focusable).
          // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
          tabIndex={0}
          role="region"
          aria-label="Checkpoint and reveal readiness, scrolls sideways on a narrow screen"
        >
          <table className="log">
            <caption className="visually-hidden">Checkpoint and reveal readiness</caption>
            <thead>
              <tr>
                <th scope="col">Evaluator</th>
                <th scope="col">Checkpoint</th>
                <th scope="col">Reveal</th>
              </tr>
            </thead>
            <tbody>
              {enrollments.map((row) => (
                <tr key={row.enrollment_id}>
                  <th scope="row">{row.reviewer_name}</th>
                  <td>
                    {row.checkpoint_count > 0
                      ? 'Frozen'
                      : checkpointBlockerLabel(row.checkpoint_blocker)}
                  </td>
                  <td>{row.revealed ? 'Revealed' : revealBlockerLabel(row.reveal_blocker)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {enrollments.length > 0 && (
        <div className="button-row">
          <ConfirmAction
            actionLabel="Freeze checkpoints"
            confirmLabel="Confirm checkpoints"
            description="Freezes a checkpoint, with its predictions, for every evaluator whose blind baseline is complete and who has none yet. Their final samples open straight away. A checkpoint cannot be undone; evaluators who are not ready are skipped."
            disabled={task.busy || !checkpointReady}
            onConfirm={() => void task.run(freezeCheckpoints)}
          />
          {household && readiness?.household_revealed && <p>The household is revealed.</p>}
          {household && !readiness?.household_revealed && (
            <ConfirmAction
              actionLabel="Reveal the household"
              confirmLabel="Confirm household reveal"
              description="Reveals identities for every evaluator in this program at once and ends blind collection for the whole household. It cannot be undone."
              disabled={task.busy || !readiness?.household_reveal_ready}
              onConfirm={() => void task.run(revealHousehold)}
            />
          )}
          <button
            className="secondary"
            disabled={task.busy}
            onClick={() => void task.run(loadProgress)}
          >
            Show session progress
          </button>
        </div>
      )}
      {enrollments.length > 0 && <NonBlindPanel enrollments={enrollments} task={task} />}
      {progress && progress.length > 0 && (
        <div
          className="log-scroll"
          // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
          tabIndex={0}
          role="region"
          aria-label="Progress by evaluator and session, scrolls sideways on a narrow screen"
        >
          <table className="log">
            <caption className="visually-hidden">Progress by evaluator and session</caption>
            <thead>
              <tr>
                <th scope="col">Evaluator</th>
                {Array.from({ length: sessionCount }, (_, index) => (
                  <th scope="col" key={index}>
                    S{index + 1}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {progress.map((row) => (
                <tr key={row.enrollmentId}>
                  <th scope="row">{row.name}</th>
                  {Array.from({ length: sessionCount }, (_, index) => (
                    <td key={index}>{row.cells[index] ?? ''}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
