import type { Enrollment, Sample } from '../api/types'

/** One calibration session of an enrollment, in schedule order. */
export type SessionGroup = {
  id: string
  /** 1-based position in the enrollment's schedule. */
  number: number
  samples: Sample[]
}

/**
 * Groups an enrollment's samples by session, keeping the server's order.
 *
 * The participant payload lists presentations ordered by session schedule then
 * position (CalibrationService.presentations), so first appearance is session
 * order; nothing here re-sorts by id or code, which would leak nothing but
 * would scramble the schedule.
 */
export function sessionsOf(enrollment: Enrollment): SessionGroup[] {
  const groups = new Map<string, Sample[]>()
  for (const sample of enrollment.presentations) {
    const group = groups.get(sample.session_id)
    if (group) group.push(sample)
    else groups.set(sample.session_id, [sample])
  }
  return Array.from(groups, ([id, samples], index) => ({ id, number: index + 1, samples }))
}

/**
 * Whether the server currently lets this sample be worked.
 *
 * #CRITICAL: Data Integrity: a sample the holdout gate holds closed must never
 * be offered, or an evaluator could record a final sample before the
 * checkpoint and destroy the prospective evaluation (gate API contract).
 * #VERIFY: only an explicit `available: false` closes a sample; a server older
 * than the gate omits the field and still has no gate to honour. The server
 * refuses every write to a closed sample regardless, so this is the first line,
 * not the only one.
 */
export function isOpen(sample: Sample): boolean {
  return sample.available !== false
}

function started(session: SessionGroup): boolean {
  return session.samples.some((sample) => sample.observations.length > 0)
}

/**
 * What the wizard has already moved past in this visit. Nothing here is
 * persisted: a reload re-derives the step from the enrollment and, at most,
 * shows a session's ranking check and boundary once more.
 */
export type WizardProgress = {
  /** Sessions whose opening screen (consent, conditions, start) was completed. */
  introduced: ReadonlySet<string>
  /** Completed sessions whose end-of-session ranking was saved or declined. */
  ranked: ReadonlySet<string>
  /** Completed sessions whose boundary screen the facilitator has passed. */
  acknowledged: ReadonlySet<string>
}

export const noProgress: WizardProgress = {
  introduced: new Set(),
  ranked: new Set(),
  acknowledged: new Set(),
}

export type WizardStep =
  | { kind: 'session_intro'; sessionId: string }
  | { kind: 'blotter'; sessionId: string; presentationId: string }
  | { kind: 'session_ranking'; sessionId: string }
  | { kind: 'session_boundary'; sessionId: string }
  | { kind: 'skin_plan' }
  | { kind: 'skin'; presentationId: string }
  | { kind: 'awaiting_checkpoint' }
  | { kind: 'household_wait' }
  | { kind: 'household_ready' }
  | { kind: 'ready_to_reveal' }
  | { kind: 'revealed' }
  | { kind: 'not_ready'; blocker: string }

/**
 * The next valid wizard step, worked one session at a time.
 *
 * Order: the current session's opening screen and samples; at the end of each
 * session its ranking and a boundary screen that never auto-advances; once no
 * open session remains, the skin-test plan (after the baseline, not before),
 * any planned skin tests, then whatever the server's `reveal_blocker` says is
 * outstanding (checkpoint, household wait) or the reveal itself.
 *
 * The pick is role-aware through `available`: the frontend never sees a
 * sample's role (ADR-005), but the server closes every final (prospective)
 * sample until a checkpoint exists, so the first session with an unlocked,
 * open sample is always the right one. A session is worked only when every
 * sample in it is open, because the server refuses to start or rank a session
 * that holds a closed sample.
 */
export function nextWizardStep(
  enrollment: Enrollment,
  progress: WizardProgress = noProgress
): WizardStep {
  const sessions = sessionsOf(enrollment)
  const currentIndex = sessions.findIndex(
    (session) =>
      session.samples.every(isOpen) && session.samples.some((sample) => !sample.blotter_locked)
  )
  const current = currentIndex === -1 ? undefined : sessions[currentIndex]
  const earlier = current ? sessions.slice(0, currentIndex) : sessions
  const finished = [...earlier]
    .reverse()
    .find((session) => session.samples.every((sample) => sample.blotter_locked))
  const currentStarted = current ? started(current) : false

  // The end of the most recent session, shown before the next one opens and
  // never once the next session has responses (a reload mid-session must not
  // bounce the recorder back to the boundary).
  if (finished && !currentStarted) {
    // A ranking is a blind judgment: once any identity in the session is
    // visible it is no longer asked for.
    const blind = finished.samples.every((sample) => !sample.post_reveal_entry)
    if (blind && !progress.ranked.has(finished.id))
      return { kind: 'session_ranking', sessionId: finished.id }
    const nothingLeft = enrollment.revealed && !current
    if (!nothingLeft && !progress.acknowledged.has(finished.id))
      return { kind: 'session_boundary', sessionId: finished.id }
  }

  if (current) {
    if (!currentStarted && !progress.introduced.has(current.id))
      return { kind: 'session_intro', sessionId: current.id }
    const sample = current.samples.find((item) => !item.blotter_locked)
    if (sample) return { kind: 'blotter', sessionId: current.id, presentationId: sample.id }
  }

  if (enrollment.revealed) return { kind: 'revealed' }
  if (!enrollment.skin_plan_locked) return { kind: 'skin_plan' }
  const skin = enrollment.presentations.find(
    (item) => isOpen(item) && item.skin_planned && !item.skin_locked
  )
  if (skin) return { kind: 'skin', presentationId: skin.id }

  // #ASSUME: External Resources: reveal_blocker is the backend's authoritative
  // gate. Only a literal null, its explicit "nothing left" signal, reaches a
  // reveal step; an unknown or unexpected value is treated as "not ready".
  // #VERIFY: the default arm below returns not_ready, never a reveal.
  const blocker = enrollment.reveal_blocker
  if (blocker === null)
    return enrollment.reveal_policy === 'HOUSEHOLD'
      ? { kind: 'household_ready' }
      : { kind: 'ready_to_reveal' }
  if (blocker === 'CHECKPOINT') return { kind: 'awaiting_checkpoint' }
  if (blocker === 'HOUSEHOLD_WAIT') return { kind: 'household_wait' }
  if (enrollment.presentations.some((item) => !isOpen(item))) return { kind: 'awaiting_checkpoint' }
  return { kind: 'not_ready', blocker }
}

/** Step-of-total orientation: skin plan, every blotter, every planned skin test, reveal. */
export function progressFor(enrollment: Enrollment): { step: number; total: number } {
  const skinPlanned = enrollment.presentations.filter((item) => item.skin_planned)
  const done =
    (enrollment.skin_plan_locked ? 1 : 0) +
    enrollment.presentations.filter((item) => item.blotter_locked).length +
    skinPlanned.filter((item) => item.skin_locked).length
  return {
    step: Math.min(done + 1, 2 + enrollment.presentations.length + skinPlanned.length),
    total: 2 + enrollment.presentations.length + skinPlanned.length,
  }
}
