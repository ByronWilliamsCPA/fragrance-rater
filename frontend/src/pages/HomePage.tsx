import { useEffect, useState } from 'react'
import { api, requestErrorMessage } from '../api/client'
import type { Assignment, Enrollment, Person, Program } from '../api/types'
import { FeedbackBanner } from '../components/FeedbackBanner'
import { EmptyState, LoadingState } from '../components/PageState'
import type { Route } from '../routing/routes'

type HomePageProps = {
  assignments: Assignment[]
  programs: Program[]
  reviewers: Person[]
  navigate: (route: Route) => void
}

function nextAction(enrollment: Enrollment): string {
  if (enrollment.revealed) return 'Review revealed results or add a post-reveal observation.'
  const openBlotter = enrollment.presentations.find((item) => !item.blotter_locked)
  if (openBlotter) return `Continue blind sample ${openBlotter.blind_code}.`
  if (!enrollment.skin_plan_locked) return 'Finalize the skin-test plan.'
  const openSkin = enrollment.presentations.find((item) => item.skin_planned && !item.skin_locked)
  if (openSkin) return `Complete the skin observation for ${openSkin.blind_code}.`
  return 'Blind work is complete. Review eligibility and reveal when ready.'
}

export function HomePage({ assignments, programs, reviewers, navigate }: HomePageProps) {
  const [enrollments, setEnrollments] = useState<Enrollment[]>([])
  const [loading, setLoading] = useState(assignments.length > 0)
  const [error, setError] = useState('')

  useEffect(() => {
    let current = true
    if (!assignments.length) {
      setEnrollments([])
      setLoading(false)
      return
    }
    setLoading(true)
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
  }, [assignments])

  return (
    <section>
      <div className="page-heading">
        <div>
          <div className="eyebrow">TODAY</div>
          <h2>Your scent journal</h2>
        </div>
        <span className="status-chip">{assignments.length} active assignments</span>
      </div>
      <p>Continue current work or record an ordinary fragrance encounter.</p>
      <FeedbackBanner error={error} />
      <div className="button-row">
        <button onClick={() => navigate('ratings')}>Record an encounter</button>
        <button className="secondary" onClick={() => navigate('recommendations')}>
          View recommendations
        </button>
      </div>
      <h3>Calibration work</h3>
      {loading ? (
        <LoadingState label="Loading assignment progress…" />
      ) : enrollments.length ? (
        <div className="recommendation-grid">
          {enrollments.map((enrollment) => {
            const assignment = assignments.find((item) => item.id === enrollment.id)
            const locked = enrollment.presentations.filter((item) => item.blotter_locked).length
            return (
              <article key={enrollment.id}>
                <h4>
                  {programs.find((item) => item.id === assignment?.program_id)?.name || 'Program'}
                </h4>
                <p>
                  {reviewers.find((item) => item.id === assignment?.reviewer_id)?.name ||
                    'Evaluator'}{' '}
                  · {locked} of {enrollment.presentations.length} blind screens locked
                </p>
                <strong>{nextAction(enrollment)}</strong>
                <div>
                  <button onClick={() => navigate('calibration')}>Continue calibration</button>
                </div>
              </article>
            )
          })}
        </div>
      ) : (
        <EmptyState title="No calibration work assigned">
          You can still record ordinary encounters and use recommendations.
        </EmptyState>
      )}
    </section>
  )
}
