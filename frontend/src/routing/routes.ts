import { useCallback, useEffect, useState, type MouseEvent } from 'react'

export type Route =
  | 'welcome'
  | 'workspace'
  | 'calibration'
  | 'protocol'
  | 'recommendations'
  | 'ratings'
  | 'programs'
  | 'about'

export type NavigationItem = {
  route: Route
  label: string
  path: string
  /**
   * Distinct `document.title` for the route.
   *
   * WCAG 2.4.2 (Page Titled) applies per URL, and these are real pushState
   * URLs a family member can bookmark, reload, and hold several of in tabs
   * at once. Every route previously rendered the same "Fragrance Rater"
   * title, which made those tabs indistinguishable and gave a screen-reader
   * user no confirmation that navigation had happened.
   */
  documentTitle: string
  managerOnly?: boolean
  hiddenFromNav?: boolean
}

export const siteName = 'Fragrance Rater'

export const navigationItems: NavigationItem[] = [
  { route: 'welcome', label: 'Welcome', path: '/', documentTitle: 'Welcome' },
  { route: 'workspace', label: 'Home', path: '/home', documentTitle: 'Home' },
  {
    route: 'calibration',
    label: 'Calibration',
    path: '/calibration',
    documentTitle: 'Blind calibration',
  },
  {
    route: 'protocol',
    label: 'Calibration protocol',
    path: '/calibration/protocol',
    documentTitle: 'Calibration protocol',
    hiddenFromNav: true,
  },
  {
    route: 'recommendations',
    label: 'Recommendations',
    path: '/recommendations',
    documentTitle: 'Recommendations',
  },
  {
    route: 'ratings',
    label: 'Log an encounter',
    path: '/ratings',
    documentTitle: 'My ratings',
  },
  {
    route: 'programs',
    label: 'Program setup',
    path: '/programs',
    documentTitle: 'Program setup',
    managerOnly: true,
  },
  {
    route: 'about',
    label: 'About',
    path: '/about',
    documentTitle: 'About this project',
    hiddenFromNav: true,
  },
]

/**
 * The full `document.title` for a route: page name, then the site name.
 *
 * Page-first so the distinguishing part survives truncation in a crowded tab
 * strip, which is the case WCAG 2.4.2 is useful in. Falls back to the site
 * name alone for a route with no navigation entry.
 */
export function documentTitleFor(route: Route): string {
  const item = navigationItems.find((entry) => entry.route === route)
  return item ? `${item.documentTitle} · ${siteName}` : siteName
}

export function routeFromPath(pathname: string): Route {
  return navigationItems.find((item) => item.path === pathname)?.route ?? 'welcome'
}

export function pathFor(route: Route): string {
  return navigationItems.find((item) => item.route === route)?.path ?? '/calibration'
}

/**
 * Click handler for an in-app route link: lets a modified or non-primary
 * click (open in new tab, etc.) fall through to normal browser handling,
 * and otherwise intercepts the click for client-side navigation.
 *
 * Shared by every internal `<a href={pathFor(...)}>` link (nav bar, footer,
 * and inline in-page links) so the guard is defined once rather than
 * reimplemented at each call site.
 */
export function followRouteLink(
  event: MouseEvent<HTMLAnchorElement>,
  destination: Route,
  navigate: (route: Route) => void
) {
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)
    return
  event.preventDefault()
  navigate(destination)
}

export function useRoute() {
  const [route, setRoute] = useState<Route>(() => routeFromPath(window.location.pathname))

  useEffect(() => {
    const onPopState = () => setRoute(routeFromPath(window.location.pathname))
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const navigate = useCallback((next: Route, replace = false, query = '') => {
    const path = pathFor(next)
    const search = query ? `?${query}` : window.location.search
    const url = `${path}${search}${window.location.hash}`
    window.history[replace ? 'replaceState' : 'pushState']({}, '', url)
    setRoute(next)
  }, [])

  return { route, navigate }
}
