import type { EnrollmentSummary } from '../api/types'

/**
 * The calibration entry-routing decision, computed once from the enriched
 * enrollment list.
 *
 * "resume" and "guided" both open the same GuidedCalibrationFlow wizard,
 * distinguished only by which enrollment they open; the wizard itself
 * computes its own starting step from that enrollment's current state
 * (see nextWizardStep in GuidedCalibrationFlow.tsx). "First" among multiple
 * candidates is the array's own order, which callers get from the API's
 * `order_by(Enrollment.id)` tiebreak: stable across requests, not a claim
 * about creation order (see the design doc's §1 note).
 */
export type CalibrationEntryDecision =
  | { kind: 'resume'; enrollmentId: string }
  | { kind: 'guided'; enrollmentId: string }
  | { kind: 'choice' }
  | { kind: 'empty' }

export function calibrationEntryFor(
  assignments: readonly EnrollmentSummary[]
): CalibrationEntryDecision {
  if (assignments.length === 0) return { kind: 'empty' }
  const incomplete = assignments.filter((entry) => !entry.revealed)
  const inProgress = incomplete.find((entry) => entry.has_started)
  if (inProgress) return { kind: 'resume', enrollmentId: inProgress.id }
  const notStarted = incomplete.find((entry) => !entry.has_started)
  if (notStarted) return { kind: 'guided', enrollmentId: notStarted.id }
  return { kind: 'choice' }
}
