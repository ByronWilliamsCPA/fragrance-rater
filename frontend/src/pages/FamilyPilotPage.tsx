import { useEffect, useRef, useState } from 'react'
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
 * renders a program member's fragrance, brand, or evidence: naming the members
 * would leak the blind answer key, so only role counts are kept from them.
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
  // Per-evaluator "facilitator" ticks, enrollments made from this page (reviewer id to enrollment
  // id, so a row stays Enrolled even if the readiness reload is lost), and facilitators whose
  // non-blind flag is not confirmed. All belong to the selected program and reset when it changes.
  const [facilitators, setFacilitators] = useState<ReadonlySet<string>>(new Set())
  const [enrolledHere, setEnrolledHere] = useState<ReadonlyMap<string, string>>(new Map())
  const [unflagged, setUnflagged] = useState<ReadonlySet<string>>(new Set())
  // The program id now selected, so a slow answer for a program left behind is dropped.
  const selectedProgram = useRef<string | undefined>(undefined)

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
    setFacilitators(new Set())
    setEnrolledHere(new Map())
    setUnflagged(new Set())
    selectedProgram.current = programId
    if (!programId) return
    let current = true
    void task.run(async () => {
      const [members, status] = await Promise.all([
        api.get<ProgramMember[]>(`/calibration/programs/${programId}/members`),
        api.get<ProgramReadiness>(`/calibration/programs/${programId}/readiness`),
      ])
      if (!current) return
      // Only the counts are kept: the member list itself is dropped right here.
      setCounts(countRoles(members.data))
      setReadiness(status.data)
    })
    return () => {
      current = false
    }
    // Program selection is the only trigger; useTask is stable for this component.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [programId])

  /** Reload readiness for `forProgram`; null when that program is no longer the selected one. */
  async function refreshReadiness(forProgram: string) {
    const response = await api.get<ProgramReadiness>(
      `/calibration/programs/${forProgram}/readiness`
    )
    if (selectedProgram.current !== forProgram) return null
    setReadiness(response.data)
    return response.data
  }

  /** The same reload, but a failure only means the rows stay as they were. */
  async function tryRefreshReadiness(forProgram: string) {
    try {
      return await refreshReadiness(forProgram)
    } catch {
      return null
    }
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

  /** Remember an enrollment made or found from this page, if `forProgram` is still selected. */
  function rememberEnrollment(forProgram: string, reviewerId: string, enrollmentId: string) {
    if (selectedProgram.current !== forProgram) return
    setEnrolledHere((current) => new Map(current).set(reviewerId, enrollmentId))
  }

  /** Mark whether a facilitator's non-blind flag is still owed, if `forProgram` is still selected. */
  function setFlagOwed(forProgram: string, reviewerId: string, owed: boolean) {
    if (selectedProgram.current !== forProgram) return
    setUnflagged((current) => setMember(current, reviewerId, owed))
  }

  async function enroll(reviewer: Person, forProgram: string) {
    const facilitator = facilitators.has(reviewer.id)
    let enrollmentId: string
    try {
      const created = await api.post<{ id: string }>(`/calibration/programs/${forProgram}/enroll`, {
        reviewer_id: reviewer.id,
        recorder_usernames: [username],
        session_size: SAMPLES_PER_SESSION,
        label_scheme: 'shared',
        randomization_algorithm: SHARED_TRIPLES,
        persistent_membership_ids: [],
        session_template: null,
      })
      enrollmentId = created.data.id
    } catch (reason) {
      // A timeout can lose the answer to an enrollment that went through, and a
      // 409 means it already exists. Reload so the row shows the server's state.
      const status = await tryRefreshReadiness(forProgram)
      const existing = status?.enrollments.find((row) => row.reviewer_id === reviewer.id)
      if (!existing || !facilitator) throw reason
      // Enrolled, facilitator ticked, and nothing here proves the flag landed.
      rememberEnrollment(forProgram, reviewer.id, existing.enrollment_id)
      setFlagOwed(forProgram, reviewer.id, true)
      task.setError(
        `${reviewer.name} is enrolled, but this page cannot confirm they were marked ` +
          `non-blind: ${requestErrorMessage(reason)} Use "Retry non-blind flag" on their row ` +
          'before any sample is sprayed.'
      )
      return
    }
    // Remember the enrollment and the owed flag before anything else can fail:
    // the row must offer the retry even if the readiness reload does not come back.
    rememberEnrollment(forProgram, reviewer.id, enrollmentId)
    if (facilitator) setFlagOwed(forProgram, reviewer.id, true)
    await tryRefreshReadiness(forProgram)
    if (!facilitator) {
      task.setNotice(`${reviewer.name} is enrolled with shared blind labels.`)
      return
    }
    // The flag must land before the page calls this evaluator done. If it
    // fails the enrollment already exists, so say exactly that and offer a retry.
    try {
      await flagNonBlind(enrollmentId)
    } catch (reason) {
      task.setError(
        `${reviewer.name} is enrolled but could NOT be marked non-blind: ` +
          `${requestErrorMessage(reason)} Use "Retry non-blind flag" on their row ` +
          'before any sample is sprayed.'
      )
      return
    }
    setFlagOwed(forProgram, reviewer.id, false)
    task.setNotice(`${reviewer.name} is enrolled and marked non-blind.`)
  }

  async function retryFlag(reviewer: Person, enrollmentId: string, forProgram: string) {
    await flagNonBlind(enrollmentId)
    setFlagOwed(forProgram, reviewer.id, false)
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
          The members are the program&apos;s fixed bottles. Their identities are not shown on this
          page so the answer key stays hidden.
        </p>
      )}

      {program && (
        <>
          <hr />
          <h3>Evaluators</h3>
          <p>
            Enrolling uses the pilot settings and cannot be changed here: shared sessions of{' '}
            {SAMPLES_PER_SESSION} samples, shared blind labels, and you ({username || 'signed in'})
            as the one recorder.
          </p>
          <AddEvaluatorForm task={task} reload={reload} />
          {reviewers.length === 0 ? (
            <p>No evaluators yet. Add one above.</p>
          ) : (
            <ul className="data-list">
              {reviewers.map((reviewer) => {
                // An enrollment made here counts even if the readiness reload was lost.
                const enrollmentId =
                  enrollmentByReviewer.get(reviewer.id) ?? enrolledHere.get(reviewer.id)
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
                          onClick={() => void task.run(() => enroll(reviewer, program.id))}
                        >
                          Enroll <span className="visually-hidden">{reviewer.name}</span>
                        </button>
                      </>
                    )}
                    {enrollmentId && unflagged.has(reviewer.id) && (
                      <button
                        disabled={task.busy}
                        onClick={() =>
                          void task.run(() => retryFlag(reviewer, enrollmentId, program.id))
                        }
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
