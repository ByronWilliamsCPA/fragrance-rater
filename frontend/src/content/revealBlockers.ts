import type { CheckpointBlocker, RevealBlocker, RevealPolicy } from '../api/types'

/**
 * Short manager-facing labels for a reveal blocker, used on progress cards and
 * the readiness table. The server's enum is additive (gate API contract), so
 * an unknown value gets a generic "not ready" label rather than `undefined`.
 */
export function revealBlockerLabel(blocker: RevealBlocker | null): string {
  switch (blocker) {
    case null:
      return 'Ready to reveal'
    case 'SKIN_PLAN':
      return 'Skin plan is not finalized'
    case 'BLOTTER':
      return 'Blotter responses remain'
    case 'SKIN':
      return 'Planned skin responses remain'
    case 'CHECKPOINT':
      return 'Checkpoint not frozen'
    case 'HOLDOUT':
      return 'Final samples remain'
    case 'HOUSEHOLD_WAIT':
      return 'Finished; waiting for the rest of the household'
    default:
      return 'Not ready to reveal'
  }
}

/** Manager-facing label for why a checkpoint cannot be frozen; null means ready. */
export function checkpointBlockerLabel(blocker: CheckpointBlocker | null): string {
  switch (blocker) {
    case null:
      return 'Ready for a checkpoint'
    case 'HOLDOUT_OBSERVED':
      return 'Too late: final samples were already recorded'
    case 'SKIN_PLAN':
      return 'Skin plan is not finalized'
    case 'BLOTTER':
      return 'Blotter responses remain'
    case 'SKIN':
      return 'Planned skin responses remain'
    case 'HAS_CHECKPOINT':
      return 'Already has a checkpoint'
    default:
      return 'Not ready for a checkpoint'
  }
}

/**
 * The one-line status for an unrevealed enrollment, in the recorder's terms.
 *
 * The server reports SKIN_PLAN first whenever the plan is open, even while
 * blotter screens remain, so the SKIN_PLAN wording must not claim the
 * blotters are done (the old guidance did). The wording never says "holdout":
 * evaluators may read this screen, and the gate API contract keeps that word
 * away from them.
 */
export function revealGuidance(blocker: RevealBlocker | null, policy?: RevealPolicy): string {
  switch (blocker) {
    case 'SKIN_PLAN':
      return 'Finish the blind blotter screens, then finalize the skin-test plan. An empty plan means no skin tests.'
    case 'BLOTTER':
      return 'Required blind blotter screens still need to be locked.'
    case 'SKIN':
      return 'Planned blind skin tests still need to be locked.'
    case 'CHECKPOINT':
      return "Blind baseline work is locked. The next samples open after a manager freezes this evaluator's checkpoint."
    case 'HOLDOUT':
      return 'The final blind samples still need to be locked.'
    case 'HOUSEHOLD_WAIT':
      return 'This evaluator is finished. Identities are revealed for everyone together once every evaluator has finished.'
    case null:
      return policy === 'HOUSEHOLD'
        ? 'Every evaluator has finished. A manager reveals the whole household together from Program setup.'
        : 'All required blind work is locked. The enrollment is eligible to reveal.'
    default:
      return 'Blind work is still outstanding.'
  }
}
