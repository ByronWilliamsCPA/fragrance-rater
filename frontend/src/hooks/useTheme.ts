import { useCallback, useEffect, useState } from 'react'

export type ThemeChoice = 'light' | 'dark'

const storageKey = 'fragrance-rater:theme'

/**
 * Reads the stored theme choice.
 *
 * #EDGE: external-resources: localStorage throws rather than returning null in
 * a Safari private window and wherever site data is blocked, and this runs
 * during the first render of every page.
 * #VERIFY: the read is wrapped, and a failure falls back to the system
 * preference instead of breaking the shell.
 */
function storedChoice(): ThemeChoice | null {
  try {
    const value = window.localStorage.getItem(storageKey)
    return value === 'light' || value === 'dark' ? value : null
  } catch {
    return null
  }
}

function systemPrefersDark(): boolean {
  // #EDGE: external-resources: jsdom (the unit-test environment) does not
  // implement matchMedia at all.
  // #VERIFY: feature-detected rather than assumed present.
  return typeof window.matchMedia === 'function'
    ? window.matchMedia('(prefers-color-scheme: dark)').matches
    : false
}

/**
 * Resolves the active theme and lets the evaluator override it.
 *
 * With no stored choice the CSS `prefers-color-scheme` block governs and no
 * `data-theme` attribute is written, so the page follows the operating system.
 * An explicit choice pins `data-theme` on the root element, which both theme
 * blocks in tokens.css key off.
 */
export function useTheme() {
  const [choice, setChoice] = useState<ThemeChoice | null>(storedChoice)
  const [systemDark, setSystemDark] = useState(systemPrefersDark)

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return
    const query = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (event: MediaQueryListEvent) => setSystemDark(event.matches)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  useEffect(() => {
    const root = document.documentElement
    if (choice) root.setAttribute('data-theme', choice)
    else root.removeAttribute('data-theme')
  }, [choice])

  const resolved: ThemeChoice = choice ?? (systemDark ? 'dark' : 'light')

  const toggle = useCallback(() => {
    const next: ThemeChoice = resolved === 'dark' ? 'light' : 'dark'
    setChoice(next)
    try {
      window.localStorage.setItem(storageKey, next)
    } catch {
      // A blocked storage write only costs persistence across reloads; the
      // choice still applies for this session.
    }
  }, [resolved])

  return { resolved, toggle }
}
