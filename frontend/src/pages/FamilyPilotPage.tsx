import { useEffect, useState } from 'react'
import { api, requestErrorMessage } from '../api/client'
import type { Person, Program, ProgramMember, ProgramReadiness } from '../api/types'
import { FeedbackBanner } from '../components/FeedbackBanner'
import { REVEAL_POLICY_PHRASES, revealPolicyOf } from '../content/revealPolicy'
import { useTask } from '../hooks/useTask'
import { followRouteLink, pathFor, type Navigate } from '../routing/routes'
import { AddEvaluatorForm } from './AddEvaluatorForm'
import { ProgramReadinessPanel } from './ProgramReadinessPanel'

type Props = {
  programs: Program[]
  reviewers: Person[]
  /** The signed-in manager, who is the one recorder login for every evaluator. */
  username: string
  reload: () => Promise<void>
  navigate: Navigate
  initialProgramId?: string
}

/**
 * The family pilot is one fixed design, so enrollment sends fixed values and
 * has no controls: shared sessions in a balanced Latin-square order, random
 * blind labels (a standard label's session number would say who shares a
 * fragrance), three samples per session, and no persistent or animalic flags.
 * The enroll tests pin this payload.
 */
const SHARED_TRIPLES = 'shared-triples-latin-rotation-v1'
const SAMPLES_PER_SESSION = 3
const NON_BLIND_REASON = 'Facilitator who labels and sprays the samples'

type RoleCounts = { baseline: number; repeats: number; holdouts: number; other: number }

function countRoles(members: ProgramMember[]): RoleCounts {
  const counts: RoleCounts = { baseline: 0, repeats: 0, holdouts: 0, other: 0 }
  for (const member of members) {
    if (member.role === 'UNIVERSAL_BASELINE') counts.baseline += 1
    else if (member.role === 'HIDDEN_REPEAT') counts.repeats += 1
    else if (member.role === 'HOLDOUT') counts.holdouts += 1
    else counts.other += 1
  }
  return counts
}

/** The one program shape the family pilot uses: active, household reveal, one blotter each. */
function isFamilyPilot(program: Program): boolean {
  return (
    program.status === 'active' &&
    revealPolicyOf(program) === 'HOUSEHOLD' &&
    (program.blotter_mode ?? 'INDIVIDUAL') === 'INDIVIDUAL'
  )
}

/**
 * Manager screen for the F1 family pilot.
 *
 * The program is created and activated by an operator script from a local
 * manifest, never here. This page only enrolls evaluators with the fixed
 * pilot settings and runs the steps after the sittings. It deliberately never
 * renders a program member's fragrance: the members are the fixed B01 to B39
 * and H01 to H10 bottles, and naming them would leak the blind answer key.
 */
export function FamilyPilotPage({
  programs,
  reviewers,
  username,
  reload,
  navigate,
  initialProgramId,
}: Props) {
  const task = useTask()
  const eligible = programs.filter(isFamilyPilot)
  const [chosenId, setChosenId] = useState('')
  const [counts, setCounts] = useState<RoleCounts | null>(null)
  const [readiness, setReadiness] = useState<ProgramReadiness | null>(null)
  // Per-evaluator "facilitator" ticks, and evaluators whose non-blind flag failed.
  const [facilitators, setFacilitators] = useState<ReadonlySet<string>>(new Set())
  const [unflagged, setUnflagged] = useState<ReadonlySet<string>>(new Set())

  const programId = [chosenId, initialProgramId, eligible.length === 1 ? eligible[0]?.id : '']
    .map((id) => eligible.find((program) => program.id === id)?.id)
    .find(Boolean)
  const program = eligible.find((item) => item.id === programId)

  useEffect(() => {
    // Fetch-on-dependency-change: clear the previous program's figures, then
    // load the selected one's.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCounts(null)
    setReadiness(null)
    if (!programId) return
    let current = true
    void task.run(async () => {
      const [members, status] = await Promise.all([
        api.get<ProgramMember[]>(`/calibration/programs/${programId}/members`),
        api.get<ProgramReadiness>(`/calibration/programs/${programId}/readiness`),
      ])
      if (!current) return
      // Only the counts are kept: the members' identities are never rendered here.
      setCounts(countRoles(members.data))
      setReadiness(status.data)
    })
    return () => {
      current = false
    }
    // Program selection is the only trigger; useTask is stable for this component.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [programId])

  async function refreshReadiness() {
    const response = await api.get<ProgramReadiness>(`/calibration/programs/${programId}/readiness`)
    setReadiness(response.data)
    return response.data
  }

  async function flagNonBlind(enrollmentId: string) {
    await api.post(`/calibration/enrollments/${enrollmentId}/non-blind`, {
      explanation: NON_BLIND_REASON,
    })
  }

  function setMember(set: ReadonlySet<string>, id: string, present: boolean) {
    const next = new Set(set)
    if (present) next.add(id)
    else next.delete(id)
    return next
  }

  async function enroll(reviewer: Person) {
    const created = await api.post<{ id: string }>(`/calibration/programs/${programId}/enroll`, {
      reviewer_id: reviewer.id,
      recorder_usernames: [username],
      session_size: SAMPLES_PER_SESSION,
      label_scheme: 'random',
      randomization_algorithm: SHARED_TRIPLES,
      persistent_membership_ids: [],
      session_template: null,
    })
    await refreshReadiness()
    if (!facilitators.has(reviewer.id)) {
      task.setNotice(`${reviewer.name} is enrolled with random blind labels.`)
      return
    }
    // The flag must land before the page calls this evaluator done. If it
    // fails the enrollment already exists, so say exactly that and offer a retry.
    try {
      await flagNonBlind(created.data.id)
    } catch (reason) {
      setUnflagged((current) => setMember(current, reviewer.id, true))
      task.setError(
        `${reviewer.name} is enrolled but could NOT be marked non-blind: ` +
          `${requestErrorMessage(reason)} Use "Retry non-blind flag" on their row ` +
          'before any sample is sprayed.'
      )
      return
    }
    setUnflagged((current) => setMember(current, reviewer.id, false))
    task.setNotice(`${reviewer.name} is enrolled and marked non-blind.`)
  }

  async function retryFlag(reviewer: Person, enrollmentId: string) {
    await flagNonBlind(enrollmentId)
    setUnflagged((current) => setMember(current, reviewer.id, false))
    task.setNotice(`${reviewer.name} is marked non-blind.`)
  }

  const enrollmentByReviewer = new Map(
    (readiness?.enrollments ?? []).map((row) => [row.reviewer_id, row.enrollment_id])
  )

  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Manager</p>
          <h2>Family pilot</h2>
        </div>
        <span className="tally">Restricted</span>
      </div>
      <p>Enroll the evaluators and run the steps after the sittings.</p>
      <FeedbackBanner error={task.error} notice={task.notice} />

      <h3>Program</h3>
      {initialProgramId && !eligible.some((item) => item.id === initialProgramId) && (
        <p className="notice">
          The link you followed names a program that is not a family pilot program.{' '}
          <button
            className="secondary"
            onClick={() => navigate('programsAdvanced', false, { program: initialProgramId })}
          >
            Open it in Advanced setup
          </button>
        </p>
      )}
      {eligible.length === 0 && (
        <p className="notice">No family pilot program is active. Ask the operator to load one.</p>
      )}
      {eligible.length > 1 && (
        <label>
          Family pilot program
          <select value={programId ?? ''} onChange={(event) => setChosenId(event.target.value)}>
            <option value="">Choose program</option>
            {eligible.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} · {item.version}
              </option>
            ))}
          </select>
        </label>
      )}
      {program && (
        <dl className="detail-list">
          <div>
            <dt>Name</dt>
            <dd>
              {program.name} · version {program.version}
            </dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{program.status}</dd>
          </div>
          <div>
            <dt>Reveal policy</dt>
            <dd>{REVEAL_POLICY_PHRASES[revealPolicyOf(program)]}</dd>
          </div>
          <div>
            <dt>Blotters</dt>
            <dd>One per evaluator</dd>
          </div>
          <div>
            <dt>Members</dt>
            <dd>
              {counts
                ? `${counts.baseline} baseline, ${counts.repeats} hidden repeats, ` +
                  `${counts.holdouts} holdouts` +
                  (counts.other ? `, ${counts.other} other` : '')
                : 'Loading'}
            </dd>
          </div>
        </dl>
      )}
      {program && (
        <p>
          The members are the fixed B01 to B39 and H01 to H10 bottles. Their identities are not
          shown on this page so the answer key stays hidden.
        </p>
      )}

      {program && (
        <>
          <hr />
          <h3>Evaluators</h3>
          <p>
            Enrolling uses the pilot settings and cannot be changed here: shared sessions of{' '}
            {SAMPLES_PER_SESSION} samples, random blind labels, and you ({username || 'signed in'})
            as the one recorder.
          </p>
          <AddEvaluatorForm task={task} reload={reload} />
          {reviewers.length === 0 ? (
            <p>No evaluators yet. Add one above.</p>
          ) : (
            <ul className="data-list">
              {reviewers.map((reviewer) => {
                const enrollmentId = enrollmentByReviewer.get(reviewer.id)
                const checkboxId = `facilitator-${reviewer.id}`
                return (
                  <li key={reviewer.id}>
                    <strong>{reviewer.name}</strong>
                    <span>{enrollmentId ? 'Enrolled' : 'Not enrolled'}</span>
                    {!enrollmentId && (
                      <>
                        <div className="choice choice--target">
                          <input
                            type="checkbox"
                            id={checkboxId}
                            checked={facilitators.has(reviewer.id)}
                            onChange={(event) =>
                              setFacilitators((current) =>
                                setMember(current, reviewer.id, event.target.checked)
                              )
                            }
                          />
                          <label htmlFor={checkboxId}>
                            Facilitator (non-blind){' '}
                            <span className="visually-hidden">for {reviewer.name}</span>
                          </label>
                          <p className="field-hint choice__hint">
                            Tick this for the one person who labels and sprays the samples and so
                            knows the answer key. Their answers are kept but excluded from
                            blind-baseline training. Decide before enrolling.
                          </p>
                        </div>
                        <button
                          disabled={task.busy || !username || readiness === null}
                          onClick={() => void task.run(() => enroll(reviewer))}
                        >
                          Enroll <span className="visually-hidden">{reviewer.name}</span>
                        </button>
                      </>
                    )}
                    {enrollmentId && unflagged.has(reviewer.id) && (
                      <button
                        disabled={task.busy}
                        onClick={() => void task.run(() => retryFlag(reviewer, enrollmentId))}
                      >
                        Retry non-blind flag{' '}
                        <span className="visually-hidden">for {reviewer.name}</span>
                      </button>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </>
      )}

      {program && (
        <ProgramReadinessPanel
          // Remounted when an evaluator is enrolled so its table reloads.
          key={`${program.id}:${readiness?.enrollments.length ?? 0}`}
          program={program}
          reload={reload}
          editablePolicy={false}
          showNonBlind={false}
        />
      )}

      <hr />
      <p>
        <a
          className="inline-target-link"
          href={pathFor('programsAdvanced')}
          onClick={(event) => followRouteLink(event, 'programsAdvanced', navigate)}
        >
          Advanced setup (not needed for the family pilot)
        </a>
      </p>
    </section>
  )
}
