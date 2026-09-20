import { useEffect, useState } from 'react'
import { api, requestErrorMessage } from '../api/client'
import type { Assignment, Capabilities, Enrollment, Person, Program } from '../api/types'
import { FeedbackBanner } from '../components/FeedbackBanner'
import { LoadingState } from '../components/PageState'
import type { Route } from '../routing/routes'

type WorkspacePageProps = {
  assignments: Assignment[]
  programs: Program[]
  reviewers: Person[]
  capabilities: Capabilities
  navigate: (route: Route, replace?: boolean, query?: string) => void
}

/**
 * The single next step for one assignment, in the evaluator's terms.
 *
 * Derived from `reveal_blocker`, which the API sets to whichever gate is
 * currently holding the enrollment closed. The strings deliberately name an
 * action rather than the blocker code, because the code is a protocol detail
 * (ADR-005) and the evaluator only needs to know what to do next.
 */
function nextAction(enrollment: Enrollment): string {
  if (enrollment.revealed) return 'Review revealed results or add a post-reveal observation.'
  if (enrollment.reveal_blocker === 'SKIN_PLAN') return 'Finalize the skin-test plan.'
  if (enrollment.reveal_blocker === 'BLOTTER') return 'Continue required blind blotter screens.'
  if (enrollment.reveal_blocker === 'SKIN') return 'Complete the planned blind skin tests.'
  return 'Required blind work is complete. Reveal when ready.'
}

export function WorkspacePage({
  assignments,
  programs,
  reviewers,
  capabilities,
  navigate,
}: WorkspacePageProps) {
  const [enrollments, setEnrollments] = useState<Enrollment[]>([])
  const [loading, setLoading] = useState(assignments.length > 0)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let current = true
    if (!assignments.length) {
      setError('')
      setEnrollments([])
      setLoading(false)
      return
    }
    setLoading(true)
    setError('')
    void Promise.all(
      assignments.map((assignment) =>
        api.get<Enrollment>(`/calibration/enrollments/${assignment.id}`)
      )
    )
      .then((responses) => {
        if (current) setEnrollments(responses.map((response) => response.data))
      })
      .catch((reason: unknown) => {
        if (current) setError(requestErrorMessage(reason))
      })
      .finally(() => {
        if (current) setLoading(false)
      })
    return () => {
      current = false
    }
  }, [assignments, reloadKey])

  return (
    <>
      <section>
        <div className="page-heading">
          <div>
            <h2>Workspace</h2>
          </div>
        </div>
        <div className="button-row">
          <button onClick={() => navigate('ratings')}>Log an encounter</button>
          <button className="secondary" onClick={() => navigate('recommendations')}>
            See recommendations
          </button>
          {capabilities.canManagePrograms && (
            <button className="secondary" onClick={() => navigate('programs')}>
              Manage programs
            </button>
          )}
        </div>
      </section>

      {assignments.length > 0 && (
        <section>
          <h3>Calibration work</h3>
          <FeedbackBanner error={error} />
          {error && (
            <button
              className="secondary"
              disabled={loading}
              onClick={() => setReloadKey((key) => key + 1)}
            >
              Retry assignment progress
            </button>
          )}
          {loading ? (
            <LoadingState label="Loading assignment progress…" />
          ) : (
            enrollments.map((enrollment) => {
              const assignment = assignments.find((item) => item.id === enrollment.id)
              const locked = enrollment.presentations.filter((item) => item.blotter_locked).length
              const total = enrollment.presentations.length
              const evaluator =
                reviewers.find((item) => item.id === assignment?.reviewer_id)?.name || 'Evaluator'
              const program =
                programs.find((item) => item.id === assignment?.program_id)?.name || 'Program'
              return (
                <article className="assignment-row" key={enrollment.id}>
                  <div>
                    <h4>{program}</h4>
                    <p>{evaluator}</p>
                  </div>
                  <div className="assignment-row__meter">
                    <progress
                      value={locked}
                      max={total}
                      aria-label={`Blind screens locked for ${evaluator} on ${program}`}
                    />
                    <small data-numeric>
                      {locked} of {total} blind screens locked
                    </small>
                  </div>
                  <div className="assignment-row__action">
                    <p>
                      <strong>{nextAction(enrollment)}</strong>
                    </p>
                    <button
                      onClick={() =>
                        navigate('calibration', false, `assignment=${enrollment.id}`)
                      }
                    >
                      Continue calibration
                    </button>
                  </div>
                </article>
              )
            })
          )}
        </section>
      )}

      <section>
        <h3>There is nothing here you can get wrong</h3>
        <p>
          Disliking a fragrance, even strongly, is worth as much to the model as liking one. It
          marks where your preferences stop, which is information nothing else in the record
          supplies.
        </p>
        <p>
          The same goes for being unsure. A scale left unanswered is a usable fact about that
          sample; a guess entered to avoid leaving a blank is not.
        </p>
      </section>
    </>
  )
}
