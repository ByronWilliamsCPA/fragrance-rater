import type { Observation, Sample } from '../api/types'

/** Statuses that mean a sample could not be assessed, so it is never ranked. */
const unrankableStatuses = ['skipped', 'unable_to_assess', 'interrupted', 'invalidated']

/** A sample's latest blind response at the stage, or undefined if none. */
export function latestAtStage(sample: Sample, stage: string): Observation | undefined {
  const rows = sample.observations
    .filter((row) => row.stage === stage)
    .map((row, index) => ({ row, index }))
    .sort(
      (a, b) => (a.row.created_at ?? '').localeCompare(b.row.created_at ?? '') || a.index - b.index
    )
  return rows.at(-1)?.row
}

/**
 * The samples the evaluator is asked to rank: detected, and not skipped or
 * unassessable at their latest response. The server makes the same decision and
 * refuses any other set, so this only spares the evaluator an error.
 */
export function rankableSamples(samples: Sample[], stage = 'BLOTTER'): Sample[] {
  return samples.filter((sample) => {
    const latest = latestAtStage(sample, stage)
    return latest?.detected === true && !unrankableStatuses.includes(latest.response_status ?? '')
  })
}

/** True once every sample has at least one response at the stage. */
export function allAssessed(samples: Sample[], stage = 'BLOTTER'): boolean {
  return samples.every((sample) => latestAtStage(sample, stage) !== undefined)
}

/**
 * Why a set of rank positions is not valid, or null if it is.
 *
 * Standard competition ranking: ties share the lower position and the next
 * position skips (1, 1, 3). A position must be one more than the number of
 * entries ranked strictly ahead of it. Mirrors `RankingInput` on the server.
 */
export function rankError(positions: (number | null)[]): string | null {
  if (positions.some((position) => position === null)) return 'Give every sample a place.'
  const placed = positions as number[]
  const sorted = [...placed].sort((a, b) => a - b)
  for (const position of sorted) {
    const expected = 1 + sorted.filter((other) => other < position).length
    if (position !== expected) {
      return 'Places must run 1, 2, 3 and so on; tied samples share a place and the next place is skipped (for example 1, 1, 3).'
    }
  }
  return null
}
