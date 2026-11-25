import axios from 'axios'

/**
 * Helpers for the facilitated format, where a facilitator types an evaluator's
 * paper sheet into the app after the sitting. The paper keeps the exact times;
 * the app stores the first smell, the time the column finished and whole
 * elapsed minutes, and refuses a column keyed to the wrong sample.
 */

/**
 * The provisional spray-to-first-smell ceiling, in minutes.
 *
 * #ASSUME: Timing Dependencies: 2 minutes is the working value of the F1
 * facilitated format (ADR-005 amendment), not a final one. It runs from the
 * blotter's spray to THIS evaluator's first smell; in a group session a new
 * blotter is sprayed when the window would be exceeded.
 * #VERIFY: it mirrors SPRAY_TO_SMELL_CEILING in
 * src/fragrance_rater/services/transcription_timing.py; the server decides
 * whether a deviation flag is raised, this only warns before saving. Change
 * both together when the P6.3 rehearsal confirms the value.
 */
export const SPRAY_TO_SMELL_CEILING_MINUTES = 2

/** Whether an enrollment is transcribed from paper (the household/facilitated format). */
export function isTranscribed(policy: string | undefined): boolean {
  return policy === 'HOUSEHOLD'
}

/**
 * Whether the code the facilitator typed is the sample's own blind code.
 *
 * Mirrors the server's comparison (trimmed, case-insensitive); the server
 * enforces it as well, so this is only the first, friendlier line.
 */
export function blindCodeMatches(entered: string, expected: string): boolean {
  const typed = entered.trim().toUpperCase()
  return typed !== '' && typed === expected.trim().toUpperCase()
}

/** A `datetime-local` value as a UTC ISO instant; null when blank or unreadable. */
export function toInstant(local: string): string | null {
  if (!local) return null
  const value = new Date(local)
  return Number.isNaN(value.getTime()) ? null : value.toISOString()
}

/** A server instant (naive UTC, no zone suffix) as a Date. */
export function fromServerInstant(value: string): Date {
  return new Date(/(Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`)
}

/** Whole minutes from spray to the column finishing (floor); null when either is missing or reversed. */
export function elapsedWholeMinutes(sprayed: string, finished: string): number | null {
  const start = toInstant(sprayed)
  const end = toInstant(finished)
  if (!start || !end) return null
  const milliseconds = new Date(end).getTime() - new Date(start).getTime()
  return milliseconds < 0 ? null : Math.floor(milliseconds / 60_000)
}

/** Minutes from spray to first smell, to the second; null when either is missing. */
export function sprayToSmellMinutes(sprayed: string, smelled: string): number | null {
  const start = toInstant(sprayed)
  const end = toInstant(smelled)
  if (!start || !end) return null
  return (new Date(end).getTime() - new Date(start).getTime()) / 60_000
}

/** Whether a first smell breaches the ceiling (exactly at it does not). */
export function overCeiling(sprayed: string, smelled: string): boolean {
  const minutes = sprayToSmellMinutes(sprayed, smelled)
  return minutes !== null && minutes > SPRAY_TO_SMELL_CEILING_MINUTES
}

/**
 * The first problem with the three paper times, or null when they are
 * consistent: spray, then first smell, then the column finishing.
 *
 * `smelled` is only checked while the first smell is still to be recorded;
 * after that the server holds it and the column is checked against the spray.
 */
export function paperTimeProblem(times: {
  sprayed: string
  smelled: string
  finished: string
  firstSmellStillToRecord: boolean
}): string | null {
  const { sprayed, smelled, finished, firstSmellStillToRecord } = times
  if (!toInstant(sprayed)) return 'Enter the time the blotter was sprayed, as written on the sheet.'
  if (firstSmellStillToRecord && !toInstant(smelled))
    return 'Enter the time the blotter was first smelled, as written on the sheet.'
  if (!toInstant(finished)) return 'Enter the time this column finished, as written on the sheet.'
  if (firstSmellStillToRecord && new Date(smelled) < new Date(sprayed))
    return 'The first smell cannot be before the spray. Check both times against the sheet.'
  if (new Date(finished) < new Date(sprayed))
    return 'The column cannot finish before the spray. Check both times against the sheet.'
  if (firstSmellStillToRecord && new Date(finished) < new Date(smelled))
    return 'The column cannot finish before the first smell. Check both times against the sheet.'
  return null
}

/** True when a failed request means the first smell was already stamped for this sample. */
export function isExposureAlreadyRecorded(reason: unknown): boolean {
  if (!axios.isAxiosError(reason) || reason.response?.status !== 409) return false
  const detail: unknown = reason.response.data?.detail
  return typeof detail === 'string' && detail.includes('already recorded')
}

/** True when a failed request means the session had already ended. */
export function isSessionAlreadyEnded(reason: unknown): boolean {
  if (!axios.isAxiosError(reason) || reason.response?.status !== 409) return false
  const detail: unknown = reason.response.data?.detail
  return typeof detail === 'string' && detail.includes('already ended')
}
