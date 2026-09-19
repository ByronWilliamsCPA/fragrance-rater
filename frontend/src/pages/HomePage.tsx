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
  if (enrollment.reveal_blocker === 'SKIN_PLAN') return 'Finalize the skin-test plan.'
  if (enrollment.reveal_blocker === 'BLOTTER') return 'Continue required blind blotter screens.'
  if (enrollment.reveal_blocker === 'SKIN') return 'Complete the planned blind skin tests.'
  return 'Required blind work is complete. Reveal when ready.'
}

/**
 * The one thing worth doing next, across every assignment.
 *
 * The landing page is the first surface a family member sees after the
 * authentication proxy, so it commits to a single primary action rather than
 * presenting an even field of choices. Unfinished blind work outranks
 * everything else, because a stalled calibration blocks the model; with none
 * outstanding, recording an ordinary encounter is always useful.
 */
function primaryAction(enrollments: Enrollment[]) {
  const outstanding = enrollments.filter((enrollment) => !enrollment.revealed).length
  // Deliberately a summary across assignments, not a repeat of any one card's
  // instruction: the per-assignment sentence belongs on that assignment.
  if (outstanding)
    return {
      summary:
        outstanding === 1
          ? 'One calibration is still in progress. Pick up where you left off.'
          : `${outstanding} calibrations are still in progress. Pick up where you left off.`,
      label: 'Continue calibration',
      route: 'calibration' as Route,
    }
  if (enrollments.length)
    return {
      summary: 'Your blind work is done. Revealed results are ready to review.',
      label: 'Review calibration',
      route: 'calibration' as Route,
    }
  return {
    summary: 'Record a fragrance you wore or smelled today.',
    label: 'Record an encounter',
    route: 'ratings' as Route,
  }
}

export function HomePage({ assignments, programs, reviewers, navigate }: HomePageProps) {
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

  const action = primaryAction(enrollments)

  return (
    <>
      <section className="landing-hero">
        <div className="page-heading">
          <div>
            <p className="eyebrow">Today</p>
            <h2>Your scent journal</h2>
          </div>
          <span className="status-chip">
            {assignments.length} active {assignments.length === 1 ? 'assignment' : 'assignments'}
          </span>
        </div>
        <p className="hero-statement">
          Record what you actually notice. That record, not a list of notes you think you like, is
          what predicts the next fragrance worth your time.
        </p>

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

        {!loading && !error && (
          <div className="landing-next">
            <p className="eyebrow">Next step</p>
            <p>{action.summary}</p>
            <div className="button-row">
              <button onClick={() => navigate(action.route)}>{action.label}</button>
              {action.route !== 'ratings' && (
                <button className="secondary" onClick={() => navigate('ratings')}>
                  Record an encounter
                </button>
              )}
              <button className="secondary" onClick={() => navigate('recommendations')}>
                View recommendations
              </button>
            </div>
          </div>
        )}
      </section>

      <section>
        <h3>Calibration work</h3>
        {loading ? (
          <LoadingState label="Loading assignment progress…" />
        ) : enrollments.length ? (
          <div className="recommendation-grid">
            {enrollments.map((enrollment) => {
              const assignment = assignments.find((item) => item.id === enrollment.id)
              const locked = enrollment.presentations.filter((item) => item.blotter_locked).length
              const total = enrollment.presentations.length
              const evaluator =
                reviewers.find((item) => item.id === assignment?.reviewer_id)?.name || 'Evaluator'
              const program =
                programs.find((item) => item.id === assignment?.program_id)?.name || 'Program'
              return (
                <article className="assignment-card" key={enrollment.id}>
                  <h4>{program}</h4>
                  <p>{evaluator}</p>
                  <div className="assignment-card__meter">
                    {/*
                      The bar needs its own accessible name: a bare <progress>
                      is announced only as a percentage, with no indication of
                      what is being measured.
                    */}
                    <progress
                      value={locked}
                      max={total}
                      aria-label={`Blind screens locked for ${evaluator} on ${program}`}
                    />
                    <small data-numeric>
                      {locked} of {total} blind screens locked
                    </small>
                  </div>
                  <p className="assignment-card__action">
                    <strong>{nextAction(enrollment)}</strong>
                  </p>
                  <div className="button-row">
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

      <section>
        <p className="eyebrow">New here</p>
        <h3>How this works</h3>
        <ul className="orientation-list">
          <li>
            <strong>Smell first, blind</strong>
            <span>
              Samples arrive as codes, not names. Nothing about the bottle can steer what you
              record.
            </span>
          </li>
          <li>
            <strong>Rate honestly</strong>
            <span>
              Disliking something strongly is as useful as loving it. There is no answer here you
              can get wrong.
            </span>
          </li>
          <li>
            <strong>The model commits first</strong>
            <span>
              Predictions are locked in writing before you smell a holdout, so the result means
              something.
            </span>
          </li>
        </ul>
      </section>
    </>
  )
}
