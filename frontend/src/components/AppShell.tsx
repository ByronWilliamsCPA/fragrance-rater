import { useEffect, useRef, type MouseEvent, type ReactNode } from 'react'
import type { Access, Capabilities } from '../api/types'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { navigationItems, type Route } from '../routing/routes'
import { ThemeToggle } from './ThemeToggle'

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
  const aboutNavItem = navigationItems.find((item) => item.route === 'about')
  const role = capabilities.canManagePrograms
    ? 'Manager'
    : capabilities.canRecordCalibration
      ? 'Recorder'
      : 'Participant'

  useDocumentTitle(route)

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
      {/*
        The masthead is a form's identification block: what this document is on
        the left, who is filling it in on the right. A description list is the
        honest markup for that, and it gives each value a real name for a
        screen reader without a visible colon-and-label in the layout.
      */}
      <header className="masthead">
        <div className="masthead__name">
          <h1>Fragrance Rater</h1>
          <span className="masthead__qualifier">Sensory evaluation record</span>
        </div>
        <div className="masthead__aside">
          <dl className="masthead__particulars">
            <dt>Account</dt>
            <dd>{access.username || 'Verified family account'}</dd>
            <dt>Role</dt>
            <dd>{role}</dd>
          </dl>
          <ThemeToggle />
        </div>
      </header>
      <nav className="app-nav" aria-label="Main navigation">
        {navigationItems
          .filter(
            (item) => !item.hiddenFromNav && (!item.managerOnly || capabilities.canManagePrograms)
          )
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
      <footer className="colophon">
        <p>Ordinary encounters and controlled observations share one preference history.</p>
        {aboutNavItem && (
          <p>
            <a href={aboutNavItem.path} onClick={(event) => follow(event, aboutNavItem.route)}>
              About this project
            </a>
          </p>
        )}
      </footer>
    </div>
  )
}
