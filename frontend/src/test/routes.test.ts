import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { navigationItems, pathFor, routeFromPath, useRoute } from '../routing/routes'

describe('routeFromPath', () => {
  it('maps the root path to welcome', () => {
    expect(routeFromPath('/')).toBe('welcome')
  })

  it('maps /home to workspace', () => {
    expect(routeFromPath('/home')).toBe('workspace')
  })

  it('falls back to welcome for an unrecognized path', () => {
    expect(routeFromPath('/nowhere')).toBe('welcome')
  })
})

describe('pathFor', () => {
  it('round-trips every navigation item path', () => {
    for (const item of navigationItems) {
      expect(pathFor(item.route)).toBe(item.path)
    }
  })
})

describe('useRoute navigate', () => {
  it('sets an explicit query string, overriding whatever is already in the URL', () => {
    window.history.replaceState({}, '', '/calibration?stale=1')
    const { result } = renderHook(() => useRoute())

    act(() => result.current.navigate('calibration', false, { assignment: 'enr1' }))

    expect(window.location.pathname).toBe('/calibration')
    expect(window.location.search).toBe('?assignment=enr1')
  })

  it('drops the query string when navigating to a different route with no query given', () => {
    window.history.replaceState({}, '', '/recommendations?recommendation_run=run-1')
    const { result } = renderHook(() => useRoute())

    act(() => result.current.navigate('ratings'))

    expect(window.location.pathname).toBe('/ratings')
    expect(window.location.search).toBe('')
  })

  it('preserves the current query string when navigating to the same route with no query given', () => {
    window.history.replaceState({}, '', '/recommendations?recommendation_run=run-1')
    const { result } = renderHook(() => useRoute())

    act(() => result.current.navigate('recommendations'))

    expect(window.location.pathname).toBe('/recommendations')
    expect(window.location.search).toBe('?recommendation_run=run-1')
  })
})
