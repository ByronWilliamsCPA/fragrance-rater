import { useEffect, useRef, type MouseEvent, type ReactNode } from 'react'
import type { Access, Capabilities } from '../api/types'
import { navigationItems, type Route } from '../routing/routes'

type AppShellProps = {
  access: Access
  capabilities: Capabilities
  route: Route
  navigate: (route: Route) => void
  children: ReactNode
}

export function AppShell({ access, capabilities, route, navigate, children }: AppShellProps) {
  const mainContent = useRef<HTMLElement>(null)
  const previousRoute = useRef(route)
  const role = capabilities.canManagePrograms
    ? 'Manager'
    : capabilities.canRecordCalibration
      ? 'Recorder'
      : 'Participant'

  useEffect(() => {
    if (previousRoute.current !== route) mainContent.current?.focus()
    previousRoute.current = route
  }, [route])

  function follow(event: MouseEvent<HTMLAnchorElement>, destination: Route) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)
      return
    event.preventDefault()
    navigate(destination)
  }

  return (
    <div className="app">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="app-header">
        <div>
          <div className="eyebrow">PERSONAL SCENT JOURNAL</div>
          <h1>Fragrance Rater</h1>
          <p>Explore your preferences, one encounter at a time.</p>
        </div>
        <div className="identity" aria-label="Current access">
          <span>{access.username || 'Verified family account'}</span>
          <strong>{role}</strong>
        </div>
      </header>
      <nav aria-label="Main navigation">
        {navigationItems
          .filter((item) => !item.managerOnly || capabilities.canManagePrograms)
          .map((item) => (
            <a
              key={item.route}
              href={item.path}
              aria-current={route === item.route ? 'page' : undefined}
              onClick={(event) => follow(event, item.route)}
            >
              {item.label}
            </a>
          ))}
      </nav>
      <main ref={mainContent} id="main-content" tabIndex={-1}>
        {children}
      </main>
      <footer>Ordinary encounters and controlled observations share one preference history.</footer>
    </div>
  )
}
