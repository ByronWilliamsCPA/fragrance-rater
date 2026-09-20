import { useCallback, useEffect, useState } from 'react'

export type Route =
  | 'home'
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
  { route: 'home', label: 'Home', path: '/', documentTitle: 'Home' },
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
  { route: 'ratings', label: 'My Ratings', path: '/ratings', documentTitle: 'My ratings' },
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
  return navigationItems.find((item) => item.path === pathname)?.route ?? 'home'
}

export function pathFor(route: Route): string {
  return navigationItems.find((item) => item.route === route)?.path ?? '/calibration'
}

export function useRoute() {
  const [route, setRoute] = useState<Route>(() => routeFromPath(window.location.pathname))

  useEffect(() => {
    const onPopState = () => setRoute(routeFromPath(window.location.pathname))
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const navigate = useCallback((next: Route, replace = false) => {
    const path = pathFor(next)
    const url = `${path}${window.location.search}${window.location.hash}`
    window.history[replace ? 'replaceState' : 'pushState']({}, '', url)
    setRoute(next)
  }, [])

  return { route, navigate }
}
