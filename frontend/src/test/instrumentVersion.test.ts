import { describe, expect, it } from 'vitest'
import { instrumentVersion } from '../instrumentVersion'

describe('instrumentVersion', () => {
  it('is the trimmed build identifier when one was injected', () => {
    expect(instrumentVersion(' abc123 ')).toBe('abc123')
  })

  it('is null for a development build, so nothing is shown', () => {
    expect(instrumentVersion(undefined)).toBeNull()
    expect(instrumentVersion('')).toBeNull()
    expect(instrumentVersion('   ')).toBeNull()
  })
})
