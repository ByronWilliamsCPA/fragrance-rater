import { describe, expect, it } from 'vitest'
import { apiV1BaseUrl } from '../api/client'

describe('API URL normalization', () => {
  it('supports host, API-root, and complete v1 configuration values', () => {
    expect(apiV1BaseUrl('https://api.example.com')).toBe('https://api.example.com/api/v1')
    expect(apiV1BaseUrl('https://api.example.com/api')).toBe('https://api.example.com/api/v1')
    expect(apiV1BaseUrl('/api/v1/')).toBe('/api/v1')
  })
})
