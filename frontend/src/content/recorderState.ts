import { numericFieldNames } from './calibrationScales'
import type { WizardProgress } from '../routing/wizardSteps'

/**
 * Where a facilitator had got to, kept in this tab's sessionStorage so an
 * accidental refresh, a laptop sleep or a crashed tab does not lose their place
 * halfway through typing in six evaluators' paper sheets.
 *
 * What the server already knows is never copied here: which session and sample
 * are next is rebuilt from the enrollment on every load. Only what the server
 * cannot know is kept:
 *
 * - which evaluator the recorder switched to (an id);
 * - which session screens (opening, ranking, boundary) were already passed
 *   (session ids);
 * - the half-typed numeric and time fields of the column being copied.
 *
 * #CRITICAL: Security: this is a blind evaluation, so nothing that could reveal
 * or reconstruct a sample's identity may reach browser storage: no fragrance,
 * brand or note names, no code-to-identity mapping, no free-text notes, no auth
 * token. Draft fields pass an allow list, not a block list, so a field added to
 * the form later is not stored until someone decides it may be.
 * #VERIFY: recorderState.test.ts asserts on the stored text itself.
 *
 * #EDGE: External Resources: sessionStorage can throw or be absent (private
 * window, blocked site data, full quota). Every access is guarded and the page
 * works exactly as it did before, only without the safety net.
 * #VERIFY: the "storage that is unavailable" tests.
 */

const PREFIX = 'fr.recorder.v1'

/** State older than this is discarded, so a stale tab cannot resurrect last week's place. */
export const RECORDER_STATE_MAX_AGE_MS = 12 * 60 * 60 * 1000

/** Ids that say whose place this is, and where. */
export type RecorderScope = { owner: string; programId: string; enrollmentId: string }

/** A draft belongs to one sample of one session. */
export type DraftScope = RecorderScope & { sessionId: string; presentationId: string }

/**
 * The only form fields a draft may hold. Free-text notes (perceived notes,
 * likes, dislikes, reminders, comments) are deliberately absent.
 */
export const DRAFT_FIELD_NAMES: readonly string[] = [
  'confirmed_blind_code',
  'sprayed_at',
  'first_smelled_at',
  'observed_at',
  'elapsed_minutes',
  'unanswered_reason',
  'recognition',
  'owned_or_worn',
  ...numericFieldNames,
]

const DETECTED_VALUES = ['', 'yes', 'no']
const MAX_FIELD_LENGTH = 40

export type Draft = { detected: string; fields: Record<string, string> }

type Stamped = { owner: string; savedAt: number }

function store(): Storage | null {
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

function remove(key: string) {
  try {
    store()?.removeItem(key)
  } catch {
    /* nothing to clean up */
  }
}

function write(key: string, value: Stamped & Record<string, unknown>) {
  try {
    store()?.setItem(key, JSON.stringify(value))
  } catch {
    /* quota or blocked storage: the page works without it */
  }
}

/** Reads a stamped value, discarding (and removing) one that is stale, foreign or malformed. */
function read(key: string, owner: string): (Stamped & Record<string, unknown>) | null {
  let raw: string | null = null
  try {
    raw = store()?.getItem(key) ?? null
  } catch {
    return null
  }
  if (raw === null) return null
  try {
    const value: unknown = JSON.parse(raw)
    if (typeof value === 'object' && value !== null) {
      const stamped = value as Stamped & Record<string, unknown>
      const age = Date.now() - stamped.savedAt
      if (stamped.owner === owner && Number.isFinite(age) && age <= RECORDER_STATE_MAX_AGE_MS)
        return stamped
    }
  } catch {
    /* malformed: fall through to discard */
  }
  remove(key)
  return null
}

const placeKey = (programId: string) => `${PREFIX}:place:${programId}`
const progressKey = (scope: RecorderScope) =>
  `${PREFIX}:progress:${scope.programId}:${scope.enrollmentId}`
const draftKey = (scope: DraftScope) =>
  `${PREFIX}:draft:${scope.programId}:${scope.enrollmentId}:${scope.sessionId}`

/** Remembers the evaluator the recorder switched to. */
export function saveEvaluator(owner: string, programId: string, enrollmentId: string) {
  write(placeKey(programId), { owner, savedAt: Date.now(), programId, enrollmentId })
}

/**
 * The evaluator to reopen, or '' when none was saved. Checked against what the
 * server now says: the enrollment must still be assigned, in the same program,
 * and not yet revealed.
 */
export function loadEvaluator(
  owner: string,
  assignments: ReadonlyArray<{ id: string; program_id: string; revealed: boolean }>
): string {
  let best: { enrollmentId: string; savedAt: number } | null = null
  for (const programId of new Set(assignments.map((item) => item.program_id))) {
    const key = placeKey(programId)
    const value = read(key, owner)
    if (!value) continue
    const enrollmentId = value.enrollmentId
    const match = assignments.find(
      (item) => item.id === enrollmentId && item.program_id === programId && !item.revealed
    )
    if (value.programId !== programId || !match) {
      remove(key)
      continue
    }
    if (!best || value.savedAt > best.savedAt)
      best = { enrollmentId: match.id, savedAt: value.savedAt }
  }
  return best?.enrollmentId ?? ''
}

function isStringList(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

/** Remembers which session screens were already passed for an enrollment. */
export function saveProgress(scope: RecorderScope, progress: Partial<WizardProgress>) {
  write(progressKey(scope), {
    owner: scope.owner,
    savedAt: Date.now(),
    programId: scope.programId,
    enrollmentId: scope.enrollmentId,
    introduced: [...(progress.introduced ?? [])],
    ranked: [...(progress.ranked ?? [])],
    acknowledged: [...(progress.acknowledged ?? [])],
  })
}

export function loadProgress(scope: RecorderScope): WizardProgress | null {
  const key = progressKey(scope)
  const value = read(key, scope.owner)
  if (!value) return null
  const { introduced, ranked, acknowledged } = value
  if (
    value.programId !== scope.programId ||
    value.enrollmentId !== scope.enrollmentId ||
    !isStringList(introduced) ||
    !isStringList(ranked) ||
    !isStringList(acknowledged)
  ) {
    remove(key)
    return null
  }
  return {
    introduced: new Set(introduced),
    ranked: new Set(ranked),
    acknowledged: new Set(acknowledged),
  }
}

/** Keeps only the allowed fields, as short strings. */
function cleanDraft(draft: Draft): Draft {
  const fields: Record<string, string> = {}
  for (const name of DRAFT_FIELD_NAMES) {
    const value = draft.fields[name]
    if (typeof value === 'string' && value !== '' && value.length <= MAX_FIELD_LENGTH)
      fields[name] = value
  }
  return { detected: DETECTED_VALUES.includes(draft.detected) ? draft.detected : '', fields }
}

/** Saves the unsaved fields of the column being typed. */
export function saveDraft(scope: DraftScope, draft: Draft) {
  const clean = cleanDraft(draft)
  write(draftKey(scope), {
    owner: scope.owner,
    savedAt: Date.now(),
    programId: scope.programId,
    enrollmentId: scope.enrollmentId,
    sessionId: scope.sessionId,
    presentationId: scope.presentationId,
    detected: clean.detected,
    fields: clean.fields,
  })
}

export function loadDraft(scope: DraftScope): Draft | null {
  const key = draftKey(scope)
  const value = read(key, scope.owner)
  if (!value) return null
  const { fields, detected } = value
  if (
    value.programId !== scope.programId ||
    value.enrollmentId !== scope.enrollmentId ||
    value.sessionId !== scope.sessionId ||
    value.presentationId !== scope.presentationId ||
    typeof detected !== 'string' ||
    typeof fields !== 'object' ||
    fields === null
  ) {
    remove(key)
    return null
  }
  return cleanDraft({ detected, fields: fields as Record<string, string> })
}

export function clearDraft(scope: DraftScope) {
  remove(draftKey(scope))
}

function removeWhere(matches: (key: string) => boolean) {
  try {
    const storage = store()
    if (!storage) return
    const keys: string[] = []
    for (let index = 0; index < storage.length; index += 1) {
      const key = storage.key(index)
      if (key !== null && matches(key)) keys.push(key)
    }
    for (const key of keys) storage.removeItem(key)
  } catch {
    /* nothing to clean up */
  }
}

/**
 * The three paper times are controlled inputs, started from the draft by
 * PaperSheetFields itself; every other draft field is a plain form control.
 */
const CONTROLLED_FIELDS = ['sprayed_at', 'first_smelled_at', 'observed_at']

function isChecked(element: Element): boolean {
  return (
    element instanceof HTMLInputElement &&
    (element.type === 'radio' || element.type === 'checkbox') &&
    element.checked
  )
}

/** Reads the draftable fields out of a form as it stands. */
export function collectDraftFields(form: HTMLFormElement): Record<string, string> {
  const fields: Record<string, string> = {}
  for (const element of Array.from(form.elements)) {
    if (
      !(element instanceof HTMLInputElement || element instanceof HTMLSelectElement) ||
      !DRAFT_FIELD_NAMES.includes(element.name)
    )
      continue
    const choice =
      element instanceof HTMLInputElement && ['radio', 'checkbox'].includes(element.type)
    if (choice && !isChecked(element)) continue
    fields[element.name] = element.value
  }
  return fields
}

/** Puts saved values back into the plain (uncontrolled) controls of a form. */
export function applyDraftFields(form: HTMLFormElement, fields: Record<string, string>) {
  for (const element of Array.from(form.elements)) {
    if (
      !(element instanceof HTMLInputElement || element instanceof HTMLSelectElement) ||
      CONTROLLED_FIELDS.includes(element.name)
    )
      continue
    const value = fields[element.name]
    if (value === undefined) continue
    if (element instanceof HTMLInputElement && element.type === 'radio')
      element.checked = element.value === value
    else element.value = value
  }
}

/**
 * Removes whatever this module stored that is now stale, malformed, or another
 * account's. Run when the recorder's page opens, so a changed login or an old
 * sitting leaves nothing behind even where no screen would have read it.
 */
export function discardStaleRecorderState(owner: string) {
  const prefix = `${PREFIX}:`
  const stale: string[] = []
  try {
    const storage = store()
    if (!storage) return
    for (let index = 0; index < storage.length; index += 1) {
      const key = storage.key(index)
      if (key?.startsWith(prefix)) stale.push(key)
    }
  } catch {
    return
  }
  // read() removes what it rejects; what it accepts is kept.
  for (const key of stale) read(key, owner)
}

/** Forgets one enrollment's passed screens and drafts (it was finalized or revealed). */
export function clearEnrollmentState(scope: RecorderScope) {
  const drafts = `${PREFIX}:draft:${scope.programId}:${scope.enrollmentId}:`
  const progress = progressKey(scope)
  removeWhere((key) => key === progress || key.startsWith(drafts))
}

/** Forgets everything this module stored, for a sign-out or an account change. */
export function clearRecorderState() {
  removeWhere((key) => key.startsWith(`${PREFIX}:`))
}
