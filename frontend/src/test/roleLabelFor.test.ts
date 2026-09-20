import { describe, expect, it } from 'vitest'
import { roleLabelFor } from '../api/types'

describe('roleLabelFor', () => {
  it('returns Manager when canManagePrograms is set', () => {
    expect(roleLabelFor({ canManagePrograms: true, canRecordCalibration: false })).toBe('Manager')
  })

  it('returns Recorder for a non-manager who can record calibration', () => {
    expect(roleLabelFor({ canManagePrograms: false, canRecordCalibration: true })).toBe('Recorder')
  })

  it('returns Participant when neither capability is set', () => {
    expect(roleLabelFor({ canManagePrograms: false, canRecordCalibration: false })).toBe(
      'Participant'
    )
  })
})
