import { useCallback, useEffect, useState } from 'react'

export type Route = 'calibration' | 'recommendations' | 'ratings' | 'programs'

export type NavigationItem = {
  route: Route
  label: string
  path: string
  managerOnly?: boolean
}

export const navigationItems: NavigationItem[] = [
  { route: 'calibration', label: 'Calibration', path: '/calibration' },
  { route: 'recommendations', label: 'Recommendations', path: '/recommendations' },
  { route: 'ratings', label: 'My Ratings', path: '/ratings' },
  { route: 'programs', label: 'Program setup', path: '/programs', managerOnly: true },
]

export function routeFromPath(pathname: string): Route {
  return navigationItems.find((item) => item.path === pathname)?.route ?? 'calibration'
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
