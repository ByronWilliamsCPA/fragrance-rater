import { describe, expect, it } from 'vitest'
import { roleLabelFor } from '../api/types'

describe('roleLabelFor', () => {
  it('returns Manager when canManagePrograms is set', () => {
    expect(
      roleLabelFor({
        canManagePrograms: true,
        canRecordCalibration: false,
        isHouseContributor: false,
      })
    ).toBe('Manager')
  })

  it('returns Recorder for a non-manager who can record calibration', () => {
    expect(
      roleLabelFor({
        canManagePrograms: false,
        canRecordCalibration: true,
        isHouseContributor: false,
      })
    ).toBe('Recorder')
  })

  it('returns Fragrance house for a house contributor account', () => {
    expect(
      roleLabelFor({
        canManagePrograms: false,
        canRecordCalibration: false,
        isHouseContributor: true,
      })
    ).toBe('Fragrance house')
  })

  it('returns Participant when neither capability is set', () => {
    expect(
      roleLabelFor({
        canManagePrograms: false,
        canRecordCalibration: false,
        isHouseContributor: false,
      })
    ).toBe('Participant')
  })
})
