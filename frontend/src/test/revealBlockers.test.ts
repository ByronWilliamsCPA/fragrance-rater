import { describe, expect, it } from 'vitest'
import {
  checkpointBlockerLabel,
  revealBlockerLabel,
  revealGuidance,
} from '../content/revealBlockers'
import type { CheckpointBlocker, RevealBlocker } from '../api/types'

// The server's blocker enums are additive (gate API contract): a value this
// build does not know yet must read as "not ready", never as undefined text.
const unknownReveal = 'SOMETHING_NEW' as RevealBlocker
const unknownCheckpoint = 'SOMETHING_NEW' as CheckpointBlocker

describe('revealBlockerLabel', () => {
  it.each([
    [null, 'Ready to reveal'],
    ['SKIN_PLAN', 'Skin plan is not finalized'],
    ['BLOTTER', 'Blotter responses remain'],
    ['SKIN', 'Planned skin responses remain'],
    ['CHECKPOINT', 'Checkpoint not frozen'],
    ['HOLDOUT', 'Final samples remain'],
    ['HOUSEHOLD_WAIT', 'Finished; waiting for the rest of the household'],
    [unknownReveal, 'Not ready to reveal'],
  ] as [RevealBlocker | null, string][])('labels %s', (blocker, label) => {
    expect(revealBlockerLabel(blocker)).toBe(label)
  })
})

describe('checkpointBlockerLabel', () => {
  it.each([
    [null, 'Ready for a checkpoint'],
    ['HOLDOUT_OBSERVED', 'Too late: final samples were already recorded'],
    ['SKIN_PLAN', 'Skin plan is not finalized'],
    ['BLOTTER', 'Blotter responses remain'],
    ['SKIN', 'Planned skin responses remain'],
    ['HAS_CHECKPOINT', 'Already has a checkpoint'],
    [unknownCheckpoint, 'Not ready for a checkpoint'],
  ] as [CheckpointBlocker | null, string][])('labels %s', (blocker, label) => {
    expect(checkpointBlockerLabel(blocker)).toBe(label)
  })
})

describe('revealGuidance', () => {
  it('does not claim the blotters are done while the skin plan is the reported blocker', () => {
    expect(revealGuidance('SKIN_PLAN')).toMatch(/^Finish the blind blotter screens/)
  })

  it.each([
    ['BLOTTER', /blotter screens still need to be locked/],
    ['SKIN', /skin tests still need to be locked/],
    ['CHECKPOINT', /freezes this evaluator's checkpoint/],
    ['HOLDOUT', /final blind samples still need to be locked/],
    ['HOUSEHOLD_WAIT', /revealed for everyone together/],
    [unknownReveal, /^Blind work is still outstanding\.$/],
  ] as [RevealBlocker, RegExp][])('explains %s', (blocker, text) => {
    expect(revealGuidance(blocker)).toMatch(text)
  })

  it('points a household program at the manager-led reveal once everyone is finished', () => {
    expect(revealGuidance(null, 'HOUSEHOLD')).toMatch(/reveals the whole household together/)
    expect(revealGuidance(null, 'ENROLLMENT')).toMatch(/eligible to reveal/)
    expect(revealGuidance(null)).toMatch(/eligible to reveal/)
  })

  it('never says "holdout" to anyone who may be an evaluator', () => {
    const all: (RevealBlocker | null)[] = [
      null,
      'SKIN_PLAN',
      'BLOTTER',
      'SKIN',
      'CHECKPOINT',
      'HOLDOUT',
      'HOUSEHOLD_WAIT',
      unknownReveal,
    ]
    for (const blocker of all) {
      expect(revealGuidance(blocker, 'HOUSEHOLD')).not.toMatch(/holdout/i)
      expect(revealBlockerLabel(blocker)).not.toMatch(/holdout/i)
    }
  })
})
