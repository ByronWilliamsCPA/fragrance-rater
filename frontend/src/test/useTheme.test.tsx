import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useTheme } from '../hooks/useTheme'

/**
 * The theme hook's failure paths.
 *
 * Every branch here is one the interface depends on but which no other test
 * reaches: jsdom does not implement `matchMedia` at all, and `localStorage`
 * throws rather than returning null in a private window or wherever site data
 * is blocked. Both are guarded in the hook, and until now neither guard had
 * ever been executed.
 */

const storageKey = 'fragrance-rater:theme'

function mockMatchMedia(matches: boolean) {
  const listeners = new Set<(event: MediaQueryListEvent) => void>()
  const query = {
    matches,
    addEventListener: (_: string, listener: (event: MediaQueryListEvent) => void) =>
      listeners.add(listener),
    removeEventListener: (_: string, listener: (event: MediaQueryListEvent) => void) =>
      listeners.delete(listener),
  }
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: vi.fn(() => query),
  })
  return {
    emit(next: boolean) {
      for (const listener of listeners) listener({ matches: next } as MediaQueryListEvent)
    },
    listenerCount: () => listeners.size,
  }
}

beforeEach(() => {
  window.localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
})

afterEach(() => {
  Reflect.deleteProperty(window, 'matchMedia')
  document.documentElement.removeAttribute('data-theme')
  vi.restoreAllMocks()
})

describe('useTheme', () => {
  it('follows the system preference until the evaluator chooses', () => {
    mockMatchMedia(true)

    const { result } = renderHook(() => useTheme())

    expect(result.current.resolved).toBe('dark')
    // No explicit choice means no attribute, so the CSS prefers-color-scheme
    // block stays in charge rather than being pinned by an override.
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
  })

  it('pins an explicit choice and persists it', () => {
    mockMatchMedia(false)

    const { result } = renderHook(() => useTheme())
    act(() => result.current.toggle())

    expect(result.current.resolved).toBe('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(window.localStorage.getItem(storageKey)).toBe('dark')
  })

  it('restores a stored choice over the system preference', () => {
    window.localStorage.setItem(storageKey, 'light')
    mockMatchMedia(true)

    const { result } = renderHook(() => useTheme())

    expect(result.current.resolved).toBe('light')
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })

  it('reacts to the system preference changing while open', () => {
    const media = mockMatchMedia(false)

    const { result, unmount } = renderHook(() => useTheme())
    expect(result.current.resolved).toBe('light')

    act(() => media.emit(true))
    expect(result.current.resolved).toBe('dark')

    // The listener is released on unmount; leaking one per mount would keep
    // updating state on a hook that no longer exists.
    unmount()
    expect(media.listenerCount()).toBe(0)
  })

  it('still applies a choice when storage is blocked', () => {
    mockMatchMedia(false)
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('storage blocked')
    })

    const { result } = renderHook(() => useTheme())
    act(() => result.current.toggle())

    // A blocked write costs persistence across reloads, not the choice itself.
    expect(result.current.resolved).toBe('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })

  it('falls back to the system preference when storage cannot be read', () => {
    mockMatchMedia(true)
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('storage blocked')
    })

    const { result } = renderHook(() => useTheme())

    expect(result.current.resolved).toBe('dark')
  })

  it('works with no matchMedia at all', () => {
    Reflect.deleteProperty(window, 'matchMedia')

    const { result } = renderHook(() => useTheme())

    // Feature-detected rather than assumed: without the guard this throws.
    expect(result.current.resolved).toBe('light')
    act(() => result.current.toggle())
    expect(result.current.resolved).toBe('dark')
  })
})
