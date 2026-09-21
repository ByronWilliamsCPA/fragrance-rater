import { describe, it, expect } from 'vitest'
import { calibrationEntryFor } from '../routing/calibrationEntry'
import type { EnrollmentSummary } from '../api/types'

function summary(overrides: Partial<EnrollmentSummary>): EnrollmentSummary {
  return {
    id: 'e1',
    program_id: 'p1',
    reviewer_id: 'r1',
    revealed: false,
    has_started: false,
    total_presentations: 3,
    blotter_complete: 0,
    skin_planned: 0,
    skin_complete: 0,
    program_name: 'Baseline',
    program_version: '1',
    group_name_summary: 'Baseline',
    ...overrides,
  }
}

describe('calibrationEntryFor', () => {
  it('routes to empty when there are no assignments', () => {
    expect(calibrationEntryFor([])).toEqual({ kind: 'empty' })
  })

  it('routes to guided for a single not-started enrollment', () => {
    const entry = summary({ id: 'e1' })
    expect(calibrationEntryFor([entry])).toEqual({ kind: 'guided', enrollmentId: 'e1' })
  })

  it('prefers resume over guided when both exist', () => {
    const notStarted = summary({ id: 'e1', has_started: false })
    const inProgress = summary({ id: 'e2', has_started: true })
    expect(calibrationEntryFor([notStarted, inProgress])).toEqual({
      kind: 'resume',
      enrollmentId: 'e2',
    })
  })

  it('routes to choice when every assignment is revealed', () => {
    const entry = summary({ id: 'e1', revealed: true, has_started: true })
    expect(calibrationEntryFor([entry])).toEqual({ kind: 'choice' })
  })

  it('picks the id-order tiebreak deterministically among multiple in-progress', () => {
    const first = summary({ id: 'a-first', has_started: true })
    const second = summary({ id: 'b-second', has_started: true })
    expect(calibrationEntryFor([second, first])).toEqual({
      kind: 'resume',
      enrollmentId: 'b-second',
    })
  })
})
