import { describe, expect, it } from 'vitest'
import { allAssessed, rankableSamples, rankError } from '../content/ranking'
import type { Observation, Sample } from '../api/types'

function sample(id: string, observations: Partial<Observation>[]): Sample {
  return {
    id,
    session_id: 's',
    blind_code: id,
    position: 1,
    skin_planned: false,
    blotter_locked: true,
    skin_locked: false,
    post_reveal_entry: false,
    observations: observations.map(
      (row, index) =>
        ({ id: `${id}${index}`, stage: 'BLOTTER', phase: 'PRE_REVEAL', ...row }) as Observation
    ),
  }
}

describe('rankableSamples', () => {
  it('keeps detected samples and drops undetected, skipped and unassessable ones', () => {
    const samples = [
      sample('a', [{ detected: true, response_status: 'completed' }]),
      sample('b', [{ detected: false, response_status: 'not_detected' }]),
      sample('c', [{ detected: true, response_status: 'skipped' }]),
      sample('d', [{ detected: true, response_status: 'unable_to_assess' }]),
      sample('e', [{ detected: true }]),
    ]

    expect(rankableSamples(samples).map((item) => item.id)).toEqual(['a', 'e'])
  })

  it('judges a sample by its latest response, not its first', () => {
    const samples = [
      sample('a', [
        { detected: true, created_at: '2026-10-30T10:00:00' },
        { detected: false, created_at: '2026-10-30T10:05:00', response_status: 'not_detected' },
      ]),
    ]

    expect(rankableSamples(samples)).toEqual([])
  })

  it('ignores skin responses when ranking at the blotter stage', () => {
    const samples = [sample('a', [{ stage: 'SKIN', detected: true }])]

    expect(rankableSamples(samples)).toEqual([])
    expect(allAssessed(samples)).toBe(false)
  })
})

describe('rankError', () => {
  it('accepts a straight ranking and a tie that skips the next place', () => {
    expect(rankError([1, 2, 3])).toBeNull()
    expect(rankError([1, 1, 3])).toBeNull()
    expect(rankError([2, 1, 2])).toBeNull()
  })

  it('refuses a missing place', () => {
    expect(rankError([1, null])).toMatch(/every sample/i)
  })

  it('refuses a gap or a wrong place after a tie', () => {
    expect(rankError([1, 3, 3])).toMatch(/places must run/i)
    expect(rankError([2, 3])).toMatch(/places must run/i)
    expect(rankError([1, 1, 2])).toMatch(/places must run/i)
  })
})
