import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  DRAFT_FIELD_NAMES,
  RECORDER_STATE_MAX_AGE_MS,
  clearDraft,
  clearEnrollmentState,
  clearRecorderState,
  discardStaleRecorderState,
  loadDraft,
  loadEvaluator,
  loadProgress,
  saveDraft,
  saveEvaluator,
  saveProgress,
} from '../content/recorderState'

const owner = 'recorder'
const scope = { owner, programId: 'p1', enrollmentId: 'e1' }
const draftScope = { ...scope, sessionId: 'sess1', presentationId: 's1' }
const assignments = [
  { id: 'e1', program_id: 'p1', revealed: false },
  { id: 'e2', program_id: 'p1', revealed: false },
  { id: 'e3', program_id: 'p1', revealed: true },
]

function everythingStored(): string {
  return Object.keys(window.sessionStorage)
    .map((key) => `${key}=${window.sessionStorage.getItem(key)}`)
    .join('\n')
}

beforeEach(() => window.sessionStorage.clear())
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('recorder place and progress', () => {
  it('remembers which evaluator the recorder switched to', () => {
    saveEvaluator(owner, 'p1', 'e2')
    expect(loadEvaluator(owner, assignments)).toBe('e2')
  })

  it('finds nothing when nothing was saved', () => {
    expect(loadEvaluator(owner, assignments)).toBe('')
    expect(loadProgress(scope)).toBeNull()
  })

  it('discards an evaluator that is no longer assigned, in another program, or revealed', () => {
    saveEvaluator(owner, 'p1', 'gone')
    expect(loadEvaluator(owner, assignments)).toBe('')
    saveEvaluator(owner, 'p1', 'e3')
    expect(loadEvaluator(owner, assignments)).toBe('')
    saveEvaluator(owner, 'p2', 'e1')
    expect(loadEvaluator(owner, assignments)).toBe('')
  })

  it('discards state saved by another account', () => {
    saveEvaluator('someone-else', 'p1', 'e2')
    expect(loadEvaluator(owner, assignments)).toBe('')
    saveProgress({ ...scope, owner: 'someone-else' }, { introduced: new Set(['sess1']) })
    expect(loadProgress(scope)).toBeNull()
  })

  it('round-trips the wizard progress as session ids only', () => {
    saveProgress(scope, {
      introduced: new Set(['sess1']),
      ranked: new Set(['sess1']),
      acknowledged: new Set(),
    })
    const progress = loadProgress(scope)
    expect([...(progress?.introduced ?? [])]).toEqual(['sess1'])
    expect([...(progress?.ranked ?? [])]).toEqual(['sess1'])
    expect([...(progress?.acknowledged ?? [])]).toEqual([])
    expect(loadProgress({ ...scope, enrollmentId: 'e2' })).toBeNull()
    expect(loadProgress({ ...scope, programId: 'p2' })).toBeNull()
  })

  it('discards state older than twelve hours and removes it', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-25T08:00:00Z'))
    saveProgress(scope, { introduced: new Set(['sess1']) })
    saveEvaluator(owner, 'p1', 'e2')
    vi.setSystemTime(new Date(Date.now() + RECORDER_STATE_MAX_AGE_MS - 1000))
    expect(loadProgress(scope)).not.toBeNull()
    expect(loadEvaluator(owner, assignments)).toBe('e2')
    vi.setSystemTime(new Date(Date.now() + 2000))
    expect(loadProgress(scope)).toBeNull()
    expect(loadEvaluator(owner, assignments)).toBe('')
    expect(window.sessionStorage.length).toBe(0)
  })

  it('discards a malformed or hand-edited value instead of throwing', () => {
    window.sessionStorage.setItem('fr.recorder.v1:progress:p1:e1', '{not json')
    expect(loadProgress(scope)).toBeNull()
    window.sessionStorage.setItem(
      'fr.recorder.v1:progress:p1:e1',
      JSON.stringify({ owner, savedAt: Date.now(), programId: 'p1', enrollmentId: 'e1', ranked: 7 })
    )
    expect(loadProgress(scope)).toBeNull()
  })
})

describe('recorder draft', () => {
  it('round-trips the allowed fields and the detected answer', () => {
    saveDraft(draftScope, {
      detected: 'yes',
      fields: { confirmed_blind_code: 'AAA1', intensity: '5', sprayed_at: '2026-11-25T10:00' },
    })
    expect(loadDraft(draftScope)).toEqual({
      detected: 'yes',
      fields: { confirmed_blind_code: 'AAA1', intensity: '5', sprayed_at: '2026-11-25T10:00' },
    })
  })

  it('drops every field that is not on the allow list, so notes never reach storage', () => {
    saveDraft(draftScope, {
      detected: 'yes',
      fields: {
        intensity: '5',
        perceived_notes: 'vanilla, musk',
        likes: 'the dry down',
        comments: 'smells like Brand X Name',
        brand: 'Brand X',
      },
    })
    expect(loadDraft(draftScope)?.fields).toEqual({ intensity: '5' })
    expect(everythingStored()).not.toMatch(/vanilla|dry down|Brand X/)
    expect(DRAFT_FIELD_NAMES).not.toContain('perceived_notes')
    expect(DRAFT_FIELD_NAMES).not.toContain('comments')
  })

  it('refuses a detected value other than the three the form offers', () => {
    saveDraft(draftScope, { detected: 'Rose Absolue by Brand X', fields: {} })
    expect(loadDraft(draftScope)?.detected).toBe('')
  })

  it('discards a draft for another sample, session, enrollment, program, or account', () => {
    saveDraft(draftScope, { detected: '', fields: { intensity: '3' } })
    expect(loadDraft({ ...draftScope, presentationId: 's2' })).toBeNull()
    saveDraft(draftScope, { detected: '', fields: { intensity: '3' } })
    expect(loadDraft({ ...draftScope, owner: 'other' })).toBeNull()
  })

  it('discards a draft older than twelve hours', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-25T08:00:00Z'))
    saveDraft(draftScope, { detected: '', fields: { intensity: '3' } })
    vi.setSystemTime(new Date(Date.now() + RECORDER_STATE_MAX_AGE_MS + 1000))
    expect(loadDraft(draftScope)).toBeNull()
  })

  it('clears one draft, one enrollment, or everything', () => {
    saveDraft(draftScope, { detected: '', fields: { intensity: '3' } })
    clearDraft(draftScope)
    expect(loadDraft(draftScope)).toBeNull()

    saveDraft(draftScope, { detected: '', fields: { intensity: '3' } })
    saveProgress(scope, { introduced: new Set(['sess1']) })
    saveEvaluator(owner, 'p1', 'e1')
    clearEnrollmentState(scope)
    expect(loadDraft(draftScope)).toBeNull()
    expect(loadProgress(scope)).toBeNull()
    expect(loadEvaluator(owner, assignments)).toBe('e1')

    saveDraft(draftScope, { detected: '', fields: { intensity: '3' } })
    clearRecorderState()
    expect(window.sessionStorage.length).toBe(0)
  })

  it('leaves unrelated storage alone when clearing', () => {
    window.sessionStorage.setItem('unrelated', 'keep')
    saveDraft(draftScope, { detected: '', fields: { intensity: '3' } })
    clearRecorderState()
    expect(window.sessionStorage.getItem('unrelated')).toBe('keep')
  })

  it('never stores into localStorage', () => {
    saveDraft(draftScope, { detected: 'no', fields: { intensity: '3' } })
    saveProgress(scope, { introduced: new Set(['sess1']) })
    saveEvaluator(owner, 'p1', 'e2')
    expect(window.localStorage.length).toBe(0)
  })
})

describe('discarding stale state when the page opens', () => {
  it('removes expired, malformed and foreign entries and keeps the live one', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-25T08:00:00Z'))
    saveDraft(draftScope, { detected: '', fields: { intensity: '3' } })
    vi.setSystemTime(new Date(Date.now() + RECORDER_STATE_MAX_AGE_MS + 1000))
    saveProgress(scope, { introduced: new Set(['sess1']) })
    saveEvaluator('someone-else', 'p1', 'e2')
    window.sessionStorage.setItem('fr.recorder.v1:progress:p9:e9', '{broken')
    window.sessionStorage.setItem('unrelated', 'keep')

    discardStaleRecorderState(owner)

    expect(Object.keys(window.sessionStorage).sort()).toEqual([
      'fr.recorder.v1:progress:p1:e1',
      'unrelated',
    ])
  })

  it('does nothing when storage is unavailable', () => {
    vi.spyOn(window, 'sessionStorage', 'get').mockImplementation(() => {
      throw new DOMException('denied', 'SecurityError')
    })
    expect(() => discardStaleRecorderState(owner)).not.toThrow()
  })
})

describe('storage that is unavailable', () => {
  it('does nothing and throws nothing when sessionStorage cannot be reached', () => {
    vi.spyOn(window, 'sessionStorage', 'get').mockImplementation(() => {
      throw new DOMException('denied', 'SecurityError')
    })
    expect(() => saveEvaluator(owner, 'p1', 'e1')).not.toThrow()
    expect(() => saveProgress(scope, { introduced: new Set(['a']) })).not.toThrow()
    expect(() => saveDraft(draftScope, { detected: '', fields: {} })).not.toThrow()
    expect(() => clearDraft(draftScope)).not.toThrow()
    expect(() => clearEnrollmentState(scope)).not.toThrow()
    expect(() => clearRecorderState()).not.toThrow()
    expect(loadEvaluator(owner, assignments)).toBe('')
    expect(loadProgress(scope)).toBeNull()
    expect(loadDraft(draftScope)).toBeNull()
  })

  it('survives a full quota', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('full', 'QuotaExceededError')
    })
    expect(() => saveDraft(draftScope, { detected: '', fields: { intensity: '1' } })).not.toThrow()
    expect(() => saveEvaluator(owner, 'p1', 'e1')).not.toThrow()
  })
})
