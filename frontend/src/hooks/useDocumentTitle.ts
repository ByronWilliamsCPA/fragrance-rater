import { useEffect } from 'react'
import { documentTitleFor, type Route } from '../routing/routes'

/**
 * Keeps `document.title` in step with the active route (WCAG 2.4.2).
 *
 * The shell is a pushState application, so nothing updates the title on its
 * own: without this every route reported the static title from index.html.
 */
export function useDocumentTitle(route: Route) {
  useEffect(() => {
    document.title = documentTitleFor(route)
  }, [route])
}
