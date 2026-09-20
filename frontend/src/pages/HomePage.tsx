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

/**
 * The one thing worth doing next, across every assignment.
 *
 * This is the first surface a family member sees after the authentication
 * proxy, so it commits to a single primary action rather than presenting an
 * even field of choices. Unfinished blind work outranks everything else,
 * because a stalled calibration holds up the model; with none outstanding,
 * recording an ordinary encounter is always useful.
 *
 * The wording is deliberately not the same as any single assignment's own
 * next action, which is stated on that assignment's row.
 */
function primaryAction(enrollments: Enrollment[]) {
  const outstanding = enrollments.filter((enrollment) => !enrollment.revealed).length
  if (outstanding)
    return {
      summary:
        outstanding === 1
          ? 'Carry on with the blind work on your open calibration.'
          : 'Carry on with the blind work on your open calibrations.',
      label: 'Continue calibration',
      route: 'calibration' as Route,
    }
  if (enrollments.length)
    return {
      summary: 'Identities are revealed. Review the results, or add a post-reveal observation.',
      label: 'Review calibration',
      route: 'calibration' as Route,
    }
  return {
    summary: 'Record a fragrance you wore or smelled today.',
    label: 'Record an encounter',
    route: 'ratings' as Route,
  }
}

/**
 * Small counts as words, larger ones as digits.
 *
 * A family pilot has single-digit enrollments, so the words cover every
 * realistic value; the numeric fallback exists so an unexpected count renders
 * correctly rather than as `undefined`.
 */
function countInWords(count: number): string {
  return ['None', 'One', 'Two', 'Three', 'Four', 'Five'][count] ?? String(count)
}

export function HomePage({ assignments, programs, reviewers, navigate }: HomePageProps) {
  const [enrollments, setEnrollments] = useState<Enrollment[]>([])
  const [loading, setLoading] = useState(assignments.length > 0)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let current = true
    if (!assignments.length) {
      // Resetting to the empty-assignments state synchronously, not deriving
      // state from a prop; the fetch below is the actual effect purpose.
      // eslint-disable-next-line react-hooks/set-state-in-effect
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
  const open = enrollments.filter((enrollment) => !enrollment.revealed).length

  return (
    <>
      <section>
        <div className="section-head">
          <h2>Your scent journal</h2>
          <span className="tally">
            {assignments.length} {assignments.length === 1 ? 'assignment' : 'assignments'}
          </span>
        </div>
        <p className="hero-statement">
          Two kinds of record end up here. An ordinary encounter is anything you wore or smelled in
          the course of a day, written down whenever you get to it. A calibration session is
          deliberate: the samples arrive as codes, you are not told what they are, and the order is
          arranged so that neither the bottle nor the sequence can steer what you write. Both feed
          the same preference history.
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
          <>
            <dl className="standing">
              <dt>Calibrations open</dt>
              <dd>{countInWords(open)}</dd>
              <dt>Next</dt>
              <dd>
                <strong>{action.summary}</strong>
              </dd>
            </dl>
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
          </>
        )}
      </section>

      <section>
        <h3>Calibration work</h3>
        {loading ? (
          <LoadingState label="Loading assignment progress…" />
        ) : enrollments.length ? (
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
                  {/*
                    The bar needs its own accessible name: a bare <progress> is
                    announced only as a percentage, with nothing saying what is
                    being measured.
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
                <div className="assignment-row__action">
                  <p>
                    <strong>{nextAction(enrollment)}</strong>
                  </p>
                  <button onClick={() => navigate('calibration')}>Continue calibration</button>
                </div>
              </article>
            )
          })
        ) : (
          <EmptyState title="No calibration work assigned">
            You can still record ordinary encounters and use recommendations.
          </EmptyState>
        )}
      </section>

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
