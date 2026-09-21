import { useCallback, useEffect, useState, type MouseEvent } from 'react'

/**
 * The one definition of every route the app has.
 *
 * `Route` is derived from this literal rather than declared beside it, so the
 * union and the table cannot drift apart: a route added here is immediately a
 * `Route`, and a route removed here is a compile error at every use. The
 * previous arrangement maintained the two independently and papered over a
 * mismatch with runtime fallbacks, which turned a typo into a silent
 * redirect instead of a build failure.
 */
const routeDefinitions = [
  { route: 'welcome', label: 'Welcome', path: '/', documentTitle: 'Welcome' },
  { route: 'workspace', label: 'Workspace', path: '/home', documentTitle: 'Workspace' },
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
    documentTitle: 'Log an encounter',
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
] as const

export type Route = (typeof routeDefinitions)[number]['route']

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

export const navigationItems: readonly NavigationItem[] = routeDefinitions

/**
 * Query parameters for a route, as a structure rather than a hand-built
 * string.
 *
 * Callers describe what they want in the URL and `navigate` builds and
 * encodes the search string, so no call site can interpolate an id straight
 * into a query and skip escaping it.
 */
export type RouteQuery = Readonly<Record<string, string>>

export type Navigate = (route: Route, replace?: boolean, query?: RouteQuery) => void

/** The deep-link parameter naming a calibration assignment. */
const assignmentParam = 'assignment'

/**
 * An assignment id already checked against the assignments the signed-in
 * identity holds.
 *
 * Branded so it is not interchangeable with the program, reviewer, and
 * presentation ids that are also bare strings: `assignmentLinkFor` is the
 * only place that can mint one, which is also the only place the check
 * happens.
 */
export type AssignmentId = string & { readonly __brand: 'AssignmentId' }

/**
 * What a `?assignment=` deep link resolved to, shaped as the props
 * `CalibrationPage` takes: at most one of the two is ever set.
 */
export type AssignmentLink = {
  /** Set when the URL named an assignment this identity actually holds. */
  initialAssignmentId?: AssignmentId
  /**
   * Set when the URL carried an `assignment` value that matched nothing: a
   * stale bookmark, a revoked assignment, or a malformed id. Kept distinct
   * from "no parameter at all" so the page can say so instead of dropping
   * the user into an empty picker with no explanation.
   */
  unresolvedAssignmentId?: string
}

/** Builds the query for a calibration deep link. */
export function assignmentQuery(assignmentId: string): RouteQuery {
  return { [assignmentParam]: assignmentId }
}

/**
 * Resolves the `assignment` query parameter against the assignments this
 * identity actually has.
 *
 * Lives here rather than in `App`: this module already owns how a `Route`
 * maps to and from a path, and the query half of a URL belongs with it.
 */
export function assignmentLinkFor(
  query: RouteQuery,
  assignmentIds: readonly string[]
): AssignmentLink {
  const requested = query[assignmentParam]
  if (!requested) return {}
  if (!assignmentIds.includes(requested)) return { unresolvedAssignmentId: requested }
  // The one place an AssignmentId is minted, immediately after the membership
  // check that is what makes the brand mean anything.
  return { initialAssignmentId: requested as AssignmentId }
}

/** The deep-link parameter naming a calibration program. */
const programParam = 'program'

/** Builds the query for a program self-assign deep link. */
export function programQuery(programId: string): RouteQuery {
  return { [programParam]: programId }
}

/**
 * Resolves the `program` query parameter against the programs this identity
 * can actually see, the same validate-then-brand pattern `assignmentLinkFor`
 * uses above.
 */
export function programLinkFor(query: RouteQuery, programIds: readonly string[]): string {
  const requested = query[programParam]
  return requested && programIds.includes(requested) ? requested : ''
}

function navigationItemFor(route: Route): NavigationItem {
  const item = navigationItems.find((entry) => entry.route === route)
  // Unreachable: `Route` is derived from this same table, so every value of
  // the type has an entry. It throws rather than falling back to an arbitrary
  // route so that a future change which breaks that invariant fails loudly at
  // the point of the mistake.
  if (!item) throw new Error(`No navigation entry for route: ${String(route)}`)
  return item
}

/**
 * The full `document.title` for a route: page name, then the site name.
 *
 * Page-first so the distinguishing part survives truncation in a crowded tab
 * strip, which is the case WCAG 2.4.2 is useful in.
 */
export function documentTitleFor(route: Route): string {
  return `${navigationItemFor(route).documentTitle} · ${siteName}`
}

/**
 * The route for a URL path.
 *
 * Takes an arbitrary string because the path comes from the address bar, so
 * this is the one lookup here that has a real miss to handle: an unknown or
 * hand-typed URL lands on the welcome page.
 */
export function routeFromPath(pathname: string): Route {
  return navigationItems.find((item) => item.path === pathname)?.route ?? 'welcome'
}

export function pathFor(route: Route): string {
  return navigationItemFor(route).path
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
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
  event.preventDefault()
  navigate(destination)
}

/**
 * Where the app currently is: the route and its query together.
 *
 * Kept as one value because the route name alone is not enough state. Two
 * `/calibration` entries with different `assignment=` values are different
 * locations, and keying only on the route made React's `Object.is` check skip
 * the re-render when moving between them.
 */
type RouteLocation = { route: Route; query: RouteQuery }

function queryFromSearch(search: string): RouteQuery {
  return Object.fromEntries(new URLSearchParams(search))
}

function searchFromQuery(query: RouteQuery): string {
  // URLSearchParams percent-encodes every key and value, so an id carrying
  // `&`, `#`, or a space cannot break out of the parameter it belongs to.
  const search = new URLSearchParams(query).toString()
  return search ? `?${search}` : ''
}

function locationFromUrl(): RouteLocation {
  return {
    route: routeFromPath(window.location.pathname),
    query: queryFromSearch(window.location.search),
  }
}

export function useRoute() {
  const [location, setLocation] = useState<RouteLocation>(locationFromUrl)

  useEffect(() => {
    // Reads the query as well as the path: back and forward between two
    // entries for the same route differ only in the query.
    const onPopState = () => setLocation(locationFromUrl())
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const navigate = useCallback<Navigate>((next, replace = false, query) => {
    // A query belongs to the route that put it there. Leaving one route for
    // another with nothing stated therefore leaves its parameters behind:
    // carrying them over meant a nav-bar round trip re-applied an old
    // `assignment=` deep link over a selection the user had since changed by
    // hand. Staying on the same route keeps them, so re-clicking the current
    // nav link is not a way to lose state. An explicit `{}` clears them.
    //
    // The comparison reads the address bar rather than the state above,
    // because a page can amend its own parameters with replaceState.
    const search =
      query !== undefined
        ? searchFromQuery(query)
        : routeFromPath(window.location.pathname) === next
          ? window.location.search
          : ''
    const url = `${pathFor(next)}${search}${window.location.hash}`
    window.history[replace ? 'replaceState' : 'pushState']({}, '', url)
    // Always a fresh object, so a same-route navigation that only changes the
    // query is still a state change React will render.
    setLocation({ route: next, query: queryFromSearch(search) })
  }, [])

  return { route: location.route, query: location.query, navigate }
}
